"""Ephemeral OIDC and SAML IdP for isolated browser regression runs.

This module is intentionally test-only.  It provides an external identity
provider boundary; QueryCraft still performs every callback, session, role,
permission, and policy action itself.
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import xmlsec
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

SAML_ASSERTION_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAML_PROTOCOL_NS = "urn:oasis:names:tc:SAML:2.0:protocol"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _iso_now(offset: timedelta = timedelta()) -> str:
    return (datetime.now(UTC) + offset).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Identity:
    """Claims emitted by the test provider for the next browser flow."""

    subject: str = "p5a-user"
    email: str = "p5a-user@example.test"
    groups: list[str] = field(default_factory=lambda: ["p5a-analysts"])
    variant: str = "valid"


class MockIdentityProvider:
    """Stateful signing IdP that keeps all keys and test identities in memory."""

    def __init__(self, issuer: str, client_id: str, backend_url: str) -> None:
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self.backend_url = backend_url.rstrip("/")
        self.identity = Identity()
        self._codes: dict[str, dict[str, str]] = {}
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._wrong_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._certificate = self._create_certificate()

    def update_identity(self, payload: dict[str, Any]) -> None:
        self.identity = Identity(
            subject=str(payload.get("subject", self.identity.subject)),
            email=str(payload.get("email", self.identity.email)),
            groups=[str(group) for group in payload.get("groups", self.identity.groups)],
            variant=str(payload.get("variant", "valid")),
        )

    def certificate_pem(self) -> str:
        return self._certificate.public_bytes(serialization.Encoding.PEM).decode()

    def jwks(self) -> dict[str, list[dict[str, str]]]:
        public_numbers = self._private_key.public_key().public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "p5a-primary",
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64url(public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")),
                    "e": _b64url(public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")),
                }
            ]
        }

    def authorize(self, query: dict[str, list[str]]) -> str:
        redirect_uri = query["redirect_uri"][0]
        state = query["state"][0]
        code = secrets.token_urlsafe(24)
        self._codes[code] = {"nonce": query["nonce"][0]}
        return f"{redirect_uri}?{urlencode({'code': code, 'state': state})}"

    def token(self, form: dict[str, list[str]]) -> dict[str, str]:
        code = form.get("code", [""])[0]
        stored = self._codes.pop(code, None)
        if stored is None:
            raise ValueError("unknown code")
        return {"access_token": "opaque", "token_type": "Bearer", "id_token": self._id_token(stored["nonce"])}

    def saml_response(self, relay_state: str) -> str:
        return base64.b64encode(self._signed_assertion(relay_state)).decode()

    def _id_token(self, nonce: str) -> str:
        now = int(time.time())
        variant = self.identity.variant
        payload = {
            "iss": self.issuer if variant != "bad_issuer" else f"{self.issuer}-wrong",
            "aud": self.client_id if variant != "bad_audience" else "wrong-client",
            "sub": self.identity.subject,
            "email": self.identity.email,
            "groups": self.identity.groups,
            "nonce": nonce if variant != "bad_nonce" else "wrong-nonce",
            "iat": now,
            "exp": now - 3600 if variant == "expired" else now + 300,
        }
        encoded_header = _b64url(json.dumps({"alg": "RS256", "kid": "p5a-primary", "typ": "JWT"}).encode())
        encoded_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode())
        signed = f"{encoded_header}.{encoded_payload}".encode()
        key = self._wrong_private_key if variant == "bad_signature" else self._private_key
        signature = key.sign(signed, padding.PKCS1v15(), hashes.SHA256())
        return f"{signed.decode()}.{_b64url(signature)}"

    def _create_certificate(self) -> x509.Certificate:
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "p5a-idp")])
        now = datetime.now(UTC)
        return (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self._private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .sign(self._private_key, hashes.SHA256())
        )

    def _signed_assertion(self, request_id: str) -> bytes:
        response = etree.Element(
            f"{{{SAML_PROTOCOL_NS}}}Response",
            nsmap={"samlp": SAML_PROTOCOL_NS, "saml": SAML_ASSERTION_NS},
        )
        response.set("ID", f"_p5a_{secrets.token_hex(8)}")
        response.set("Version", "2.0")
        response.set("IssueInstant", _iso_now())
        response.set("InResponseTo", request_id)
        response.set("Destination", f"{self.backend_url}/api/v1/auth/sso/saml/callback")
        etree.SubElement(response, f"{{{SAML_ASSERTION_NS}}}Issuer").text = self.issuer
        status = etree.SubElement(response, f"{{{SAML_PROTOCOL_NS}}}Status")
        etree.SubElement(status, f"{{{SAML_PROTOCOL_NS}}}StatusCode").set(
            "Value", "urn:oasis:names:tc:SAML:2.0:status:Success"
        )
        assertion = etree.SubElement(response, f"{{{SAML_ASSERTION_NS}}}Assertion")
        assertion.set("ID", f"_p5a_assertion_{secrets.token_hex(8)}")
        assertion.set("Version", "2.0")
        assertion.set("IssueInstant", _iso_now())
        etree.SubElement(assertion, f"{{{SAML_ASSERTION_NS}}}Issuer").text = self.issuer
        subject = etree.SubElement(assertion, f"{{{SAML_ASSERTION_NS}}}Subject")
        etree.SubElement(subject, f"{{{SAML_ASSERTION_NS}}}NameID").text = self.identity.subject
        confirmation = etree.SubElement(subject, f"{{{SAML_ASSERTION_NS}}}SubjectConfirmation")
        confirmation.set("Method", "urn:oasis:names:tc:SAML:2.0:cm:bearer")
        data = etree.SubElement(confirmation, f"{{{SAML_ASSERTION_NS}}}SubjectConfirmationData")
        data.set("InResponseTo", request_id)
        data.set("Recipient", f"{self.backend_url}/api/v1/auth/sso/saml/callback")
        data.set("NotOnOrAfter", _iso_now(timedelta(minutes=5)))
        conditions = etree.SubElement(assertion, f"{{{SAML_ASSERTION_NS}}}Conditions")
        conditions.set("NotBefore", _iso_now(timedelta(minutes=-1)))
        conditions.set("NotOnOrAfter", _iso_now(timedelta(minutes=5)))
        restriction = etree.SubElement(conditions, f"{{{SAML_ASSERTION_NS}}}AudienceRestriction")
        etree.SubElement(restriction, f"{{{SAML_ASSERTION_NS}}}Audience").text = "urn:p5a-querycraft-sp"
        attributes = etree.SubElement(assertion, f"{{{SAML_ASSERTION_NS}}}AttributeStatement")
        for name, values in (("email", [self.identity.email]), ("groups", self.identity.groups)):
            attribute = etree.SubElement(attributes, f"{{{SAML_ASSERTION_NS}}}Attribute")
            attribute.set("Name", name)
            for value in values:
                etree.SubElement(attribute, f"{{{SAML_ASSERTION_NS}}}AttributeValue").text = value
        self._sign(assertion)
        return etree.tostring(response, xml_declaration=True, encoding="utf-8")

    def _sign(self, assertion: etree._Element) -> None:
        signature = xmlsec.template.create(assertion, xmlsec.Transform.EXCL_C14N, xmlsec.Transform.RSA_SHA256, ns="ds")
        assertion.insert(1, signature)
        reference = xmlsec.template.add_reference(signature, xmlsec.Transform.SHA256, uri="")
        xmlsec.template.add_transform(reference, xmlsec.Transform.ENVELOPED)
        xmlsec.template.add_transform(reference, xmlsec.Transform.EXCL_C14N)
        key_info = xmlsec.template.ensure_key_info(signature)
        xmlsec.template.add_x509_data(key_info)
        context = xmlsec.SignatureContext()
        private_pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        context.key = xmlsec.Key.from_memory(private_pem, xmlsec.KeyFormat.PEM, None)
        context.key.load_cert_from_memory(self.certificate_pem(), xmlsec.KeyFormat.PEM)
        context.sign(signature)


class Handler(BaseHTTPRequestHandler):
    provider: MockIdentityProvider

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/authorize":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", self.provider.authorize(parse_qs(urlparse(self.path).query)))
            self.end_headers()
            return
        if path == "/.well-known/jwks.json":
            self._json(HTTPStatus.OK, self.provider.jwks())
            return
        if path == "/metadata":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(b"<EntityDescriptor/>")
            return
        if path == "/__p5__/certificate":
            self._text(HTTPStatus.OK, self.provider.certificate_pem())
            return
        if path == "/sso":
            query = parse_qs(urlparse(self.path).query)
            payload = self.provider.saml_response(query["RelayState"][0])
            self._text(
                HTTPStatus.OK,
                _post_form(
                    f"{self.provider.backend_url}/api/v1/auth/sso/saml/callback",
                    payload,
                    query["RelayState"][0],
                ),
                "text/html",
            )
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        form = parse_qs(raw_body.decode())
        path = urlparse(self.path).path
        if path == "/token":
            try:
                self._json(HTTPStatus.OK, self.provider.token(form))
            except ValueError:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_grant"})
            return
        if path == "/__p5__/identity":
            self.provider.update_identity(json.loads(raw_body or b"{}"))
            self._json(HTTPStatus.NO_CONTENT, {})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _json(self, status: HTTPStatus, payload: object) -> None:
        self._text(status, json.dumps(payload), "application/json")

    def _text(self, status: HTTPStatus, body: str, content_type: str = "text/plain") -> None:
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _post_form(acs_url: str, response: str, relay_state: str) -> str:
    return (
        f'<form id="p5a" method="post" action="{acs_url}">'
        f'<input name="SAMLResponse" value="{response}">'
        f'<input name="RelayState" value="{relay_state}"></form>'
        "<script>document.forms.p5a.submit()</script>"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--backend-url", required=True)
    args = parser.parse_args()
    Handler.provider = MockIdentityProvider(args.issuer, args.client_id, args.backend_url)
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

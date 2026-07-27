"""Regression checks for the isolated external-IdP test boundary."""

from authlib.jose import jwt
from lxml import etree
from onelogin.saml2.auth import OneLogin_Saml2_Auth

from tests.e2e_support.mock_identity_provider import MockIdentityProvider


def _provider() -> MockIdentityProvider:
    return MockIdentityProvider(
        issuer="http://idp.localhost:19090",
        client_id="p5a-client",
        backend_url="http://querycraft.localhost:19080",
    )


def test_oidc_token_is_signed_by_the_published_jwks_and_binds_nonce():
    provider = _provider()
    callback_url = provider.authorize(
        {
            "redirect_uri": ["http://querycraft.localhost:19080/api/v1/auth/sso/oidc/callback"],
            "state": ["state-1"],
            "nonce": ["nonce-1"],
        }
    )
    code = callback_url.split("code=", 1)[1].split("&", 1)[0]

    claims = jwt.decode(provider.token({"code": [code]})["id_token"], provider.jwks())
    claims.validate()

    assert claims["iss"] == provider.issuer
    assert claims["aud"] == "p5a-client"
    assert claims["nonce"] == "nonce-1"


def test_saml_response_contains_a_signed_assertion_bound_to_the_request():
    provider = _provider()

    response = etree.fromstring(__import__("base64").b64decode(provider.saml_response("request-1")))

    assert response.get("InResponseTo") == "request-1"
    assert response.xpath("//*[local-name()='Assertion']//*[local-name()='Signature']")


def test_saml_response_is_accepted_by_the_same_assertion_parser_as_querycraft():
    """Regression: the mock assertion signature must reference its assertion ID."""
    provider = _provider()
    auth = OneLogin_Saml2_Auth(
        {
            "https": "off",
            "http_host": "querycraft.localhost:19080",
            "script_name": "/api/v1/auth/sso/saml/callback",
            "server_port": "80",
            "get_data": {},
            "post_data": {"SAMLResponse": provider.saml_response("request-1")},
        },
        {
            "sp": {
                "entityId": "urn:p5a-querycraft-sp",
                "assertionConsumerService": {
                    "url": "http://querycraft.localhost:19080/api/v1/auth/sso/saml/callback",
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
            },
            "idp": {
                "entityId": provider.issuer,
                "singleSignOnService": {"url": f"{provider.issuer}/sso"},
                "x509cert": provider.certificate_pem(),
            },
            "security": {"wantAssertionsSigned": True, "wantMessagesSigned": False},
        },
    )

    auth.process_response()

    assert auth.get_errors() == []
    assert auth.is_authenticated()

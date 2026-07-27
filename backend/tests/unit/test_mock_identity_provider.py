"""Regression checks for the isolated external-IdP test boundary."""

from authlib.jose import jwt
from lxml import etree

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

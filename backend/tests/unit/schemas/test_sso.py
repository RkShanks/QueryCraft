"""Regression tests for the SSO provider OpenAPI secret contract."""

import pytest


@pytest.mark.parametrize("schema_name", ["SsoProviderCreate", "SsoProviderUpdate"])
def test_sso_secret_inputs_are_write_only_in_runtime_openapi(schema_name):
    from app.main import create_app

    properties = create_app().openapi()["components"]["schemas"][schema_name]["properties"]
    secret_fields = {"client_secret", "saml_metadata_xml", "saml_certificate"}

    fields_without_write_only = {
        field_name for field_name in secret_fields if properties[field_name].get("writeOnly") is not True
    }
    assert fields_without_write_only == set()


def test_sso_response_schema_exposes_only_masked_secret_fields():
    from app.schemas.sso import SsoProviderResponse

    properties = SsoProviderResponse.model_json_schema()["properties"]
    masked_fields = {
        "client_secret_masked",
        "saml_metadata_xml_masked",
        "saml_certificate_masked",
    }
    unmasked_fields = {
        "client_secret",
        "saml_metadata_xml",
        "saml_certificate",
        "encrypted_client_secret",
        "encrypted_saml_metadata_xml",
        "encrypted_saml_certificate",
    }

    assert masked_fields <= set(properties)
    assert unmasked_fields & set(properties) == set()

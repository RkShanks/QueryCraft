"""Deployment proxy ownership and response-policy regressions for CHUNK-30."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
NGINX_CONFIGURATION = REPOSITORY_ROOT / "frontend" / "nginx.conf"
FRONTEND_DOCKERFILE = REPOSITORY_ROOT / "frontend" / "Dockerfile"

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
        "form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
        "worker-src 'self' blob:"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=(), payment=(), usb=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


def _nginx_configuration() -> str:
    return NGINX_CONFIGURATION.read_text(encoding="utf-8")


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/health", "/missing"])
async def test_direct_backend_responses_omit_proxy_owned_headers(path: str):
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)

    assert all(header not in response.headers for header in SECURITY_HEADERS)


def test_proxy_defines_each_deployment_security_header_once_for_all_responses():
    configuration = _nginx_configuration()

    for header, expected_value in SECURITY_HEADERS.items():
        directive = rf'add_header\s+{re.escape(header)}\s+"{re.escape(expected_value)}"\s+always;'
        assert len(re.findall(directive, configuration)) == 1
    assert configuration.count("add_header ") == len(SECURITY_HEADERS) + 1


def test_proxy_cache_policy_preserves_api_contracts_and_classifies_web_assets():
    configuration = _nginx_configuration()

    assert 'add_header Cache-Control "$querycraft_cache_control" always;' in configuration
    assert '~:text/html "no-store";' in configuration
    assert '"public, max-age=31536000, immutable";' in configuration
    assert "proxy_hide_header" not in configuration
    assert "proxy_ignore_headers" not in configuration
    assert "location ^~ /assets/" in configuration
    assert "try_files $uri =404;" in configuration
    assert "try_files $uri $uri/ /index.html;" in configuration


def test_frontend_image_installs_reviewable_nginx_configuration():
    dockerfile = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY nginx.conf /etc/nginx/conf.d/default.conf" in dockerfile
    assert "RUN echo 'server" not in dockerfile

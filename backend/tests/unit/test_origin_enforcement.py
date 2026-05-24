"""Tests for Origin header validation enforcement (T-032).

Asserts POST with missing/invalid Origin returns 403 and GET bypasses the check.
Tests pass against the running middleware.
"""

import pytest
from starlette.responses import JSONResponse

from app.core.security import OriginValidatorMiddleware


class TestOriginEnforcement:
    """Verify Origin validation middleware behavior."""

    @pytest.fixture
    def allowed_origins(self):
        return ["http://localhost:3000"]

    async def _run_middleware(self, middleware, scope):
        """Run middleware and collect response messages."""
        messages = []

        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(message):
            messages.append(message)

        await middleware(scope, receive, send)
        return messages

    @pytest.mark.asyncio
    async def test_post_missing_origin_returns_403(self, allowed_origins):
        """POST without Origin header must return 403."""

        async def app(scope, receive, send):
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        middleware = OriginValidatorMiddleware(app, allowed_origins=allowed_origins)
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [],
            "state": {},
        }
        messages = await self._run_middleware(middleware, scope)
        assert messages[0]["status"] == 403

    @pytest.mark.asyncio
    async def test_post_invalid_origin_returns_403(self, allowed_origins):
        """POST with Origin not in ALLOWED_ORIGINS must return 403."""

        async def app(scope, receive, send):
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        middleware = OriginValidatorMiddleware(app, allowed_origins=allowed_origins)
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [(b"origin", b"http://evil.com")],
            "state": {},
        }
        messages = await self._run_middleware(middleware, scope)
        assert messages[0]["status"] == 403

    @pytest.mark.asyncio
    async def test_post_valid_origin_passes(self, allowed_origins):
        """POST with valid Origin must pass through."""

        async def app(scope, receive, send):
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        middleware = OriginValidatorMiddleware(app, allowed_origins=allowed_origins)
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [(b"origin", b"http://localhost:3000")],
            "state": {},
        }
        messages = await self._run_middleware(middleware, scope)
        assert messages[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_get_bypasses_origin_check(self, allowed_origins):
        """GET requests must bypass Origin validation."""

        async def app(scope, receive, send):
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        middleware = OriginValidatorMiddleware(app, allowed_origins=allowed_origins)
        scope = {
            "type": "http",
            "method": "GET",
            "headers": [],
            "state": {},
        }
        messages = await self._run_middleware(middleware, scope)
        assert messages[0]["status"] == 200


class TestSamlAcsOriginBypass:
    """SAML ACS POST endpoint bypasses Origin validation (T-645 review fix).

    POST /api/v1/auth/sso/saml/callback is a public IdP callback that
    cannot rely on same-origin browser Origin validation.
    """

    SAML_ACS_PATH = "/api/v1/auth/sso/saml/callback"

    @pytest.fixture
    def allowed_origins(self):
        return ["http://localhost:3000"]

    async def _run_middleware(self, middleware, scope):
        messages = []

        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(message):
            messages.append(message)

        await middleware(scope, receive, send)
        return messages

    @pytest.mark.asyncio
    async def test_saml_acs_post_without_origin_passes(self, allowed_origins):
        """POST to SAML ACS path without Origin header must pass through."""

        async def app(scope, receive, send):
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        middleware = OriginValidatorMiddleware(app, allowed_origins=allowed_origins)
        scope = {
            "type": "http",
            "method": "POST",
            "path": self.SAML_ACS_PATH,
            "headers": [],
            "state": {},
        }
        messages = await self._run_middleware(middleware, scope)
        assert messages[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_saml_acs_post_with_any_origin_passes(self, allowed_origins):
        """POST to SAML ACS path with any Origin must pass through (IdP origin varies)."""

        async def app(scope, receive, send):
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        middleware = OriginValidatorMiddleware(app, allowed_origins=allowed_origins)
        scope = {
            "type": "http",
            "method": "POST",
            "path": self.SAML_ACS_PATH,
            "headers": [(b"origin", b"https://idp.example.com")],
            "state": {},
        }
        messages = await self._run_middleware(middleware, scope)
        assert messages[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_other_post_without_origin_still_rejected(self, allowed_origins):
        """POST to a non-ACS path without Origin must still return 403."""

        async def app(scope, receive, send):
            response = JSONResponse({"ok": True})
            await response(scope, receive, send)

        middleware = OriginValidatorMiddleware(app, allowed_origins=allowed_origins)
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/query",
            "headers": [],
            "state": {},
        }
        messages = await self._run_middleware(middleware, scope)
        assert messages[0]["status"] == 403

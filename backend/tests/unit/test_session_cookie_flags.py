"""Tests for session cookie security flags (T-031).

Asserts sign-in response sets HttpOnly, Secure, SameSite=Strict on the session_id cookie.
Tests fail if any flag is missing.
"""

from starlette.responses import Response

from app.core.security import SessionMiddleware


class TestSessionCookieFlags:
    """Verify session cookie security attributes."""

    def test_cookie_has_httponly_flag(self):
        """session_id cookie must have HttpOnly flag."""
        response = Response()
        SessionMiddleware.set_cookie(response, "test-session-id", secure=True)
        set_cookie = response.headers["set-cookie"]
        assert "HttpOnly" in set_cookie

    def test_cookie_has_secure_flag(self):
        """session_id cookie must have Secure flag."""
        response = Response()
        SessionMiddleware.set_cookie(response, "test-session-id", secure=True)
        set_cookie = response.headers["set-cookie"]
        assert "Secure" in set_cookie

    def test_cookie_has_samesite_strict(self):
        """session_id cookie must have SameSite=Strict."""
        response = Response()
        SessionMiddleware.set_cookie(response, "test-session-id", secure=True)
        set_cookie = response.headers["set-cookie"]
        assert "SameSite=strict" in set_cookie or "SameSite=Strict" in set_cookie

    def test_cookie_path_is_root(self):
        """session_id cookie path must be /."""
        response = Response()
        SessionMiddleware.set_cookie(response, "test-session-id", secure=True)
        set_cookie = response.headers["set-cookie"]
        assert "Path=/" in set_cookie

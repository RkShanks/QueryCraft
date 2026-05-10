"""T-232: EphemeralAttempt must not silently default llm_provider."""

from app.core.attempt_store import EphemeralAttempt


def test_ephemeral_attempt_no_default_provider():
    """Empty default ensures QueryService sets it explicitly from active config."""
    attempt = EphemeralAttempt(session_id="s", attempt_id="a", user_id="u")
    assert attempt.llm_provider == ""

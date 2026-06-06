"""T-741: AUDIT_RETENTION_MONTHS config setting (FR-142)."""

from app.core.config import Settings, get_settings


class TestAuditRetentionMonths:
    """Verify AUDIT_RETENTION_MONTHS is in Settings and bound from env."""

    def test_audit_retention_months_default_24(self):
        settings = Settings.model_construct(
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            PLATFORM_ENCRYPTION_KEY="dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyExMjM=",
        )
        assert settings.AUDIT_RETENTION_MONTHS == 24

    def test_audit_retention_months_from_env(self, monkeypatch):
        monkeypatch.setenv("AUDIT_RETENTION_MONTHS", "36")
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.AUDIT_RETENTION_MONTHS == 36

    def test_audit_retention_months_type_int(self):
        settings = Settings.model_construct(
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            PLATFORM_ENCRYPTION_KEY="dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyExMjM=",
        )
        assert isinstance(settings.AUDIT_RETENTION_MONTHS, int)

"""Phase 6 enum completeness tests."""

from app.db.models.enums import AuditActionType, Permission


def test_phase6_audit_action_types_exist_with_contract_values():
    expected = {
        "QUOTA_CONFIG_CHANGE": "quota.config.change",
        "QUOTA_EXCEEDED": "quota.exceeded",
        "QUOTA_WARNING": "quota.warning",
        "HOSTILE_INPUT_BLOCKED": "hostile.input.blocked",
        "HOSTILE_INPUT_FLAGGED": "hostile.input.flagged",
        "DETECTION_CONFIG_CHANGE": "detection.config.change",
        "AUDIT_SEARCH": "audit.search",
        "AUDIT_EXPORT": "audit.export",
        "AUDIT_PURGE": "audit.purge",
    }

    for member_name, value in expected.items():
        assert getattr(AuditActionType, member_name).value == value


def test_phase6_admin_permissions_exist_with_contract_values():
    assert Permission.ADMIN_QUOTAS_MANAGE.value == "admin.quotas.manage"
    assert Permission.ADMIN_SECURITY_MANAGE.value == "admin.security.manage"

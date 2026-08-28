"""Real API/DB proof for CHUNK-28 audit filter-context privacy."""

from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService


@pytest.mark.usefixtures("clean_audit_table")
@pytest.mark.asyncio
async def test_context_search_and_export_share_filters_without_persisting_raw_values(
    authenticated_client,
    db_session,
    async_engine_fixture,
):
    await AuditService.log(
        db_session,
        action=AuditActionType.AUDIT_VERIFY,
        actor_identity="safe-seeded-actor",
        resource_type="audit_chain",
        resource_id="audit_chain",
        outcome="success",
        context={"verified": True},
    )
    await db_session.commit()

    exact_context_response = await authenticated_client.post(
        "/api/v1/admin/audit/filter-context",
        json={"action_type": "audit.verify"},
    )
    assert exact_context_response.status_code == 200
    exact_context = exact_context_response.json()["filter_context"]

    search_response = await authenticated_client.get(
        "/api/v1/admin/audit/entries",
        params={"filter_context": exact_context, "page_size": 10},
    )
    export_response = await authenticated_client.post(
        "/api/v1/admin/audit/export",
        json={"format": "json", "filter_context": exact_context},
    )
    assert search_response.status_code == 200
    assert export_response.status_code == 200
    search_sequences = [entry["sequence_number"] for entry in search_response.json()["entries"]]
    export_document = json.loads(export_response.content)
    export_sequences = [entry["sequence_number"] for entry in export_document["entries"]]
    assert export_sequences == search_sequences
    assert export_document["metadata"]["filter_summary"] == ["action_type"]

    canary = f"actor-{uuid4()}"
    privacy_context_response = await authenticated_client.post(
        "/api/v1/admin/audit/filter-context",
        json={"actor_identity": canary},
    )
    assert privacy_context_response.status_code == 200
    assert privacy_context_response.headers["cache-control"] == "no-store"
    privacy_context = privacy_context_response.json()["filter_context"]
    assert canary not in privacy_context_response.text
    assert canary not in base64.b64decode(privacy_context).decode("utf-8", errors="ignore")

    privacy_search = await authenticated_client.get(
        "/api/v1/admin/audit/entries",
        params={"filter_context": privacy_context},
    )
    privacy_export = await authenticated_client.post(
        "/api/v1/admin/audit/export",
        json={"format": "csv", "filter_context": privacy_context},
    )
    assert privacy_search.status_code == 200
    assert privacy_export.status_code == 200
    assert privacy_search.headers["cache-control"] == "no-store"
    assert privacy_export.headers["cache-control"] == "no-store"
    assert canary not in privacy_search.text
    assert canary not in privacy_export.text
    assert canary not in privacy_export.headers["content-disposition"]

    async with async_engine_fixture.connect() as connection:
        contexts = await connection.execute(text("SELECT context FROM audit_log_entries"))
        persisted_contexts = json.dumps([row[0] for row in contexts], default=str)
    assert canary not in persisted_contexts
    assert "actor_identity" in persisted_contexts

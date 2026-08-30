"""Real Redis proof that attempt lifecycle state never retains user canaries."""

from __future__ import annotations

import base64
import binascii
import json
from collections import Counter
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core.attempt_store import EphemeralAttempt, get_attempt, store_attempt

CONNECTION_ID = UUID("550e8400-e29b-41d4-a716-446655440001")
LIFECYCLE_STATES = ("PENDING", "GENERATED", "EVALUATED", "EXECUTED", "REJECTED", "FAILED", "TIMEOUT")


def _contains_canary(value: Any, canary: str) -> bool:
    canary_bytes = canary.encode()
    if isinstance(value, bytes):
        if canary_bytes in value:
            return True
        try:
            return canary_bytes in base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            return False
    if isinstance(value, str):
        return _contains_canary(value.encode(), canary)
    if isinstance(value, dict):
        return any(_contains_canary(part, canary) for pair in value.items() for part in pair)
    if isinstance(value, (list, tuple, set)):
        return any(_contains_canary(part, canary) for part in value)
    return False


async def _redis_values(redis_client, key: str, key_type: str) -> list[Any]:
    if key_type == "string":
        return [await redis_client.get(key)]
    if key_type == "hash":
        return [await redis_client.hgetall(key)]
    if key_type == "list":
        return list(await redis_client.lrange(key, 0, -1))
    if key_type == "set":
        return list(await redis_client.smembers(key))
    if key_type == "zset":
        return list(await redis_client.zrange(key, 0, -1, withscores=True))
    if key_type == "stream":
        return list(await redis_client.xrange(key))
    return []


async def _scan_redis_namespace(redis_client, canary: str) -> dict[str, Any]:
    cursor = 0
    key_count = 0
    value_count = 0
    canary_present = False
    namespaces: Counter[str] = Counter()
    types: Counter[str] = Counter()
    while True:
        cursor, keys = await redis_client.scan(cursor=cursor, match="*", count=100)
        for key in keys:
            key_count += 1
            key_name = key.decode() if isinstance(key, bytes) else key
            namespaces[key_name.partition(":")[0]] += 1
            canary_present = canary_present or _contains_canary(key, canary)
            key_type = await redis_client.type(key)
            type_name = key_type.decode() if isinstance(key_type, bytes) else key_type
            types[type_name] += 1
            for value in await _redis_values(redis_client, key, type_name):
                value_count += 1
                canary_present = canary_present or _contains_canary(value, canary)
        if cursor == 0:
            break
    return {
        "canary_present": canary_present,
        "key_count": key_count,
        "value_count": value_count,
        "namespaces": sorted(namespaces),
        "types": dict(sorted(types.items())),
    }


@pytest.mark.integration
@pytest.mark.parametrize("state", LIFECYCLE_STATES)
async def test_each_persisted_attempt_state_hides_canary(redis_client, state: str) -> None:
    """Every persisted lifecycle state is opaque in all Redis data types."""
    canary = f"chunk28-lifecycle-canary-{state.lower()}"
    await store_attempt(
        EphemeralAttempt(
            attempt_id=f"lifecycle-{state.lower()}",
            session_id="lifecycle-session",
            database_connection_id=CONNECTION_ID,
            question=canary,
            sql=f"SELECT '{canary}'",
            state=state,
        ),
        "lifecycle-session",
        redis_client,
    )

    before_read = await _scan_redis_namespace(redis_client, canary)
    restored = await get_attempt(f"lifecycle-{state.lower()}", "lifecycle-session", redis_client)
    after_read = await _scan_redis_namespace(redis_client, canary)
    question_restored = restored.question == canary
    sql_restored = restored.sql == f"SELECT '{canary}'"
    assert before_read["canary_present"] is False, f"Redis leak in lifecycle {state}"
    assert after_read["canary_present"] is False, f"Redis leak after read in lifecycle {state}"
    assert question_restored is True, f"question restore failed in lifecycle {state}"
    assert sql_restored is True, f"SQL restore failed in lifecycle {state}"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("replacement", "state"),
    [("retry-rejected", "REJECTED"), ("regenerate-replacement", "EXECUTED")],
)
async def test_retry_replacement_attempt_hides_canary(redis_client, replacement: str, state: str) -> None:
    """Reject/regenerate replacement records preserve retry text only in memory."""
    canary = f"chunk28-replacement-canary-{replacement}"
    attempt_id = f"replacement-{replacement}"
    await store_attempt(
        EphemeralAttempt(
            attempt_id=attempt_id,
            session_id="replacement-session",
            database_connection_id=CONNECTION_ID,
            question=canary,
            sql=f"SELECT '{canary}'",
            attempt_number=2,
            state=state,
        ),
        "replacement-session",
        redis_client,
    )

    summary = await _scan_redis_namespace(redis_client, canary)
    restored = await get_attempt(attempt_id, "replacement-session", redis_client)
    restored_text = restored.question == canary and restored.sql == f"SELECT '{canary}'"
    assert summary["canary_present"] is False, f"Redis leak in replacement {replacement}"
    assert restored_text is True, f"replacement restore failed for {replacement}"


async def _attempt_states(redis_client) -> list[str]:
    cursor = 0
    states: list[str] = []
    while True:
        cursor, keys = await redis_client.scan(cursor=cursor, match="attempt:*", count=100)
        for key in keys:
            raw = await redis_client.get(key)
            if raw is not None:
                states.append(json.loads(raw)["state"])
        if cursor == 0:
            return sorted(states)


@pytest.mark.integration
async def test_api_success_keeps_canary_out_of_real_redis(
    authenticated_client,
    redis_client,
    query_submit_payload,
    caplog,
) -> None:
    """A successful real API flow keeps question and generated SQL opaque."""
    from app.source_db.adapters import ExecuteResult

    canary = "chunk28-api-success-canary"
    with (
        patch(
            "app.api.v1.query.LLMProviderFactory.from_config",
            return_value=AsyncMock(generate_sql=AsyncMock(return_value="SELECT 1 AS id")),
        ),
        patch(
            "app.source_db.adapters.PostgresAdapter.execute",
            new=AsyncMock(return_value=ExecuteResult(columns=["id"], rows=[(1,)])),
        ),
    ):
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload(canary),
        )

    summary = await _scan_redis_namespace(redis_client, canary)
    states = await _attempt_states(redis_client)
    response_successful = response.status_code == 200
    logs_safe = all(canary not in record.getMessage() for record in caplog.records)
    assert response_successful is True, "successful API flow did not return success"
    assert logs_safe is True, "successful API flow logged the canary"
    assert summary["canary_present"] is False, "successful API flow retained the canary in Redis"
    assert states == ["EXECUTED"], "successful API flow did not persist its executed state"


@pytest.mark.integration
async def test_api_provider_failure_keeps_canary_out_of_pending_redis_state(
    authenticated_client,
    redis_client,
    query_submit_payload,
    caplog,
) -> None:
    """Provider failure leaves only opaque pending attempt state."""
    canary = "chunk28-api-provider-canary"
    with patch(
        "app.api.v1.query.LLMProviderFactory.from_config",
        return_value=AsyncMock(generate_sql=AsyncMock(side_effect=RuntimeError("provider failure"))),
    ):
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload(canary),
        )

    response_safe = canary not in response.text
    logs_safe = all(canary not in record.getMessage() for record in caplog.records)
    summary = await _scan_redis_namespace(redis_client, canary)
    states = await _attempt_states(redis_client)
    assert response_safe is True, "provider failure response contains the canary"
    assert logs_safe is True, "provider failure logged the canary"
    assert summary["canary_present"] is False, "provider failure retained the canary in Redis"
    assert states == ["PENDING"], "provider failure did not preserve the pending lifecycle state"


@pytest.mark.integration
async def test_api_evaluator_rejection_keeps_canary_out_of_rejected_redis_state(
    authenticated_client,
    redis_client,
    query_submit_payload,
    caplog,
) -> None:
    """Evaluator rejection stores an opaque rejected attempt."""
    canary = "chunk28-api-rejection-canary"
    with patch(
        "app.api.v1.query.LLMProviderFactory.from_config",
        return_value=AsyncMock(generate_sql=AsyncMock(return_value="DROP TABLE users")),
    ):
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload(canary),
        )

    response_safe = canary not in response.text
    logs_safe = all(canary not in record.getMessage() for record in caplog.records)
    summary = await _scan_redis_namespace(redis_client, canary)
    states = await _attempt_states(redis_client)
    assert response_safe is True, "evaluator rejection response contains the canary"
    assert logs_safe is True, "evaluator rejection logged the canary"
    assert summary["canary_present"] is False, "evaluator rejection retained the canary in Redis"
    assert states == ["REJECTED"], "evaluator rejection did not persist its rejected lifecycle state"


@pytest.mark.integration
async def test_api_timeout_keeps_canary_out_of_timeout_redis_state(
    authenticated_client,
    redis_client,
    query_submit_payload,
    caplog,
) -> None:
    """Source timeout stores an opaque timeout attempt."""
    canary = "chunk28-api-timeout-canary"
    with (
        patch(
            "app.api.v1.query.LLMProviderFactory.from_config",
            return_value=AsyncMock(generate_sql=AsyncMock(return_value="SELECT 1 AS id")),
        ),
        patch(
            "app.source_db.adapters.PostgresAdapter.execute",
            new=AsyncMock(side_effect=TimeoutError()),
        ),
    ):
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload(canary),
        )

    response_safe = canary not in response.text
    logs_safe = all(canary not in record.getMessage() for record in caplog.records)
    summary = await _scan_redis_namespace(redis_client, canary)
    states = await _attempt_states(redis_client)
    assert response_safe is True, "timeout response contains the canary"
    assert logs_safe is True, "timeout flow logged the canary"
    assert summary["canary_present"] is False, "timeout flow retained the canary in Redis"
    assert states == ["TIMEOUT"], "timeout flow did not persist its timeout lifecycle state"

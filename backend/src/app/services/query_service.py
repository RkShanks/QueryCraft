"""QueryService — submit, accept, reject, regenerate logic."""

import asyncio
import json
import uuid
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.attempt_store import EphemeralAttempt, delete_attempt, get_attempt, store_attempt
from app.core.exceptions import SessionBusy, SourceDBTimeout
from app.core.processing_lock import acquire_lock, release_lock
from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.schemas.query import (
    AcceptedQuerySummary,
    ColumnMeta,
    EvaluatorRejection,
    QueryResult,
    RefinePrompt,
    Violation,
)


class QueryService:
    """Orchestrates the question-to-result lifecycle."""

    def __init__(
        self,
        accepted_query_repository: AcceptedQueryRepository,
        redis: Redis,
        llm: Any,
        evaluator: Any,
        source_db_executor: Any,
    ) -> None:
        self._repo = accepted_query_repository
        self._redis = redis
        self._llm = llm
        self._evaluator = evaluator
        self._executor = source_db_executor

    async def _acquire_lock(self, session_id: str) -> bool:
        """Try to acquire a per-session processing lock."""
        return await acquire_lock(session_id, self._redis)

    async def _release_lock(self, session_id: str) -> None:
        """Release the per-session processing lock."""
        await release_lock(session_id, self._redis)

    async def submit_question(
        self,
        session_id: str,
        user_id: str,
        question: str,
    ) -> QueryResult | EvaluatorRejection:
        """Submit a question: LLM -> evaluate -> execute -> result."""
        if not await self._acquire_lock(session_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "concurrent", "message_key": "error.concurrent"},
            )

        attempt_id = str(uuid.uuid4())
        attempt = EphemeralAttempt(
            attempt_id=attempt_id,
            session_id=session_id,
            user_id=user_id,
            question=question,
            state="PENDING",
        )

        try:
            await store_attempt(attempt, session_id, self._redis)

            # 1. LLM generation
            try:
                sql = await self._llm.generate_sql(question, "")
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "llm_unavailable", "message_key": "error.llmUnavailable"},
                ) from exc

            attempt.sql = sql
            attempt.state = "GENERATED"
            await store_attempt(attempt, session_id, self._redis)

            # 2. Evaluator gate
            eval_result = await self._evaluator.evaluate(sql, None)
            if not eval_result.passed:
                attempt.state = "REJECTED"
                attempt.evaluator_result = {
                    "passed": False,
                    "violations": [
                        {"rule": v.rule_name, "message_key": v.message_key}
                        for v in eval_result.violations
                    ],
                }
                await store_attempt(attempt, session_id, self._redis)
                violations = [
                    Violation(rule=v.rule_name, message_key=v.message_key)
                    for v in eval_result.violations
                ]
                return EvaluatorRejection(
                    message_key="query.evaluator.rejected",
                    violations=violations,
                )

            attempt.state = "EVALUATED"
            await store_attempt(attempt, session_id, self._redis)

            # 3. Execute against source DB
            try:
                columns, rows = await asyncio.wait_for(
                    self._executor.execute(sql),
                    timeout=30,
                )
            except (TimeoutError, SourceDBTimeout) as exc:
                attempt.state = "TIMEOUT"
                await store_attempt(attempt, session_id, self._redis)
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail={"error": "timeout", "message_key": "error.timeout"},
                ) from exc

            attempt.state = "EXECUTED"
            attempt.executor_result = {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
            await store_attempt(attempt, session_id, self._redis)

            # 4. Build result
            column_metas = []
            for c in columns:
                if isinstance(c, dict):
                    column_metas.append(ColumnMeta(name=c["name"], type=c["type"]))
                else:
                    column_metas.append(ColumnMeta(name=c, type="text"))
            result = QueryResult(
                kind="result",
                attempt_id=attempt_id,
                question=question,
                generated_sql=sql,
                columns=column_metas,
                rows=rows,
                row_count=len(rows),
                attempt_number=1,
                is_last_auto_retry=False,
            )

            return result
        finally:
            await self._release_lock(session_id)

    async def accept_query(
        self,
        session_id: str,
        user_id: str,
        attempt_id: str,
        database_connection_id: str,
    ) -> AcceptedQuerySummary:
        """Accept a query result: persist to DB and delete Redis attempt."""
        lock_key = f"accept:{attempt_id}"
        lock_acquired = await self._redis.set(lock_key, "1", nx=True, ex=5)
        if not lock_acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "accept_conflict", "message_key": "error.acceptConflict"},
            )

        try:
            raw = await self._redis.get(f"attempt:{attempt_id}")
            if raw is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "attempt_expired", "message_key": "error.attemptExpired"},
                )

            attempt = json.loads(raw)
            if attempt.get("session_id") != session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "attempt_invalid", "message_key": "error.attemptInvalid"},
                )

            if attempt.get("state") != "EXECUTED":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "attempt_state_invalid", "message_key": "error.attemptStateInvalid"},
                )

            query = await self._repo.create(
                user_id=uuid.UUID(user_id),
                database_connection_id=uuid.UUID(database_connection_id),
                question_text=attempt.get("question_text") or attempt.get("question", ""),
                generated_sql=attempt.get("generated_sql") or attempt.get("sql", ""),
                llm_provider=attempt.get("llm_provider", "ollama"),
                attempt_id=attempt_id,
            )

            await self._redis.delete(f"attempt:{attempt_id}")

            return AcceptedQuerySummary(
                id=str(query.id),
                question_text=query.question_text,
                generated_sql=query.generated_sql,
                accepted_at=query.accepted_at.isoformat(),
            )
        finally:
            await self._redis.delete(lock_key)

    async def reject_query(
        self,
        attempt_id: str,
        session_id: str,
    ) -> QueryResult | RefinePrompt:
        """Reject a query result and trigger one auto-retry.

        Behaviour is identical to regenerate_query: discards the current
        attempt, provides it as negative context to the LLM, and generates
        a new SQL attempt. If this is the second consecutive rejection (or
        the regenerated SQL is byte-equal), returns a RefinePrompt instead
        of a new result.

        Raises:
            SessionBusy: if a concurrent operation is in progress.
            AttemptNotFound: if the attempt does not exist.
            AttemptOwnershipViolation: if session_id doesn't match.
        """
        return await self.regenerate_query(attempt_id, session_id)

    async def regenerate_query(
        self,
        attempt_id: str,
        session_id: str,
    ) -> QueryResult | RefinePrompt:
        """Regenerate SQL for a rejected query result.

        Flow:
        1. Acquire processing lock.
        2. Get prior attempt (validate ownership).
        3. Build LLM prompt with negative context.
        4. Call LLM.
        5. Inv 4 byte-equal check: if new SQL == prior SQL -> RefinePrompt.
        6. Run evaluator (Inv 1).
        7. If evaluator fails -> store attempt, return RefinePrompt.
        8. If evaluator passes -> run executor.
        9. Store new attempt.
        10. Check max retries -> if exceeded, return RefinePrompt.
        11. Release lock, return QueryResult.

        Raises:
            SessionBusy: if a concurrent operation is in progress.
            AttemptNotFound: if the attempt does not exist.
            AttemptOwnershipViolation: if session_id doesn't match.
        """
        if not await self._acquire_lock(session_id):
            raise SessionBusy()

        try:
            prior = await get_attempt(attempt_id, session_id, self._redis)
            await delete_attempt(attempt_id, self._redis)

            # Max retries: original (attempt_number=1) + 1 regenerate = 2 total
            next_attempt_number = (prior.attempt_number or 1) + 1
            if next_attempt_number > 2:
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            # Build negative context from prior attempt
            negative_examples = [prior.sql] if prior.sql else []

            # Call LLM
            try:
                new_sql = await self._llm.generate_sql(
                    prior.question,
                    "",
                    negative_examples=negative_examples,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "llm_unavailable", "message_key": "error.llmUnavailable"},
                ) from exc

            # Inv 4: byte-equal duplicate detection
            if new_sql == prior.sql:
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            # Inv 1: evaluator gate
            eval_result = await self._evaluator.evaluate(new_sql, None)
            if not eval_result.passed:
                # Store the failed attempt so the user can see why
                new_attempt_id = str(uuid.uuid4())
                failed_attempt = EphemeralAttempt(
                    attempt_id=new_attempt_id,
                    session_id=session_id,
                    sql=new_sql,
                    question=prior.question,
                    attempt_number=next_attempt_number,
                    evaluator_result={
                        "passed": False,
                        "violations": [
                            {"rule": v.rule_name, "message_key": v.message_key}
                            for v in eval_result.violations
                        ],
                    },
                )
                await store_attempt(failed_attempt, session_id, self._redis)
                return RefinePrompt(
                    message_key="query.refine.message",
                    should_refine=True,
                )

            # Execute against source DB
            try:
                columns, rows = await asyncio.wait_for(
                    self._executor.execute(new_sql),
                    timeout=30,
                )
            except (TimeoutError, asyncio.TimeoutError, SourceDBTimeout) as exc:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail={"error": "timeout", "message_key": "error.timeout"},
                ) from exc

            # Build result and store ephemeral attempt
            new_attempt_id = str(uuid.uuid4())
            column_metas = []
            for c in columns:
                if isinstance(c, dict):
                    column_metas.append(ColumnMeta(name=c["name"], type=c["type"]))
                else:
                    column_metas.append(ColumnMeta(name=c, type="text"))
            result = QueryResult(
                kind="result",
                attempt_id=new_attempt_id,
                question=prior.question,
                generated_sql=new_sql,
                columns=column_metas,
                rows=rows,
                row_count=len(rows),
                attempt_number=next_attempt_number,
                is_last_auto_retry=next_attempt_number >= 2,
            )

            new_attempt = EphemeralAttempt(
                attempt_id=new_attempt_id,
                session_id=session_id,
                sql=new_sql,
                question=prior.question,
                attempt_number=next_attempt_number,
                state="PENDING",
                executor_result={
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                },
            )
            await store_attempt(new_attempt, session_id, self._redis)

            return result
        finally:
            await self._release_lock(session_id)

"""QueryService — submit, accept, reject, regenerate logic."""

import asyncio
import json
import uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.repositories.accepted_query_repository import AcceptedQueryRepository
from app.schemas.query import (
    AcceptedQuerySummary,
    ColumnMeta,
    EvaluatorRejection,
    QueryResult,
    Violation,
)


class QueryService:
    """Orchestrates the question-to-result lifecycle."""

    def __init__(
        self,
        accepted_query_repository: AcceptedQueryRepository,
        redis: Redis,
        llm,
        evaluator,
        source_db_executor,
    ):
        self._repo = accepted_query_repository
        self._redis = redis
        self._llm = llm
        self._evaluator = evaluator
        self._executor = source_db_executor

    async def _acquire_lock(self, session_id: str) -> bool:
        """Try to acquire a per-session processing lock."""
        lock_key = f"lock:{session_id}"
        acquired = await self._redis.set(lock_key, "1", nx=True, ex=40)
        return acquired is not None

    async def _release_lock(self, session_id: str) -> None:
        """Release the per-session processing lock."""
        await self._redis.delete(f"lock:{session_id}")

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

        try:
            # 1. LLM generation
            try:
                sql = await self._llm.generate_sql(question, "")
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "llm_unavailable", "message_key": "error.llmUnavailable"},
                ) from exc

            # 2. Evaluator gate
            eval_result = await self._evaluator.evaluate(sql, None)
            if not eval_result.passed:
                violations = [
                    Violation(rule=v.rule_name, message_key=v.message_key)
                    for v in eval_result.violations
                ]
                return EvaluatorRejection(
                    message_key="query.evaluator.rejected",
                    violations=violations,
                )

            # 3. Execute against source DB
            try:
                columns, rows = await asyncio.wait_for(
                    self._executor.execute(sql),
                    timeout=30,
                )
            except TimeoutError as exc:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail={"error": "timeout", "message_key": "error.timeout"},
                ) from exc

            # 4. Build result and store ephemeral attempt
            attempt_id = str(uuid.uuid4())
            result = QueryResult(
                kind="result",
                attempt_id=attempt_id,
                question=question,
                generated_sql=sql,
                columns=[ColumnMeta(name=c["name"], type=c["type"]) for c in columns],
                rows=rows,
                row_count=len(rows),
                attempt_number=1,
                is_last_auto_retry=False,
            )

            attempt_data = {
                "attempt_id": attempt_id,
                "session_id": session_id,
                "user_id": user_id,
                "question_text": question,
                "generated_sql": sql,
                "llm_provider": "ollama",
                "attempt_number": 1,
                "rejected_sqls": [],
            }
            await self._redis.set(
                f"attempt:{attempt_id}",
                json.dumps(attempt_data),
                ex=15 * 60,
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

        query = await self._repo.create(
            user_id=uuid.UUID(user_id),
            database_connection_id=uuid.UUID(database_connection_id),
            question_text=attempt["question_text"],
            generated_sql=attempt["generated_sql"],
            llm_provider=attempt["llm_provider"],
        )

        await self._redis.delete(f"attempt:{attempt_id}")

        return AcceptedQuerySummary(
            id=str(query.id),
            question_text=query.question_text,
            generated_sql=query.generated_sql,
            accepted_at=query.accepted_at.isoformat(),
        )

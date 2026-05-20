"""History Pydantic schemas matching openapi.yaml.

Defines HistoryListResponse and AcceptedQueryDetail.
"""

from pydantic import BaseModel

from app.schemas.query import AcceptedQuerySummary


class HistoryListResponse(BaseModel):
    """GET /history response."""

    items: list[AcceptedQuerySummary]
    total: int | None = None
    next_cursor: str | None = None


class AcceptedQueryDetail(BaseModel):
    """GET /history/{id} response."""

    id: str
    question_text: str
    generated_sql: str
    llm_provider: str
    accepted_at: str
    database_connection_id: str | None = None
    result_columns: list | None = None
    result_rows: list | None = None
    result_row_count: int | None = None

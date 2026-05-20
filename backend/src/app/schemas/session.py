"""Session Pydantic schemas."""

from pydantic import BaseModel


class AttemptSummary(BaseModel):
    """Summary of an accepted query within a session."""

    id: str
    question_text: str
    generated_sql: str
    accepted_at: str
    saved: bool
    feedback: int | None = None
    result_columns: list | None = None
    result_rows: list | None = None
    result_row_count: int | None = None
    database_connection_id: str | None = None


class SessionSummary(BaseModel):
    """Summary of a session for list views."""

    id: str
    preview_text: str
    created_at: str
    last_activity_at: str


class SessionDetail(BaseModel):
    """Full session detail with conversation history."""

    id: str
    connection_id: str | None = None
    preview_text: str
    created_at: str
    last_activity_at: str
    attempts: list[AttemptSummary]


class CreateSessionResponse(BaseModel):
    """Response after creating a session."""

    id: str
    preview_text: str
    created_at: str


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    items: list[SessionSummary]
    total: int


class SessionConnectionUpdate(BaseModel):
    """Request body for updating session connection (T-434, FR-094)."""

    connection_id: str


class SessionConnectionResponse(BaseModel):
    """Response after updating session connection."""

    id: str
    connection_id: str | None = None
    preview_text: str
    created_at: str
    last_activity_at: str

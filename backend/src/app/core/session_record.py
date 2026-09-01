"""Strict validation boundary for persisted authentication sessions."""

import json
import math
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, ValidationError, field_validator

from app.core.exceptions import SessionRecordInvalid

NonEmptyString = Annotated[str, Field(min_length=1)]


class SessionRecord(BaseModel):
    """Complete server-created authentication record stored in Redis."""

    model_config = ConfigDict(extra="forbid", strict=True)

    user_id: NonEmptyString
    username: NonEmptyString
    display_name: NonEmptyString
    role: NonEmptyString
    role_id: NonEmptyString | None
    role_name: NonEmptyString | None
    permissions: list[NonEmptyString]
    auth_provider: Literal["local", "oidc", "saml"]
    subject_id: NonEmptyString
    email: NonEmptyString | None = None
    created_at: StrictFloat
    last_activity: StrictFloat
    generation: Annotated[StrictInt, Field(ge=0)] | None = None

    @field_validator("user_id", "role_id")
    @classmethod
    def canonical_uuid(cls, identifier: str | None) -> str | None:
        if identifier is None:
            return None
        try:
            parsed_identifier = uuid.UUID(identifier)
        except ValueError:
            raise ValueError("identifier must be a UUID") from None
        if str(parsed_identifier) != identifier:
            raise ValueError("identifier must be canonical")
        return identifier

    @field_validator("created_at", "last_activity")
    @classmethod
    def finite_timestamp(cls, timestamp: float) -> float:
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("timestamp must be finite and non-negative")
        return timestamp


def parse_session_record(session_json: str, indexed_user_id: str | None = None) -> dict[str, Any]:
    """Return validated session fields or one constant typed failure."""
    try:
        record = SessionRecord.model_validate_json(session_json)
    except (ValidationError, json.JSONDecodeError, TypeError):
        raise SessionRecordInvalid from None
    if indexed_user_id is not None and record.user_id != indexed_user_id:
        raise SessionRecordInvalid()
    return record.model_dump(mode="json", exclude_unset=True)

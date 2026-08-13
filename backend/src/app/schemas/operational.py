"""Non-sensitive operational probe response schemas."""

from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["live"] = "live"


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"


class NotReadyResponse(BaseModel):
    status: Literal["not_ready"] = "not_ready"

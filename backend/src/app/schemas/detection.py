"""Phase 6 hostile-input detection schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class DetectionThresholdRead(BaseModel):
    """Current detection threshold configuration."""

    block_confidence: float
    flag_confidence: float
    updated_at: datetime


class DetectionThresholdUpdate(BaseModel):
    """Detection threshold update request."""

    block_confidence: float = Field(..., ge=0.0, le=1.0)
    flag_confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("block_confidence", "flag_confidence", mode="before")
    @classmethod
    def require_json_number(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("detection thresholds must be JSON numbers")
        return value

    @model_validator(mode="after")
    def validate_threshold_order(self):
        if self.block_confidence <= self.flag_confidence:
            raise ValueError("block_confidence must be greater than flag_confidence")
        return self

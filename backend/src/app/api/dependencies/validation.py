"""Reusable FastAPI dependencies for contract-mandated request validation."""

from fastapi import Body, HTTPException
from pydantic import BaseModel, ValidationError


def validate_body[T: BaseModel](model: type[T]):
    """Return a FastAPI dependency that validates request body against ``model``.

    On validation failure raises HTTP 400 with the contract-mandated
    ``ErrorResponse`` envelope instead of FastAPI's default 422 shape.
    """

    async def _validator(body: dict = Body(...)) -> T:  # noqa: B008
        try:
            return model.model_validate(body)
        except ValidationError as exc:
            details = []
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err.get("loc", []))
                details.append(
                    {
                        "field": field,
                        "message_key": err.get("type", "error.validation.generic"),
                        "message_params": {"msg": err.get("msg", "")},
                    }
                )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.generic",
                    "details": details,
                },
            ) from None

    return _validator

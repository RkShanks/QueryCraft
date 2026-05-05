"""Auth router — sign-in, sign-out, me."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_redis
from app.core.security import SessionMiddleware
from app.repositories.user_repository import UserRepository
from app.schemas.auth import SignInRequest, UserProfile
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


async def _get_auth_service(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis: Redis = Depends(get_redis),  # noqa: B008
) -> AuthService:
    return AuthService(UserRepository(db), redis)


@router.post("/sign-in", response_model=UserProfile)
async def sign_in(
    request: Request,
    response: Response,
    payload: SignInRequest,
    auth_service: AuthService = Depends(_get_auth_service),  # noqa: B008
):
    """POST /auth/sign-in — authenticate and set session cookie."""
    profile, session_id = await auth_service.sign_in(payload.username, payload.password)
    SessionMiddleware.set_cookie(response, session_id, secure=False)
    return profile


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(_get_auth_service),  # noqa: B008
):
    """POST /auth/sign-out — delete session and clear cookie."""
    session_id = request.cookies.get(SessionMiddleware.COOKIE_NAME)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    # Verify session exists
    try:
        await auth_service.get_me(session_id)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        ) from None
    await auth_service.sign_out(session_id)
    SessionMiddleware.delete_cookie(response)
    return None


@router.get("/me", response_model=UserProfile)
async def get_me(
    request: Request,
    auth_service: AuthService = Depends(_get_auth_service),  # noqa: B008
):
    """GET /auth/me — return current user profile."""
    session_id = request.cookies.get(SessionMiddleware.COOKIE_NAME)
    if not session_id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message_key": "error.unauthorized"},
        )
    return await auth_service.get_me(session_id)

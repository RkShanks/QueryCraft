"""Create a test user for e2e. Idempotent. Dev/test only — not run in production."""
import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.models.user import User


USERNAME = os.environ.get("E2E_TEST_USERNAME", "e2e_user")
PASSWORD = os.environ.get("E2E_TEST_PASSWORD", "e2e_password_123")


async def main() -> None:
    db_url = os.environ["DATABASE_URL"]                # platform DB
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        existing = await s.scalar(select(User).where(User.username == USERNAME))
        if existing:
            print(f"User {USERNAME} already exists (id={existing.id}); no-op.")
            return
        user = User(
            username=USERNAME,
            display_name=USERNAME,
            password_hash=hash_password(PASSWORD),
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        print(f"Created user {USERNAME} (id={user.id}).")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)

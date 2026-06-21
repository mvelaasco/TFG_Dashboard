from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_session import get_session
from domain.auth.user import User
from infrastructure.auth.jwt import verify_token
from infrastructure.db.repositories.pg_auth_repository import PgAuthRepository

_security = HTTPBearer(auto_error=False)


async def get_current_user(
    token: str | None = Depends(_security),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    if token is None:
        return None
    payload = verify_token(token.credentials)
    if payload is None:
        return None
    repo = PgAuthRepository(session)
    return await repo.find_by_email(payload.get("email", ""))


async def require_admin(
    user: User | None = Depends(get_current_user),
) -> User:
    if user is None or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )
    return user

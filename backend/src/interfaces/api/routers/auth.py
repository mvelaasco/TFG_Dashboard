from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_session import get_session
from infrastructure.auth.dependencies import get_current_user
from infrastructure.auth.jwt import create_token
from infrastructure.auth.password import verify_password
from infrastructure.db.repositories.pg_auth_repository import PgAuthRepository
from interfaces.schemas.auth_schema import (
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from domain.auth.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
#inyecciones de dependencias manuales, podrían ser reemplazadas por un contenedor de dependencias
    repo = PgAuthRepository(session)
    user = await repo.find_by_email(body.email)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada",
        )
    token = create_token(user.id, user.email, user.is_admin)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(
    user: User | None = Depends(get_current_user),
) -> UserResponse:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return UserResponse(**user.model_dump())

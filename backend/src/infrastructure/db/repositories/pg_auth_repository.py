from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.auth_repository import AuthRepository
from domain.auth.user import User
from infrastructure.db.models.user_model import UserModel


class PgAuthRepository(AuthRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            username=model.username,
            hashed_password=model.hashed_password,
            is_admin=model.is_admin,
            is_active=model.is_active,
            created_at=model.created_at,
        )

    async def save(self, user: User) -> User:
        model = UserModel(
            email=user.email,
            username=user.username,
            hashed_password=user.hashed_password,
            is_admin=user.is_admin,
            is_active=user.is_active,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def find_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email.lower())
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.username == username.lower())
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

from abc import ABC, abstractmethod
from domain.auth.user import User


class AuthRepository(ABC):

    @abstractmethod
    async def save(self, user: User) -> User:
        ...

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None:
        ...

    @abstractmethod
    async def find_by_username(self, username: str) -> User | None:
        ...

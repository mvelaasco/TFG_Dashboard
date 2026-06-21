from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import settings


engine = create_async_engine(
    settings.db_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # descarta conexiones muertas automáticamente
    echo=False,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # evita lazy-load tras commit
)


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos ORM."""
    pass


async def get_session() -> AsyncSession:
    """Dependencia de FastAPI. Gestiona el ciclo de vida de la sesión."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
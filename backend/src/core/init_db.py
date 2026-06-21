from sqlalchemy import text

from core.db_session import Base, engine
from infrastructure.auth.password import hash_password

SEED_ADMIN = {
    "email": "admin@tfg.com",
    "username": "admin",
    "hashed_password": hash_password("admin123"),
    "is_admin": True,
    "is_active": True,
}

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("""
                INSERT INTO users (email, username, hashed_password, is_admin, is_active)
                VALUES (:email, :username, :hashed_password, :is_admin, :is_active)
                ON CONFLICT (email) DO NOTHING
            """),
            SEED_ADMIN,
        )
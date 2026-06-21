from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from core.db_session import Base


class UserModel(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True)
    email           = Column(String(255), nullable=False, unique=True)
    username        = Column(String(100), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    is_admin        = Column(Boolean, nullable=False, default=False)
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

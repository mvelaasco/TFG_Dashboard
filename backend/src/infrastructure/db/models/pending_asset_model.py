from sqlalchemy import Column, String, CheckConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from core.db_session import Base


class PendingAssetModel(Base):
    __tablename__ = "pending_assets"

    symbol     = Column(String(20), primary_key=True)
    name       = Column(String(200), nullable=True)
    asset_type = Column(String(20), default="stock")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    status     = Column(String(20), default="pending")

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processing', 'done', 'failed')"),
    )

from sqlalchemy import Column, Integer, Numeric, ForeignKey, String
from sqlalchemy.dialects.postgresql import TIMESTAMP
from core.db_session import Base


class MetricModel(Base):
    __tablename__ = "analytical_metrics"

    time                = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    base_asset_id       = Column(Integer, ForeignKey("assets.id"), primary_key=True, nullable=False)
    comparison_asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    metric_name         = Column(String(50), nullable=False)
    window_days         = Column(Integer, nullable=False)
    metric_value        = Column(Numeric(18, 8), nullable=False)
    calculated_at       = Column(TIMESTAMP(timezone=True))

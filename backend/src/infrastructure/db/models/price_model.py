from sqlalchemy import Column, Integer, BigInteger, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from core.db_session import Base


class PriceModel(Base):
    __tablename__ = "asset_prices"

    time     = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), primary_key=True, nullable=False)
    open     = Column(Numeric(18, 6))
    high     = Column(Numeric(18, 6))
    low      = Column(Numeric(18, 6))
    close    = Column(Numeric(18, 6), nullable=False)
    volume   = Column(BigInteger)
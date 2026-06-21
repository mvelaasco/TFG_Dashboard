from sqlalchemy import Column, Integer, String, Date, Numeric

from core.db_session import Base


class WeeklyPriceModel(Base):
    __tablename__ = "weekly_prices"

    symbol      = Column(String(20), primary_key=True, nullable=False)
    week_number = Column(Integer, primary_key=True, nullable=False)
    week_start  = Column(Date, nullable=False)
    close       = Column(Numeric(18, 6), nullable=False)
    pct_change  = Column(Numeric(18, 6), nullable=True)

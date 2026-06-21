from sqlalchemy import Column, Date, Integer, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func

from core.db_session import Base


class NewsModel(Base):
    __tablename__ = "historical_news"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    date = Column(Date, nullable=False)
    datetime = Column(TIMESTAMP(timezone=True), nullable=False)
    headline = Column(Text, nullable=False)
    source = Column(String(100))
    url = Column(Text)
    summary = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

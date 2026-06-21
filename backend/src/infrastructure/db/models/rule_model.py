from sqlalchemy import Column, Integer, String, Text, Numeric

from core.db_session import Base


class RuleModel(Base):
    __tablename__ = "association_rules"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    antecedent      = Column(Text, nullable=False)
    consequent      = Column(Text, nullable=False)
    support         = Column(Numeric(18, 8))
    confidence      = Column(Numeric(18, 8))
    lift            = Column(Numeric(18, 8))
    coverage        = Column(Numeric(18, 8))
    amplitude       = Column(Numeric(18, 8))
    netconf         = Column(Numeric(18, 8))

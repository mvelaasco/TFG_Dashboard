from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from core.db_session import Base


class AssetTypeModel(Base):
    __tablename__ = "asset_types"

    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)

    assets = relationship("AssetModel", back_populates="asset_type")


class AssetModel(Base):
    __tablename__ = "assets"

    id            = Column(Integer, primary_key=True)
    symbol        = Column(String(20),  nullable=False, unique=True)
    name          = Column(String(200), nullable=False)
    asset_type_id = Column(Integer, ForeignKey("asset_types.id"))
    currency      = Column(String(10),  nullable=False, default="USD")
    exchange      = Column(String(50))
    timezone      = Column(String(50),  nullable=False, default="America/New_York")

    asset_type = relationship("AssetTypeModel", back_populates="assets")
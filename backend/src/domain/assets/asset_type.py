from enum import Enum


class AssetType(str, Enum):
    STOCK  = "stock"
    ETF    = "etf"
    CRYPTO = "crypto"
    INDEX  = "index"
    FX     = "fx"
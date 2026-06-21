import httpx
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from application.ports.exceptions import RateLimitExceeded
from application.ports.market_data_client import MarketDataClient
from core.config import settings
from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from domain.prices.price import Price


PRICE_SCALE = Decimal("0.000001")


class TiingoClient(MarketDataClient):
    """
    Implementación de MarketDataClient usando la API de Tiingo.
    Cubre acciones, ETFs e índices con datos EOD (End of Day).
    """

    BASE_URL = "https://api.tiingo.com/tiingo"

    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Token {settings.tiingo_api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Implementación del puerto
    # ------------------------------------------------------------------

    async def fetch_asset_metadata(self, symbol: str) -> Asset | None:
        url = f"{self.BASE_URL}/daily/{symbol.lower()}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._headers, timeout=10.0)
            except httpx.RequestError:
                return None

        if response.status_code == 404:
            return None
        if response.status_code == 403:
            raise PermissionError(f"API key inválida o sin acceso a '{symbol}'")
        if response.status_code == 429:
            raise RateLimitExceeded(f"Cuota de Tiingo excedida para '{symbol}'")
        response.raise_for_status()

        data = response.json()
        return Asset(
            symbol=data["ticker"].upper(),
            name=data.get("name", symbol),
            asset_type=self._infer_asset_type(data),
            currency="USD",
            exchange=data.get("exchangeCode", None),
        )

    async def fetch_daily_prices(
        self,
        symbol:    str,
        from_date: date,
        to_date:   date,
    ) -> list[Price]:
        url = f"{self.BASE_URL}/daily/{symbol.lower()}/prices"
        params = {
            "startDate": from_date.isoformat(),
            "endDate":   to_date.isoformat(),
            "resampleFreq": "daily",
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self._headers,
                    params=params,
                    timeout=15.0,
                )
            except httpx.RequestError as e:
                raise ConnectionError(f"Error conectando con Tiingo: {e}") from e

        if response.status_code == 404:
            return []
        if response.status_code == 429:
            raise RateLimitExceeded(f"Cuota de Tiingo excedida para '{symbol}'")
        response.raise_for_status()

        return [
            self._parse_price(row, symbol)
            for row in response.json()
            if row.get("close") is not None
        ]

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_price(row: dict, symbol: str) -> Price:
        """
        Convierte una fila del JSON de Tiingo en una entidad Price.
        Usa precios ajustados (adj*) para todos los campos OHLC
        para garantizar consistencia cuando hay splits o dividendos.
        """
        raw_time = row["date"]
        if raw_time.endswith("Z"):
            raw_time = raw_time[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw_time)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        return Price(
            time=dt,
            asset_id=0,
            open=Decimal(str(row["adjOpen"])).quantize(PRICE_SCALE, rounding=ROUND_HALF_UP)  if row.get("adjOpen")  is not None else None,
            high=Decimal(str(row["adjHigh"])).quantize(PRICE_SCALE, rounding=ROUND_HALF_UP)  if row.get("adjHigh")  is not None else None,
            low=Decimal(str(row["adjLow"])).quantize(PRICE_SCALE, rounding=ROUND_HALF_UP)    if row.get("adjLow")   is not None else None,
            close=Decimal(str(row["adjClose"])).quantize(PRICE_SCALE, rounding=ROUND_HALF_UP),
            volume=int(row["adjVolume"])       if row.get("adjVolume") is not None else None,
        )

    @staticmethod
    def _infer_asset_type(data: dict) -> AssetType:
        """
        Tiingo no devuelve el tipo de activo explícitamente.
        Lo inferimos del campo description o lo dejamos como STOCK por defecto.
        """
        description = (data.get("description") or "").lower()
        name = (data.get("name") or "").lower()

        if any(w in name for w in ["etf", "fund", "ishares", "vanguard", "spdr"]):
            return AssetType.ETF
        if any(w in description for w in ["index", "índice"]):
            return AssetType.INDEX
        return AssetType.STOCK
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository
from application.ports.market_data_client import MarketDataClient
from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from domain.prices.price import Price


@dataclass
class IngestPricesRequest:
    symbol:    str
    from_date: date
    to_date:   date


@dataclass
class IngestPricesResult:
    symbol:         str
    rows_inserted:  int
    already_existed: bool   # True si el activo ya estaba en BD


class IngestPrices:
    """
    Caso de uso: dado un símbolo y un rango de fechas, obtiene los
    precios de la fuente de datos externa y los persiste en la BD.

    Reglas de negocio orquestadas aquí:
      1. Si el activo no existe en BD, se crea antes de insertar precios.
      2. Los precios se insertan en bulk para minimizar round-trips a BD.
      3. El caso de uso nunca conoce qué API concreta provee los datos
         ni qué tecnología persiste los resultados.
    """

    def __init__(
        self,
        asset_repo:   AssetRepository,
        price_repo:   PriceRepository,
        market_client: MarketDataClient,
    ) -> None:
        self._assets  = asset_repo
        self._prices  = price_repo
        self._client  = market_client

    async def execute(self, request: IngestPricesRequest) -> IngestPricesResult:
        symbol = request.symbol.upper().strip()

        # 1. Busca el activo en BD
        asset = await self._assets.find_by_symbol(symbol)
        already_existed = asset is not None

        # 2. Si no existe, lo obtiene de la fuente externa y lo persiste
        if asset is None:
            asset = await self._client.fetch_asset_metadata(symbol)
            if asset is None:
                raise ValueError(
                    f"El símbolo '{symbol}' no existe en la fuente de datos."
                )
            asset = await self._assets.save(asset)

        # 3. Obtiene los precios del rango solicitado
        prices = await self._client.fetch_daily_prices(
            symbol=symbol,
            from_date=request.from_date,
            to_date=request.to_date,
        )

        if not prices:
            return IngestPricesResult(
                symbol=symbol,
                rows_inserted=0,
                already_existed=already_existed,
            )

        # 4. Reasigna asset_id correcto (el cliente devuelve asset_id=0 por convención)
        prices_with_id = [
            p.model_copy(update={"asset_id": asset.id})
            for p in prices
        ]

        # 5. Persiste en bulk
        rows = await self._price_repo_save(prices_with_id)

        return IngestPricesResult(
            symbol=symbol,
            rows_inserted=rows,
            already_existed=already_existed,
        )

    async def _price_repo_save(self, prices: list[Price]) -> int:
        return await self._prices.save_batch(prices)
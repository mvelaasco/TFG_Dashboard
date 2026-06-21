from datetime import date

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from application.use_cases.get_news import GetNews, GetNewsRequest
from core.db_session import get_session
from infrastructure.db.repositories.pg_news_repository import PgNewsRepository
from infrastructure.external_apis.finnhub_client import FinnhubClient
from interfaces.schemas.news_schema import NewsItemResponse
import httpx

router = APIRouter(prefix="/assets", tags=["news"])


@router.get("/{symbol}/news", response_model=list[NewsItemResponse])
async def get_news(
    symbol: str,
    date: date = Query(..., description="Fecha en formato YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
) -> list[NewsItemResponse]:
    """
    Devuelve noticias para un símbolo y fecha concretos.
    Primera consulta: llama a Finnhub y persiste (~1500ms).
    Consultas posteriores: devuelve desde BD propia (~50ms).
    """
    #inyecciones de dependencias manuales, podrían ser reemplazadas por un contenedor de dependencias
    http_client = httpx.AsyncClient()
    use_case = GetNews(
        news_repo=PgNewsRepository(session),
        news_client=FinnhubClient(http_client),
    )
    items = await use_case.execute(GetNewsRequest(symbol=symbol, date=date))
    return [NewsItemResponse(**item.model_dump()) for item in items]

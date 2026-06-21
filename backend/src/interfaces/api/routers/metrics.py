from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from application.use_cases.compute_correlations import (
    ComputeCorrelations,
    ComputeCorrelationsRequest,
)
from application.use_cases.compute_coverage import (
    ComputeCoverage,
    ComputeCoverageRequest,
)
from application.use_cases.compute_coverage_calendar import (
    ComputeCoverageCalendar,
    CoverageCalendarRequest,
)
from core.config import settings
from core.db_session import get_session
from infrastructure.db.repositories.pg_asset_repository import PgAssetRepository
from infrastructure.db.repositories.pg_metric_repository import PgMetricRepository
from infrastructure.db.repositories.pg_price_repository import PgPriceRepository
from application.use_cases.compute_volatility import (
    ComputeVolatility,
    VolatilityRequest,
)
from application.use_cases.compute_correlation_matrix import (
    ComputeCorrelationMatrix,
    CorrelationMatrixRequest,
)
from interfaces.schemas.metric_schema import (
    CorrelationMatrixResponse,
    CorrelationPoint,
    CorrelationRequest,
    CorrelationResponse,
    CorrelationSeriesResponse,
    CorrelatePairRequest,
    CorrelatePairResponse,
    CoverageCalendarDaySchema,
    CoverageCalendarResponse,
    CoverageGapSchema,
    CoverageItemSchema,
    CoverageResponse,
    CoverageSummarySchema,
    VolatilityPoint,
    VolatilityResponse,
)


router = APIRouter(prefix="/metrics", tags=["metrics"])




@router.post("/correlations", response_model=CorrelationResponse)
async def compute_correlations(
    payload: CorrelationRequest,
    session: AsyncSession = Depends(get_session),
) -> CorrelationResponse:
    risk_symbols = settings.risk_index_symbol_list
    if not risk_symbols:
        raise HTTPException(
            status_code=400,
            detail="RISK_INDEX_SYMBOLS no está configurado.",
        )

    today = date.today()
    if payload.to_date and payload.to_date > today:
        raise HTTPException(status_code=400, detail="to_date no puede ser futura")
    if payload.from_date and payload.from_date > today:
        raise HTTPException(status_code=400, detail="from_date no puede ser futura")
        
#inyecciones de dependencias manuales, podrían ser reemplazadas por un contenedor de dependencias

    asset_repo = PgAssetRepository(session)
    price_repo = PgPriceRepository(session)
    metric_repo = PgMetricRepository(session)

    # llama al constructor y le inyecta la implementación de los repositorios, luego ejecuta el caso de uso con los parámetros del request
    use_case = ComputeCorrelations(
        asset_repo=asset_repo,
        price_repo=price_repo,
        metric_repo=metric_repo,
    )

    result = await use_case.execute(
        ComputeCorrelationsRequest(
            risk_symbols=risk_symbols,
            from_date=payload.from_date,
            to_date=payload.to_date,
        )
    )

    if result.missing_risk_symbols:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Faltan símbolos de riesgo en la BD.",
                "missing": result.missing_risk_symbols,
            },
        )

    return CorrelationResponse(
        metrics_inserted=result.metrics_inserted,
        pairs_processed=result.pairs_processed,
        missing_risk_symbols=result.missing_risk_symbols,
    )


@router.get("/correlations", response_model=CorrelationSeriesResponse)
async def get_correlations(
    base_symbol: str = Query(..., description="Símbolo del activo base"),
    risk_symbol: str = Query(..., description="Símbolo del índice de riesgo"),
    window_days: int = Query(30, description="Ventana en días"),
    from_date: date | None = Query(None, description="Fecha inicio YYYY-MM-DD"),
    to_date: date | None = Query(None, description="Fecha fin YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
) -> CorrelationSeriesResponse:
    if window_days not in (30, 90):
        raise HTTPException(
            status_code=400,
            detail="window_days debe ser 30 o 90.",
        )

    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail="from_date no puede ser mayor que to_date.",
        )

    asset_repo = PgAssetRepository(session)
    metric_repo = PgMetricRepository(session)

    base = await asset_repo.find_by_symbol(base_symbol)
    if base is None:
        raise HTTPException(
            status_code=404,
            detail=f"Activo '{base_symbol}' no encontrado",
        )

    risk = await asset_repo.find_by_symbol(risk_symbol)
    if risk is None:
        raise HTTPException(
            status_code=404,
            detail=f"Activo '{risk_symbol}' no encontrado",
        )

    if from_date is None:
        from_time = datetime(1970, 1, 1, tzinfo=timezone.utc)
    else:
        from_time = datetime(
            from_date.year,
            from_date.month,
            from_date.day,
            tzinfo=timezone.utc,
        )

    if to_date is None:
        to_time = datetime.now(timezone.utc)
    else:
        to_time = datetime(
            to_date.year,
            to_date.month,
            to_date.day,
            23,
            59,
            59,
            tzinfo=timezone.utc,
        )

    metric_name = f"correlation_{window_days}d"
    series = await metric_repo.find_series(
        base_asset_id=base.id,
        comparison_asset_id=risk.id,
        metric_name=metric_name,
        window_days=window_days,
        from_time=from_time,
        to_time=to_time,
    )

    points = [
        CorrelationPoint(
            time=m.time,
            value=m.metric_value,
        )
        for m in series
    ]

    return CorrelationSeriesResponse(
        base_symbol=base.symbol,
        risk_symbol=risk.symbol,
        window_days=window_days,
        series=points,
    )


@router.get("/coverage", response_model=CoverageResponse)
async def get_coverage(
    symbols: str | None = Query(None, description="Lista CSV de símbolos"),
    min_gap_days: int = Query(2, ge=1, description="Tamaño mínimo de gap en días"),
    session: AsyncSession = Depends(get_session),
) -> CoverageResponse:
    asset_repo = PgAssetRepository(session)
    price_repo = PgPriceRepository(session)
    use_case = ComputeCoverage(
        asset_repo=asset_repo,
        price_repo=price_repo,
    )

    symbol_list = None
    if symbols is not None:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    result = await use_case.execute(
        ComputeCoverageRequest(
            symbols=symbol_list,
            min_gap_days=min_gap_days,
        )
    )

    summary = CoverageSummarySchema(
        symbols_count=result.summary.symbols_count,
        coverage_pct_avg=result.summary.coverage_pct_avg,
        symbols_below_threshold=result.summary.symbols_below_threshold,
        threshold_pct=result.summary.threshold_pct,
    )

    items = []
    for item in result.items:
        gaps = [
            CoverageGapSchema(start=g.start, end=g.end, days=g.days)
            for g in item.gaps
        ]
        items.append(
            CoverageItemSchema(
                symbol=item.symbol,
                expected_days=item.expected_days,
                available_days=item.available_days,
                coverage_pct=item.coverage_pct,
                missing_days=item.missing_days,
                first_date=item.first_date,
                last_date=item.last_date,
                freshness_lag_days=item.freshness_lag_days,
                record_count=item.record_count,
                gaps=gaps,
            )
        )

    return CoverageResponse(summary=summary, items=items)


@router.get("/coverage-calendar", response_model=CoverageCalendarResponse)
async def get_coverage_calendar(
    from_date: date = Query(..., description="Fecha inicio YYYY-MM-DD"),
    to_date: date = Query(..., description="Fecha fin YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
) -> CoverageCalendarResponse:
    today = date.today()
    if from_date > today:
        raise HTTPException(status_code=400, detail="from_date no puede ser futura")
    if to_date > today:
        raise HTTPException(status_code=400, detail="to_date no puede ser futura")

    asset_repo = PgAssetRepository(session)
    price_repo = PgPriceRepository(session)
    use_case = ComputeCoverageCalendar(asset_repo, price_repo)

    result = await use_case.execute(
        CoverageCalendarRequest(from_date=from_date, to_date=to_date),
    )

    days = [
        CoverageCalendarDaySchema(
            date=d.date,
            actual_count=d.actual_count,
            expected_count=d.expected_count,
            is_weekend=d.is_weekend,
        )
        for d in result.days
    ]

    return CoverageCalendarResponse(
        from_date=result.from_date,
        to_date=result.to_date,
        total_assets=result.total_assets,
        days=days,
    )


@router.get("/volatility", response_model=VolatilityResponse)
async def get_volatility(
    symbol: str = Query(..., description="Símbolo del activo"),
    window_days: int = Query(30, description="Ventana en días para el cálculo (30, 90, 180)"),
    from_date: date | None = Query(None, description="Fecha inicio YYYY-MM-DD"),
    to_date: date | None = Query(None, description="Fecha fin YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
) -> VolatilityResponse:
    if window_days not in (30, 90, 180):
        raise HTTPException(
            status_code=400,
            detail="window_days debe ser 30, 90 o 180.",
        )

    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail="from_date no puede ser mayor que to_date.",
        )

    today = date.today()
    if to_date and to_date > today:
        raise HTTPException(status_code=400, detail="to_date no puede ser futura")
    if from_date and from_date > today:
        raise HTTPException(status_code=400, detail="from_date no puede ser futura")

    asset_repo = PgAssetRepository(session)
    price_repo = PgPriceRepository(session)
    use_case = ComputeVolatility(asset_repo, price_repo)

    try:
        result = await use_case.execute(VolatilityRequest(
            symbol=symbol,
            window_days=window_days,
            from_date=from_date,
            to_date=to_date,
        ))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    points = [
        VolatilityPoint(time=p.time, value=p.value)
        for p in result.series
    ]

    return VolatilityResponse(
        symbol=result.symbol,
        window_days=result.window_days,
        series=points,
    )


@router.get("/correlation-matrix", response_model=CorrelationMatrixResponse)
async def get_correlation_matrix(
    top_n: int = Query(15, ge=2, le=50, description="Número de activos"),
    from_date: date | None = Query(None, description="Fecha inicio YYYY-MM-DD"),
    to_date: date | None = Query(None, description="Fecha fin YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
) -> CorrelationMatrixResponse:
    asset_repo = PgAssetRepository(session)
    price_repo = PgPriceRepository(session)
    use_case = ComputeCorrelationMatrix(asset_repo, price_repo)

    result = await use_case.execute(
        CorrelationMatrixRequest(
            top_n=top_n,
            from_date=from_date,
            to_date=to_date,
        )
    )

    return CorrelationMatrixResponse(
        symbols=result.symbols,
        matrix=result.matrix,
    )


@router.post("/correlate-pair", response_model=CorrelatePairResponse)
async def correlate_pair(
    payload: CorrelatePairRequest,
    session: AsyncSession = Depends(get_session),
) -> CorrelatePairResponse:
    asset_repo = PgAssetRepository(session)
    price_repo = PgPriceRepository(session)
    metric_repo = PgMetricRepository(session)

    base_asset = await asset_repo.find_by_symbol(payload.base_symbol)
    if not base_asset:
        raise HTTPException(
            status_code=404,
            detail=f"Activo base '{payload.base_symbol}' no encontrado.",
        )

    target_asset = await asset_repo.find_by_symbol(payload.target_symbol)
    if not target_asset:
        raise HTTPException(
            status_code=404,
            detail=f"Activo destino '{payload.target_symbol}' no encontrado.",
        )

    if base_asset.symbol == target_asset.symbol:
        raise HTTPException(
            status_code=400,
            detail="base_symbol y target_symbol deben ser distintos.",
        )

    today = date.today()
    if payload.to_date and payload.to_date > today:
        raise HTTPException(status_code=400, detail="to_date no puede ser futura")
    if payload.from_date and payload.from_date > today:
        raise HTTPException(status_code=400, detail="from_date no puede ser futura")

    use_case = ComputeCorrelations(
        asset_repo=asset_repo,
        price_repo=price_repo,
        metric_repo=metric_repo,
    )

    result = await use_case.execute(
        ComputeCorrelationsRequest(
            risk_symbols=[target_asset.symbol],
            base_symbols=[payload.base_symbol],
            from_date=payload.from_date,
            to_date=payload.to_date,
        )
    )

    return CorrelatePairResponse(
        metrics_inserted=result.metrics_inserted,
        pairs_processed=result.pairs_processed,
    )

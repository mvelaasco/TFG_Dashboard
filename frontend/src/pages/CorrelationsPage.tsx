import { useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  Asset,
  correlatePair,
  fetchAssets,
  fetchAssetPrices,
  fetchCorrelations,
  fetchVolatility,
  type CorrelationSeriesResponse,
  type VolatilityResponse,
} from '../api';
import AssetPicker from '../components/AssetPicker';

type Status = {
  kind: 'idle' | 'loading' | 'success' | 'error';
  message: string;
};

type PricePoint = { time: string; close: number };

const DEFAULT_WINDOW: 30 | 90 = 30;
const DEFAULT_FROM = '2024-01-01';
const DEFAULT_TO = new Date().toISOString().slice(0, 10);
const MARKET_SINCE = '2023-01-01';

function formatValue(value: number) {
  return value.toFixed(4);
}

function makeChartEvents(symbol: string) {
  return {
    click: (params: { name: string }) => {
      if (params.name) {
        const date = params.name.slice(0, 10);
        const query = new URLSearchParams({ symbol, date });
        window.location.href = `/news?${query.toString()}`;
      }
    },
  };
}

function makeMarketOption(
  prices: PricePoint[],
  color: string,
  areaColor: string,
  label: string,
  formatterPrefix: string,
) {
  if (!prices.length) return null;
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (params: { name: string; value: number }[]) => {
        const d = params[0];
        return `<strong>${d.name}</strong><br/>${formatterPrefix}: <strong>$${Number(d.value).toFixed(2)}</strong>`;
      },
    },
    grid: { left: 38, right: 8, top: 8, bottom: 16 },
    xAxis: {
      type: 'category',
      data: prices.map((p) => p.time.slice(0, 10)),
      axisLabel: { show: false },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#aebad3', fontSize: 9, formatter: '${value}' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
    },
    series: [
      {
        type: 'line',
        data: prices.map((p) => p.close),
        smooth: true,
        showSymbol: false,
        lineStyle: { color, width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: areaColor },
              { offset: 1, color: areaColor.replace(/[\d.]+\)$/, '0)') },
            ],
          },
        },
      },
    ],
  };
}

function makeVolatilityOption(vol: VolatilityResponse | null, color: string) {
  if (!vol?.series.length) return null;
  const points = vol.series.map((p) => ({ time: p.time.slice(0, 10), value: Number(p.value) }));
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (params: { name: string; value: number }[]) => {
        const d = params[0];
        return `<strong>${d.name}</strong><br/>Vol: <strong>${(d.value).toFixed(2)}%</strong>`;
      },
    },
    grid: { left: 50, right: 12, top: 8, bottom: 20 },
    xAxis: {
      type: 'category',
      data: points.map((p) => p.time),
      axisLabel: { color: '#aebad3', fontSize: 9, showMaxLabel: true, showMinLabel: true },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#aebad3', fontSize: 9, formatter: '{value}%' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
    },
    series: [
      {
        type: 'line',
        data: points.map((p) => +((p.value)*100).toFixed(2)),
        smooth: true,
        showSymbol: false,
        lineStyle: { color, width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: color.replace('1)', '0.25)') },
              { offset: 1, color: 'rgba(0,0,0,0)' },
            ],
          },
        },
      },
    ],
  };
}

function makeOverlayOption(
  basePrices: PricePoint[],
  riskPrices: PricePoint[],
  baseSymbol: string,
  riskSymbol: string,
) {
  if (!basePrices.length || !riskPrices.length) return null;

  const baseMap = new Map(basePrices.map((p) => [p.time.slice(0, 10), p.close]));
  const riskMap = new Map(riskPrices.map((p) => [p.time.slice(0, 10), p.close]));
  const commonDates = [...baseMap.keys()].filter((d) => riskMap.has(d)).sort();
  if (commonDates.length < 2) return null;

  const base0 = baseMap.get(commonDates[0])!;
  const risk0 = riskMap.get(commonDates[0])!;
  const base100 = commonDates.map((d) => (baseMap.get(d)! / base0) * 100);
  const risk100 = commonDates.map((d) => (riskMap.get(d)! / risk0) * 100);

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (params: { seriesName: string; value: number; name: string }[]) => {
        const date = params[0].name;
        const lines = params.map(
          (p) => `${p.seriesName}: <strong>${p.value.toFixed(2)}</strong>`,
        );
        return `<strong>${date}</strong><br/>${lines.join('<br/>')}`;
      },
    },
    legend: {
      data: [baseSymbol, riskSymbol],
      textStyle: { color: '#aebad3' },
      top: 0,
    },
    grid: { left: 56, right: 16, top: 36, bottom: 28 },
    xAxis: {
      type: 'category',
      data: commonDates,
      axisLabel: { color: '#aebad3', fontSize: 11, showMaxLabel: true, showMinLabel: true },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#aebad3', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
    },
    series: [
      {
        name: baseSymbol,
        type: 'line',
        data: base100,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#7de2d1', width: 2.5 },
      },
      {
        name: riskSymbol,
        type: 'line',
        data: risk100,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#ffb86b', width: 2.5 },
      },
    ],
  };
}

function makeCorrelationOption(corr: CorrelationSeriesResponse | null) {
  if (!corr?.series.length) return null;
  const dates = corr.series.map((p) => p.time.slice(0, 10));
  const values = corr.series.map((p) => Number(p.value));
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (params: { name: string; value: number }[]) => {
        const d = params[0];
        return `<strong>${d.name}</strong><br/>Correlación: <strong>${Number(d.value).toFixed(4)}</strong><br/><span style="font-size:11px;color:#aebad3">Click para noticias</span>`;
      },
    },
    grid: { left: 56, right: 16, top: 16, bottom: 28 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#aebad3', fontSize: 11, showMaxLabel: true, showMinLabel: true },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: -1,
      max: 1,
      axisLabel: { color: '#aebad3', fontSize: 11, formatter: '{value}' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
    },
    series: [
      {
        type: 'line',
        data: values,
        smooth: true,
        showSymbol: true,
        symbolSize: 4,
        lineStyle: { color: '#7de2d1', width: 2.5 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(125,226,209,0.3)' },
              { offset: 1, color: 'rgba(125,226,209,0)' },
            ],
          },
        },
        markLine: {
          silent: true,
          lineStyle: { color: 'rgba(125,226,209,0.3)', type: 'dashed' },
          label: { show: false },
          data: [{ yAxis: 0 }],
        },
      },
    ],
  };
}

export default function CorrelationsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [baseSymbol, setBaseSymbol] = useState('AAPL');
  const [riskSymbol, setRiskSymbol] = useState('VIXY');
  const [windowDays, setWindowDays] = useState<30 | 90>(DEFAULT_WINDOW);
  const [fromDate, setFromDate] = useState(DEFAULT_FROM);
  const [toDate, setToDate] = useState(DEFAULT_TO);
  const [status, setStatus] = useState<Status>({ kind: 'idle', message: 'Listo.' });
  const [correlation, setCorrelation] = useState<CorrelationSeriesResponse | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const [basePrices, setBasePrices] = useState<PricePoint[]>([]);
  const [riskPrices, setRiskPrices] = useState<PricePoint[]>([]);

  const [spyPrices, setSpyPrices] = useState<PricePoint[]>([]);
  const [customSymbol, setCustomSymbol] = useState('AAPL');
  const [customPrices, setCustomPrices] = useState<PricePoint[]>([]);

  const [volSymbol, setVolSymbol] = useState('SPY');
  const [volWindow, setVolWindow] = useState<30 | 90 | 180>(90);
  const [volFromDate, setVolFromDate] = useState('2020-01-01');
  const [volToDate, setVolToDate] = useState(DEFAULT_TO);
  const [volData, setVolData] = useState<VolatilityResponse | null>(null);

  useEffect(() => {
    void loadAssets();
    void loadMarketData();
  }, []);

  useEffect(() => {
    void loadCustomPrice();
  }, [customSymbol]);

  useEffect(() => {
    void loadVolatility();
  }, [volSymbol, volWindow, volFromDate, volToDate]);

  async function loadAssets() {
    try {
      const data = await fetchAssets();
      setAssets(data);
    } catch {
      setStatus({ kind: 'error', message: 'Error cargando activos.' });
    }
  }

  async function loadMarketData() {
    const spy = await fetchAssetPrices('SPY', MARKET_SINCE).catch(() => []);
    setSpyPrices(spy.map((p) => ({ time: p.time, close: Number(p.close) })));
  }

  async function loadCustomPrice() {
    const data = await fetchAssetPrices(customSymbol, MARKET_SINCE).catch(() => []);
    setCustomPrices(data.map((p) => ({ time: p.time, close: Number(p.close) })));
  }

  async function loadVolatility() {
    try {
      const data = await fetchVolatility({
        symbol: volSymbol,
        windowDays: volWindow,
        fromDate: volFromDate,
        toDate: volToDate,
      });
      setVolData(data);
    } catch {
      setVolData(null);
    }
  }

  async function handleLoadSeries() {
    try {
      setIsBusy(true);
      setStatus({ kind: 'loading', message: 'Calculando y cargando serie...' });

      await correlatePair({
        base_symbol: baseSymbol,
        target_symbol: riskSymbol,
        from_date: fromDate || null,
        to_date: toDate || null,
      });

      const data = await fetchCorrelations({
        baseSymbol,
        riskSymbol,
        windowDays,
        fromDate: fromDate || undefined,
        toDate: toDate || undefined,
      });

      setCorrelation(data);

      const [baseP, riskP] = await Promise.all([
        fetchAssetPrices(baseSymbol, fromDate || undefined, toDate || undefined),
        fetchAssetPrices(riskSymbol, fromDate || undefined, toDate || undefined),
      ]);
      setBasePrices(baseP.map((p) => ({ time: p.time, close: Number(p.close) })));
      setRiskPrices(riskP.map((p) => ({ time: p.time, close: Number(p.close) })));

      setStatus({
        kind: 'success',
        message: `${data.base_symbol} vs ${data.risk_symbol} · ${data.series.length} puntos.`,
      });
    } catch (error) {
      setCorrelation(null);
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Error.' });
    } finally {
      setIsBusy(false);
    }
  }

  const spyOption = useMemo(
    () => makeMarketOption(spyPrices, '#7de2d1', 'rgba(125,226,209,0.3)', 'SPY · S&P 500', 'SPY'),
    [spyPrices],
  );
  const customOption = useMemo(
    () => makeMarketOption(customPrices, '#5ba8ff', 'rgba(91,168,255,0.3)', `${customSymbol}`, customSymbol),
    [customPrices, customSymbol],
  );
  const volOption = useMemo(
    () => makeVolatilityOption(volData, '#ffb86b'),
    [volData],
  );
  const overlayOption = useMemo(
    () => makeOverlayOption(basePrices, riskPrices, baseSymbol, riskSymbol),
    [basePrices, riskPrices, baseSymbol, riskSymbol],
  );

  const correlationOption = useMemo(
    () => makeCorrelationOption(correlation),
    [correlation],
  );

  const meanValue = useMemo(() => {
    if (!correlation?.series.length) return '—';
    const values = correlation.series.map((point) => Number(point.value));
    const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
    return formatValue(avg);
  }, [correlation]);

  const chartEvents = useMemo(() => ({
    click: (params: { dataIndex: number }) => {
      if (correlation && params.dataIndex != null) {
        const date = correlation.series[params.dataIndex].time.slice(0, 10);
        const query = new URLSearchParams({ symbol: baseSymbol, date });
        window.location.href = `/news?${query.toString()}`;
      }
    },
  }), [correlation, baseSymbol]);

  function renderMarketChart(
    option: ReturnType<typeof makeMarketOption>,
    header: string,
    selector?: React.ReactNode,
    onEvents?: Record<string, (params: any) => void>,
  ) {
    return (
      <div className="market-chart-item">
        <div className="market-chart-header">
          <span>{header}</span>
          {selector}
        </div>
        {option ? (
          <ReactECharts option={option} style={{ height: 150 }} onEvents={onEvents} />
        ) : (
          <div className="empty-state"><h3>Sin datos</h3></div>
        )}
      </div>
    );
  }

  const customSelector = (
    <select value={customSymbol} onChange={(e) => setCustomSymbol(e.target.value)}
      style={{ padding: '4px 6px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(4,8,18,0.7)', color: 'var(--text)', fontSize: '0.72rem', outline: 'none' }}>
      {assets.map((a) => <option key={a.symbol} value={a.symbol}>{a.symbol} – {a.name}</option>)}
    </select>
  );

  const volControls = (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      <select value={volSymbol} onChange={(e) => setVolSymbol(e.target.value)}
        style={{ padding: '4px 6px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(4,8,18,0.7)', color: 'var(--text)', fontSize: '0.72rem', outline: 'none' }}>
        {assets.map((a) => <option key={a.symbol} value={a.symbol}>{a.symbol} – {a.name}</option>)}
      </select>
      <select value={volWindow} onChange={(e) => setVolWindow(Number(e.target.value) as 30 | 90 | 180)}
        style={{ padding: '4px 6px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(4,8,18,0.7)', color: 'var(--text)', fontSize: '0.72rem', outline: 'none' }}>
        <option value={30}>30d</option>
        <option value={90}>90d</option>
        <option value={180}>180d</option>
      </select>
      <input type="date" value={volFromDate} onChange={e => setVolFromDate(e.target.value)}
        style={{ padding: '4px 6px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(4,8,18,0.7)', color: 'var(--text)', fontSize: '0.72rem', outline: 'none', width: 110 }} />
      <input type="date" value={volToDate} onChange={e => setVolToDate(e.target.value)}
        style={{ padding: '4px 6px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(4,8,18,0.7)', color: 'var(--text)', fontSize: '0.72rem', outline: 'none', width: 110 }} />
    </div>
  );

  return (
    <main className="layout corr-layout">
      <section className="hero card market-hero">
        <div className="hero-header">
          <div className="eyebrow">TFG Finance · mercado</div>
          <div className={`status status-${status.kind}`}>
            <span className="status-dot" />
            <span>{status.message}</span>
          </div>
        </div>
        <div className="market-grid" style={{ gridTemplateColumns: '1fr 1fr 2fr' }}>
          {renderMarketChart(spyOption, 'SPY · S&P 500', undefined, makeChartEvents('SPY'))}
          {renderMarketChart(customOption, 'Personalizado', customSelector, makeChartEvents(customSymbol))}
          <div className="market-chart-item">
            <div className="market-chart-header">
              <span>Volatilidad anualizada</span>
              {volControls}
            </div>
            {volOption ? (
              <ReactECharts option={volOption} style={{ height: 150 }} onEvents={makeChartEvents(volSymbol)} />
            ) : (
              <div className="empty-state"><h3>Sin datos</h3></div>
            )}
          </div>
        </div>
      </section>

      <section className="card controls compact-controls">
        <div className="controls-row">
          <label>
            <span>Activo A</span>
            <AssetPicker value={baseSymbol} onChange={setBaseSymbol} assets={assets} />
          </label>
          <label>
            <span>Activo B</span>
            <AssetPicker value={riskSymbol} onChange={setRiskSymbol} assets={assets} />
          </label>
          <label>
            <span>Ventana</span>
            <select value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value) as 30 | 90)}>
              <option value={30}>30d</option>
              <option value={90}>90d</option>
            </select>
          </label>
          <label>
            <span>Desde</span>
            <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          </label>
          <label>
            <span>Hasta</span>
            <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </label>
          <div className="controls-actions">
            <button type="button" className="primary" onClick={handleLoadSeries} disabled={isBusy}>
              Ver
            </button>
          </div>
        </div>
      </section>

      <section className="card chart-card">
        <div className="section-title split">
          <div>
            <h2>Serie de correlación</h2>
            <p>
              {correlation
                ? `${correlation.base_symbol} vs ${correlation.risk_symbol} · ventana ${correlation.window_days}d`
                : 'Todavía no has cargado una serie.'}
            </p>
          </div>
          <div className="mini-metrics">
            <span>Media</span>
            <strong>{meanValue}</strong>
          </div>
        </div>

        {correlationOption ? (
          <ReactECharts option={correlationOption} style={{ height: 380 }} onEvents={chartEvents} />
        ) : (
          <div className="empty-state">
            <h3>Sin datos todavía</h3>
            <p>Pulsa "Ver correlación" para cargar la serie.</p>
          </div>
        )}
      </section>

      <section className="card heatmap-card">
        <div className="section-title">
          <div>
            <h2>Precios normalizados</h2>
            <p>
              {basePrices.length
                ? `${baseSymbol} vs ${riskSymbol} · base 100`
                : 'Carga una serie de correlación para ver los precios.'}
            </p>
          </div>
        </div>
        {overlayOption ? (
          <ReactECharts option={overlayOption} style={{ height: 380 }} onEvents={makeChartEvents(baseSymbol)} />
        ) : (
          <div className="empty-state">
            <h3>Sin datos suficientes</h3>
            <p>Se necesitan al menos 2 fechas comunes entre ambos activos.</p>
          </div>
        )}
      </section>
    </main>
  );
}
import { useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';

import {
  fetchCoverage,
  fetchCoverageCalendar,
} from '../api';

function formatPct(value: number) {
  return `${value.toFixed(1)}%`;
}

function coverageColor(value: number) {
  if (value >= 95) return '#87f29b';
  if (value >= 90) return '#ffb86b';
  return '#ff7a90';
}

function freshnessColor(days: number) {
  if (days <= 2) return '#87f29b';
  if (days <= 7) return '#ffb86b';
  return '#ff7a90';
}

export default function DataQualityPage() {
  const [coverage, setCoverage] = useState<CoverageResponse | null>(null);
  const [calendar, setCalendar] = useState<CoverageCalendarDay[]>([]);
  const [symbolFilter, setSymbolFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([loadCoverage(), loadCalendar()]).finally(() => setLoading(false));
  }, []);

  async function loadCoverage() {
    const data = await fetchCoverage();
    setCoverage(data);
  }

  async function loadCalendar() {
    const to = new Date();
    const from = new Date();
    from.setFullYear(from.getFullYear() - 1);
    const data = await fetchCoverageCalendar(
      from.toISOString().slice(0, 10),
      to.toISOString().slice(0, 10),
    );
    setCalendar(data.days);
  }

  const items = useMemo(() => {
    if (!coverage) return [];
    let list = coverage.items;
    if (symbolFilter) {
      const q = symbolFilter.toLowerCase();
      list = list.filter(
        (i) => i.symbol.toLowerCase().includes(q) || String(i.record_count).includes(q),
      );
    }
    return list.sort((a, b) => a.freshness_lag_days - b.freshness_lag_days);
  }, [coverage, symbolFilter]);

  const totalRecords = useMemo(
    () => items.reduce((s, i) => s + i.record_count, 0),
    [items],
  );

  const staleCount = useMemo(
    () => items.filter((i) => i.freshness_lag_days > 7).length,
    [items],
  );

  const avgCoverage = useMemo(
    () => (items.length ? items.reduce((s, i) => s + i.coverage_pct, 0) / items.length : 0),
    [items],
  );

  const heatmapData = useMemo(() => {
    return calendar.map((d) => [d.date, d.actual_count]);
  }, [calendar]);

  const maxCount = useMemo(
    () => Math.max(...calendar.map((d) => d.actual_count), 1),
    [calendar],
  );

  const heatmapOption = useMemo(() => {
    const dates = calendar.length > 0
      ? [calendar[0].date, calendar[calendar.length - 1].date]
      : ['2025-01-01', '2025-12-31'];

    return {
      backgroundColor: 'transparent',
      tooltip: {
        position: 'top',
        formatter: (p: { value: [string, number]; data: [string, number] }) => {
          const day = calendar.find((d) => d.date === (p.value || p.data)[0]);
          if (!day) return '';
          const status = day.is_weekend
            ? 'Fin de semana'
            : day.actual_count === 0
              ? 'Sin datos'
              : day.actual_count >= day.expected_count
                ? 'Completo'
                : 'Parcial';
          return [
            `<strong>${day.date}</strong>`,
            `Tickers: ${day.actual_count} / ${day.expected_count}`,
            `Estado: ${status}`,
          ].join('<br/>');
        },
      },
      calendar: {
        range: dates,
        cellSize: [18, 18],
        top: 40,
        bottom: 20,
        left: 40,
        right: 40,
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        itemStyle: { borderWidth: 2, borderColor: '#0d1117' },
        dayLabel: {
          color: '#aebad3',
          fontSize: 10,
          firstDay: 1,
          nameMap: ['D', 'L', 'M', 'X', 'J', 'V', 'S'],
        },
        monthLabel: {
          color: '#aebad3',
          fontSize: 10,
          margin: 12,
          nameMap: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
        },
        yearLabel: { show: false },
      },
      series: [{
        type: 'heatmap',
        coordinateSystem: 'calendar',
        data: heatmapData,
        itemStyle: {
          color: (params: { value: [string, number] }) => {
            const day = calendar.find((d) => d.date === params.value[0]);
            if (!day) return 'transparent';
            if (day.is_weekend) return '#1a1d27';
            if (day.actual_count === 0) return '#ff4d4d';
            const ratio = day.actual_count / day.expected_count;
            if (ratio >= 0.95) return '#1a6b3c';
            if (ratio >= 0.5) return '#b8860b';
            return '#8b3a3a';
          },
        },
      }],
    };
  }, [heatmapData, calendar]);



  return (
    <main className="layout data-layout">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
        {[
          { label: 'Cobertura media', value: coverage ? formatPct(avgCoverage) : '—' },
          { label: 'Registros totales', value: totalRecords.toLocaleString() },
          { label: 'Símbolos', value: items.length },
          { label: 'Desactualizados >7d', value: staleCount, color: staleCount > 0 ? '#ff7a90' : '#87f29b' },
        ].map((s) => (
          <article key={s.label} className="card" style={{ padding: '12px 16px', textAlign: 'center' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--muted)', textTransform: 'uppercase' }}>{s.label}</span>
            <strong style={{ display: 'block', fontSize: '1.3rem', color: s.color || 'var(--text)', marginTop: 4 }}>{s.value}</strong>
          </article>
        ))}
      </div>

      <div className="card" style={{ padding: '12px 16px', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <input
            value={symbolFilter}
            onChange={(e) => setSymbolFilter(e.target.value)}
            placeholder="Filtrar por símbolo…"
            style={{
              flex: 1, minWidth: 0, padding: '8px 10px', borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(4,8,18,0.8)', color: 'var(--text)',
            }}
          />
          <button className="primary" style={{ padding: '8px 14px' }} onClick={() => loadCoverage()}>
            Actualizar
          </button>
        </div>
      </div>

      {loading ? (
        <p style={{ color: 'var(--muted)', textAlign: 'center', padding: 40 }}>Cargando…</p>
      ) : (
        <>
          <section className="card" style={{ padding: 16, marginBottom: 16, display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ marginBottom: 8, fontSize: '0.9rem' }}>Calendario de cobertura {calendar.length > 0 ? `(${calendar[0].date.slice(0, 4)}-${calendar[calendar.length - 1].date.slice(0, 4)})` : ''}</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--muted)', marginBottom: 12 }}>
              Verde = completo, Amarillo = parcial, Rojo = sin datos, Gris = fin de semana
            </p>
            <div style={{ flexGrow: 1, minHeight: 280, width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              <ReactECharts
                option={heatmapOption}
                style={{ height: '100%', width: '100%' }}
                opts={{ renderer: 'svg' }}
                notMerge={true}
                lazyUpdate={true}
              />
            </div>
          </section>

          <section className="card" style={{ padding: 16 }}>
            <h3 style={{ marginBottom: 12, fontSize: '0.9rem' }}>Detalle por activo</h3>
            <div style={{ overflowX: 'auto', maxHeight: 400, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                    <th style={thStyle}>Símbolo</th>
                    <th style={thStyle}>Registros</th>
                    <th style={thStyle}>Cobertura</th>
                    <th style={thStyle}>Frescura</th>
                    <th style={thStyle}>Desde</th>
                    <th style={thStyle}>Hasta</th>
                    <th style={thStyle}>Alertas</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.symbol} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={tdStyle}><strong>{item.symbol}</strong></td>
                      <td style={tdStyle}>{item.record_count.toLocaleString()}</td>
                      <td style={{ ...tdStyle, color: coverageColor(item.coverage_pct) }}>
                        {formatPct(item.coverage_pct)}
                      </td>
                      <td style={{ ...tdStyle, color: freshnessColor(item.freshness_lag_days) }}>
                        {item.freshness_lag_days}d
                      </td>
                      <td style={tdStyle}>{item.first_date}</td>
                      <td style={tdStyle}>{item.last_date}</td>
                      <td style={tdStyle}>
                        {item.freshness_lag_days > 7 ? (
                          <span style={{ color: '#ff7a90' }}>🔴 Desactualizado</span>
                        ) : item.coverage_pct < 90 ? (
                          <span style={{ color: '#ffb86b' }}>🟡 Cobertura baja</span>
                        ) : (
                          <span style={{ color: '#87f29b' }}>🟢 Ok</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 10px',
  color: 'var(--muted)',
  fontWeight: 600,
  fontSize: '0.7rem',
  textTransform: 'uppercase',
  whiteSpace: 'nowrap',
};

const tdStyle: React.CSSProperties = {
  padding: '8px 10px',
  whiteSpace: 'nowrap',
};

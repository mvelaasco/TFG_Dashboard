import { useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { fetchAssets, fetchRules, fetchWeeklyPrices, Asset, Rule, WeeklyPricePoint } from '../api';

type SortKey = 'support' | 'confidence' | 'lift' | 'antecedent' | 'consequent';
type SortDir = 'asc' | 'desc';

const MONTHS = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

// Es la funcion encargada de formatear las reglas para mostrarlas en la tabla
function formatConditions(raw: string): string {
  const inner = raw.startsWith('[') ? raw.slice(1, -1) : raw;
  const parts: string[] = [];
  let depth = 0;
  let buf = '';
  for (const ch of inner) {
    if (ch === '[') depth++;
    if (ch === ']') depth--;
    if (ch === ',' && depth === 0) { parts.push(buf.trim()); buf = ''; continue; }
    buf += ch;
  }
  if (buf.trim()) parts.push(buf.trim());

  return parts.map(p => {
    let s = p.replace(/\]$/, ')');

    //Elimina los corchetes y reduce los decimales a 2 cifras
    s = s.replace(/(\w+)_pct_change\(\[([\d.-]+),\s*([\d.-]+)\]\)/, (_, sym, lo, hi) =>
      `${sym} ∈ [${(+lo).toFixed(2)}, ${(+hi).toFixed(2)}]%`);
    return s;
    //Filtro para no mostrar el mes en la columna de Antecedente, la columna de semanas si se muestra
  }).filter(s => !s.startsWith('month(')).join('<br>');
}

// Coge el mes que diga la regla y lo muestra en la columna de Mes. Si no encuentra el mes, muestra un guion
function extractMonth(raw: string): string {
  const m = raw.match(/month\(\[(\d+),\s*(\d+)\]\)/);
  return m ? `${MONTHS[+m[1]]}-${MONTHS[+m[2]]}` : '—';
}

function parseCSV(text: string) {
  return text
    .trim()
    .split('\n')
    .slice(1)
    .filter(Boolean)
    .map(l => {
      const [ant, interval, count] = l.split(',').map(s => s.trim());
      return { antecedent: ant, interval, count: parseFloat(count) };
    });
}

function cleanName(s: string) { return s.split('||')[0]; }

// Es la pagina principal donde se muestran las reglas de asociación, la tabla y las gráficas
export default function RulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>('lift');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [filterText, setFilterText] = useState('');
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([]);
  const [weeklyData, setWeeklyData] = useState<WeeklyPricePoint[]>([]);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableSymbols, setAvailableSymbols] = useState<string[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [rawRows, setRawRows] = useState<{ antecedent: string; interval: string; count: number }[]>([]);
  const [sankeyOption, setSankeyOption] = useState<Record<string, unknown> | null>(null);
  const [sankeyEmpty, setSankeyEmpty] = useState(false);
  const [visibleIntervals, setVisibleIntervals] = useState<Set<string>>(new Set(['negativo', 'cruce', 'positivo']));
  const [visibleAntecedents, setVisibleAntecedents] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch('/sankey3/index.csv')
      .then(r => r.text())
      .then(text => {
        const symbols = text.trim().split('\n').slice(1).map(l => l.trim()).filter(Boolean);
        setAvailableSymbols(symbols);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedSymbol) { setRawRows([]); setVisibleAntecedents(new Set()); return; }
    fetch(`/sankey3/${selectedSymbol}.csv`)
      .then(r => r.text())
      .then(text => {
        const rows = parseCSV(text);
        setRawRows(rows);
        setVisibleAntecedents(new Set(rows.map(r => r.antecedent)));
      })
      .catch(() => { setRawRows([]); setVisibleAntecedents(new Set()); });
  }, [selectedSymbol]);

  useEffect(() => {
    if (!selectedSymbol || rawRows.length === 0) {
      setSankeyOption(null);
      setSankeyEmpty(false);
      return;
    }

    const colors: Record<string, string> = {
      negativo: '#ff7a90',
      cruce:    '#5ba8ff',
      positivo: '#87f29b',
    };

    const filtered = rawRows
      .filter(r => visibleIntervals.has(r.interval))
      .filter(r => visibleAntecedents.has(r.antecedent));

    if (filtered.length === 0) {
      setSankeyOption(null);
      setSankeyEmpty(true);
      return;
    }

    setSankeyEmpty(false);

    const antNodes = [...new Set(filtered.map(r => r.antecedent))].map(name => ({
      name, depth: 0,
    }));

    const consNodes = [...new Set(filtered.map(r => r.interval))].map(iv => ({
      name: `${selectedSymbol}||${iv}`,
      depth: 1,
      label: { show: true, formatter: () => `${selectedSymbol} (${iv})` },
      itemStyle: { color: colors[iv] },
    }));

    const linkMap = new Map<string, number>();
    filtered.forEach(r => {
      const key = `${r.antecedent}→${r.interval}`;
      linkMap.set(key, (linkMap.get(key) ?? 0) + r.count);
    });

    const links = [...linkMap.entries()].map(([key, value]) => {
      const [ant, iv] = key.split('→');
      return {
        source: ant,
        target: `${selectedSymbol}||${iv}`,
        value,
        lineStyle: { color: colors[iv] },
      };
    });

    setSankeyOption({
      tooltip: {
        trigger: 'item' as const,
        formatter: (params: any) => {
          if (params.dataType === 'edge') {
            return `${cleanName(params.data.source)} → ${cleanName(params.data.target)}<br/>Reglas: ${params.data.value}`;
          }
          return cleanName(params.name);
        },
      },
      series: [{
        type: 'sankey' as const,
        data: [...antNodes, ...consNodes],
        links,
        emphasis: {
          focus: 'adjacency',
          blurScope: 'global',
        },
        lineStyle: { opacity: 0.3 },
        label: { show: true, color: '#ccc', fontSize: 11 },
      }],
    });
  }, [rawRows, visibleIntervals, visibleAntecedents, selectedSymbol]);

  useEffect(() => {
    //Espera a que terminen ambas peticiones de reglas y activos
    Promise.all([fetchRules(), fetchAssets()])
      .then(([rulesData, assetsData]) => {
        setRules(rulesData);
        setAssets(assetsData);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);// No se repite, solo al montar el componente

  useEffect(() => { //Montaje de los datos de gráfica de precios semanales
    if (selectedSymbols.length === 0) {
      setWeeklyData([]);
      return;
    }
    setChartLoading(true);
    fetchWeeklyPrices(selectedSymbols, dateFrom || undefined, dateTo || undefined)
      .then(data => {
        setWeeklyData(data);
        setChartLoading(false);
      })
      .catch(err => {
        console.error(err);
        setChartLoading(false);
      });
  }, [selectedSymbols, dateFrom, dateTo]);

  // Es la función que añade o elimina simbolos en la gráfica
  const toggleSymbol = (symbol: string) => {
    setSelectedSymbols(prev => {
      if (prev.includes(symbol)) {
        return prev.filter(s => s !== symbol);
      }
      if (prev.length >= 5) return prev; //limite 5 para no saturar
      return [...prev, symbol];
    });
  };

  //Funcion que maneja el ordenamiento 
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sortedRules = useMemo(() => {
    const filtered = rules.filter(r => {
      if (!filterText) return true;
      const q = filterText.toLowerCase();
      return r.consequent.toLowerCase().includes(q);
    });

    return [...filtered].sort((a, b) => {
      const aVal = a[sortKey] ?? 0;
      const bVal = b[sortKey] ?? 0;
      if (typeof aVal === 'string') {
        return sortDir === 'asc'
          ? aVal.localeCompare(bVal as string)
          : (bVal as string).localeCompare(aVal);
      }
      return sortDir === 'asc'
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
  }, [rules, sortKey, sortDir, filterText]);

  const allAntecedents = useMemo(
    () => [...new Set(rawRows.map(r => r.antecedent))].sort(),
    [rawRows]
  );

  const chartOption = useMemo(() => {
    const symbols = [...new Set(weeklyData.map(d => d.symbol))].sort();
    const dates = [...new Set(weeklyData.map(d => d.week_start))].sort();

    const series = symbols.map(symbol => ({
      name: symbol,
      type: 'line' as const,
      data: dates.map(date => {
        const pt = weeklyData.find(d => d.symbol === symbol && d.week_start === date);
        return pt?.pct_change ?? null;
      }),
    }));

    return {
      tooltip: { trigger: 'axis' as const },
      legend: { data: symbols, textStyle: { color: '#ccc' } },
      grid: { left: 60, right: 20, top: 40, bottom: 40 },
      xAxis: {
        type: 'category' as const,
        data: dates,
        axisLabel: { color: '#999', fontSize: 10, rotate: 45 },
      },
      yAxis: {
        type: 'value' as const,
        axisLabel: { color: '#999', formatter: '{value}%' },
        splitLine: { lineStyle: { color: '#333' } },
      },
      series,
    };
  }, [weeklyData]);

  const sortArrow = (key: SortKey) => {
    if (sortKey !== key) return '';
    return sortDir === 'asc' ? ' ▲' : ' ▼';
  };

  // Render principal de la página
  if (loading) {
    return <main className="layout rules-layout"><div className="status">Cargando reglas...</div></main>;
  }

  if (error) {
    return <main className="layout rules-layout"><div className="status status-error">{error}</div></main>;
  }

  return (
    <main className="layout rules-layout">
      <div className="card rules-table-card">
        <h3 className="section-title">Reglas de Asociación ({sortedRules.length})</h3>
        <div className="controls compact-controls" style={{ marginBottom: 8 }}>
          <input
            type="text"
            placeholder="Filtrar reglas..."
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
            className="filter-input"
          />
        </div>
        <div className="rules-table-wrapper">
          <table className="rules-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('antecedent')}>
                  Antecedent{sortArrow('antecedent')}
                </th>
                <th>Mes</th>
                <th onClick={() => handleSort('consequent')}>
                  Consequent{sortArrow('consequent')}
                </th>
                <th onClick={() => handleSort('support')}>
                  Support{sortArrow('support')}
                </th>
                <th onClick={() => handleSort('confidence')}>
                  Confidence{sortArrow('confidence')}
                </th>
                <th onClick={() => handleSort('lift')}>
                  Lift{sortArrow('lift')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedRules.map(r => (
                <tr key={r.id}>
                  <td className="rule-cell" dangerouslySetInnerHTML={{ __html: formatConditions(r.antecedent) }} />
                  <td className="num-cell month-cell">{extractMonth(r.antecedent)}</td>
                  <td className="rule-cell" dangerouslySetInnerHTML={{ __html: formatConditions(r.consequent) }} />
                  <td className="num-cell">{r.support?.toFixed(2)}</td>
                  <td className="num-cell">{r.confidence?.toFixed(2)}</td>
                  <td className="num-cell">{r.lift?.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card rules-chart-card">
        <h3 className="section-title">Evolución semanal porcentual</h3>
        <div className="controls-row" style={{ marginBottom: 8, gap: 8 }}>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="filter-input" style={{ width: 160 }} />
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="filter-input" style={{ width: 160 }} />
        </div>
        <div className="symbol-selector">
          {assets.slice(0, 30).map(a => (
            <button
              key={a.symbol}
              className={`symbol-chip ${selectedSymbols.includes(a.symbol) ? 'active' : ''}`}
              onClick={() => toggleSymbol(a.symbol)}
              disabled={!selectedSymbols.includes(a.symbol) && selectedSymbols.length >= 5}
            >
              {a.symbol}
            </button>
          ))}
        </div>
        {chartLoading ? (
          <div className="status">Cargando datos...</div>
        ) : selectedSymbols.length === 0 ? (
          <div className="empty-state"><h3>Selecciona símbolos (máx 5)</h3></div>
        ) : (
          <ReactECharts option={chartOption} style={{ height: 300 }} />
        )}
      </div>

      <div className="card rules-force-card">
        <h3 className="section-title">Sankey por símbolo</h3>
        <div className="controls-row" style={{ marginBottom: 12, gap: 8 }}>
          <select
            value={selectedSymbol ?? ''}
            onChange={e => setSelectedSymbol(e.target.value || null)}
            className="filter-input"
            style={{ flex: 1 }}
          >
            <option value="">Seleccionar símbolo...</option>
            {availableSymbols.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
          {selectedSymbol ? (
            <>
              {sankeyEmpty ? (
                <div className="empty-state"><h3>Sin reglas para los filtros seleccionados</h3></div>
              ) : sankeyOption ? (
                <ReactECharts option={sankeyOption} style={{ height: 400 }} />
              ) : (
                <div className="empty-state"><h3>Cargando...</h3></div>
              )}
              <div className="sankey-legend">
                {['negativo', 'cruce', 'positivo'].map(t => (
                  <button
                    key={t}
                    className={`symbol-chip ${visibleIntervals.has(t) ? 'active' : ''}`}
                    onClick={() => setVisibleIntervals(prev => {
                      const next = new Set(prev);
                      if (next.has(t)) next.delete(t); else next.add(t);
                      return next;
                    })}
                    style={{ textTransform: 'capitalize' }}
                  >
                    {t}
                  </button>
                ))}
                <span style={{ color: '#999', fontSize: 12, marginLeft: 8 }}>
                  {['negativo', 'cruce', 'positivo'].filter(t => visibleIntervals.has(t)).length}/3
                </span>
              </div>
              <div className="sankey-legend" style={{ maxHeight: 200, overflowY: 'auto', flexWrap: 'wrap', gap: 6 }}>
                {allAntecedents.map(ant => (
                  <button
                    key={ant}
                    className={`symbol-chip ${visibleAntecedents.has(ant) ? 'active' : ''}`}
                    onClick={() => setVisibleAntecedents(prev => {
                      const next = new Set(prev);
                      if (next.has(ant)) next.delete(ant); else next.add(ant);
                      return next;
                    })}
                  >
                    {ant}
                  </button>
                ))}
                <span style={{ color: '#999', fontSize: 12, marginLeft: 8 }}>
                  {visibleAntecedents.size}/{allAntecedents.length}
                </span>
              </div>
            </>
          ) : (
            <div className="empty-state"><h3>Elige un símbolo consecuente</h3></div>
          )}
      </div>
    </main>
  );
}

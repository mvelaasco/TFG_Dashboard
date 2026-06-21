import { useEffect, useMemo, useState } from 'react';

import { Asset, fetchAssets, fetchNews, NewsItem } from '../api';

type Status = {
  kind: 'idle' | 'loading' | 'success' | 'error';
  message: string;
};

const DEFAULT_DATE = new Date().toISOString().slice(0, 10);
const MIN_NEWS_DATE = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

function uniqueSources(items: NewsItem[]) {
  return Array.from(new Set(items.map((item) => item.source).filter(Boolean))).length;
}

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

export default function NewsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [symbol, setSymbol] = useState('');
  const [date, setDate] = useState(DEFAULT_DATE);
  const [status, setStatus] = useState<Status>({ kind: 'idle', message: 'Listo para consultar noticias.' });
  const [items, setItems] = useState<NewsItem[]>([]);
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    void loadAssets();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const querySymbol = params.get('symbol');
    const queryDate = params.get('date');

    if (querySymbol) {
      setSymbol(querySymbol.toUpperCase());
    }

    if (queryDate) {
      setDate(queryDate);
    }

    if (querySymbol && queryDate) {
      void handleLoadNews(querySymbol.toUpperCase(), queryDate);
    }
  }, []);

  async function loadAssets() {
    try {
      const data = await fetchAssets();
      setAssets(data);
    } catch (error) {
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Error cargando activos.' });
    }
  }

  async function handleLoadNews(nextSymbol?: string, nextDate?: string) {
    const resolvedSymbol = (nextSymbol ?? symbol).toUpperCase();
    const resolvedDate = nextDate ?? date;
    const yearAgo = new Date();
    yearAgo.setFullYear(yearAgo.getFullYear() - 1);
    if (new Date(resolvedDate) < yearAgo) {
      setStatus({ kind: 'error', message: 'La fecha debe estar dentro del último año.' });
      return;
    }
    try {
      setIsBusy(true);
      setStatus({ kind: 'loading', message: 'Buscando noticias...' });
      const data = await fetchNews({ symbol: resolvedSymbol, date: resolvedDate });
      setItems(data);
      setStatus({
        kind: 'success',
        message: data.length ? `Noticias cargadas para ${resolvedSymbol}.` : 'No hay noticias para ese día.',
      });
    } catch (error) {
      setItems([]);
      setStatus({ kind: 'error', message: error instanceof Error ? error.message : 'Error consultando noticias.' });
    } finally {
      setIsBusy(false);
    }
  }

  const assetSymbols = useMemo(() => assets.map((asset) => asset.symbol).sort(), [assets]);
  const latestNewsTime = items.length ? items[0].datetime : null;

  return (
    <main className="layout news-layout">
      <section className="card controls compact-controls">
        <div className="controls-row">
          <label>
            <span>Símbolo</span>
            <input list="news-symbols" value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} />
          </label>
          <label>
            <span>Fecha</span>
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} min={MIN_NEWS_DATE} />
          </label>
          <div className="controls-actions">
            <button type="button" className="primary" onClick={() => void handleLoadNews()} disabled={isBusy}>
              Ver noticias
            </button>
          </div>
        </div>

        <datalist id="news-symbols">
          {assetSymbols.map((value) => (
            <option key={value} value={value} />
          ))}
        </datalist>
      </section>

      <div className="stat-grid">
        <article>
          <span>Titulares</span>
          <strong>{items.length}</strong>
        </article>
        <article>
          <span>Fuentes</span>
          <strong>{uniqueSources(items)}</strong>
        </article>
        <article>
          <span>Último timestamp</span>
          <strong>{latestNewsTime ? formatTime(latestNewsTime) : '—'}</strong>
        </article>
        <article>
          <span>Símbolo</span>
          <strong>{symbol.toUpperCase()}</strong>
        </article>
      </div>

      <div className={`status status-${status.kind}`}>
        <span className="status-dot" />
        <span>{status.message}</span>
      </div>

      <section className="card list-card">
        <div className="news-list">
          {items.map((item) => (
            <article key={`${item.symbol}-${item.datetime}-${item.url ?? ''}`} className="news-row">
              <div>
                <strong className="news-headline">{item.headline}</strong>
                <div className="news-meta">
                  <span>{formatTime(item.datetime)}</span>
                  {item.source && <span>{item.source}</span>}
                </div>
                {item.summary && <p className="news-summary">{item.summary}</p>}
              </div>
              {item.url && (
                <a className="news-link" href={item.url} target="_blank" rel="noreferrer">
                  Abrir
                </a>
              )}
            </article>
          ))}
          {!items.length && <p className="empty-inline">No hay noticias cargadas aún.</p>}
        </div>
      </section>
    </main>
  );
}

import { useEffect, useState } from 'react';
import {
  fetchAssets,
  addAsset,
  enqueueIngestion,
  type Asset,
} from '../api';
import DataQualityPage from './DataQualityPage';

export default function PremiumPage() {
  const [activeTab, setActiveTab] = useState<'assets' | 'dataquality'>('assets');

  return (
    <main className="layout" style={{ gridTemplateColumns: '1fr', gridTemplateAreas: "'main'" }}>
      <section className="card" style={{ gridArea: 'main', padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', borderBottom: '1px solid var(--card-border)' }}>
          {([
            { key: 'assets', label: 'Activos' },
            { key: 'dataquality', label: 'Calidad de Datos' },
          ] as const).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                flex: 1,
                padding: '16px 12px',
                borderRadius: 0,
                background: activeTab === tab.key ? 'rgba(125,226,209,0.1)' : 'transparent',
                color: activeTab === tab.key ? 'var(--accent)' : 'var(--muted)',
                fontWeight: activeTab === tab.key ? 700 : 400,
                borderBottom: activeTab === tab.key ? '2px solid var(--accent)' : '2px solid transparent',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="admin-container" style={{ padding: 24 }}>
          {activeTab === 'assets' && <AssetsTab />}
          {activeTab === 'dataquality' && <DataQualityPage />}
        </div>
      </section>
    </main>
  );
}

/*function IngestTab() {
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleIngest() {
    setLoading(true);
    setStatus(null);
    try {
      const result = await adminRequest<{ message: string }>('/admin/ingest', { method: 'POST' }).catch(() => null);
      if (result) {
        setStatus(`✅ ${result.message}`);
      } else {
        const result2 = await adminRequest<{ metrics_inserted: number }>('/metrics/correlations', {
          method: 'POST',
          body: JSON.stringify({}),
        });
        setStatus(`✅ Correlaciones calculadas: ${result2.metrics_inserted} métricas`);
      }
    } catch (err) {
      setStatus(`❌ ${err instanceof Error ? err.message : 'Error'}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Ingesta de datos</h2>
      <p style={{ color: 'var(--muted)', marginBottom: 20, lineHeight: 1.6 }}>
        Ejecuta la ingesta de precios desde las APIs externas (Tiingo, Finnhub)
        y recalcula las métricas de correlación.
      </p>
      <button className="primary" onClick={handleIngest} disabled={loading}>
        {loading ? 'Ingestando…' : 'Ejecutar ingesta'}
      </button>
      {status && (
        <p style={{ marginTop: 16, padding: 12, borderRadius: 12, background: 'rgba(255,255,255,0.04)' }}>
          {status}
        </p>
      )}
    </div>
  );
}*/

function AssetsTab() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newSymbol, setNewSymbol] = useState('');
  const [newName, setName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => { loadAssets(); }, []);

  async function loadAssets() {
    try {
      setLoading(true);
      const data = await fetchAssets();
      setAssets(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error');
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd() {
    if (!newSymbol || !newName) return;
    try {
      const asset = await addAsset({ symbol: newSymbol, name: newName });
      await enqueueIngestion({ symbol: asset.symbol, asset_type: asset.asset_type });
      setNewSymbol('');
      setName('');
      await loadAssets();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error');
    }
  }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Gestión de activos</h2>

      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap', alignItems: 'end' }}>
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--muted)', textTransform: 'uppercase' }}>Símbolo</span>
          <input value={newSymbol} onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
            style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(4,8,18,0.8)', color: 'var(--text)' }} />
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--muted)', textTransform: 'uppercase' }}>Nombre</span>
          <input value={newName} onChange={(e) => setName(e.target.value)}
            style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(4,8,18,0.8)', color: 'var(--text)' }} />
        </label>
        <button onClick={handleAdd} className="primary" style={{ padding: '8px 14px' }}>Añadir</button>
      </div>

      <input
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        placeholder="Buscar por símbolo o nombre…"
        style={{
          width: '100%', marginBottom: 16, padding: '8px 10px', borderRadius: 10,
          border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(4,8,18,0.8)', color: 'var(--text)',
        }}
      />

      {error && <p style={{ color: 'var(--danger)', marginBottom: 12 }}>{error}</p>}

      {loading ? (
        <p style={{ color: 'var(--muted)' }}>Cargando activos…</p>
      ) : (
        <div className="asset-list">
          {assets.filter((a) => {
            if (!searchQuery) return true;
            const q = searchQuery.toLowerCase();
            return a.symbol.toLowerCase().includes(q) || a.name.toLowerCase().includes(q);
          }).map((a) => (
            <div key={a.symbol} className="asset-row" style={{ alignItems: 'center' }}>
              <div>
                <strong>{a.symbol}</strong>
                <span>{a.name}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}




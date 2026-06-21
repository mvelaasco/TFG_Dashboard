import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import type { Asset } from '../api';

type AssetPickerProps = {
  value: string;
  onChange: (symbol: string) => void;
  assets: Asset[];
  label?: string;
};

// Archivo que gestiona la implementación del selector de activos con busqueda integrada
export default function AssetPicker({ value, onChange, assets, label }: AssetPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [dropdownPos, setDropdownPos] = useState<{
    top: number; left: number; width: number;
  } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const portalRef = useRef<HTMLDivElement>(null);

  const selectedAsset = useMemo(
    () => assets.find(a => a.symbol === value),
    [assets, value],
  );

  const filtered = useMemo(() => {
    if (!search.trim()) return assets;
    const q = search.toLowerCase();
    return assets.filter(
      a => a.symbol.toLowerCase().includes(q) || a.name.toLowerCase().includes(q),
    );
  }, [assets, search]);

  const recalcPosition = useCallback(() => {
    if (inputRef.current) {
      const rect = inputRef.current.getBoundingClientRect();
      setDropdownPos({
        top: rect.bottom + 4,
        left: rect.left,
        width: rect.width,
      });
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      setHighlightedIndex(0);
      recalcPosition();
    }
  }, [isOpen, search, recalcPosition]);

  useEffect(() => {
    if (!isOpen) {
      setDropdownPos(null);
      return;
    }

    function onScroll(e: Event) {
      if (portalRef.current && portalRef.current.contains(e.target as Node)) {
        return;
      }
      setIsOpen(false);
    }
    window.addEventListener('scroll', onScroll, true);
    return () => window.removeEventListener('scroll', onScroll, true);
  }, [isOpen]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      if (
        containerRef.current &&
        !containerRef.current.contains(target) &&
        portalRef.current &&
        !portalRef.current.contains(target)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  function handleSelect(symbol: string) {
    onChange(symbol);
    setSearch('');
    setIsOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setIsOpen(true);
        setSearch('');
        e.preventDefault();
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (filtered.length === 0) break;
        setHighlightedIndex(prev => Math.min(prev + 1, filtered.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (filtered.length === 0) break;
        setHighlightedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filtered.length > 0 && filtered[highlightedIndex]) {
          handleSelect(filtered[highlightedIndex].symbol);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        break;
    }
  }

  return (
    <div ref={containerRef} style={{ minWidth: 0 }}>
      {label && (
        <span style={{
          fontSize: '0.75rem',
          color: 'var(--muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          display: 'block',
          marginBottom: 4,
        }}>
          {label}
        </span>
      )}
      <input
        ref={inputRef}
        type="text"
        className="filter-input"
        placeholder={selectedAsset ? `${value} – ${selectedAsset.name}` : 'Buscar activo...'}
        value={isOpen ? search : `${value} – ${selectedAsset?.name ?? value}`}
        onChange={e => { setSearch(e.target.value); setIsOpen(true); }}
        onFocus={() => { setIsOpen(true); setSearch(''); }}
        onKeyDown={handleKeyDown}
        style={{ width: '100%' }}
      />
      {isOpen && dropdownPos && createPortal(
        <div ref={portalRef} style={{
          position: 'fixed',
          top: dropdownPos.top,
          left: dropdownPos.left,
          width: dropdownPos.width,
          zIndex: 9999,
          borderRadius: 12,
          border: '1px solid var(--card-border)',
          background: 'var(--bg-alt)',
          maxHeight: 220,
          overflowY: 'auto',
          boxShadow: 'var(--shadow)',
        }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '12px 14px', color: 'var(--muted)', fontSize: '0.85rem' }}>
              Sin resultados
            </div>
          ) : (
            filtered.map((asset, i) => (
              <div
                key={asset.id}
                onClick={() => handleSelect(asset.symbol)}
                onMouseEnter={() => setHighlightedIndex(i)}
                style={{
                  padding: '8px 14px',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  alignItems: 'center',
                  background: i === highlightedIndex ? 'rgba(125,226,209,0.12)' : 'transparent',
                  color: i === highlightedIndex ? 'var(--text)' : 'var(--muted)',
                  borderBottom: i < filtered.length - 1 ? '1px solid rgba(166,189,255,0.06)' : 'none',
                  transition: 'background 0.1s ease',
                }}
              >
                <strong style={{
                  color: 'var(--text)',
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: '0.85rem',
                  whiteSpace: 'nowrap',
                }}>
                  {asset.symbol}
                </strong>
                <span style={{
                  fontSize: '0.85rem',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  textAlign: 'right',
                }}>
                  {asset.name}
                </span>
              </div>
            ))
          )}
        </div>,
        document.body
      )}
    </div>
  );
}

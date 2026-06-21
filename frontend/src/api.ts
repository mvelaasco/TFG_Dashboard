export type Asset = {
  id: number;
  symbol: string;
  name: string;
  asset_type?: string | null;
};

export type CorrelationPoint = {
  time: string;
  value: string;
};

export type CorrelationSeriesResponse = {
  base_symbol: string;
  risk_symbol: string;
  window_days: number;
  series: CorrelationPoint[];
};

export type CorrelationBuildResponse = {
  metrics_inserted: number;
  pairs_processed: number;
  missing_risk_symbols: string[];
};

export type CoverageGap = {
  start: string;
  end: string;
  days: number;
};

export type CoverageItem = {
  symbol: string;
  expected_days: number;
  available_days: number;
  coverage_pct: number;
  missing_days: number;
  first_date: string;
  last_date: string;
  freshness_lag_days: number;
  record_count: number;
  gaps: CoverageGap[];
};

export type CoverageSummary = {
  symbols_count: number;
  coverage_pct_avg: number;
  symbols_below_threshold: number;
  threshold_pct: number;
};

export type CoverageResponse = {
  summary: CoverageSummary;
  items: CoverageItem[];
};

export type CoverageCalendarDay = {
  date: string;
  actual_count: number;
  expected_count: number;
  is_weekend: boolean;
};

export type CoverageCalendarResponse = {
  from_date: string;
  to_date: string;
  total_assets: number;
  days: CoverageCalendarDay[];
};

export type NewsItem = {
  id: number | null;
  symbol: string;
  date: string;
  datetime: string;
  headline: string;
  source: string | null;
  url: string | null;
  summary: string | null;
};

export type PriceData = {
  time: string;
  close: string;
};

export type UserInfo = {
  id: number;
  email: string;
  username: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string | null;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
};

const DEFAULT_API_BASE = 'http://localhost:8000';
export const TOKEN_KEY = 'tfg_auth_token';

function getApiBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE;
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchAssets() {
  return requestJson<Asset[]>('/assets');
}

export async function buildCorrelations(payload: {
  from_date?: string | null;
  to_date?: string | null;
}) {
  return requestJson<CorrelationBuildResponse>('/metrics/correlations', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export type CorrelatePairResponse = {
  metrics_inserted: number;
  pairs_processed: number;
};

export async function correlatePair(payload: {
  base_symbol: string;
  target_symbol: string;
  from_date?: string | null;
  to_date?: string | null;
}) {
  return requestJson<CorrelatePairResponse>('/metrics/correlate-pair', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchCorrelations(params: {
  baseSymbol: string;
  riskSymbol: string;
  windowDays: 30 | 90;
  fromDate?: string;
  toDate?: string;
}) {
  const searchParams = new URLSearchParams({
    base_symbol: params.baseSymbol,
    risk_symbol: params.riskSymbol,
    window_days: String(params.windowDays),
  });

  if (params.fromDate) {
    searchParams.set('from_date', params.fromDate);
  }

  if (params.toDate) {
    searchParams.set('to_date', params.toDate);
  }

  return requestJson<CorrelationSeriesResponse>(`/metrics/correlations?${searchParams.toString()}`);
}

export async function fetchCoverage(params?: { symbols?: string[]; minGapDays?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.symbols?.length) {
    searchParams.set('symbols', params.symbols.join(','));
  }
  if (params?.minGapDays) {
    searchParams.set('min_gap_days', String(params.minGapDays));
  }

  const query = searchParams.toString();
  return requestJson<CoverageResponse>(`/metrics/coverage${query ? `?${query}` : ''}`);
}

export async function fetchCoverageCalendar(fromDate: string, toDate: string) {
  const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  return requestJson<CoverageCalendarResponse>(`/metrics/coverage-calendar?${params.toString()}`);
}

export async function fetchNews(params: { symbol: string; date: string }) {
  const searchParams = new URLSearchParams({ date: params.date });
  return requestJson<NewsItem[]>(`/assets/${params.symbol}/news?${searchParams.toString()}`);
}

export async function fetchAssetPrices(symbol: string, fromDate?: string, toDate?: string) {
  const params = new URLSearchParams();
  if (fromDate) params.set('from_date', fromDate);
  if (toDate) params.set('to_date', toDate);
  const query = params.toString();
  return requestJson<PriceData[]>(`/assets/${symbol}/prices${query ? `?${query}` : ''}`);
}

export async function loginApi(email: string, password: string) {
  return requestJson<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchMe() {
  return requestJson<UserInfo>('/auth/me');
}

export type VolatilityPoint = {
  time: string;
  value: string;
};

export type VolatilityResponse = {
  symbol: string;
  window_days: number;
  series: VolatilityPoint[];
};

export type CorrelationMatrixResponse = {
  symbols: string[];
  matrix: number[][];
};

export async function fetchCorrelationMatrix(params?: {
  topN?: number;
  fromDate?: string;
  toDate?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.topN) searchParams.set('top_n', String(params.topN));
  if (params?.fromDate) searchParams.set('from_date', params.fromDate);
  if (params?.toDate) searchParams.set('to_date', params.toDate);
  const query = searchParams.toString();
  return requestJson<CorrelationMatrixResponse>(`/metrics/correlation-matrix${query ? `?${query}` : ''}`);
}

export async function fetchVolatility(params: {
  symbol: string;
  windowDays: number;
  fromDate?: string;
  toDate?: string;
}) {
  const searchParams = new URLSearchParams({
    symbol: params.symbol,
    window_days: String(params.windowDays),
  });
  if (params.fromDate) searchParams.set('from_date', params.fromDate);
  if (params.toDate) searchParams.set('to_date', params.toDate);
  return requestJson<VolatilityResponse>(`/metrics/volatility?${searchParams.toString()}`);
}

export type Rule = {
  id: number;
  antecedent: string;
  consequent: string;
  support: number | null;
  confidence: number | null;
  lift: number | null;
  netconf: number | null;
  coverage: number | null;
  amplitude: number | null;
};

export async function fetchRules() {
  return requestJson<Rule[]>('/rules');
}

export type WeeklyPricePoint = {
  week_start: string;
  symbol: string;
  pct_change: number | null;
};

export async function fetchWeeklyPrices(symbols: string[], fromDate?: string, toDate?: string) {
  const params = new URLSearchParams();
  params.set('symbols', symbols.join(','));
  if (fromDate) params.set('from_date', fromDate);
  if (toDate) params.set('to_date', toDate);
  return requestJson<WeeklyPricePoint[]>(`/rules/weekly-prices?${params.toString()}`);
}

export type AddAssetPayload = { symbol: string; name: string };
export type AddAssetResponse = { symbol: string; asset_type: string };
export type EnqueuePayload = { symbol: string; asset_type: string };
export type EnqueueResponse = { message: string };

export async function addAsset(payload: AddAssetPayload) {
  return requestJson<AddAssetResponse>('/admin/assets', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function enqueueIngestion(payload: EnqueuePayload) {
  return requestJson<EnqueueResponse>('/admin/enqueue', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

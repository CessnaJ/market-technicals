// 데이터 타입 정의

export interface OHLCV {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface IndicatorData {
  date: string;
  value: number;
}

export interface MACDData extends IndicatorData {
  signal: number;
  histogram: number;
}

export interface BollingerData extends IndicatorData {
  upper: number;
  middle: number;
  lower: number;
}

export interface RSIData extends IndicatorData {}

export interface VPCIData extends IndicatorData {
  vpc: number;
  vpr: number;
  vm: number;
  signal: 'CONFIRM_BULL' | 'CONFIRM_BEAR' | 'DIVERGE_BULL' | 'DIVERGE_BEAR';
}

export interface DarvasBox {
  start_date: string;
  end_date: string | null;
  top: number;
  bottom: number;
  status: 'FORMING' | 'ACTIVE' | 'BROKEN_UP' | 'BROKEN_DOWN';
}

export interface FibonacciLevel {
  level: string;
  price: number;
  strength?: number;
}

export interface FibonacciData {
  mode?: 'auto' | 'manual';
  trend?: 'UP' | 'DOWN';
  swing_low: number;
  swing_high: number;
  levels: Record<string, number>;
  extensions?: Record<string, number>;
}

export interface StageDescription {
  label: string;
  title: string;
  summary: string;
  checklist: string[];
}

export interface StageHistoryPoint {
  date: string;
  stage: number;
  stage_label: string;
  close: number;
  ma_30w: number | null;
  slope: 'RISING' | 'FALLING' | 'FLAT' | null;
  slope_pct: number | null;
  distance_to_ma: number | null;
  mansfield_rs: number | null;
}

export interface StageTransition {
  date: string;
  from_stage: number;
  to_stage: number;
  label: string;
}

export interface WeinsteinData {
  ticker?: string;
  current_stage: number;
  stage_label: string;
  ma_30w: number | null;
  mansfield_rs: number | null;
  benchmark_ticker?: string | null;
  benchmark_name?: string | null;
  description?: StageDescription;
  stage_history?: StageHistoryPoint[];
  transitions?: StageTransition[];
}

export interface Signal {
  signal_type: string;
  signal_date: string;
  direction: 'BULLISH' | 'BEARISH' | 'WARNING';
  strength: number | null;
  details: any;
}

export interface FinancialMetrics {
  ticker: string;
  name: string;
  period_date: string | null;
  psr?: number | null;
  per?: number | null;
  pbr?: number | null;
  roe?: number | null;
  debt_ratio?: number | null;
  market_cap?: number | null;
}

export interface RelativeStrengthPoint {
  date: string;
  stock_performance: number;
  benchmark_performance: number;
  relative_spread: number;
  relative_ratio: number;
  mansfield_rs: number | null;
}

export interface RelativeStrengthData {
  ticker: string;
  benchmark_ticker: string;
  benchmark_name: string;
  timeframe: 'daily' | 'weekly' | 'monthly';
  current_relative_return: number;
  current_mansfield_rs: number | null;
  series: RelativeStrengthPoint[];
}

export interface StockSearchSuggestion {
  ticker: string;
  name: string;
  market: string | null;
  sector: string | null;
  industry: string | null;
  match_type:
    | 'ticker_exact'
    | 'ticker_prefix'
    | 'name_exact'
    | 'name_prefix'
    | 'name_contains'
    | 'initials_prefix'
    | 'initials_contains';
}

export interface StockSearchResponse {
  master_ready: boolean;
  suggestions: StockSearchSuggestion[];
}

export interface StockTheme {
  code: string;
  name: string;
}

export interface RelatedThemeGroup {
  theme_code: string;
  theme_name: string;
  stocks: StockSearchSuggestion[];
}

export interface StockProfileResponse {
  ticker: string;
  name: string;
  market: string | null;
  sector: string | null;
  industry: string | null;
  themes: StockTheme[];
  related_by_sector: StockSearchSuggestion[];
  related_by_theme: RelatedThemeGroup[];
}

export interface SmaConfig {
  id: string;
  visible: boolean;
  period: number;
  color: string;
  lineWidth: 1 | 2 | 3 | 4;
}

export type CollapsedHeaderState = 'collapsed' | 'expanded';

export interface ChartHoverSnapshot {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  changePct: number | null;
  sma: Record<string, number | null>;
  bollinger?: {
    upper: number | null;
    middle: number | null;
    lower: number | null;
  };
  rsi?: number | null;
  macd?: {
    value: number | null;
    signal: number | null;
    histogram: number | null;
  };
  vpci?: {
    value: number | null;
    signal?: string;
  };
  stage?: {
    stage: number;
    label: string;
    ma30w: number | null;
    mansfield: number | null;
  } | null;
  rs?: {
    stock: number;
    benchmark: number;
    ratio: number;
    mansfield: number | null;
  } | null;
}

export interface ChartHistoryMetadata {
  oldest_date: string | null;
  newest_date: string | null;
  has_more_before: boolean;
  loaded_count: number;
}

export interface ChartDataResponse {
  ticker: string;
  name: string;
  timeframe: string;
  scale: string;
  ohlcv: OHLCV[];
  history: ChartHistoryMetadata;
  indicators: {
    sma?: Record<string, IndicatorData[]>;
    macd?: MACDData[];
    rsi?: RSIData[];
    bollinger?: BollingerData[];
    vpci?: VPCIData[];
  };
}

export interface WatchlistItem {
  id: number;
  ticker: string;
  name: string;
  memo: string | null;
  priority: number;
  added_at: string;
}

// 색상 팔레트
export const COLORS = {
  background: '#111827',      // gray-900
  panel: '#1f2937',          // gray-800
  text: '#ffffff',            // white
  textMuted: '#9ca3af',     // gray-400
  bullish: '#22c55e',        // green-500
  bearish: '#ef4444',       // red-500
  warning: '#f59e0b',        // amber-500
  stage1: '#8b5cf6',        // violet-500
  stage2: '#16a34a',        // emerald-600
  stage3: '#ea580c',        // orange-500
  stage4: '#dc2626',        // red-600
  candleUp: '#22c55e',       // green
  candleDown: '#ef4444',     // red
  volumeHigh: '#f59e0b',     // amber
  volumeNormal: '#6b7280',   // gray-500
  fibonacciLine: '#f59e0b',  // amber
  fibonacciStrong: '#ef4444', // red (confluence)
  darvasBox: 'rgba(139, 92, 246, 0.2)', // violet with opacity
  darvasBorder: '#8b5cf6',   // violet
} as const;

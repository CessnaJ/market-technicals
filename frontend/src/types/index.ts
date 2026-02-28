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
  swing_low: number;
  swing_high: number;
  levels: Record<string, number>;
}

export interface WeinsteinData {
  current_stage: number;
  stage_label: string;
  ma_30w: number;
  mansfield_rs: number;
}

export interface Signal {
  id: number;
  signal_type: string;
  signal_date: string;
  direction: 'BULLISH' | 'BEARISH' | 'WARNING';
  strength: number | null;
  is_false_signal: boolean | null;
  details: any;
}

export interface FinancialMetrics {
  ticker: string;
  name: string;
  psr?: number;
  per?: number;
  pbr?: number;
  roe?: number;
  debt_ratio?: number;
  market_cap?: number;
}

export interface ChartDataResponse {
  ticker: string;
  name: string;
  timeframe: string;
  scale: string;
  ohlcv: OHLCV[];
  indicators: {
    sma?: Record<string, IndicatorData[]>;
    macd?: MACDData[];
    rsi?: RSIData[];
    bollinger?: BollingerData[];
    vpci?: VPCIData[];
  };
  weinstein?: WeinsteinData;
  darvas_boxes?: DarvasBox[];
  fibonacci?: FibonacciData;
  signals?: Signal[];
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

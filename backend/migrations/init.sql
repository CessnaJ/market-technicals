-- ============================
-- Technical Analysis Dashboard
-- Database Initialization Script
-- ============================

-- ============================
-- 종목 기본 정보
-- ============================
CREATE TABLE IF NOT EXISTS stocks (
    id          SERIAL PRIMARY KEY,
    ticker      VARCHAR(20) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    market      VARCHAR(20),
    sector      VARCHAR(100),
    industry    VARCHAR(100),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stocks_ticker ON stocks(ticker);
CREATE INDEX IF NOT EXISTS idx_stocks_market ON stocks(market);

-- ============================
-- 일봉 OHLCV
-- ============================
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    id          BIGSERIAL PRIMARY KEY,
    stock_id    INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    date        DATE NOT NULL,
    open        NUMERIC(18, 2) NOT NULL,
    high        NUMERIC(18, 2) NOT NULL,
    low         NUMERIC(18, 2) NOT NULL,
    close       NUMERIC(18, 2) NOT NULL,
    volume      BIGINT NOT NULL,
    adj_close   NUMERIC(18, 2),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (stock_id, date)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_daily_stock_date ON ohlcv_daily(stock_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_daily_date ON ohlcv_daily(date DESC);

-- ============================
-- 주봉 OHLCV (일봉에서 계산하여 저장)
-- ============================
CREATE TABLE IF NOT EXISTS ohlcv_weekly (
    id            BIGSERIAL PRIMARY KEY,
    stock_id      INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    week_start    DATE NOT NULL,
    open          NUMERIC(18, 2) NOT NULL,
    high          NUMERIC(18, 2) NOT NULL,
    low           NUMERIC(18, 2) NOT NULL,
    close         NUMERIC(18, 2) NOT NULL,
    volume        BIGINT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (stock_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_weekly_stock_date ON ohlcv_weekly(stock_id, week_start DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_weekly_date ON ohlcv_weekly(week_start DESC);

-- ============================
-- 재무 데이터
-- ============================
CREATE TABLE IF NOT EXISTS financial_data (
    id                  SERIAL PRIMARY KEY,
    stock_id            INTEGER NOT NULL REFERENCES stocks(id),
    period_type         VARCHAR(10) NOT NULL,
    period_date         DATE NOT NULL,
    revenue             NUMERIC(24, 0),
    operating_income    NUMERIC(24, 0),
    net_income          NUMERIC(24, 0),
    total_assets        NUMERIC(24, 0),
    total_equity        NUMERIC(24, 0),
    shares_outstanding  BIGINT,
    market_cap          NUMERIC(24, 0),
    psr                 NUMERIC(10, 4),
    per                 NUMERIC(10, 4),
    pbr                 NUMERIC(10, 4),
    roe                 NUMERIC(10, 4),
    debt_ratio          NUMERIC(10, 4),
    fetched_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (stock_id, period_type, period_date)
);

CREATE INDEX IF NOT EXISTS idx_financial_data_stock ON financial_data(stock_id);
CREATE INDEX IF NOT EXISTS idx_financial_data_period ON financial_data(period_date DESC);

-- ============================
-- 관심종목 (Watchlist)
-- ============================
CREATE TABLE IF NOT EXISTS watchlist (
    id          SERIAL PRIMARY KEY,
    ticker      VARCHAR(20) NOT NULL,
    name        VARCHAR(100),
    memo        TEXT,
    priority    INTEGER DEFAULT 0,
    added_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON watchlist(ticker);

-- ============================
-- 지표 계산 캐시
-- ============================
CREATE TABLE IF NOT EXISTS indicator_cache (
    id              BIGSERIAL PRIMARY KEY,
    stock_id        INTEGER NOT NULL REFERENCES stocks(id),
    indicator_name  VARCHAR(50) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    parameters      JSONB NOT NULL DEFAULT '{}',
    date            DATE NOT NULL,
    value           JSONB NOT NULL,
    computed_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (stock_id, indicator_name, timeframe, parameters, date)
);

CREATE INDEX IF NOT EXISTS idx_indicator_cache_lookup
    ON indicator_cache(stock_id, indicator_name, timeframe, date DESC);

-- ============================
-- 시그널 로그
-- ============================
CREATE TABLE IF NOT EXISTS signals (
    id              BIGSERIAL PRIMARY KEY,
    stock_id        INTEGER NOT NULL REFERENCES stocks(id),
    signal_type     VARCHAR(50) NOT NULL,
    signal_date     DATE NOT NULL,
    direction       VARCHAR(10) NOT NULL,
    strength        NUMERIC(5, 2),
    is_false_signal BOOLEAN,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_stock ON signals(stock_id);
CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(signal_date DESC);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);

-- ============================
-- Insert benchmark ticker (KOSPI)
-- ============================
INSERT INTO stocks (ticker, name, market, is_active)
VALUES ('0001', 'KOSPI 지수', 'INDEX', TRUE)
ON CONFLICT (ticker) DO NOTHING;

-- ============================
-- Create function for updated_at timestamp
-- ============================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_stocks_updated_at BEFORE UPDATE ON stocks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE asset_types (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO asset_types (name) VALUES
    ('stock'), ('etf'), ('crypto'), ('index'), ('fx');

CREATE TABLE assets (
    id            SERIAL PRIMARY KEY,
    symbol        VARCHAR(20)  NOT NULL UNIQUE,
    name          VARCHAR(200) NOT NULL,
    asset_type_id INTEGER      REFERENCES asset_types(id),
    currency      VARCHAR(10)  NOT NULL DEFAULT 'USD',
    exchange      VARCHAR(50),
    timezone      VARCHAR(50)  NOT NULL DEFAULT 'America/New_York'
);

CREATE INDEX idx_assets_symbol ON assets(symbol);

CREATE TABLE asset_prices (
    time     TIMESTAMPTZ    NOT NULL,
    asset_id INTEGER        NOT NULL REFERENCES assets(id),
    open     NUMERIC(18, 6),
    high     NUMERIC(18, 6),
    low      NUMERIC(18, 6),
    close    NUMERIC(18, 6) NOT NULL,
    volume   BIGINT
);

SELECT create_hypertable('asset_prices', 'time',
    chunk_time_interval => INTERVAL '1 month');

CREATE INDEX idx_prices_asset_time
    ON asset_prices (asset_id, time DESC);

CREATE TABLE analytical_metrics (
    time                TIMESTAMPTZ    NOT NULL,
    base_asset_id       INTEGER        NOT NULL REFERENCES assets(id),
    comparison_asset_id INTEGER        REFERENCES assets(id),
    metric_name         VARCHAR(50)    NOT NULL,
    window_days         INTEGER        NOT NULL,
    metric_value        NUMERIC(18, 8) NOT NULL,
    calculated_at       TIMESTAMPTZ    DEFAULT NOW()
);

SELECT create_hypertable('analytical_metrics', 'time',
    chunk_time_interval => INTERVAL '1 month');

CREATE INDEX idx_metrics_lookup
    ON analytical_metrics (base_asset_id, metric_name, window_days, time DESC);

CREATE TABLE IF NOT EXISTS historical_news (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20)  NOT NULL,
    date        DATE         NOT NULL,
    datetime    TIMESTAMPTZ  NOT NULL,
    headline    TEXT         NOT NULL,
    source      VARCHAR(100),
    url         TEXT,
    summary     TEXT,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_symbol_date
    ON historical_news (symbol, date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_news_symbol_datetime_url
    ON historical_news (symbol, datetime, url);

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    username        VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS association_rules (
    id              SERIAL PRIMARY KEY,
    antecedent      TEXT           NOT NULL,
    consequent      TEXT           NOT NULL,
    support         NUMERIC(18, 8),
    confidence      NUMERIC(18, 8),
    lift            NUMERIC(18, 8),
    coverage        NUMERIC(18, 8),
    amplitude       NUMERIC(18, 8),
    netconf         NUMERIC(18, 8)
);

CREATE TABLE IF NOT EXISTS weekly_prices (
    symbol      VARCHAR(20)    NOT NULL,
    week_number INTEGER        NOT NULL,
    week_start  DATE           NOT NULL,
    close       NUMERIC(18, 6) NOT NULL,
    pct_change  NUMERIC(18, 6),
    PRIMARY KEY (symbol, week_number)
);

INSERT INTO users (email, username, hashed_password, is_admin)
VALUES (
    'admin@tfg.com',
    'admin',
    '$2b$12$D1ZAfFdnXZpD8RLDR9HJoevF096q5oQlPaENSLh58/VNyKhCJKZpK',
    TRUE
) ON CONFLICT (email) DO NOTHING;

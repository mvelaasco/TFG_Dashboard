CREATE TABLE IF NOT EXISTS pending_assets (
    symbol     VARCHAR(20) PRIMARY KEY,
    name       VARCHAR(200),
    asset_type VARCHAR(20) DEFAULT 'stock',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status     VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'done', 'failed'))
);

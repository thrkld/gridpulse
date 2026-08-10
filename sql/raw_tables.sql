-- Raw payloads
CREATE TABLE IF NOT EXISTS carbon_intensity_raw (
    id SERIAL PRIMARY KEY,
    ingested_at TIMESTAMPTZ NOT NULL,
    endpoint TEXT NOT NULL, -- 'regional' | 'national' | 'generation'
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS elexon_raw (
    id SERIAL PRIMARY KEY,
    ingested_at TIMESTAMPTZ NOT NULL,
    endpoint TEXT NOT NULL, -- 'imbalance' | 'market-index' | 'demand-forecast' | 'demand-outturn'
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS neso_raw (
    id SERIAL PRIMARY KEY,
    ingested_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
);

-- Every staging view filters on endpoint before exploding the payload
CREATE INDEX IF NOT EXISTS carbon_intensity_raw_endpoint_ingested_at_idx
    ON carbon_intensity_raw (endpoint, ingested_at);

CREATE INDEX IF NOT EXISTS elexon_raw_endpoint_ingested_at_idx
    ON elexon_raw (endpoint, ingested_at);

CREATE INDEX IF NOT EXISTS neso_raw_ingested_at_idx
    ON neso_raw (ingested_at);

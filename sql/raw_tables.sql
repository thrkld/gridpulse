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
    endpoint TEXT NOT NULL, -- 'imbalance' | 'market-index'
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS neso_raw (
    id SERIAL PRIMARY KEY,
    ingested_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
);
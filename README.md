# GridPulse

[![CI](https://github.com/thrkld/gridpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/thrkld/gridpulse/actions/workflows/ci.yml)

An ELT pipeline for UK electricity data (carbon intensity, national demand and wholesale/imbalance prices) ingested into Postgres as raw JSON and modelled with dbt.

## What it answers

- When is the greenest and cheapest half-hour of the day and are they the same?
- How accurate are carbon intensity and demand forecasts once actuals land?
- How do imbalance prices move with demand and the renewables share?
- How much of GB demand is met by interconnector imports vs domestic generation?

## Architecture

![Architecture Diagram](docs/images/gridpulse%20architecture%20dark.png)

- **Raw** - untouched API responses as JSONB, append-only. Every ingestion is a snapshot; nothing is ever updated or deleted, so re-runs and backfills are trivially safe and forecast revisions are preserved as history.
- **Staging** - one dbt view per source endpoint: unpack the JSON, reformat and derive UTC settlement fields. No between-table logic.
- **Marts** *(in progress)* - star schema keyed on the UTC half-hour: deduplication to latest-known-value per period, and the cross-source joins that answer the questions above.

## Dealing with different 'clocks'

Carbon Intensity and Elexon publish UTC instants. NESO publishes a *local* settlement date and period number, meaning 46 periods on the spring clock change and 50 in autumn. Standardizing to UTC fixes these issues.

Full reasoning for this and every other design choice, including rejected alternatives: [docs/decisions.md](docs/decisions.md).

## Data sources

| Source | Data | Initial load | Ongoing | Revision sweep |
|---|---|---|---|---|
| [Carbon Intensity API](https://carbonintensity.org.uk/) | gCO₂/kWh, generation mix, national + regional | backfill from 2024-01-01 via date-range endpoints, fetched in ~14-day chunks (regional is 7 days) | every 30 min | daily, trailing 48 h. Actuals land within hours and are stable after a day; regional is forecast-only, so no sweep |
| [NESO Data Portal](https://www.neso.energy/data-portal) | national demand, embedded generation, interconnector flows | first snapshot ships with ~2 months of history | 2x daily full snapshot | built in: the dataset is a rolling window, so every fetch re-captures the full revision period |
| [Elexon BMRS](https://bmrs.elexon.co.uk/) | imbalance prices, market index | backfill from 2024-01-01, one call per settlement date | every 30 min | daily trailing 7 days (interim settlement run) and weekly trailing 35 days (initial settlement run); later reconciliation runs are out of scope by design |

*The initial load has been run against the cloud database. Revision sweeps are implemented and tested, but only start running unattended once orchestration is deployed.*

Sources keep revising data after publication, so past periods are re-fetched
until they settle. Every fetch lands as a new append-only snapshot; marts
resolve to the latest value per settlement period, which makes all sweeps and
backfills safe to re-run.

## Running it

Requires Docker and Python 3.12+.

```bash
git clone https://github.com/thrkld/gridpulse && cd gridpulse

# database
cp .env.example .env # local password, plus PG* settings if using a hosted database
docker compose up -d
docker exec -i gridpulse-postgres-1 psql -U gridpulse -d gridpulse < sql/raw_tables.sql

# ingestion
pip install -r requirements.txt -e .
python -m gridpulse.ingest.run_carbon_intensity
python -m gridpulse.ingest.run_neso
python -m gridpulse.ingest.run_elexon

# historical load, run once per database
python scripts/backfill.py

# orchestration (schedules the above per the data sources table)
dagster dev -f src/gridpulse/orchestration/definitions.py -p 3001

# transformations
pip install -r requirements-dbt.txt
cd dbt && dbt deps && dbt build
```

dbt expects a gridpulse profile in ~/.dbt/profiles.yml pointing at
localhost:5432 (dev schema public). dbt does not read .env, so to build against
a hosted database add a second output to that profile and run
`dbt build --target prod`.


## Testing
- pytest - settlement-period conversion (including DST edge days), backfill chunking and date coverage, and sweep windows.
- dbt - 114 schema tests across staging: grain uniqueness per model, null constraints with severity matched to how load-bearing each column is, accepted ranges and values, and a row count assertion on every model so that an empty one cannot pass by having nothing to check.
- CI - pytest and ruff (format + lint) on every push and pull request.
```
make check # See 'Makefile' for specific format of tests
cd dbt && dbt build
```

## Status
- [X] Ingestion for all three sources (6 endpoints), raw JSONB layer
- [X] dbt staging models with UTC settlement normalisation + test suite
- [X] Settlement-period dimension spine, DST unit tests, CI (pytest)
- [X] Backfill + revision sweeps for CI and Elexon
- [X] Local Dagster orchestration: ingestion assets + schedules
- [X] Cloud Postgres on Azure, historical load complete and validated by the dbt suite
- [ ] Unattended scheduled runs: Dagster deployed off the laptop
- [ ] Ingestion hardening: response validation and a run audit table (retries implemented)
- [ ] Marts: star schema, latest-value dedup, cross-source joins
- [ ] CI running the full dbt build against ephemeral Postgres
- [ ] Dashboard; demand/price forecast consumer

Operational history is logged in `docs/incidents.md` once unattended runs begin.

## Attribution & licences

- **Elexon** — Contains BMRS data © Elexon Limited copyright and database right 2026.
  Licensed under the [BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
- **Carbon Intensity API** — data provided by the National Energy System Operator
  via the [Carbon Intensity API](https://carbonintensity.org.uk/), licensed under
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **NESO** — Supported by National Energy SO Open Data, under the
  [NESO Open Licence](https://www.neso.energy/data-portal/neso-open-licence).

The licences above apply to the ingested data; the code in this repository is
licensed under the [MIT License](LICENSE).

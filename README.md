# GridPulse

[![CI](https://github.com/thrkld/gridpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/thrkld/gridpulse/actions/workflows/ci.yml)

GridPulse is an ELT pipeline for UK electricity data. It ingests carbon intensity, national demand and wholesale and imbalance prices into Postgres as raw JSON, and then models that data with dbt.

## What it answers

- When is the greenest half hour of the day, when is the cheapest, and are they the same one?
- How accurate do the carbon intensity and demand forecasts turn out to be once the actual figures land?
- How do imbalance prices move as demand and the renewables share change?
- How much of GB demand is met by interconnector imports rather than by domestic generation?
- When does the price of power go negative, and what is the grid doing when it happens?
- What does being out of balance actually cost, measured against the wholesale price?
- How much has embedded solar hollowed out midday demand since 2024?
- How different are the nations' grids from one another?

## Architecture

![Architecture Diagram](docs/images/gridpulse%20architecture%20dark.png)

The **raw** layer stores API responses as JSONB exactly as they arrived, and it is append only. Every ingestion is a snapshot, and nothing is ever updated or deleted, which is what makes re-runs and backfills safe to repeat and what preserves forecast revisions as history rather than overwriting them.

The **staging** layer puts one dbt view over each source endpoint. Those views unpack the JSON, tidy up the types and derive the UTC settlement fields, but they do no logic that spans tables.

The **marts** layer is six tables keyed on the UTC half hour. Each one deduplicates its sources down to their latest known value and then joins them together: a settlement-period spine, a wide fact carrying every source on one row, and four facts at their own grain for the generation mix, forecast publications, regions and interconnectors. Model and column descriptions are written into the database as comments on every build, so the caveats reach whatever queries the tables rather than stopping at this repository. The reasoning behind that shape, along with the alternatives that were rejected, sits in [docs/decisions.md](docs/decisions.md).

## Where it runs

Ingestion runs unattended in the cloud. Dagster schedules the fetches from an Azure VM, and the data lands in an Azure Database for PostgreSQL server in the same region. Dagster keeps its own run and schedule history in a second database on that same server, so restarting the containers does not lose any of it.

The same code also runs locally against the Postgres in `docker-compose.yml`, because the connection details are read from the environment rather than hardcoded. Anything that has gone wrong since the first scheduled run is written down in [docs/incidents.md](docs/incidents.md).

## Dealing with different 'clocks'

Carbon Intensity and Elexon both publish UTC instants, but NESO publishes a *local* settlement date together with a period number. That means a NESO day has 46 periods when the clocks go forward in spring and 50 when they go back in autumn. Normalising everything to UTC on the way in is what stops those two conventions from colliding.

The reasoning behind this and every other design choice, including the alternatives that were rejected, is in [docs/decisions.md](docs/decisions.md).

## Data sources

| Source | Data | Initial load | Ongoing | Revision sweep |
|---|---|---|---|---|
| [Carbon Intensity API](https://carbonintensity.org.uk/) | gCO₂/kWh, generation mix, national + regional | backfill from 2024-01-01 via date-range endpoints, fetched in ~14-day chunks (regional is 7 days) | every 30 min | daily, trailing 48 h. Actuals land within hours and are stable after a day; regional is forecast-only, so no sweep |
| [NESO Data Portal](https://www.neso.energy/data-portal) | national demand, embedded generation, interconnector flows | one call per year against the historic demand resources, from 2024-01-01 | 2x daily full snapshot | built in: the live feed is a rolling window, so every fetch re-captures the full revision period |
| [Elexon BMRS](https://bmrs.elexon.co.uk/) | imbalance prices, market index, demand forecast and outturn | backfill from 2024-01-01: one call per settlement date for imbalance and one per day of publications for the forecast | every 30 min | daily trailing 7 days (interim settlement run) and weekly trailing 35 days (initial settlement run); later reconciliation runs are out of scope by design |

Every source keeps revising its data after first publishing it, so past periods have to be fetched again until they settle. Each fetch lands as another append-only snapshot, and the marts resolve each settlement period down to its latest value, which is what makes the sweeps and backfills safe to run as many times as you like.

The demand forecast is worth calling out, because Elexon republishes it roughly 59 times per period as that period approaches. All of those publications are kept rather than only the last one, which is what makes it possible to measure how the forecast improves with less time to run.

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

dbt looks for a gridpulse profile in `~/.dbt/profiles.yml` pointing at localhost:5432, using the dev schema `public`. It does not read `.env`, so if you want to build against a hosted database you need to add a second output to that profile and then run `dbt build --target prod`.

## Testing

**pytest** covers the settlement-period conversion including the days the clocks change, the backfill chunking and the date ranges it produces, the sweep windows, how failed requests are retried, and how the database connection is resolved from the environment.

**dbt** runs 205 tests across staging and marts. Those check the grain of each model is unique, that null constraints have a severity matching how load-bearing the column is, that values fall in accepted ranges, and that no model has silently lost periods, because a table with holes in it passes every test that only examines rows which exist.

**CI** runs pytest and ruff, both format and lint, on every push and pull request.

```
make check # See 'Makefile' for specific format of tests
cd dbt && dbt build
```

## Status

- [X] Ingestion for all three sources (8 endpoints), raw JSONB layer
- [X] dbt staging models with UTC settlement normalisation + test suite
- [X] Settlement-period dimension spine, DST unit tests, CI (pytest)
- [X] Backfill + revision sweeps for CI and Elexon
- [X] Local Dagster orchestration: ingestion assets + schedules
- [X] Cloud Postgres on Azure, historical load complete and validated by the dbt suite
- [X] Unattended scheduled runs: Dagster deployed on an Azure VM, first scheduled run 2026-08-06
- [X] Marts: six tables keyed on the UTC half hour, latest-value dedup, cross-source joins
- [ ] Ingestion hardening: response validation and a run audit table (retries implemented)
- [ ] CI running the full dbt build against ephemeral Postgres
- [ ] Dashboard; demand/price forecast consumer

## Attribution & licences

- **Elexon**: contains BMRS data © Elexon Limited copyright and database right 2026, licensed under the [BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
- **Carbon Intensity API**: data provided by the National Energy System Operator via the [Carbon Intensity API](https://carbonintensity.org.uk/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **NESO**: supported by National Energy SO Open Data, under the [NESO Open Licence](https://www.neso.energy/data-portal/neso-open-licence).

Those licences apply to the ingested data. The code in this repository is licensed under the [MIT License](LICENSE).

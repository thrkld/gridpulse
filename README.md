# GridPulse

[![CI](https://github.com/thrkld/gridpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/thrkld/gridpulse/actions/workflows/ci.yml)

GridPulse is an ELT pipeline for UK electricity data. It ingests carbon intensity, national demand and wholesale and imbalance prices into Postgres as raw JSON, and then models that data with dbt.

## What it answers

- When are the greenest and cheapest half hours, and how closely do their daily patterns align?
- How accurate do the carbon intensity and demand forecasts turn out to be once the actual figures land?
- How do imbalance prices move as demand and the renewables share change?
- How large are net interconnector imports relative to GB national demand?
- When does the price of power go negative, and what is the grid doing when it happens?
- How far does the imbalance price differ from the wholesale price?
- How have midday demand and estimated embedded solar changed since 2024?
- How different are the nations' grids from one another?

## Architecture

![Architecture Diagram](docs/images/gridpulse%20architecture%20dark.png)

The **raw** layer stores API responses as JSONB exactly as they arrived, and it is append only. Every ingestion is a snapshot, and nothing is ever updated or deleted, which is what makes re-runs and backfills safe to repeat and what preserves forecast revisions as history rather than overwriting them.

The **staging** layer puts one dbt view over each source endpoint. Those views unpack the JSON, tidy up the types and derive the UTC settlement fields, but they do no logic that spans tables.

The **marts** layer is six tables keyed on the UTC half hour. Each one deduplicates its sources down to their latest known value and then joins them together: a settlement-period spine, a wide fact carrying every source on one row, and four facts at their own grain for the generation mix, forecast publications, regions and interconnectors. The reasoning behind that shape, along with the alternatives that were rejected, sits in [docs/decisions.md](docs/decisions.md).

## Where it runs

Ingestion and transformation both run unattended in the cloud. Dagster schedules them from an Azure VM, and the data lands in an Azure Database for PostgreSQL server in the same region. Dagster keeps its own run and schedule history in a second database on that same server, so restarting the containers does not lose any of it.

| Schedule | Cadence | What it does |
|---|---|---|
| `half_hourly_refresh` | every 30 min | latest carbon intensity and Elexon |
| `twice_daily_refresh` | 10:00 and 22:00 UTC | full NESO snapshot |
| `daily_sweep` | 00:15 UTC | carbon intensity trailing 48 h, Elexon interim settlement 7 d |
| `weekly_sweep` | 00:45 Sunday | Elexon initial settlement, trailing 35 d |
| `six_hourly_dbt_build` | 02:20, 08:20, 14:20, 20:20 UTC | all six marts and their tests, 93 seconds |
| `nightly_dbt_build` | 04:00 UTC | every model and its tests (203 in the current project) |

The dbt project is loaded through `dagster-dbt`, so each model and test is an asset rather than one opaque step, and the raw assets are keyed to match dbt's source names. That makes the graph a single unbroken lineage from the API call through to the mart, instead of two halves that happen to run in order.

The same code also runs locally against the Postgres in `docker-compose.yml`, because the connection details are read from the environment rather than hardcoded. Anything that has gone wrong since the first scheduled run is written down in [docs/incidents.md](docs/incidents.md).

## Dealing with different 'clocks'

Carbon Intensity and Elexon both publish UTC instants, but NESO publishes a *local* settlement date together with a period number. That means a NESO day has 46 periods when the clocks go forward in spring and 50 when they go back in autumn. Normalising everything to UTC on the way in is what stops those two conventions from colliding.

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

# orchestration (schedules ingestion and dbt per the data sources table)
dagster dev -f src/gridpulse/orchestration/definitions.py -p 3001

# transformations
pip install -r requirements-dbt.txt
cd dbt && dbt deps && dbt build
```

dbt reads `dbt/profiles.yml`, which is committed and takes its connection details from the environment, so the same file serves a laptop, the local Docker database and the deployed container. It has a `dev` output pointing at localhost and a `prod` output for the hosted database.

dbt does not read `.env` itself, so export it first when building against the cloud:

```bash
set -a && . .env && set +a
cd dbt && DBT_TARGET=prod dbt build
```

## Metabase dashboard

The Compose stack serves Metabase at <http://localhost:3002>. Finish its first-run
setup, then create an API key in **Admin → Settings → Authentication → API keys**.
The key needs permission to manage the database connection, collection and questions;
an administrator key can provision the full setup. Keep it in the gitignored `.env`:

```dotenv
METABASE_URL=http://localhost:3002
METABASE_API_KEY=your-key
```

From the repository root, after building the marts:

```bash
python scripts/provision_metabase.py --verify
```

The script creates a `GridPulse (managed)` collection and prints the dashboard URL.
Rerunning updates SQL, descriptions, chart settings and layout, including recovery
after a partially completed run. It leaves other collections and dashboards alone.
Treat the managed collection as repository-owned: manual layout changes there will
be replaced. Question names are identifiers. A declared previous name is migrated
in place; an undeclared rename leaves the old question available for manual cleanup.

For an existing Metabase database connection, set `METABASE_DATABASE_ID` to its
numeric ID. Otherwise the script reuses a connection named `GridPulse marts`, or
creates one from `PG*`. It does not update an existing connection's credentials.
For local Docker data, set `METABASE_PGHOST=postgres` and
`METABASE_PGSSLMODE=disable`; the password defaults to `POSTGRES_PASSWORD`.
`localhost` inside Metabase is the Metabase container, not the database container.
Hosted connections must be reachable from Docker and allowed through any firewall.
For `verify-full` or `verify-ca`, the script uploads the CA bundle from
`METABASE_PGSSLROOTCERT`, `PGSSLROOTCERT`, or certifi (in that order), because a
certificate path on your laptop is not a path inside the Metabase container.
New connections disable full field-value scanning; native SQL questions do not
need Metabase to scan every raw and staging column.
Use a read-only database account for ongoing dashboard access.

The 15 questions cover the original analytical questions and expose coverage:

| Question | Dashboard evidence |
|---|---|
| Greenest versus cheapest | Matched daily-pattern charts and overlap between each day's cheapest and lowest-carbon quarters |
| Forecast accuracy | Carbon MAE by month; NDF MAE at six horizons on the same target periods |
| Imbalance and grid conditions | Demand/renewables bins with sample counts |
| Imports | Net cross-border flow relative to demand; country totals sum links before averaging |
| Negative prices | Monthly frequency among known prices, plus matched grid conditions |
| Imbalance versus wholesale | Signed and absolute price spreads, not a participant's realised cash cost |
| Midday solar | Completed-month national demand, estimated embedded solar and demand with solar added back; not a causal estimate |
| Nations | England, Scotland and Wales on common half-hours; regional intensity is forecast-only |

Monthly field coverage and daily NDF publication coverage accompany the charts.
Permanent source gaps remain missing. The demand chart measures historical
publisher accuracy, including recovered publications; it does not replay what this
pipeline knew at the time. Carbon ingestion does not retain fixed-horizon forecast
vintages. The marts refresh every six hours, so this is not a live dashboard.
See [probe findings](docs/probe_findings.md) for the source limitations and
[incidents](docs/incidents.md) for recovered outages.

The Metabase image is pinned and its application state is persisted in a Docker
volume. That volume is not a backup; this local Compose setup is not a hardened
public deployment.

## Testing

**pytest** covers the settlement-period conversion including the days the clocks change, the backfill chunking and the date ranges it produces, the sweep windows, how failed requests are retried, and how the database connection is resolved from the environment. Dashboard tests cover update/recovery behaviour, scope protection and chart definitions. PostgreSQL fixtures check missing-value denominators, matched samples, forecast horizons, flow aggregation, carbon/price alignment and publication windows.

**dbt** defines 203 tests across staging and marts. Those check the grain of each model is unique, that null constraints have a severity matching how load-bearing the column is, that values fall in accepted ranges, and that no model has silently lost periods, because a table with holes in it passes every test that only examines rows which exist. The NDF publication-window test warns after a two-UTC-day grace period; it can flag source delays as well as ingestion gaps and needs investigation, not automatic zero-filling.

**CI** runs pytest and ruff, both format and lint, on every push and pull request.

```
make check # See 'Makefile' for specific format of tests
cd dbt && dbt build
```

SQL fixture tests skip unless `GRIDPULSE_TEST_POSTGRES` is set to a disposable
PostgreSQL connection string. They create only temporary tables, exclude `public`
from the search path, and roll back every transaction. CI runs these against its
Postgres service:

```bash
GRIDPULSE_TEST_POSTGRES='postgresql://user:password@localhost:5432/testdb' pytest tests/metabase_sql_test.py
```

An optional end-to-end test provisions a **fresh, disposable** Metabase instance,
executes every question, reruns provisioning and checks recovery from an empty
dashboard. It refuses an already configured instance. It uses the usual `PG*` or
`METABASE_PG*` connection settings; queries require the marts to exist:

```bash
GRIDPULSE_TEST_METABASE_URL=http://localhost:TEST_PORT pytest tests/metabase_api_test.py
```

Do not point this at your main Metabase instance. Remove the disposable container
after testing, since its application database holds the test account and database
connection credentials. Neither integration test changes production source data.

## Status

- [X] Ingestion for all three sources (8 endpoints), raw JSONB layer
- [X] dbt staging models with UTC settlement normalisation + test suite
- [X] Settlement-period dimension spine, DST unit tests, CI (pytest)
- [X] Backfill + revision sweeps for CI and Elexon
- [X] Local Dagster orchestration: ingestion assets + schedules
- [X] Cloud Postgres on Azure, historical load complete and validated by the dbt suite
- [X] Unattended scheduled runs: Dagster deployed on an Azure VM, first scheduled run 2026-08-06
- [X] Marts: six tables keyed on the UTC half hour, latest-value dedup, cross-source joins
- [X] dbt orchestrated in Dagster: models and tests as assets, deployed 2026-08-27
- [X] Incremental materialisation for the two models that rebuilt in full, keyed on arrival time
- [X] CI building every model against an empty Postgres on each push
- [X] Swap checked on every ingestion run, after the August outage
- [ ] Ingestion hardening: validate responses at fetch, so a 200 carrying the wrong shape fails immediately (retries implemented)
- [ ] dbt tests running in CI against seeded fixtures
- [X] Repository-managed Metabase questions, coverage checks and SQL regression fixtures
- [ ] Provision and visually verify the dashboard in the main Metabase instance
- [ ] Demand/price forecast consumer

## Attribution & licences

- **Elexon**: contains BMRS data © Elexon Limited copyright and database right 2026, licensed under the [BMRS data licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
- **Carbon Intensity API**: data provided by the National Energy System Operator via the [Carbon Intensity API](https://carbonintensity.org.uk/), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **NESO**: supported by National Energy SO Open Data, under the [NESO Open Licence](https://www.neso.energy/data-portal/neso-open-licence).

Those licences apply to the ingested data. The code in this repository is licensed under the [MIT License](LICENSE).

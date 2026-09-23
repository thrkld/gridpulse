# Operations

## Deployment

Ingestion and transformation both run unattended in the cloud. Dagster schedules them from an Azure VM, and the data lands in an Azure Database for PostgreSQL server in the same region. Dagster keeps its own run and schedule history in a second database on that same server, so restarting the containers does not lose any of it.

| Schedule | Cadence | What it does |
|---|---|---|
| `half_hourly_refresh` | every 30 min | latest carbon intensity and Elexon |
| `twice_daily_refresh` | 10:00 and 22:00 UTC | full NESO snapshot |
| `daily_sweep` | 00:15 UTC | carbon intensity trailing 48 h, Elexon interim settlement 7 d |
| `weekly_sweep` | 00:45 Sunday | Elexon initial settlement, trailing 35 d |
| `six_hourly_dbt_build` | 02:20, 08:20, 14:20, 20:20 UTC | all six marts and their tests, 93 seconds |
| `publish_dashboard` | 02:50, 08:50, 14:50, 20:50 UTC | renders the 14 analyses and publishes the page |
| `nightly_dbt_build` | 04:00 UTC | every model and its tests (203 in the current project) |

The dbt project is loaded through `dagster-dbt`, so each model and test is an asset rather than one opaque step, and the raw assets are keyed to match dbt's source names. The publishing asset declares the marts it reads as dependencies. That makes the graph a single unbroken lineage from the API call through to the published chart, instead of stages that happen to run in order.

The same code also runs locally against the Postgres in `docker-compose.yml`, because the connection details are read from the environment rather than hardcoded. Anything that has gone wrong since the first scheduled run is written down in [docs/incidents.md](incidents.md).


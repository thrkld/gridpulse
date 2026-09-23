# Metabase dashboard

Metabase is the local exploration surface for the marts. The 15 questions, their
SQL, chart settings and dashboard layout are provisioned from this repository by
`scripts/provision_metabase.py`. The static dashboard is rendered separately by
`gridpulse.charts` and does not depend on Metabase. Read the
[saved analysis](findings.md) without setup; the [README](../README.md) tracks
public deployment status.

## Setup

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

## Database connection

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

## What the questions cover

| Question | Dashboard evidence |
|---|---|
| Greenest versus cheapest | Matched daily-pattern charts and overlap between each day's cheapest and lowest-carbon quarters |
| Forecast accuracy | Average carbon forecast error by month; demand forecast error from 30 minutes to 21 hours ahead on the same target periods |
| Imbalance and grid conditions | Demand/renewables bins with sample counts |
| Imports | Net cross-border flow relative to demand; country totals sum links before averaging |
| Negative prices | Monthly frequency among known prices, plus matched grid conditions |
| Imbalance versus wholesale | Signed and absolute price spreads, not a participant's realised cash cost |
| Midday solar | Completed-month national demand, estimated embedded solar and demand with solar added back; not a causal estimate |
| Nations | England, Scotland and Wales on common half-hours; regional intensity is forecast-only |

Monthly field coverage and daily NDF publication coverage accompany the charts.
Permanent source gaps remain missing. The demand chart measures historical
publisher accuracy, including recovered publications; it does not replay what this
pipeline knew at the time. Carbon ingestion does not retain forecasts made at a consistent number of hours before delivery. The marts refresh every six hours, so this is not a live dashboard.
See [probe findings](probe_findings.md) for the source limitations and
[incidents](incidents.md) for recovered outages.

The Metabase image is pinned and its application state is persisted in a Docker
volume. That volume is not a backup; this local Compose setup is not a hardened
public deployment.

## Integration tests

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

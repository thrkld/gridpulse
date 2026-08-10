# Design Decisions

Format: what was decided, why, what was rejected, and current status. Status is honest: `implemented`, `partial`, or `planned`.

---

## Architecture
### ELT with a raw JSONB layer

Load untouched API responses directly into postgres as JSONB first; all transformation happens afterwards in dbt/SQL.

**Why:** Keeps ingestion lossless and fully replayable. Any transformation logic can be re-derived from raw history without re-ingestion.

**Rejected:** ETL (transforming in Python before load), which would permanently discard source fidelity.

**Status:** implemented.

### Append-only raw layer with idempotent ingestion

No overwriting raw tables: append-only, meaning re-running ingestion inserts new records rather than modifying existing ones.

**Why:** Makes ingestion safe to retry and preserves full historical revisions (e.g forecast updates over time).

**Rejected:** UPSERT/ON CONFLICT updates in raw tables, which would destroy historical revisions and make ingestion order-dependent.

**Status:** partial (raw layer implemented; mart-side dedup planned).

### UTC as the canonical settlement-time model

All sources are normalised to a UTC half-hour timeline. `start_time` (UTC instant) is the primary join key across all datasets. Settlement periods are defined on the UTC clock rather than source-specific local conventions

**Why:** Eliminates DST and source-local settlement inconsistencies. Ensures joins are temporally consistent.

**Rejected:** Keeping source-specific settlement periods and reconciling during joins, which introduces repeated DST edge-case handling.

**Status:** implemented across staging models.

### Cross-source joins occur in marts, not staging

No cross-source joining within staging tables. Staging serves as cleaning and standardising jsonb data pre-mart processing

**Why:** Keeps staging models independently testable and prevents cross-source logic from contaminating raw transformations.

**Rejected:** Performing joins in staging, which couples datasets and makes validation harder.

**Status:** staging implemented; marts planned.

### One raw table per source with endpoint discriminator

Each source has a single raw table. Multiple endpoints are distinguished using an 'endpoint' column rather than separate tables.

**Why:** Keeps raw schema minimal and avoids duplication of identical table structures.

**Rejected:** table-per-endpoint design, which introduces unnecessary schema duplication.

**Status:** implemented

### Fetch times (non-sweeping)
| API | Frequency |
| --------- | --- |
| Neso | 2x per day |
| Elexon | Half hourly |
| Carbon Intensity | Half hourly |

**Why:** Uncertain update times for NESO, large snapshot which updates one time per day with a changing boundary. Elexon and Carbon Intensity API fetches discernable from previous one every 30 minutes.

**Rejected:** half-hourly NESO polling (48 identical snapshots per day, see probe_findings.md).

**Status:** implemented

## Ingestion
### Retries on transient API failures

API requests retry up to four times with exponential backoff. Responses in the 4xx range are not retried, apart from 429.

**Why:** A backfill makes hundreds of sequential calls, and one transient 500 or read timeout would otherwise end the entire run. A 4xx means the request itself is wrong, so repeating it wastes time and puts avoidable load on the source.

**Rejected:** Retrying every failure equally, which turns one unfixable bad request into four of them.

**Status:** implemented.

### Date-range backfills are chunked per endpoint, on UTC instants

Each ranged endpoint has its own maximum chunk length, established by testing the API. Chunk boundaries are calculated in UTC, while the span being covered is still anchored to London settlement days.

**Why:** The limits differ by endpoint. Carbon intensity regional and Elexon market index reject ranges over seven days, while carbon intensity national and generation accept fourteen. Chunk arithmetic has to be done in UTC because adding a timedelta to a London-local datetime moves by wall clock, so a seven day chunk crossing the autumn clock change covers 169 hours and is rejected.

**Rejected:** A single chunk size shared by all endpoints, which fails on whichever limit is smallest; and chunking on London-local datetimes, which breaks every October.

**Status:** implemented.

### Backfill is a script, not an orchestrated asset

Historical loading is run on demand from `scripts/backfill.py`. Only the latest fetches and the revision sweeps are registered as Dagster assets.

**Why:** Backfill runs once per environment and then has nothing left to do, so there is no schedule to give it. Keeping it out of the asset graph also prevents an accidental materialisation from replaying two years of API calls.

**Rejected:** Registering backfill as a Dagster asset or job, which leaves a permanent trigger for a job only needed at setup.

**Status:** implemented.

### Demand forecasts come from Elexon, not NESO

The national demand forecast is taken from Elexon's NDF dataset, alongside the settled outturn from the same publisher. NESO's forecast rows are kept for embedded wind and solar only.

**Why:** NESO publishes a zero in every demand and interconnector column on a forecast row, so there is nothing to compare an actual against. Elexon publishes a real forecast with the time it was published, and republishes it repeatedly as the period approaches, so error can be measured against how far ahead the forecast was made. Taking the outturn from Elexon as well keeps the comparison within one publisher's definition of national demand.

**Rejected:** Treating NESO's forecast rows as a demand forecast, which would report near total error against a literal zero; and Elexon's `/forecast/demand/day-ahead` endpoint, which ignores its date parameters and returns only the most recent publication, so it cannot be backfilled.

**Status:** implemented.

### Demand history comes from NESO's yearly resources

History is loaded once from the historic-demand-data resource for each year. The live feed only keeps the current window up to date.

**Why:** The live feed reaches back to the start of the previous month and no further, so it can never accumulate history behind the point ingestion started. Without the yearly resources, the questions about demand and interconnector flows would have covered five weeks against two and a half years for everything else. The historic resources carry no forecast indicator column at all, so their rows arrive with it null rather than marked settled, which anything reading them has to allow for.

**Rejected:** Letting the live feed accumulate, which would take years to match the other sources and would still hold nothing from before ingestion began.

**Status:** implemented.

## Deployment
### Managed Postgres on Azure, with a planned move

Data is held in Azure Database for PostgreSQL Flexible Server, Burstable B1ms with 32 GB storage, in Sweden Central. The free allocation lasts twelve months, after which the database moves to a cheaper host.

**Why:** Taking the database off a laptop is the point of deploying at all, and Azure is the most widely recognised platform offering a year of it at no cost. Sweden Central is used because the student subscription's region policy denies everything else. Nothing depends on Azure-specific services, so moving later is a dump and restore.

**Rejected:** Oracle Cloud's always free VM, which reclaims instances that stay under twenty percent CPU and would take the pipeline down without warning; Railway, which is simpler to run but costs from the first day and hides the infrastructure work; AWS, whose free tier is now six months of credits with one gigabyte of database storage.

**Status:** implemented for storage. Orchestration still runs locally.

### Database connection is resolved from the environment

`get_connection` uses `DATABASE_URL` when it is set, then individual `PG*` variables, then a local default.

**Why:** The same code then runs against local Docker, against the cloud database from a laptop, and inside a deployed container, with no change to the ingestion modules. Deployment platforms supply `DATABASE_URL` directly, and the separate variables avoid having to URL-encode passwords by hand.

**Rejected:** Hardcoded connection settings, which tie the ingestion layer to one database.

**Status:** implemented.

## Testing
### Every staging model asserts that it has rows

Each staging model carries a `dbt_utils.at_least_one` test on `ingested_at`.

**Why:** A model returning no rows passes every other test, because there is nothing there to fail. The national generation model was empty for exactly this reason after its payload shape changed, and nothing in the test suite reported it.

**Rejected:** Relying on column tests alone, which cannot tell clean data apart from no data.

**Status:** implemented.

### Test severity reflects whether the source or the pipeline is at fault

Columns with known upstream gaps warn on any nulls and only fail once the count passes a threshold.

**Why:** The carbon intensity API has twice published nothing for a stretch of periods since 2024, leaving 45 null forecasts. Failing a build over data the source never sent is noise, while a sudden increase would indicate a parsing problem worth stopping for.

**Rejected:** Dropping the test, which would hide a real regression; and failing on any null, which breaks the build for something outside the pipeline's control.

**Status:** implemented.

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

**Status:** implemented.

### UTC as the canonical settlement-time model

All sources are normalised to a UTC half-hour timeline. `start_time` (UTC instant) is the primary join key across all datasets. Settlement periods are defined on the UTC clock rather than source-specific local conventions

**Why:** Eliminates DST and source-local settlement inconsistencies. Ensures joins are temporally consistent.

**Rejected:** Keeping source-specific settlement periods and reconciling during joins, which introduces repeated DST edge-case handling.

**Status:** implemented across staging models.

### Cross-source joins occur in marts, not staging

No cross-source joining within staging tables. Staging serves as cleaning and standardising jsonb data pre-mart processing

**Why:** Keeps staging models independently testable and prevents cross-source logic from contaminating raw transformations.

**Rejected:** Performing joins in staging, which couples datasets and makes validation harder.

**Status:** implemented.

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

### Endpoints without a revision sweep get a wider catch-up window

Market index and the demand forecast are re-fetched over the trailing 24 hours on every run, rather than the two hours they actually need.

**Why:** Neither is revised after publication, so there is nothing for a settlement sweep to collect and none was written. That left them with a two-hour recovery window, and the gap between the backfill finishing and the deployment picking up the new code cost 86 periods of market index that nothing healed. Imbalance survived the same interruption untouched, because its sweeps re-fetch seven and thirty-five days regardless of why the data is missing.

**Rejected:** Adding sweeps for both, which would imply revisions that do not happen and would fetch far more than the gap requires; and leaving the window at two hours, which makes any interruption longer than one scheduled run permanent.

**Status:** implemented.

### Requests never span a calendar year

Carbon intensity backfill chunks are split at 1 January before being sent.

**Why:** The generation range endpoint truncates a straddling request at the year end and still returns 200, so a chunk covering new year silently loses everything after 31 December. This removed roughly twelve days of history at each year boundary, and nothing in the pipeline noticed because a short response is indistinguishable from a quiet period.

**Rejected:** Detecting short responses by comparing the record count against the range requested, which would catch this case but depends on knowing how many records a range should contain, and that varies with clock changes and source outages.

**Status:** implemented.

## Deployment
### The two large marts are built incrementally, keyed on arrival time

`fct_regional` and `fct_demand_forecast_publication` are `materialized='incremental'` and filter on `ingested_at`, not on `start_time`.

**Why:** Staging models are views over `jsonb_array_elements`. `ingested_at` is a real column on the raw table, so a filter on it is applied before the explode and only surviving payloads are detoasted. `start_time` is pulled out of the JSON, so a filter on it cannot be evaluated until after the explode has already happened. Measured on the regional generation view, the first plans at a cost of 98,098 and the second at 33,712,757, for identical output. Choosing the intuitive key would have produced a model that looks incremental and saves nothing.

**Rejected:** Filtering on `start_time`, for the reason above; and leaving both as full rebuilds, which cost 340 of the 384 seconds the marts spent building and forced the frequent schedule to exclude a model.

**Status:** implemented. The two dropped from 276 and 156 seconds to 9 and 4.

### Whole periods are replaced, not individual publications

`fct_demand_forecast_publication` has a grain of `(start_time, publish_time)` but a `unique_key` of `start_time` alone, and it reads its own previous rows back for the periods a batch touches.

**Why:** Two parts of the model need every publication for a period rather than the ones that happened to arrive together. `is_latest_publication` is a window over the period, so a partial batch marks several rows as latest. The outturn join is the subtler one: the outturn lands up to 91.6 hours after the period, long after publications for it have stopped, so a period reached only through its forecast would keep a null error for good. The batch therefore takes new rows from staging by arrival time, adds the periods' earlier rows back from the table itself, and recomputes over the union. Reading those earlier rows from staging instead would mean filtering on `start_time` and would cost more than a full rebuild.

**Rejected:** A plain append keyed on the publication grain, which breaks both the flag and the error and is caught by two existing tests; and moving the flag downstream into `fct_half_hour`, which removes a documented column that a dashboard may want.

**Status:** implemented.

### CI runs the models but not the tests

Every push builds the whole dbt project against an empty Postgres service container with `dbt run`.

**Why:** 202 tests previously gated nothing, so a broken model was found by the nightly build the following morning if anyone looked. Running the models against a real database catches a bad `ref`, invalid SQL and a column dropped upstream but still selected downstream. It cannot run the tests, because fifteen `at_least_one` tests exist precisely to fail on an empty model and would fail by design. Making the tests run needs seeded fixtures, which is worth doing separately rather than not validating anything in the meantime.

**Rejected:** `dbt parse` alone, which never executes any SQL and so lets a broken column reference through; and a full `dbt build`, which cannot pass without data.

**Status:** implemented. Seeded fixtures remain outstanding.

### The host is checked for swap on every ingestion run

A Dagster asset reads `SwapTotal` from `/proc/meminfo` and fails if it is zero.

**Why:** The VM has 842 MiB of RAM and cannot hold Dagster's three processes without swap. When the swapfile disappeared in August the load average reached 15 and the machine became too starved to accept an SSH session, so it took three days to diagnose from outside. The check rides on the existing half-hourly schedule rather than getting one of its own, because a new schedule arrives stopped unless `default_status` is set, and a health check nobody enabled is worse than none. The assets in that job are independent, so this failing marks the run red without stopping the ingestion beside it.

**Rejected:** A systemd unit on the VM, which is more robust but lives outside the repository and so is invisible to anyone reading the code; and continuing to rely on noticing missing data days later, which is how the outage was actually found.

**Status:** implemented. This detects the condition rather than preventing it, and why the swapfile vanished is still unknown.

### dbt runs as Dagster assets, not as a shell step

The dbt project is loaded through `dagster-dbt`, so every model and test is an asset in the same graph as the ingestion. Raw-layer assets are keyed to match dbt's source names, which joins the two halves into one lineage from API call to mart.

**Why:** A single asset shelling out to `dbt build` would schedule the work but show one green box, so a failure means reading logs to find out which model broke. Keying the ingestion assets to the dbt sources is what makes the graph continuous rather than two disconnected islands, and it costs nothing beyond naming.

**Rejected:** A plain asset running `dbt build` as a subprocess, which is fewer moving parts and gives up per-model visibility; and Dagster's schedules calling dbt with no asset representation at all, which puts the lineage nowhere.

**Status:** implemented.

### Transformation runs on two cadences

All six marts rebuild every six hours, and the full graph including every test runs nightly.

**Why:** A full build spends 1,967 seconds of database time, and 896 of those are tests against the 15 million row regional generation view. Refreshing that often enough for a dashboard would keep a burstable server under sustained load and starve the ingestion that shares it. Staging is materialised as views, so a frequent refresh does not need to touch them at all, and selecting the marts alone brought the run down to 202 seconds.

**Rejected:** Excluding only the regional mart, which reads as the obvious optimisation and saves 11%, because the expensive tests hang off staging rather than off the mart; and one nightly build, which leaves a dashboard a day stale.

**Status:** implemented. The frequent run initially excluded `fct_regional` as well, at 202 seconds. Once it and the publication mart became incremental the whole set fell to 93 seconds and the exclusion was dropped.

### One Dagster run at a time

`deploy/dagster.yaml` sets `max_concurrent_runs: 1` on the queued run coordinator.

**Why:** It was unset, so nothing capped concurrency. On 2026-08-28 three schedules landing within an hour of each other ran simultaneously rather than queueing, exhausted a 1 GiB machine and took ingestion down for ten hours. A single dbt build peaks at 1.9 GB on its own, so two overlapping need more than 3 GB, and the failure was a matter of when rather than whether. Queueing costs a few minutes of delay on a pipeline whose freshest source updates every thirty minutes, which is nothing.

**Rejected:** Sizing the machine for peak concurrency instead, which pays for headroom that exists only to absorb a collision that need not happen; and spacing the schedules alone, which reduces the chance of overlap without bounding it, and does nothing about catch-up runs after downtime, which is how the same machine was flattened a second time that morning.

**Status:** implemented, alongside spacing the dbt schedules away from the sweep window.

### The orchestration VM is sized from a measured peak

The VM has 4 GiB. A full dbt build was measured at 1.9 GB peak, sequential, with one dbt thread.

**Why:** The original 1 GiB machine was adequate for ingestion alone and became impossible once dbt joined the containers, which was not obvious until it was measured. 2 GiB would leave roughly a hundred megabytes of headroom at peak and put the pipeline back to swapping on every nightly build. Anything smaller cannot run this project at all, which quietly excludes most free VM tiers.

**Rejected:** Continuing to tune around an undersized machine, having spent a morning on swap and disk before measuring the thing that actually mattered.

**Status:** implemented on Azure. Compute is a candidate to move to a cheaper host, since nothing depends on the provider and the database connection is resolved from the environment.

### Managed Postgres on Azure, with a planned move

Data is held in Azure Database for PostgreSQL Flexible Server, Burstable B1ms with 32 GB storage, in Sweden Central. The free allocation lasts twelve months, after which the database moves to a cheaper host.

**Why:** Taking the database off a laptop is the point of deploying at all, and Azure is the most widely recognised platform offering a year of it at no cost. Sweden Central is used because the student subscription's region policy denies everything else. Nothing depends on Azure-specific services, so moving later is a dump and restore.

**Rejected:** Oracle Cloud's always free VM, which reclaims instances that stay under twenty percent CPU and would take the pipeline down without warning; Railway, which is simpler to run but costs from the first day and hides the infrastructure work; AWS, whose free tier is now six months of credits with one gigabyte of database storage.

**Status:** implemented. Orchestration moved onto an Azure VM on 2026-08-06 and dbt joined it on 2026-08-27.

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

### Facts are tested for missing periods, not only for bad values

Each fact carries a test comparing the periods it holds against the settlement spine across its own date range.

**Why:** Column tests can only examine rows that exist, so a fact with holes in it passes every one of them. A truncated backfill response cost the generation mart 1,197 periods, and uniqueness, null and range tests all stayed green throughout because the missing rows had nothing to fail. The threshold is set so that the outages the sources genuinely have will warn while a lost chunk, which costs hundreds of periods at a time, will fail.

**Rejected:** Trusting row counts to reveal it, which only works if you know what the count should be; and building facts from the spine so gaps become null rows, which suits the cross-source fact but would leave the mix carrying nine empty rows per missing period.

**Status:** implemented on every fact.

### Availability is measured from the data rather than from a separate log

Uptime is counted by grouping `ingested_at` into half-hourly buckets per day and comparing against the number of scheduled runs, rather than by recording each run somewhere.

**Why:** A successful fetch already writes a timestamp, so the raw layer is a complete record of every run that worked, going back to the first one. That needs no new table and cannot drift out of step with reality, because it is the same rows the pipeline is judged on.

**Rejected:** Trusting Dagster's own run history, which is a separate database that has already been lost once and says nothing about whether data actually landed.

**Status:** implemented as a query. The limitation is that a run which fired and failed leaves no trace, so this measures successes rather than attempts.

**Revisited 2026-08-27:** the rejected alternative was Dagster's own run history, on the grounds that it lives in a database that had already been lost once. That was true when Dagster kept its state in a container. It now runs on the same managed server as the data, so Dagster does record every attempt including the failures this query cannot see, and a separate audit table would duplicate it. The gap is closed by where the state lives rather than by anything built.

## Marts
### Wide tables keyed on the half hour rather than a star schema

The marts are a settlement-period spine and a small number of facts joined on `start_time`, with no dimension tables.

**Why:** The dimensions a star would add hold nine fuels, eighteen regions and eleven interconnectors, so normalising them saves a few kilobytes while adding a join to every query on a database with one virtual CPU. `start_time` is already a natural key: eight bytes, unambiguous, and readable without a lookup.

**Rejected:** A conformed star with surrogate keys, which earns its keep when many facts share dimensions and a reporting layer expects that shape, and which here would cost more than it returns.

**Status:** implemented.

### Each source is deduplicated on its own terms, not on arrival order

Every source is reduced to one row per period with `distinct on`, but the ordering key differs per source. Imbalance orders by Elexon's own `created_datetime` before ingestion time. NESO orders settled rows ahead of forecast rows using a null-safe comparison, then by ingestion time.

**Why:** Arrival order is a property of the pipeline rather than of the data, so it is only a safe tiebreak. Elexon stamps its own revision clock, which is the publisher's statement about which version supersedes which. NESO needs the null-safe form because the 35,088 historic rows carry no indicator column at all, and a bare comparison against 'F' evaluates to null on every one of them, which would sort settled history behind forecasts and blank two years of demand.

**Rejected:** One ordering by ingestion time everywhere, which is right for four sources and quietly wrong for the two that matter most.

**Status:** implemented.

### A settled marker is not trusted on its own

NESO's demand and flow columns are only read where the row is marked settled and national demand is above zero. The `demand_is_settled` flag carries the same condition.

**Why:** Forecast rows publish a literal zero in every demand and flow column, which is the documented behaviour and the reason the flag exists. What was not expected is that NESO also publishes settled rows the same way, six of them in August 2026 alone. One of those survives as the latest snapshot, and without this condition it reaches the marts as a national demand collapse to zero and a simultaneous outage across eleven interconnectors. Both figures are plausible enough in isolation to end up on a chart.

**Rejected:** Trusting the indicator, which is what the source says rather than what it published; and a hardcoded plausibility floor, which would need revisiting whenever demand shifts.

**Status:** implemented.

### Interconnector flows are kept both wide and long

The flows appear as a net column on `fct_half_hour` and again as one row per link on `fct_interconnector_flow`.

**Why:** The two shapes answer different questions. Correlating imports against price or demand needs the flows on the same row as everything else, and a map needs one row per link so it can group by counterparty country. Deriving either from the other at query time costs a join or an aggregate on every chart.

**Rejected:** Only the long form, which makes every cross-source question a join; and only the wide form, which cannot be mapped without unpivoting in the dashboard. The price of holding both is a test asserting the net column equals the sum of the cross-border rows, so the two cannot drift apart.

**Status:** implemented.

### The Scotland to England boundary is carried as a flow but named as a boundary

The Scottish transfer sits in the flow fact with `is_cross_border` false, under the name "Scotland-England boundary" rather than NESO's column name.

**Why:** It is an internal GB boundary, so counting it as an import inflates the total by about 60%. It also averages 2,378 MW, which is larger than any real interconnector, so an unfiltered chart of average flow by link puts it at the top. A flag alone still depends on somebody remembering to apply it, whereas a name that does not read as an interconnector fails safe.

**Rejected:** Dropping it, which loses a genuinely interesting flow; and keeping the source's name, which leaves the most misleading row in the table looking exactly like the others.

**Status:** implemented.

### One system price column rather than a buy and sell pair

`fct_half_hour` carries a single `system_price`.

**Why:** GB moved to single cash-out pricing in 2015, and the two columns are identical across all 119,133 staging rows. Carrying both would invite a dashboard to plot a spread that is always zero.

**Rejected:** Both columns for source fidelity, which the raw layer already provides. A warn-severity test asserts they stay equal, so a return to dual pricing announces itself rather than being silently averaged away.

**Status:** implemented.

### Regional modelling covers intensity and mix, not demand

`fct_regional` holds forecast intensity and nine fuel shares for 18 regions, and no demand at all.

**Why:** No ingested source publishes demand below national level. England and Wales together is as far down as it goes, and that sits on the half-hourly fact. Saying so in the model's description is what stops somebody looking for it. The regions also nest, since 15 to 17 are the nations and 18 is GB, so a `region_type` column exists to make filtering to the 14 distribution regions the obvious move. Averaging across all 18 rows shifts carbon intensity by about 4 gCO2/kWh, which is small enough that nothing would ever flag it.

**Rejected:** Regional demand, which cannot be sourced; and leaving the aggregates out, which would lose the nation comparison the regional story is built on.

**Status:** implemented.

### Column documentation is persisted into the database

`persist_docs` writes every model and column description into Postgres comments on each build.

**Why:** The guards this layer depends on are all written as prose: filter regions to distribution level before averaging, exclude the Scottish boundary from imports, stop lead-time comparisons at 21.75 hours, treat regional intensity as forecast only. A dashboard reads column help text from the database, so without this the warnings reach anybody reading the repository and nobody using the data.

**Rejected:** Repeating the caveats in the dashboard, which puts the same rule in two places and lets them diverge.

**Status:** implemented.

### Local settlement periods are numbered by position, not by clock arithmetic

`london_settlement_period` counts rows within a local date, ordered by the UTC instant, rather than deriving a number from the local time.

**Why:** The industry numbers settlement periods from local midnight, so a day holds 46 periods when the clocks go forward and 50 when they go back. On the autumn change the wall clock reads 01:30 twice, and arithmetic on local time cannot separate those two half hours, so it would number them identically and end the day at 48. Counting position in a UTC-ordered sequence keeps them distinct and needs no special handling in either direction.

**Rejected:** Deriving the number from the local hour and minute, which is correct on 363 days a year and wrong on the two that the project exists to handle properly.

**Status:** implemented.


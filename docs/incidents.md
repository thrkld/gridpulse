# Incidents

Operational history from the point the pipeline started running unattended. Format: what happened, what caused it, how it was resolved, and what changed as a result.

---

## 2026-08-06: Dagster deployed, scheduled runs began

Dagster runs on an Azure VM in Sweden Central, in the same region as the managed Postgres it writes to. The webserver and daemon run as two containers from one image, and Dagster's own run and schedule state is held in a separate `dagster` database on the same server.

The first unattended run fired at 09:00 UTC and landed carbon intensity data with nothing running locally.

## 2026-08-06: Webserver returned no data, database unreachable from the VM

Both containers started and stayed up, but the UI returned an empty response through the SSH tunnel rather than an error page.

**Cause:** the VM's public IP had not been added to the Postgres firewall. Dagster could not reach its own storage database, so the webserver retried in a loop instead of serving. The container logs showed repeated connection timeouts, which is what distinguishes a blocked route from a rejected login.

**Resolution:** added the VM's outbound address, taken from `curl ifconfig.me`, as a firewall rule on the server. Dagster reconnected on its next retry without needing a restart.

**Changed as a result:** nothing in the code. The firewall is address based, so any change to the VM's IP will cause the same failure, which is why the public IP is static.

## 2026-08-06: First image build failed on a name collision

`docker compose up --build` failed with `image "gridpulse-dagster:latest": already exists`, even though the image had been built.

**Cause:** both services declared a build and shared one image tag, so Compose built them in parallel and the two builds collided writing the same tag.

**Resolution:** the webserver builds the image and the daemon references the finished tag.

**Changed as a result:** `deploy/docker-compose.yml` now has a single build definition.

## 2026-08-23 to 2026-08-26: Pipeline down for three days after swap disappeared

Ingestion stopped entirely. NESO made its last run on the 23rd at 10:00, the half-hourly sources struggled on until the 25th at around 14:00, and nothing ran again until the 26th at 21:00. The 24th recorded no runs at all.

**Cause:** the 2 GB swapfile was no longer active. With 842 MiB of RAM and nothing to fall back on, the load average reached 15 on a single core. Dagster could not reach Postgres, and the machine was too starved to accept an SSH session, serve the serial console or answer the VM agent promptly, which is why it took so long to diagnose from outside.

**Resolution:** recreated the swapfile through the portal's Run command, which was the only route in that still worked. Ingestion resumed on its own once memory pressure eased, because every schedule fires on its own cron and Dagster retries rather than giving up.

**Changed as a result:** nothing in the code, and that is the uncomfortable part. Nothing yet checks that swap is present, and it is load-bearing rather than a nicety: this machine cannot run Dagster's three processes without it. Why the swapfile vanished has not been established.

**What recovered and what did not:** NESO healed completely on its own, because every fetch pulls a rolling window reaching back to the start of the previous month. Elexon imbalance and demand outturn healed too, since both are re-fetched for yesterday and today on every run. Market index, the demand forecast and regional carbon intensity all needed re-fetching by hand, the first two because the wider catch-up window had been written but not yet deployed, and regional because its sweep skips it by design.

**How it was found:** the `no_missing_periods` tests, written three days earlier, failed on the publication mart and located both gaps precisely. They were the first thing to notice the damage.

## 2026-08-27: dbt moved into the deployment, pipeline complete end to end

Until today the marts only existed because they were built by hand from a laptop. Ingestion ran unattended and wrote to the raw layer every thirty minutes, but nothing rebuilt anything on top of it, so the modelled tables aged from the moment they were made.

dbt now runs on the VM through `dagster-dbt`. Every model and test is an asset in the same graph as the ingestion, and the raw assets are keyed to match dbt's source names, so the lineage runs unbroken from the API call to the mart rather than stopping at the raw table.

Two cadences: the marts every six hours without the regional one, and the whole graph with all 205 tests at 01:00. The frequent run selects the marts rather than excluding the expensive model, because the cost is not in the mart at all. A full build spends 1,967 seconds of database time and 896 of those are tests against the fifteen million row regional generation view, so excluding the mart alone saves 11%. Staging is materialised as views and never needs rebuilding, and selecting only the marts brings the run to 202 seconds.

**How it went:** the image built with dbt on the first attempt. A full materialisation through the container passed 207 tests with 10 warnings, all of them source gaps already documented in probe findings, and the six-hourly job then ran clean. The marts now carry snapshots ingested at 18:03 rather than whatever a laptop last produced.

**Worth knowing for next time:** two schedules had to be enabled by hand after deploying, because the code does not set `default_status` and new schedules therefore arrive stopped. Nothing warns you about this, and the symptom would have been a pipeline that looked deployed and never ran.

**Still outstanding:** `dbt-core` is not pinned. It arrives as a transitive dependency of `dagster-dbt`, so the container built 1.11.14 while the laptop has 1.11.11, and a rebuild months from now could take something different again. The swapfile also still has no check on it, and its disappearance in August remains unexplained.

## 2026-08-27: swap is now checked, and the two large marts build incrementally

Two threads left open by the entries above are closed here.

**Swap.** The August outage ended with "nothing yet checks that swap is present, and it is load-bearing rather than a nicety". A Dagster asset now reads `SwapTotal` from `/proc/meminfo` on every half-hourly ingestion run and fails if it is zero. It rides on the existing schedule deliberately, because the deployment earlier today showed that a new schedule arrives stopped, and a health check nobody enabled would have been worse than none. This detects the condition rather than preventing it, and why the swapfile vanished is still unknown.

**Incremental builds.** `fct_regional` and `fct_demand_forecast_publication` were rebuilding in full on every run, 276 and 156 seconds, which is why the six-hourly schedule had to exclude one of them. Both now build incrementally and take 9 and 4 seconds.

The finding that made it work is worth recording, because the intuitive answer is wrong. Staging models are views over `jsonb_array_elements`, so filtering on `start_time` cannot be evaluated until after the payload has been exploded, while `ingested_at` is a real column on the raw table and filters before it. Same rows out, 344x the work: cost 98,098 against 33,712,757 on the regional generation view. An incremental model keyed on `start_time` would have looked correct and saved nothing.

`fct_demand_forecast_publication` needed more than a filter. Its latest-publication flag is a window over the whole period, and its outturn arrives up to 91.6 hours late, so a batch selected by arrival time never holds everything a period needs. It now replaces whole periods and reads its own earlier rows back for the periods a batch touches.

**How it was verified:** a full refresh, then two consecutive incremental runs. All three produced identical row counts and identical checksums on both tables, with exactly one latest-publication flag per period and no settled period missing its outturn.

**Also corrected:** `sql/raw_tables.sql` declared three indexes that did not exist on the cloud database, which had only primary keys. They have been applied. They are worth very little for these queries, since the raw heap is 99 pages and the win is entirely in the pushdown, but the repository was describing something untrue.

## 2026-08-28: ingestion down eight hours after the first full nightly dbt build

Ingestion stopped at 01:51 UTC and did not run again until the VM was restarted at about 10:45. Twenty settlement periods were missing at the point it was noticed.

**Cause:** memory. Available memory fell below 5% at around 01:00, which is when `nightly_dbt_build` fires. This was the first full nightly build since dbt was added to the containers the previous day, so the machine was holding the Dagster webserver, the daemon, and a dbt process working through 217 nodes, on 842 MiB of RAM.

The reason it did not simply recover is that `deploy/dagster.yaml` configured `QueuedRunCoordinator` with no `max_concurrent_runs`, so nothing capped how many runs could execute at once. `six_hourly_dbt_build` at 00:00, `daily_sweep` at 00:15 and `nightly_dbt_build` at 01:00 were not queueing behind each other, they were competing, and ingestion was competing with all three. After the restart the same absent limit let the daemon launch five catch-up runs simultaneously, which was visible as five `multiprocessing-fork` workers holding about 360 MiB between them.

**Resolution:** restarted the VM from the portal. Run command hung rather than returning, the same symptom as August, because the agent could not get enough CPU to answer. Swap was present and active on reboot, so the fstab entry added the previous day did its job.

**Changed as a result:** `max_concurrent_runs: 1`, which is the actual fix and was simply never set. Alongside it, prod dbt threads dropped from 2 to 1, `nightly_dbt_build` moved from 01:00 to 04:00 so it no longer overlaps the 00:15 sweep, and `six_hourly_dbt_build` moved to 02:20 and every six hours from there, off both midnight and the half-hourly ingestion slots. The incremental marts written the same day cut the nightly build from about 11 minutes to 7 and a half, which shortens the pressure without reducing its peak.

**Two wrong turns worth recording.** The first diagnosis was the August failure repeating, a missing swapfile. It was not: swap was present throughout. The second was a full disk, reached because CPU sitting at 5% seemed to rule out memory exhaustion. That was backwards, since low CPU was the aftermath of processes dying rather than evidence against it. The portal's available-memory metric settled it. Both detours cost time that a memory check on the host would have saved.

**Still outstanding:** the swap asset added the previous day checks that swap exists, and would have passed cleanly through this entire incident. Available memory is the thing worth alerting on, and nothing watches it. The honest structural answer is that 842 MiB was adequate for ingestion alone and is not adequate for ingestion plus Dagster plus dbt, so a resize to a size with 2 GiB is the fix that stops this being managed around.

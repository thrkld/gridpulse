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

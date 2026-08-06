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

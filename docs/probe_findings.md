# Findings

## stg_ci_national

- Latency
    Ingestion time maps to last entire snapshot as would expect
    (i.e ingested_at 04:11 or 04:00 maps to start_time 3:30)

- Anomalies
    Intensity Actual had an empty value in one instance

## stg_ci_national_generation

- Latency
    See stg_ci_national

- Anomalies
    N/A

## stg_ci_regional

- Latency
    See stg_ci_national

- Anomalies
    N/A

## stg_ci_regional_generational

- Latency
    See stg_ci_national

- Anomalies
    N/A

## stg_elexon_imbalance

- Latency
   skip from ingested_at 10:30pm start time to 12:00am.

   fix: fetch yesterday also, required for UTC/current time split

## stg_elexon_market_imbalance

- Anomalies
    N2EXMIDP automatically 0, fills up when half hour starts

- Latency
    end time maps as stg_ci_national for APXMIDP, fills up once end_time has passed

## stg_neso

- Latency
    No update observed during the entire probe window (48 snapshots over 27h).
    Latest actual stayed at start_time 2026-07-07 07:00 UTC throughout; all snapshots identical. Refresh cadence is slower than daily. Probe window too short to measure. Half-hourly ingestion is pointless for this source; daily (or less) is sufficient. Re-probe over several days to find the update time.

- Anomalies
    F rows have ND/TSD = 0; demand fields only populated on A rows.
    Full-snapshot endpoint: ~2,100 records per call, so staging holds 48 duplicate copies (~102k rows) needs mart-side dedup.
    One read timeout (30s) on 2026-07-07 18:00 UTC probe.
    Stray manual ingest from 2026-06-21 present in neso_raw.

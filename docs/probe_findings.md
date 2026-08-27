# Source findings

## Publication timing (July 2026 half-hourly probe)
### stg_ci_national

- Latency
    Ingestion time maps to last entire snapshot as would expect
    (i.e ingested_at 04:11 or 04:00 maps to start_time 3:30)

- Anomalies
    Intensity Actual had an empty value in one instance

### stg_ci_national_generation

- Latency
    See stg_ci_national

- Anomalies
    N/A

### stg_ci_regional

- Latency
    See stg_ci_national

- Anomalies
    N/A

### stg_ci_regional_generation

- Latency
    See stg_ci_national

- Anomalies
    N/A

### stg_elexon_imbalance

- Latency
    settlement_date rolls over at 00:00 UK local

    from_date : first start_time maps to 00:00 LOCAL on first day date

    to_date : last record is safely readable half an hour behind ingestion time, i.e 9:30 end time will be fetchable from 10:00

- Anomalies
    N/A

### stg_elexon_market_index

- Anomalies
    N2EXMIDP automatically 0, fills up when half hour starts

- Latency
    end time maps as stg_ci_national for APXMIDP, fills up once end_time has passed

### stg_neso

- Latency
    No update within either probe window; all snapshots identical.
    Between runs the actuals cutoff advanced 2026-07-07 07:00 UTC -> 2026-07-09 07:00 UTC, and portal last_modified was 08:20 UTC. 
    Jul 8 refresh never appeared during a full-day watch, so timing is not reliable day to day.
    Half-hourly ingestion pointless; ingest twice daily - One sweep at 10am, once at 10pm, checking if last_modified is updated.

- Anomalies
    F rows have ND/TSD = 0; demand fields only populated on A rows.
    Full-snapshot endpoint: ~2,100 records per call, so staging holds 48 duplicate copies (~102k rows) needs mart-side dedup.
    One read timeout (30s) on 2026-07-07 18:00 UTC probe.
    Stray manual ingest from 2026-06-21 present in neso_raw.

## Backfill findings (August 2026)
### Carbon Intensity
- /generation returns `data` as an object for the single endpoint but an array for the ranged one.
- Regional range endpoint rejects 14 days (400); national/generation accept 14
- Forecast gaps: 2025-01-12/13 (27 periods), 2025-08-10/11 (18)
- Occasional transient 500s on valid requests
- /generation truncates any range that crosses 1 January, returning 200 with the
  data up to 31 December and nothing after it. A 14-day request spanning new year
  came back with 97 of 673 records. /intensity does not do this over the same range,
  which is why national kept the data and generation lost it. Reproducible on demand,
  so chunks must stop at the year boundary.
- Three windows are absent from /generation entirely and cannot be re-fetched:
  2024-06-11/12 (22 periods), 2025-01-12/13 (17) and 2025-08-10/11 (8). The first is
  missing from /intensity too, so that one is an outage across the whole API. The other
  two are the same events that show as null forecasts in the national data above.

### Elexon
- market-index rejects ranges >7 days (400)
- Chunk boundaries are inclusive therefore consecutive chunks duplicate one period

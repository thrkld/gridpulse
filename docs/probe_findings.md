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
    A rows are not always populated either: 12 rows across 6 periods in August 2026
    carry the settled indicator with ND, England/Wales demand and all 11 flows at
    zero, and TSD at 500. Five healed on a later snapshot, one has not, so the
    marts require a settled marker AND a demand above zero before reading the row.

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
  2024-06-11/12 (22 periods), 2025-01-12/13 (17) and 2025-08-10/11 (8), so 47 in total,
  against 31 on /intensity, which loses only the June window but loses more of it. The
  endpoints therefore degraded by different amounts in the same outage. Re-fetching was
  attempted twice and returned a handful of records each time, so the data does not exist.

### Elexon
- market-index rejects ranges >7 days (400)
- Chunk boundaries are inclusive therefore consecutive chunks duplicate one period

### Cross-source recovery and permanent gaps
- NESO publishes a Historic GB Generation Mix dataset (resource
  f93d1835-75bc-43e5-84ad-12472b180a98) which does hold those windows, along with 309,476
  half-hourly rows reaching back well before 2024 and generation in MW rather than only
  percentages. It is the route to a longer baseline if one is ever wanted.
- Its wind is defined differently from the API's. NESO splits transmission-connected
  WIND from estimated WIND_EMB, while the API reports the two combined, so the mapping is
  WIND_perc + WIND_EMB_perc, which matches the API to within 0.4 points. Transmission wind
  is metered and embedded wind is modelled, so the split is more informative rather than
  more accurate.
- Carbon intensity itself differs between the two by about 14 gCO2/kWh on average.
  Overnight periods agree within a point, so the divergence is in daytime periods and
  embedded solar is the likely cause, but this has not been established. Patching the
  gaps from this source would therefore splice in periods measuring something slightly
  different from their neighbours, which is why the gaps are left documented instead.

## Marts findings (August 2026)

- Elexon stops publishing the demand forecast at a fixed time of day rather than at a
  fixed lead, so the longest lead available depends on the period: 44.75 hours for a
  04:00 period against 21.75 for an 05:00 one. Above 21.75 hours the sample is
  therefore overnight periods only, whose demand is low and flat, and mean absolute
  error falls from 681 MW at 22 hours to 468 MW at 44. That is the sample changing,
  not the forecast improving, so comparisons across lead time have to stop at 21.75
  hours. `fct_demand_forecast_publication.is_comparable_lead` carries the cutoff.
- Greenlink is published from 2024-01-01 but reads exactly zero until 2024-09-12,
  which is when the link energised. It is never null. Roughly 42% of its rows are
  zero, and most of that is the eight months before it existed rather than idle time.
- APX publishes zero for both price and volume until a period opens for trading. 19
  periods since 2024 never filled in, so a zero price there means unknown rather than
  free. Those are nulled in the marts; the two periods that cleared at zero with real
  volume behind them are kept.
- The imbalance revision clock and arrival order have never disagreed: of 953 periods
  Elexon revised, ordering by `created_datetime` and ordering by `ingested_at` pick
  the same row every time. The revision clock is still the correct key, but it is
  defensive rather than load-bearing today.

## Forecast and calendar audit (18 September 2026)

Reproduce the checks with `python scripts/audit_forecast_data.py`. They use a
read-only transaction against the configured database. Counts below describe the
original audit snapshot; subsequent ingestion and repairs can change them.

### INDO publication latency and ingestion latency are different

Across 47,594 target periods, first publication was 0.5 hours after `start_time`
at both the median and p99. The maximum was 5.12 hours before the live era and
1.8 hours from 6 August onwards. There were 69 pre-live and two live periods
above one hour. No period in the stored snapshots had more than one distinct
non-null national-demand value. This is evidence of no observed revisions in
that sample, not a guarantee that INDO cannot revise.

Live-era first ingestion had a median delay of 1.01 hours and a maximum of
112.83 hours. The earlier 91.6-hour figure in the incremental model referred to
pipeline arrival, not Elexon publication. The five-day overlap is retained for
arrival-time processing and catch-up; backfilled rows carry a new ingestion time.

For an as-of feature, use the actual source publication time. To replay what this
pipeline could have known, also require the snapshot's ingestion time to precede
the prediction origin. A fixed 30-minute or one-hour delay cannot cover the
observed exceptions or outages. The forecast mart retains the latest ingestion
of each publication, not its first arrival, and drops outturn publication time;
use staging/raw history when reconstructing availability.

### A forecast can cover every target period and still be missing publications

The original audit found 1,655 forecast rows in 30 publication slots on
23 August, ending at 14:47 UTC, versus 2,816 rows in 48 slots on surrounding
days. The missing slots ran from 15:17 to 23:47 UTC. On the target side,
24 August had a median of 40.5 publications and 25 comparable publications,
against 58 and 43 in the baseline. The observed baseline range was 35–82
publications per target period; it is not an invariant count.

`no_missing_periods` could not detect this because each target still had at least
one forecast. A publication-time coverage check is now included, using the
observed half-hourly cadence from 20 July and warning after two UTC days of grace.
It detects missing slots, including gaps at the end of the dataset. It does not
prove that every slot contains all its expected targets, or that the publisher
will always retain this cadence. The dashboard also shows forecast row counts.

Verification during implementation corrected the chat's claim that timestamps
always fall at :17/:47. Across July–September they vary, including :16, :18,
:45 and :48. The check bins actual timestamps into UTC half-hour windows rather
than expecting an exact minute. Exact-minute matching produced 1,116 false or
unverified gaps before this correction.

The 23 August repair restored 2,816 rows and all 48 half-hour windows. Three
empty windows remain on 6 August (10:30, 12:00 and 12:30 UTC). A fresh NDF API
read from 10:00–14:00 returned exactly the same 511 unique target/publication
keys as the mart, with no missing or extra keys. Publications instead arrived
at 13:12, 13:20 and 13:28. These are source-cadence gaps, not evidence that our
ingestion lost those publications. The warning is retained rather than masking
the date or inventing forecasts.

The dashboard's demand comparison selects one publication at each requested
horizon and only scores targets with all six horizons available. It rejects
forecasts older than 30 minutes at that origin, so an outage cannot silently
substitute a nine-hour-old forecast. It measures historical publisher accuracy,
including backfills, rather than replaying the pipeline's live availability.

### Holiday demand differs substantially from nearby weekdays

The audit compared 22 England/Wales bank holidays in 2024–2026 with the same
weekday within ±28 days, excluding other listed holidays. Mean INDO demand was
2.4–28.1% lower. Christmas, Boxing Day and New Year were 18.6–28.1% lower;
Early May was 6.0–6.8% lower. Easter Monday ranged from 3.0% to 18.9% lower.

These are descriptive differences, not causal estimates or fixed forecast
adjustments. The original query accepted days with at least 44 outturns,
comparators near the history boundary are one-sided, and the Christmas baseline
includes other holiday-season weekdays. Weather and year-to-year changes are
not controlled. A future model should consider nation-specific bank holidays
and the Christmas/New Year period as calendar features. No holiday feature has
been added to the spine as part of the dashboard work.

### Limits for future forecasting consumers

- `fct_half_hour` and the regional/mix marts contain latest-known values. Target
  period demand, mix, price and intensity are not valid advance predictors.
  Even lagged values need availability checks when revisions or outages matter.
- National CI ingestion currently uses the current-period and historical range
  endpoints, not a forward forecast endpoint. Its stored forecast error cannot
  be interpreted as a day-ahead forecast score.
- A seven-day UTC lag can shift local clock time across DST. Define how repeated
  and missing local half-hours are matched before using seasonal lag features.
- Changing embedded generation means 2024 and 2026 are not interchangeable
  training populations. Use chronological evaluation and report seasonal errors.

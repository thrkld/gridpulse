# Dashboard data audit — 19 September 2026

The July–September changes do not indicate a general break when scheduled
collection started. The main limitations are **inconsistent historical solar
revisions**, **small missed carbon revisions** and **time-of-day selection in
demand forecast comparisons**. The carbon error spike remains in fresh source
responses; missing data does not explain it.

This report covers all 15 managed Metabase questions. July and August are
complete months; September means **1–18 September**, using London dates.
Findings and action statuses describe the September 19 audit, not a live health
check. The solar description below reflects the subsequently updated solar-only
chart; the audit measurements are unchanged.

## Monthly comparison

| Measure | July 2026 | August 2026 | September 1–18 |
|---|---:|---:|---:|
| Expected half-hours | 1,488 | 1,488 | 864 |
| Carbon forecast/actual pairs | 1,488 | 1,488 | 864 |
| Carbon forecast MAE, gCO₂/kWh | 9.36 | 12.37 | 16.10 |
| Carbon bias, forecast minus actual | −0.84 | −1.27 | −5.38 |
| APX priced half-hours | 1,482 | 1,488 | 860 |
| Mean APX price, £/MWh | 106.22 | 129.87 | 130.85 |
| Negative-price half-hours | 76 | 10 | 38 |
| Negative share of known prices | 5.13% | 0.67% | 4.42% |
| Mean absolute imbalance/APX spread, £/MWh | 19.94 | 23.60 | 29.14 |
| Settled, positive NESO demand half-hours | 1,488 | 1,488 | 863 |
| Mean national demand, MW | 21,849 | 22,073 | 23,284 |
| Mean wind share | 23.92% | 23.69% | 40.76% |
| Mean solar share | 13.75% | 10.94% | 7.08% |
| Net imports / demand, matched half-hours | 20.01% | 15.24% | 5.10% |

MAE is the average absolute difference between forecast and actual; bias keeps
the sign. These figures describe changes, not their weather or market causes.
Complete coverage does not establish that values are correct or final.

Scheduled collection began on **6 August**. Carbon history was first loaded on
4 August and substantially re-fetched on 25 August. Historical forecasts can
therefore predate the pipeline without having been collected in real time.

## Carbon: the error spike survives source checks

Comparing only days 1–18 of each month gives MAE of **8.99 → 11.67 → 16.10**.
September being incomplete does not, by itself, explain the increase.

| Period | MAE, gCO₂/kWh | Finding |
|---|---:|---|
| August 1–5 | 12.18 | Elevated before scheduled collection began |
| August 6–30 | 11.34 | No upward step at the collection boundary |
| August 31 | 39.08 | All signed errors are non-negative |
| September 1–8 | 23.61 | Main concentration of high September errors |
| September 9–18 | 10.09 | Closer to the earlier baseline |

Fresh API responses were compared with all **3,840 half-hours** in the window:

- Every forecast and every July actual matched.
- Thirty August actuals differed on August 24, 26 and 27, by at most 5 gCO₂/kWh.
- Nineteen September actuals differed, all on September 18, by at most 2.
- Fresh values changed monthly MAE to **9.36, 12.40 and 16.12**, leaving the spike intact.

The mart matched the latest stored raw values throughout, so these differences
were not introduced by dbt. August's missed revisions fall outside the routine
48-hour sweep and are consistent with incomplete catch-up around the outages.
September 18 was still within the normal refresh window.

The spike is present in the provider's values, but its cause remains unverified:
forecasting error, actual-intensity error and difficult conditions are not
distinguished here. The endpoint supplies no forecast publication timestamp,
so this is not a comparison at a fixed number of hours ahead or a reconstruction
of what the pipeline knew at the time.

## Demand forecasts: comparable samples, incomplete daily coverage

Each forecast lead time is scored against the same target half-hours. That
retains **73.9% of July, 74.1% of August and 75.0% of September**: respectively
1,099/1,488, 1,103/1,488 and 648/864 targets.

| Hours ahead | July MAE, MW | August MAE, MW | September 1–18 MAE, MW |
|---|---:|---:|---:|
| 0.5 | 549.5 | 536.0 | 603.0 |
| 1 | 559.3 | 540.4 | 604.3 |
| 2 | 574.0 | 545.4 | 618.4 |
| 4 | 596.8 | 549.5 | 650.5 |
| 8 | 649.9 | 545.8 | 670.4 |
| 21 | 741.5 | 616.0 | 729.8 |

“Hours ahead” specifies when the forecast is selected. The latest publication
available then must be no more than 30 minutes old. For example, forecasts
selected 0.5 hours ahead were actually published about 0.717 hours ahead on
average. This freshness limit prevents old forecasts from silently filling gaps.

The exclusions are not evenly distributed. September excludes every target in
the 05:00, 07:00 and 08:00 London hours, plus parts of other hours. Removing the
21-hour comparison would retain 89.6% of targets, not all of them. The chart is
a fair comparison between lead times **within its sample**, not a measure of
accuracy across every time of day.

Fresh NDF responses for September 1–2 publication days matched all **5,632**
target/publication keys and values in the mart. This supports source availability
as the explanation for exclusions on those days, but is not a full-history
reconciliation. Backfilled publications are included: this measures historical
publisher accuracy rather than live pipeline availability.

## Solar: historical revisions were collected inconsistently

Two checks confirmed that the series mixes older and newer estimates:

- All **248 July midday solar estimates** changed between stored snapshots
  collected August 4–31. The mean revision was **+278.91 MW**, about 2.3%, and
  the largest was 360 MW. Demand and embedded wind were unchanged.
- Comparing **11,566 periods** with NESO's fresh 2026 historic resource found
  **4,163 differing solar values in January–June**. Demand and embedded wind
  agreed throughout. July and the available August subset matched; the response
  contained only 1,392 August periods, not the full month.

| 2026 month | Solar half-hours differing | Stored midday mean, MW | Fresh midday mean, MW |
|---|---:|---:|---:|
| January | 380 | 2,821.20 | 2,825.52 |
| February | 416 | 3,300.55 | 3,305.63 |
| March | 663 | 7,208.34 | 7,222.81 |
| April | 791 | 10,907.56 | 10,958.56 |
| May | 942 | 10,317.75 | 10,450.04 |
| June | 971 | 10,189.77 | 10,397.12 |
| July | 0 | 12,283.15 | 12,283.15 |

Periods were matched through elapsed UTC half-hours, including the spring clock
change. The rolling feed captured July's revisions but could not revisit every
earlier month. Both the solar line and “demand plus embedded solar” inherit this
inconsistency. The chart adds back **solar only**, not wind; it is not a causal
estimate of demand without solar. Carbon intensity and generation-share charts
use a different source and are unaffected by these NESO revisions.

The revision is too small to explain the entire reported July-on-July increase,
but the remainder is not independently verified physical growth. Solar is
estimated, and the 2024/2025 historic resources were not reconciled.

## Chart-by-chart checks

| Chart | Finding or limitation |
|---|---|
| Carbon intensity by half-hour | Matched carbon/price periods only; clock-change days excluded. The all-history minimum at 13:00 is barely below 12:30: 108.2 versus 108.3 gCO₂/kWh. It is not a universal best time. |
| Wholesale price by half-hour | The monthly minimum is 13:30 in all three months. The shared carbon/price sample mixes seasons; APX is a wholesale index, not a household tariff. |
| Cheap/low-carbon overlap | 61.0% overlap between each day's cheapest and lowest-carbon quarters across 977 complete days. Boundary ties share weight; clock-change days are excluded. Descriptive, not a significance test. |
| Carbon forecast error | Complete pairs; the spike survives equal-length and fresh-source checks. See the carbon section. |
| Demand forecast error | Same targets at all six lead times, but time-of-day exclusions limit representativeness. See the demand section. |
| Imbalance price by conditions | The 45–50 GW / 0–20% renewables bin has only six observations, averaging £1,967/MWh. All nine fuel categories were present; share totals of 99.8–100.2% are consistent with rounding. |
| Net imports relative to demand | The decline survives the complete-ten-link rule; only September's invalid NESO period is excluded. This is a net-flow/demand ratio, not traced imported consumption. |
| Negative-price frequency | Uses known prices as its denominator. All ten August negative half-hours occurred on August 8, not ten independent days. |
| Conditions by price sign | Negative-price periods have higher mean renewable shares in each month. The comparison does not control for time, season or demand; August's negative sample is one day. |
| Imbalance–wholesale gap | Removing absolute spreads above £100 still gives monthly means of £19.74 → £22.99 → £28.04/MWh. Recent prices can revise; the gap is not a participant's realised cash cost. |
| Midday demand and solar | Completed months only; July and August each have 248 midday observations. Complete coverage does not resolve the historical-revision issue above. |
| Nations | 4,320 common half-hours per nation in the 90-day card. Regional intensity is forecast-only; equivalent forecast vintages were not verified. |
| Imports by country | 4,319 common half-hours per counterparty. Links are summed before averaging and the Scottish boundary is excluded. Net averages can hide two-way flows. |
| Monthly coverage | Exposes missing prices and invalid demand, but not stale revisions or live availability. Regional, fuel, interconnector and forecast-sample completeness required separate checks. |
| Daily publication coverage | Three empty slots on August 6; August 23 is repaired. A full set of UTC publication slots does not guarantee every target has every requested lead time. |

Monthly, all-history and rolling 90-day results should not be quoted
interchangeably. For example, August demand MAE is 536 → 616 MW, while the
all-history chart at audit time was 503.6 → 653.3 MW.

## Source gaps and follow-up actions

Fresh responses confirmed ten APX gaps: July 27 at 02:00–04:30 UTC and
September 11 at 22:00–23:30 UTC. Each returned zero price **and** zero volume;
these are excluded as unknown prices, not counted as free electricity.

NESO's September 18 14:00 UTC row was marked settled but had zero national
demand and flows. The positive-demand guard correctly excludes it. Across seven
sampled July–September dates, valid NESO demand, embedded generation and total
cross-border flow matched the mart. This was a spot check, not full validation
of the source's estimates.

The following actions were **not applied by this audit**:

| Issue | Follow-up |
|---|---|
| Mixed solar revisions | Refresh 2026 history and rebuild affected marts. Schedule historical refreshes with prior-year overlap at year-end; check earlier years before multi-year claims. Preserve append-only snapshots. |
| Missed carbon revisions | Re-fetch August 24–27, rebuild and verify. Recheck September 18 after its normal sweep. Add checks for periods last observed too early to capture revisions. |
| Partial months | Show month-to-date labels, through-dates and matched counts; retain completed months for solar. A high partial-month MAE is not automatically an error. |
| Demand sample exclusions | Show inclusion rates and clock-time coverage. Keep the matched comparison and freshness limit; do not fill missing forecasts with zero. |
| Sparse groups | Flag low-count imbalance bins and show day/event counts for negative-price groups. Keep unusual observations rather than removing them to smooth results. |
| Coverage blind spots | Distinguish missing rows, missing components, revisions and live arrival; add regional, per-link and forecast lead-time checks. |
| Known publication gaps | Record acknowledged source-timing exceptions while retaining historical visibility and alerts for new gaps, rather than moving the test start date past them. |

Historical Carbon Intensity endpoint gaps still affect some 2024/2025 samples.
They should not be filled from differently defined NESO data. Imbalance-price
sweeps revisit 7/35 days; later reconciliation remains outside project scope.

## Reproduction and verification

```bash
python scripts/audit_dashboard_data.py --as-of 2026-09-19
python scripts/audit_dashboard_data.py --as-of 2026-09-19 --compare-carbon
python scripts/audit_dashboard_data.py --as-of 2026-09-19 --compare-neso
python scripts/audit_dashboard_data.py --as-of 2026-09-19 --check demand_sample_by_hour
make check
```

The script uses read-only database transactions; source comparisons fetch
without inserting. `--as-of` is an exclusive London **target-date cutoff**, not
a reconstruction of the database at that time. Later revisions and backfills
can change rerun results.

On September 19, all 15 deployed SQL definitions matched the repository and all
five checked fact-table grains were unique. Formatting, lint and 74 tests passed;
10 opt-in integration tests were skipped. The audit did not rebuild marts, rerun
the full dbt or disposable-Metabase integration tests, visually inspect every
chart, or verify the VM's deployed code. No source data or dashboards were changed.

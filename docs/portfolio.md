# GridPulse — electricity data analytics

GridPulse brings together public electricity data from Elexon, NESO and the
Carbon Intensity API to analyse Great Britain's demand, carbon intensity and
wholesale prices. Python ingestion, PostgreSQL and dbt turn source responses
into comparable half-hourly datasets. Metabase questions and a 14-chart report
present the findings alongside sample definitions, limitations and supporting
figures.

## CV wording

**GridPulse | Personal data analytics project | Python, SQL, PostgreSQL, dbt, Metabase**

- Built an electricity analytics pipeline integrating three public APIs into
  PostgreSQL and modelling half-hourly datasets with SQL and dbt.
- Analysed daily carbon and price patterns, demand forecast accuracy from 30 minutes to 21 hours ahead, embedded solar, country-level electricity flows, imbalance–wholesale price gaps and
  conditions associated with negative prices.
- Developed reproducible visualisations in Matplotlib and repository-managed
  Metabase questions, using matched samples, explicit missing-data handling and
  documented limitations to support interpretation.

For a shorter CV entry:

> Built a Python, SQL and dbt analytics project integrating three public
> electricity APIs; evaluated demand forecasts from 30 minutes to 21 hours ahead and produced
> reproducible dashboards covering carbon intensity, prices and grid demand.

## Talking about the analysis

- **Comparable samples:** compare carbon intensity and price on the same half
  hours, and score forecasts at all six advance timings on the same target periods.
- **Meaningful measures:** use mean absolute error for forecast accuracy, known
  prices as the denominator for negative-price frequency, and aggregate flows
  relative to demand for the imports ratio.
- **Data quality:** preserve source revisions, account for clock changes,
  distinguish missing observations from zero, and expose the figures behind each
  chart.
- **Interpretation:** distinguish historical average patterns from daily
  coincidence, forecast values from actual observations, and associations from
  causal effects. Explain how uneven solar revisions and recovered forecast
  publications affect the conclusions.

The forecast analysis evaluates Elexon's published forecasts; it does not claim
to build a forecasting model. The project demonstrates analytical methods and
reporting, without claiming measured commercial savings or business adoption.
Use numerical findings from a dated dashboard build when presenting results.

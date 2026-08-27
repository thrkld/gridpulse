from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetKey,
    Definitions,
    ScheduleDefinition,
    asset,
)
from dagster_dbt import (
    DbtCliResource,
    DbtProject,
    build_schedule_from_dbt_selection,
    dbt_assets,
)

from gridpulse.ingest.run_carbon_intensity import (
    run_latest as ci_run_latest,
    run_sweep as ci_run_sweep,
)
from gridpulse.ingest.run_elexon import (
    run_latest as elexon_run_latest,
    run_sweep_initial as elexon_run_sweep_initial,
    run_sweep_interim as elexon_run_sweep_interim,
)
from gridpulse.ingest.run_neso import run_latest as neso_run_latest


# `dagster dev` regenerates the manifest; the image ships one parsed at build time, so
# starting a container never depends on the database being reachable.
DBT_PROJECT = DbtProject(project_dir=Path(__file__).parents[3] / "dbt")
DBT_PROJECT.prepare_if_dev()


@dbt_assets(manifest=DBT_PROJECT.manifest_path, project=DBT_PROJECT)
def gridpulse_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


# These keys deliberately match the dbt source keys (source name + table name), so the
# Dagster graph connects the ingestions that update the raw tables to dbt's staging views.
@asset(key=AssetKey(["gridpulse", "carbon_intensity_raw"]))
def carbon_intensity_latest_raw():
    ci_run_latest()


@asset
def carbon_intensity_sweep_raw():
    ci_run_sweep()


@asset(key=AssetKey(["gridpulse", "elexon_raw"]))
def elexon_latest_raw():
    elexon_run_latest()


@asset
def elexon_sweep_initial_raw():
    elexon_run_sweep_initial()


@asset
def elexon_sweep_interim_raw():
    elexon_run_sweep_interim()


@asset(key=AssetKey(["gridpulse", "neso_raw"]))
def neso_latest_raw():
    neso_run_latest()


half_hourly_schedule = ScheduleDefinition(
    name="half_hourly_refresh",
    cron_schedule="*/30 * * * *",  # Runs every 30min
    target=[carbon_intensity_latest_raw, elexon_latest_raw],
    execution_timezone="UTC",
)

twice_daily_schedule = ScheduleDefinition(
    name="twice_daily_refresh",
    cron_schedule="0 10,22 * * *",  # Runs 10:00 and 22:00 UTC
    target=[neso_latest_raw],
    execution_timezone="UTC",
)

daily_schedule = ScheduleDefinition(
    name="daily_sweep",
    cron_schedule="15 0 * * *",  # Runs daily at 00:15 UTC
    target=[carbon_intensity_sweep_raw, elexon_sweep_interim_raw],
    execution_timezone="UTC",
)

weekly_schedule = ScheduleDefinition(
    name="weekly_sweep",
    cron_schedule="45 0 * * 0",  # Runs weekly at 00:45 UTC
    target=[elexon_sweep_initial_raw],
    execution_timezone="UTC",
)

# Staging is materialized as views, so only the mart tables need refreshing between
# full runs. Selecting marts alone skips the tests against the 15m row regional
# generation view, which are 896 of the 1,967 seconds a full build spends on the
# database. fct_regional is left out because it is a further 223 seconds and its
# intensity is forecast-only, so a day-old figure loses nothing.
six_hourly_dbt_schedule = build_schedule_from_dbt_selection(
    [gridpulse_dbt_assets],
    job_name="six_hourly_dbt_build",
    schedule_name="six_hourly_dbt_build",
    cron_schedule="0 */6 * * *",
    dbt_select="marts",
    dbt_exclude="fct_regional",
    execution_timezone="UTC",
)

nightly_dbt_schedule = build_schedule_from_dbt_selection(
    [gridpulse_dbt_assets],
    job_name="nightly_dbt_build",
    schedule_name="nightly_dbt_build",
    cron_schedule="0 1 * * *",
    execution_timezone="UTC",
)

defs = Definitions(
    schedules=[
        half_hourly_schedule,
        twice_daily_schedule,
        daily_schedule,
        weekly_schedule,
        six_hourly_dbt_schedule,
        nightly_dbt_schedule,
    ],
    assets=[
        gridpulse_dbt_assets,
        carbon_intensity_latest_raw,
        carbon_intensity_sweep_raw,
        elexon_latest_raw,
        elexon_sweep_initial_raw,
        elexon_sweep_interim_raw,
        neso_latest_raw,
    ],
    resources={"dbt": DbtCliResource(project_dir=DBT_PROJECT)},
)

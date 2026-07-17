from dagster import Definitions, asset, ScheduleDefinition

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


@asset
def carbon_intensity_latest_raw():
    ci_run_latest()


@asset
def carbon_intensity_sweep_raw():
    ci_run_sweep()


@asset
def elexon_latest_raw():
    elexon_run_latest()


@asset
def elexon_sweep_initial_raw():
    elexon_run_sweep_initial()


@asset
def elexon_sweep_interim_raw():
    elexon_run_sweep_interim()


@asset
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

defs = Definitions(
    schedules=[
        half_hourly_schedule,
        twice_daily_schedule,
        daily_schedule,
        weekly_schedule,
    ],
    assets=[
        carbon_intensity_latest_raw,
        carbon_intensity_sweep_raw,
        elexon_latest_raw,
        elexon_sweep_initial_raw,
        elexon_sweep_interim_raw,
        neso_latest_raw,
    ],
)

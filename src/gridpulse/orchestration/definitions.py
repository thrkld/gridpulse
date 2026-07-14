from dagster import Definitions, asset, ScheduleDefinition

from gridpulse.ingest.run_carbon_intensity import run_latest as ci_run_latest
from gridpulse.ingest.run_elexon import run_latest as elexon_run_latest
from gridpulse.ingest.run_neso import run_latest as neso_run_latest


@asset
def carbon_intensity_latest_raw():
    ci_run_latest()


@asset
def elexon_latest_raw():
    elexon_run_latest()


@asset
def neso_latest_raw():
    neso_run_latest()

half_hourly_schedule = ScheduleDefinition(
    name="half_hourly_refresh",
    cron_schedule="*/30 * * * *", # Runs every 30min
    target=[carbon_intensity_latest_raw,elexon_latest_raw],
    execution_timezone="UTC"
)

twice_daily_schedule = ScheduleDefinition(
    name="twice_daily_refresh",
    cron_schedule="0 10,22 * * *", # Runs 10am and 10pm
    target=[neso_latest_raw],
    execution_timezone="UTC"
)

defs = Definitions(
    schedules=[half_hourly_schedule,twice_daily_schedule],
    assets=[carbon_intensity_latest_raw, elexon_latest_raw, neso_latest_raw]
)

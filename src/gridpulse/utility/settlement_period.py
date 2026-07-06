from datetime import date, time, datetime, timedelta
from zoneinfo import ZoneInfo

"""
Helper functions that return universally agreed upon settlement periods and utc
times
RETURN
    settlement_date : start date (date UTC) 
    settlement_period : 1-48
        UTC
        1 = 00:00-00:30
        48 = 23:30-00:00
    start_time : datetime (UTC)
    end_time : datetime (UTC)
"""


# Carbon Intensity / Elexon : Start time in UTC
def carbon_elexon_dim(start_time: datetime) -> dict:
    end_time = start_time + timedelta(minutes=30)
    settlement_period = (start_time.hour * 2) + (start_time.minute // 30) + 1

    return {
        "settlement_date": start_time.date(),
        "settlement_period": settlement_period,
        "start_time": start_time,
        "end_time": end_time,
    }


# Neso : Only stores date and local settlement period - Last sunday of march = 46 periods, forward again 1 hour last sunday of october
def neso_dim(settlement_date_local: date, settlement_period_local: int):
    london = ZoneInfo("Europe/London")
    utc = ZoneInfo("UTC")

    utc_start = datetime.combine(
        settlement_date_local, time.min, tzinfo=london
    ).astimezone(utc)
    utc_start += timedelta(minutes=(settlement_period_local - 1) * 30)
    utc_end = utc_start + timedelta(minutes=30)

    return {
        "settlement_date": utc_start.date(),
        "settlement_period": utc_start.hour * 2 + utc_start.minute // 30 + 1,
        "start_time": utc_start,
        "end_time": utc_end,
    }

"""Create or update the managed GridPulse dashboard.

Set METABASE_API_KEY in .env, then run python scripts/provision_metabase.py.
SQL lives in scripts/metabase/. Re-running applies changes to managed cards.
"""

import argparse
import os
from pathlib import Path

import certifi
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

METABASE_URL = os.environ.get("METABASE_URL", "http://localhost:3002").rstrip("/")
API_KEY = os.environ.get("METABASE_API_KEY")
DB_NAME = "GridPulse marts"
COLLECTION_NAME = "GridPulse (managed)"
DASHBOARD_NAME = "GB electricity: carbon, price and demand"
MANAGED_DESCRIPTION = (
    "Managed by scripts/provision_metabase.py. Edit definitions in the repository."
)


def question(
    key,
    name,
    description,
    display="table",
    dimension=None,
    metrics=None,
    previous_names=(),
    settings=None,
):
    settings = dict(settings or {})
    if dimension:
        settings.update({"graph.dimensions": [dimension], "graph.metrics": metrics})
    return {
        "key": key,
        "name": name,
        "description": description,
        "display": display,
        "visualization_settings": settings,
        "previous_names": previous_names,
    }


QUESTIONS = [
    question(
        "greenest",
        "Average Carbon Intensity by half hour",
        "Average by London clock time since 2024, through yesterday. Clock-change days are excluded. ",
        "bar",
        "Local time",
        ["Carbon intensity gCO2/kWh"],
        previous_names=("Greenest half hour",),
    ),
    question(
        "cheapest",
        "Average Wholesale Price by half hour",
        "APX market index price, on the same periods as the carbon chart. ",
        "bar",
        "Local time",
        ["Market price GBP/MWh"],
        previous_names=("Cheapest half hour",),
    ),
    question(
        "daily_minima",
        "Overlap of Cheapest and Lowest-Carbon Half-Hours",
        "Overlap between each day's cheapest 25% and lowest-carbon 25% of half-hours, "
        "averaged since 2024. Complete days only, excluding clock changes; ties share weight equally.",
        "row",
        "Periods",
        ["Also greenest %", "Outside greenest %"],
        previous_names=(
            "How closely do greenest and cheapest periods align?",
            "Do the greenest and cheapest periods coincide?",
            "How often are cheap periods also low-carbon?",
            "Overlap of the cheapest and greenest six hours",
        ),
        settings={
            "stackable.stack_type": "stacked",
            "series_settings": {
                "Also greenest %": {"color": "#509B69"},
                "Outside greenest %": {"color": "#B8BDC5"},
            },
            "column_settings": {
                '["name","Also greenest %"]': {"suffix": "%", "decimals": 1},
                '["name","Outside greenest %"]': {"suffix": "%", "decimals": 1},
            },
            "graph.show_values": True,
            "graph.label_value_formatting": "full",
            "graph.y_axis.auto_range": False,
            "graph.y_axis.min": 0,
            "graph.y_axis.max": 100,
            "graph.x_axis.labels_enabled": False,
            "graph.y_axis.labels_enabled": False,
            "graph.show_goal": False,
        },
    ),
    question(
        "carbon_accuracy",
        "Average Carbon Forecast Error by Month",
        "Mean absolute error (MAE): the absolute difference between forecast and actual "
        "national carbon intensity for each half-hour, averaged by month. Only periods "
        "with both values are included; the current month is shown through yesterday. "
        "This is not a fixed-horizon forecast evaluation.",
        "line",
        "Month",
        ["MAE gCO2/kWh"],
        previous_names=("Carbon forecast error by month",),
    ),
    question(
        "demand_accuracy",
        "Average Demand Forecast Error by Hours Ahead",
        "Average absolute difference between Elexon's national demand forecast and actual demand. "
        "Hours ahead means how long before the predicted half-hour the forecast was published. "
        "Lower is better. Each point uses the same periods, with forecasts available at all six times.",
        "line",
        "Hours ahead",
        ["Average error (MW)"],
        previous_names=("Demand forecast error by horizon",),
    ),
    question(
        "imbalance_conditions",
        "Average Imbalance Price by Demand and Renewable Share",
        "Average imbalance price across different levels of demand and renewable generation. "
        "Renewables here means wind, solar and hydro. Groups with few half-hours may give unreliable averages.",
        previous_names=("Imbalance price by demand and renewable share",),
    ),
    question(
        "imports",
        "Net imports relative to national demand",
        "Monthly net electricity imports, expressed as a percentage of national demand. "
        "Positive values mean GB imported more than it exported. "
        "Includes only periods with complete interconnector data.",
        "line",
        "Month",
        ["Net imports / demand %"],
    ),
    question(
        "negative_frequency",
        "Negative Wholesale Price Frequency",
        "Percentage of half-hours with a wholesale price below £0/MWh in each month. "
        "Periods with missing prices are excluded.",
        "line",
        "Month",
        ["Negative price %"],
        previous_names=(
            "How often market prices go negative",
            "Percentage of Half-Hours with Negative Wholesale Prices by Month",
        ),
    ),
    question(
        "negative_conditions",
        "Grid Conditions by Price Sign",
        "Average demand, generation shares and carbon intensity during negative-price half-hours, compared with other half-hours. "
        "Both groups include only periods with all measurements available.",
        previous_names=("Grid conditions during negative prices",),
    ),
    question(
        "imbalance_spread",
        "Imbalance–Wholesale Price Gap",
        "Monthly average difference between imbalance and wholesale prices. "
        "Positive signed differences mean imbalance prices were higher; "
        "the absolute difference shows the average gap regardless of direction.",
        "line",
        "Month",
        ["Mean spread GBP/MWh", "Mean absolute spread GBP/MWh"],
        previous_names=("Imbalance price relative to wholesale",),
    ),
    question(
        "solar",
        "Midday National Demand and Embedded Solar",
        "Monthly averages between 11:00 and 15:00 London time, for completed months since 2024. "
        "National demand already reflects the reduction from embedded solar. "
        "Demand plus embedded solar adds that estimate back; subtracting it would "
        "count the reduction twice. The sum excludes other embedded generation, "
        "so it is not total consumption. Compare the same month across years.",
        "line",
        "Month",
        ["National demand MW", "Demand plus embedded solar MW", "Embedded solar MW"],
        previous_names=(
            "Midday demand and embedded generation",
            "Midday Demand and Estimated Solar ",
            "Midday Demand and Estimated Solar",
        ),
    ),
    question(
        "nations",
        "Forecast Carbon Intensity and Mix by Nation",
        "Average forecast carbon intensity and selected electricity shares for England, Scotland "
        "and Wales over the last 90 completed days. Each nation uses the same half-hours. "
        "Northern Ireland is not covered.",
        previous_names=(
            "How the nations' grids differ",
            "Average Forecast Carbon Intensity and Electricity Mix by Nation",
        ),
    ),
    question(
        "country_flows",
        "Average Net Electricity Imports by Country",
        "Average net electricity flow over the last 90 completed days. Positive values mean "
        "imports into GB; negative values mean exports. Connections to the same country are combined.",
        "row",
        "Country",
        ["Average net flow MW"],
        previous_names=("Net interconnector flow by counterparty",),
    ),
    question(
        "coverage",
        "Data coverage by month",
        "Available half-hourly records compared with the number expected each month. "
        "Gaps show where measurements are missing; present values may still be revised.",
    ),
    question(
        "publication_coverage",
        "Daily Demand Forecast Publication Coverage",
        "Number of 30-minute publication windows containing demand forecasts each UTC day, "
        "out of 48 expected. Missing windows may reflect collection gaps or irregular publication times. "
        "A present window does not guarantee every forecast is available.",
        previous_names=("Demand publication coverage by UTC day",),
    ),
]


def question_sql(spec):
    # These two charts must use exactly the same sample.
    filename = (
        "daily_pattern" if spec["key"] in {"greenest", "cheapest"} else spec["key"]
    )
    return (ROOT / "scripts" / "metabase" / f"{filename}.sql").read_text().strip()


def api(method, path, **kwargs):
    response = requests.request(
        method,
        f"{METABASE_URL}/api{path}",
        headers={"x-api-key": API_KEY},
        timeout=120,
        **kwargs,
    )
    if not response.ok:
        # Database errors can contain connection details.
        raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}")
    return response.json() if response.content else None


def find_by_name(items, name):
    matches = [item for item in items if item.get("name") == name]
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple objects named {name!r}; resolve the duplicate first."
        )
    return matches[0] if matches else None


def ensure_collection():
    existing = find_by_name(api("GET", "/collection"), COLLECTION_NAME)
    if existing:
        if existing.get("description") != MANAGED_DESCRIPTION:
            raise RuntimeError(
                "The collection name is already in use by an unmanaged collection."
            )
        return existing["id"]
    return api(
        "POST",
        "/collection",
        json={
            "name": COLLECTION_NAME,
            "description": MANAGED_DESCRIPTION,
        },
    )["id"]


def collection_items(collection_id):
    items = []
    while True:
        page = api(
            "GET",
            f"/collection/{collection_id}/items",
            params={"limit": 100, "offset": len(items)},
        )
        items.extend(page["data"])
        total = page.get("total")
        if len(page["data"]) < 100 or (total is not None and len(items) >= total):
            return items


def ensure_database():
    database_id = os.environ.get("METABASE_DATABASE_ID")
    if database_id:
        return api("GET", f"/database/{int(database_id)}")["id"]
    existing = find_by_name(api("GET", "/database")["data"], DB_NAME)
    if existing:
        return existing["id"]

    host = os.environ.get("METABASE_PGHOST", os.environ.get("PGHOST", "postgres"))
    local = host == "postgres"
    sslmode = os.environ.get(
        "METABASE_PGSSLMODE",
        "disable" if local else os.environ.get("PGSSLMODE", "require"),
    )
    details = {
        "host": host,
        "port": int(
            os.environ.get("METABASE_PGPORT", os.environ.get("PGPORT", "5432"))
        ),
        "dbname": os.environ.get(
            "METABASE_PGDATABASE", os.environ.get("PGDATABASE", "gridpulse")
        ),
        "user": os.environ.get(
            "METABASE_PGUSER", os.environ.get("PGUSER", "gridpulse")
        ),
        "password": os.environ.get("METABASE_PGPASSWORD")
        or os.environ.get("POSTGRES_PASSWORD" if local else "PGPASSWORD"),
        "ssl": sslmode != "disable",
        "ssl-mode": sslmode,
    }
    if not details["password"]:
        raise RuntimeError(
            "Set METABASE_PGPASSWORD or the appropriate Postgres password in .env."
        )
    if sslmode in {"verify-ca", "verify-full"}:
        certificate = Path(
            os.environ.get("METABASE_PGSSLROOTCERT")
            or os.environ.get("PGSSLROOTCERT")
            or certifi.where()
        )
        # The Python host's certificate path does not exist inside Metabase.
        details["ssl-root-cert-options"] = "uploaded"
        details["ssl-root-cert-value"] = certificate.read_text()
    return api(
        "POST",
        "/database",
        json={
            "name": DB_NAME,
            "engine": "postgres",
            "is_full_sync": False,
            "details": details,
        },
    )["id"]


def ensure_question(database_id, collection_id, spec, items):
    accepted_names = {spec["name"], *spec.get("previous_names", ())}
    matches = [
        item
        for item in items
        if item.get("model") == "card" and item.get("name") in accepted_names
    ]
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple managed questions match {spec['name']!r}; resolve the duplicate first."
        )
    existing = matches[0] if matches else None
    payload = {
        "name": spec["name"],
        "description": spec["description"],
        "collection_id": collection_id,
        "display": spec["display"],
        "dataset_query": {
            "type": "native",
            "database": database_id,
            "native": {"query": question_sql(spec)},
        },
        "visualization_settings": spec["visualization_settings"],
    }
    if existing:
        api("PUT", f"/card/{existing['id']}", json=payload)
        print(f"updated: {spec['name']}")
        return existing["id"]
    created = api("POST", "/card", json=payload)
    print(f"created: {spec['name']}")
    return created["id"]


def ensure_dashboard(collection_id, card_ids, items):
    existing = find_by_name(
        [item for item in items if item.get("model") == "dashboard"], DASHBOARD_NAME
    )
    payload = {
        "name": DASHBOARD_NAME,
        "collection_id": collection_id,
        "description": "GB electricity since 2024. Charts use completed days; solar uses completed months. "
        "Read question descriptions for definitions and check coverage tables before interpreting gaps. "
        "Models refresh every six hours, not in real time. This dashboard's layout is managed by the repository.",
    }
    dashboard_id = (
        existing["id"] if existing else api("POST", "/dashboard", json=payload)["id"]
    )
    dashboard = api("GET", f"/dashboard/{dashboard_id}")
    previous = {card["card_id"]: card for card in dashboard.get("dashcards", [])}
    dashcards = []
    for index, card_id in enumerate(card_ids):
        dashcards.append(
            {
                "id": previous.get(card_id, {}).get("id", -(index + 1)),
                "card_id": card_id,
                "row": (index // 2) * 8,
                "col": (index % 2) * 12,
                "size_x": 12,
                "size_y": 8,
                "parameter_mappings": [],
                "visualization_settings": {},
            }
        )
    api("PUT", f"/dashboard/{dashboard_id}", json={**payload, "dashcards": dashcards})
    return dashboard_id


def verify_cards(card_ids):
    for card_id in card_ids:
        result = api("POST", f"/card/{card_id}/query", json={"ignore_cache": True})
        if result.get("status") != "completed":
            raise RuntimeError(
                f"Question {card_id} failed to execute; inspect it in Metabase."
            )
        print(f"verified question {card_id}: {result.get('row_count', 0)} rows")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Execute every question after provisioning.",
    )
    args = parser.parse_args()
    if not API_KEY:
        parser.error(
            "Set METABASE_API_KEY in .env (Admin → Settings → Authentication → API keys)."
        )
    database_id = ensure_database()
    collection_id = ensure_collection()
    items = collection_items(collection_id)
    card_ids = [
        ensure_question(database_id, collection_id, spec, items) for spec in QUESTIONS
    ]
    dashboard_id = ensure_dashboard(collection_id, card_ids, items)
    if args.verify:
        verify_cards(card_ids)
    print(f"\n{METABASE_URL}/dashboard/{dashboard_id}")


if __name__ == "__main__":
    main()

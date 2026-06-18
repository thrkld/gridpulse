import requests
from datetime import datetime, date,timezone

headers = {
  'Accept': 'application/json'
}
# Ingests a single instance of the raw regional, national or generation data for carbon intensity
def fetch_regional_ci() -> dict:
  r = requests.get('https://api.carbonintensity.org.uk/regional', headers=headers, timeout=30)
  r.raise_for_status()
  return{
    "ingested_utc" : datetime.now(timezone.utc).isoformat(),
    "payload" : r.json()
  }

def fetch_national_ci() -> dict:
  n = requests.get('https://api.carbonintensity.org.uk/intensity', headers=headers, timeout=30)
  n.raise_for_status()
  return{
    "ingested_utc" : datetime.now(timezone.utc).isoformat(),
    "payload" : n.json()
  }

def fetch_generation_ci() -> dict:
  g = requests.get('https://api.carbonintensity.org.uk/generation', headers=headers, timeout=30)
  g.raise_for_status()
  return{
    "ingested_utc" : datetime.now(timezone.utc).isoformat(),
    "payload" : g.json()
  }


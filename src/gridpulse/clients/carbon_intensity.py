import requests
from datetime import datetime, date,timezone
headers = {
  'Accept': 'application/json'
}

# Ingests a single instance of the raw regional, national and generation data for carbon intensity
def carbon_intensity_ingestion() -> dict:
  r = requests.get('https://api.carbonintensity.org.uk/regional', params={}, headers = headers)
  n = requests.get('https://api.carbonintensity.org.uk/intensity', params={}, headers = headers)
  g = requests.get('https://api.carbonintensity.org.uk/generation', params={}, headers = headers)

  return {
    "ingested_utc" : datetime.now(timezone.utc).isoformat(),
    "regional_data" : r.json(),
    "national_data" : n.json(),
    "generation_data" : g.json()
  }
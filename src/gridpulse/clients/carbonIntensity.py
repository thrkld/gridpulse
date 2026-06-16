import requests
from datetime import datetime, date,timezone
headers = {
  'Accept': 'application/json'
}

# Ingests a single instance of the raw regional, national and generation data for carbon intensity
def carbonIntensityIngestion() -> dict:
  r = requests.get('https://api.carbonintensity.org.uk/regional', params={}, headers = headers)
  n = requests.get('https://api.carbonintensity.org.uk/intensity', params={}, headers = headers)
  g = requests.get('https://api.carbonintensity.org.uk/generation', params={}, headers = headers)

  return {
    "ingestedUTC" : datetime.now(timezone.utc).isoformat(),
    "regionalData" : r.json(),
    "nationalData" : n.json(),
    "generationData" : g.json()
  }
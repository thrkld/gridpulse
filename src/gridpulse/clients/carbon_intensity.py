import requests
headers = {
  'Accept': 'application/json'
}

# This is the data for one half hour
r = requests.get('https://api.carbonintensity.org.uk/regional', params={}, headers = headers)
regionalData = r.json()['data'][0]

n = requests.get('https://api.carbonintensity.org.uk/intensity', params={}, headers = headers)
g = requests.get('https://api.carbonintensity.org.uk/generation', params={}, headers = headers)
nationalData = n.json()['data'][0]
generationData = g.json()['data']


regional = [
    {
        "from" : regionalData["from"],
        "to" : regionalData["to"],
        "regionID" : r["regionid"],
        "shortName" : r["shortname"],
        "forecast" : r["intensity"]["forecast"],
        "index" : r["intensity"]["index"],
        "generationMix" : r["generationmix"]
    }
    for r in regionalData["regions"]
]

for row in regional:
    print(row)

national = [
    {
        "from" : nationalData["from"],
        "to" : nationalData["to"],
        "forecast" : nationalData["intensity"]["forecast"],
        "actual" : nationalData["intensity"]["actual"],
        "index" : nationalData["intensity"]["index"]
    }
]

generation = [
    {
        "from" : generationData["from"],
        "to" : generationData["to"],
        "generationMix" : generationData["generationmix"]
    }
]

for row in national:
    print(row)
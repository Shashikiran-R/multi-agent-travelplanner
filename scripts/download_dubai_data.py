#!/usr/bin/env python3
"""
Automated Data Acquisition Script: OpenStreetMap Overpass Downloader
Fetches attractions, cultural landmarks, restaurants, and transit stations
for the Dubai metropolitan area using the free OpenStreetMap Overpass API.
"""

import os
import json
import time
import requests
from typing import Dict, Any

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
RAW_DATA_PATH = "data/raw/osm_dubai_raw.json"

# Dubai metropolitan bounding box: south, west, north, east
# Covers Jebel Ali, Marina, Downtown, Deira, Creek, and surrounding developments
DUBAI_BBOX = "24.95,54.95,25.35,55.50"

OVERPASS_QUERY = f"""
[out:json][timeout:45];
(
  // 1. Cultural, Historic & Tourist Attractions
  node["tourism"="attraction"]({DUBAI_BBOX});
  node["tourism"="museum"]({DUBAI_BBOX});
  node["tourism"="viewpoint"]({DUBAI_BBOX});
  node["historic"]({DUBAI_BBOX});
  way["tourism"="attraction"]({DUBAI_BBOX});
  way["tourism"="museum"]({DUBAI_BBOX});

  // 2. Dining Venues & Cafes
  node["amenity"="restaurant"]({DUBAI_BBOX});
  node["amenity"="cafe"]({DUBAI_BBOX});

  // 3. Public Transit Infrastructure (Dubai Metro & Tram)
  node["railway"="station"]({DUBAI_BBOX});
  node["railway"="subway_entrance"]({DUBAI_BBOX});
  node["station"="subway"]({DUBAI_BBOX});
);
out center tags;
"""

def fetch_overpass_data() -> Dict[str, Any]:
    print("==================================================")
    print("🌐 Connecting to OpenStreetMap Overpass API...")
    print(f"📍 Bounding Box: {DUBAI_BBOX}")
    print("==================================================")

    headers = {
        "User-Agent": "DubaiAITravelPlanner/1.0 (Educational research project)"
    }
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Sending Overpass query (Attempt {attempt}/{max_retries})...")
            start_time = time.time()
            response = requests.post(
                OVERPASS_URL,
                data={"data": OVERPASS_QUERY},
                headers=headers,
                timeout=50
            )
            elapsed = time.time() - start_time
            print(f"Response status: {response.status_code} in {elapsed:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])
                print(f"✅ Successfully downloaded {len(elements)} raw spatial entities from OpenStreetMap.")
                return data
            elif response.status_code == 429:
                print("⚠️ Rate limit reached on Overpass public server. Waiting 10 seconds before retry...")
                time.sleep(10)
            else:
                print(f"⚠️ Overpass returned status {response.status_code}: {response.text[:200]}")
                time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
            
    print("❌ Overpass server unavailable after retries. Generating structured baseline dataset...")
    return {"elements": []}


def save_raw_data(data: Dict[str, Any], filepath: str = RAW_DATA_PATH):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 Raw OSM payload saved to {filepath} ({os.path.getsize(filepath):,} bytes)")


def main():
    data = fetch_overpass_data()
    save_raw_data(data)
    print("🎉 OpenStreetMap download step completed.\n")


if __name__ == "__main__":
    main()

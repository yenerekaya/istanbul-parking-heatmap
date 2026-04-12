#!/usr/bin/env python3
"""
Fetch İSPARK parking lot locations from IBB API.
Equivalent of the original fetch_meter_locations.py but for İSPARK data.

API: https://api.ibb.gov.tr/ispark/Park
Output: public/data/park_locations.json

Usage: python3 scripts/fetch_park_locations.py
"""

import json
import sys
import urllib.request
from pathlib import Path

ISPARK_API = "https://api.ibb.gov.tr/ispark/Park"

# Istanbul bounding box for validation
IST_BBOX = {"lat_min": 40.80, "lat_max": 41.35, "lng_min": 28.50, "lng_max": 29.50}


def fetch_parks():
    """Fetch all parks from İSPARK API."""
    print("Fetching parks from İSPARK API...")
    req = urllib.request.Request(
        ISPARK_API,
        headers={
            "Accept": "application/json",
            "User-Agent": "istanbul-parking-heatmap/1.0",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    print(f"  Received {len(data)} park records")
    return data


def process_parks(raw_parks):
    """Process raw API data into the format expected by the frontend."""
    results = []
    skipped = 0

    for p in raw_parks:
        try:
            lat = float(p.get("lat", 0))
            lng = float(p.get("lng", 0))
        except (ValueError, TypeError):
            skipped += 1
            continue

        # Validate within Istanbul bbox
        if not (IST_BBOX["lat_min"] <= lat <= IST_BBOX["lat_max"] and
                IST_BBOX["lng_min"] <= lng <= IST_BBOX["lng_max"]):
            skipped += 1
            continue

        park_id = p.get("parkID")
        if not park_id:
            skipped += 1
            continue

        capacity = int(p.get("capacity", 0))
        if capacity <= 0:
            skipped += 1
            continue

        # Map parkType to a simpler category
        park_type = p.get("parkType", "").upper()

        results.append({
            "id": str(park_id),
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "meters": capacity,  # "meters" field used as capacity for compatibility
            "street": p.get("parkName", ""),
            "hood": p.get("district", ""),
            "parkType": park_type,
            "workHours": p.get("workHours", ""),
            "locationName": p.get("locationName", ""),
            "address": p.get("address", ""),
            "freeTime": int(p.get("freeTime", 0)),
        })

    if skipped:
        print(f"  Skipped {skipped} parks (missing data or out of Istanbul bbox)")

    results.sort(key=lambda x: x["id"])
    return results


def main():
    out_dir = Path(__file__).parent.parent / "public" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "park_locations.json"

    raw_parks = fetch_parks()
    parks = process_parks(raw_parks)

    print(f"\nProcessed {len(parks)} valid parks")
    if parks:
        print(f"  Capacity range: {min(p['meters'] for p in parks)}-{max(p['meters'] for p in parks)} per park")
        print(f"  Lat range: {min(p['lat'] for p in parks):.4f} - {max(p['lat'] for p in parks):.4f}")
        print(f"  Lng range: {min(p['lng'] for p in parks):.4f} - {max(p['lng'] for p in parks):.4f}")

        # Park type breakdown
        types = {}
        for p in parks:
            pt = p.get("parkType", "UNKNOWN")
            types[pt] = types.get(pt, 0) + 1
        print(f"  Park types:")
        for pt, count in sorted(types.items()):
            print(f"    {pt}: {count}")

        # District breakdown (top 10)
        districts = {}
        for p in parks:
            d = p.get("hood", "UNKNOWN")
            districts[d] = districts.get(d, 0) + 1
        print(f"  Districts: {len(districts)} ({', '.join(sorted(districts.keys())[:5])}...)")

    with open(out_path, "w") as f:
        json.dump(parks, f, separators=(",", ":"), ensure_ascii=False)

    size_kb = out_path.stat().st_size / 1024
    print(f"\nWrote {out_path} ({size_kb:.0f} KB, {len(parks)} parks)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

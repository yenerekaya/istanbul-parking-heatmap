#!/usr/bin/env python3
"""
Generate mock 168-slot weekly profiles from a single İSPARK API snapshot.
Useful for testing the frontend before the scraper has collected enough data.

Uses the current snapshot's occupancy as a baseline and applies realistic
hourly/daily patterns to generate a plausible weekly profile.

Input: İSPARK API (live)
       public/data/park_locations.json (from fetch_park_locations.py)
Output: public/data/parking_week.json

Usage: python3 scripts/generate_mock_profiles.py
"""

import json
import math
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ISPARK_API = "https://api.ibb.gov.tr/ispark/Park"

# Typical hourly demand pattern for Istanbul (0-23h, normalized 0-1)
# Based on general urban parking patterns
HOURLY_PATTERN = [
    0.30, 0.20, 0.15, 0.12, 0.10, 0.12,  # 00-05: overnight
    0.18, 0.35, 0.55, 0.75, 0.85, 0.90,  # 06-11: morning ramp
    0.88, 0.85, 0.82, 0.80, 0.78, 0.75,  # 12-17: afternoon
    0.70, 0.65, 0.60, 0.55, 0.48, 0.38,  # 18-23: evening decline
]

# Day-of-week multiplier (Mon=0 to Sun=6)
DOW_MULTIPLIER = [
    1.00,  # Monday
    1.02,  # Tuesday
    1.05,  # Wednesday (peak)
    1.03,  # Thursday
    0.95,  # Friday
    0.80,  # Saturday
    0.60,  # Sunday
]


def fetch_snapshot():
    """Fetch current İSPARK snapshot."""
    print("Fetching İSPARK snapshot...")
    req = urllib.request.Request(
        ISPARK_API,
        headers={
            "Accept": "application/json",
            "User-Agent": "istanbul-parking-heatmap/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(f"  Received {len(data)} parks")
    return data


def compute_baseline_occupancy(park):
    """Compute current occupancy ratio from snapshot."""
    capacity = int(park.get("capacity", 0))
    empty = int(park.get("emptyCapacity", 0))
    if capacity <= 0:
        return 0.5  # default
    return max(0.0, min(1.0, (capacity - empty) / capacity))


def generate_profile(baseline, seed=0):
    """
    Generate a 168-slot weekly profile from a baseline occupancy.
    Applies hourly and daily patterns with some randomness.
    """
    import random
    rng = random.Random(seed)

    slots = [0.0] * 168

    for dow in range(7):
        for hour in range(24):
            idx = dow * 24 + hour

            # Base pattern
            hourly = HOURLY_PATTERN[hour]
            daily = DOW_MULTIPLIER[dow]

            # Scale by baseline (parks that are currently full tend to stay full)
            value = baseline * hourly * daily

            # Add noise (±10%)
            noise = rng.gauss(0, 0.05)
            value = max(0.0, min(1.0, value + noise))

            slots[idx] = round(value, 3)

    return slots


def main():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "public" / "data"
    park_path = data_dir / "park_locations.json"
    out_path = data_dir / "parking_week.json"

    if not park_path.exists():
        print(f"Error: {park_path} not found. Run fetch_park_locations.py first.",
              file=sys.stderr)
        sys.exit(1)

    with open(park_path) as f:
        park_locations = json.load(f)
    park_lookup = {p["id"]: p for p in park_locations}

    snapshot = fetch_snapshot()

    # Build baseline occupancy from snapshot
    baselines = {}
    for p in snapshot:
        park_id = str(p.get("parkID", ""))
        if park_id in park_lookup:
            baselines[park_id] = compute_baseline_occupancy(p)

    print(f"\nMatched {len(baselines)} parks with locations")

    # Generate profiles
    results = []
    for park_id, park_info in park_lookup.items():
        baseline = baselines.get(park_id, 0.5)
        slots = generate_profile(baseline, seed=hash(park_id) % 10000)

        block = {
            "id": park_id,
            "lng": park_info["lng"],
            "lat": park_info["lat"],
            "meters": park_info["meters"],
            "street": park_info.get("street", ""),
            "hood": park_info.get("hood", ""),
            "slots": slots,
        }
        results.append(block)

    results.sort(key=lambda x: x["id"])

    now = datetime.now(timezone.utc)
    output = {
        "generated": now.isoformat(),
        "dateRange": {
            "from": now.strftime("%Y-%m-%d"),
            "to": now.strftime("%Y-%m-%d"),
        },
        "blocks": results,
        "_note": "Mock profiles generated from single snapshot. Replace with real aggregated data.",
    }

    with open(out_path, "w") as f:
        json.dump(output, f, separators=(",", ":"), ensure_ascii=False)

    size_kb = out_path.stat().st_size / 1024
    print(f"\nWrote {out_path} ({size_kb:.0f} KB, {len(results)} parks)")
    print("\nNOTE: These are mock profiles. Run scrape_ispark.py hourly and")
    print("      then aggregate_ispark.py for real data.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

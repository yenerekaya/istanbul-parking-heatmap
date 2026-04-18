#!/usr/bin/env python3
"""
Fetch live İSPARK occupancy and update the weekly profile JSON in-place.

Designed for GitHub Actions: no database needed. Reads the existing
parking_week.json, updates the current hour's slot with fresh API data,
and writes it back. Over time the profile converges to real averages.

Algorithm:
  - For each park, the current hour/dow slot is updated using exponential
    moving average: new = alpha * live + (1 - alpha) * old
  - ALPHA controls how fast old data fades (0.1 = smooth, 0.5 = reactive)
  - Parks not yet in the profile are added from the API snapshot

Usage: python3 scripts/update_parking_week.py
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ISPARK_API = "https://api.ibb.gov.tr/ispark/Park"

# Exponential moving average weight for new observations
# 0.1 = very smooth (needs ~10 samples to converge)
# 0.3 = moderate (good balance for hourly updates)
ALPHA = 0.3

# Istanbul bounding box
IST_BBOX = {"lat_min": 40.80, "lat_max": 41.35, "lng_min": 28.50, "lng_max": 29.50}


def fetch_live(retries=3, timeout=30):
    """Fetch all İSPARK parks with live occupancy."""
    req = urllib.request.Request(
        ISPARK_API,
        headers={
            "Accept": "application/json",
            "User-Agent": "istanbul-parking-heatmap/1.0",
        },
    )
    import time
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data
        except Exception as e:
            print(f"  Attempt {attempt}/{retries} failed: {e}", file=sys.stderr)
            if attempt < retries:
                time.sleep(10)
    raise RuntimeError(f"API unreachable after {retries} attempts")


def park_to_block(p):
    """Convert an İSPARK API park record to a block dict for parking_week.json."""
    try:
        lat = float(p.get("lat", 0))
        lng = float(p.get("lng", 0))
    except (ValueError, TypeError):
        return None

    if not (IST_BBOX["lat_min"] <= lat <= IST_BBOX["lat_max"] and
            IST_BBOX["lng_min"] <= lng <= IST_BBOX["lng_max"]):
        return None

    capacity = int(p.get("capacity", 0))
    if capacity <= 0:
        return None

    return {
        "id": str(p.get("parkID", "")),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "meters": capacity,
        "street": p.get("parkName", ""),
        "hood": p.get("district", ""),
        "slots": [0.0] * 168,
    }


def compute_occupancy(park):
    """Compute occupancy ratio from live API data."""
    capacity = int(park.get("capacity", 0))
    empty = int(park.get("emptyCapacity", 0))
    if capacity <= 0:
        return 0.0
    return max(0.0, min(1.0, (capacity - empty) / capacity))


def main():
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "public" / "data"
    week_path = data_dir / "parking_week.json"
    locations_path = data_dir / "park_locations.json"

    # Current time in Turkey (UTC+3)
    now_utc = datetime.now(timezone.utc)
    # Turkey is always UTC+3 (no DST)
    from datetime import timedelta
    now_tr = now_utc + timedelta(hours=3)

    # ISO dow: 0=Mon..6=Sun
    iso_dow = now_tr.weekday()
    hour = now_tr.hour
    slot_idx = iso_dow * 24 + hour

    day_names = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
    print(f"İSPARK Update — {now_tr.strftime('%Y-%m-%d %H:%M')} Turkey time")
    print(f"  Slot: {day_names[iso_dow]} {hour:02d}:00 (index {slot_idx})")

    # Fetch live data
    print("\nFetching live İSPARK data...")
    try:
        live_parks = fetch_live()
    except Exception as e:
        print(f"API Error: {e}", file=sys.stderr)
        print("Skipping update — will retry next hour.")
        sys.exit(0)
    print(f"  Received {len(live_parks)} parks")

    # Build live occupancy map
    live_occ = {}
    live_blocks = {}
    for p in live_parks:
        block = park_to_block(p)
        if block:
            park_id = block["id"]
            live_occ[park_id] = compute_occupancy(p)
            live_blocks[park_id] = block

    print(f"  Valid parks: {len(live_occ)}")

    # Load existing profile (or create new)
    if week_path.exists():
        with open(week_path) as f:
            week_data = json.load(f)
        existing_blocks = {b["id"]: b for b in week_data.get("blocks", [])}
        print(f"  Existing profile: {len(existing_blocks)} parks")
    else:
        week_data = {
            "generated": now_utc.isoformat(),
            "dateRange": {"from": now_utc.strftime("%Y-%m-%d"), "to": now_utc.strftime("%Y-%m-%d")},
            "blocks": [],
        }
        existing_blocks = {}
        print("  No existing profile, creating new")

    # Update each park's slot with EMA
    updated = 0
    added = 0
    for park_id, occ in live_occ.items():
        if park_id in existing_blocks:
            block = existing_blocks[park_id]
            old_val = block["slots"][slot_idx]

            if old_val > 0:
                # Exponential moving average
                new_val = ALPHA * occ + (1 - ALPHA) * old_val
            else:
                # First observation for this slot
                new_val = occ

            block["slots"][slot_idx] = round(new_val, 3)

            # Also update metadata in case it changed
            lb = live_blocks[park_id]
            block["lat"] = lb["lat"]
            block["lng"] = lb["lng"]
            block["meters"] = lb["meters"]
            block["street"] = lb["street"]
            block["hood"] = lb["hood"]

            updated += 1
        else:
            # New park — add with current observation
            new_block = live_blocks[park_id]
            new_block["slots"][slot_idx] = round(occ, 3)
            existing_blocks[park_id] = new_block
            added += 1

    print(f"\n  Updated: {updated} parks")
    print(f"  Added: {added} new parks")

    # Rebuild blocks list
    all_blocks = sorted(existing_blocks.values(), key=lambda b: b["id"])

    # Stats
    all_occ = [b["slots"][slot_idx] for b in all_blocks if b["slots"][slot_idx] > 0]
    if all_occ:
        avg = sum(all_occ) / len(all_occ)
        print(f"  Current slot avg occupancy: %{avg*100:.0f} ({len(all_occ)} parks)")

    # Count how many slots have data (convergence indicator)
    total_filled = sum(
        1 for b in all_blocks for s in b["slots"] if s > 0
    )
    total_possible = len(all_blocks) * 168
    coverage = total_filled / total_possible * 100 if total_possible > 0 else 0
    print(f"  Profile coverage: {total_filled}/{total_possible} slots ({coverage:.1f}%)")

    # Write output
    week_data["generated"] = now_utc.isoformat()
    week_data["dateRange"]["to"] = now_utc.strftime("%Y-%m-%d")
    if not week_data["dateRange"].get("from"):
        week_data["dateRange"]["from"] = now_utc.strftime("%Y-%m-%d")
    week_data["blocks"] = all_blocks

    data_dir.mkdir(parents=True, exist_ok=True)
    with open(week_path, "w") as f:
        json.dump(week_data, f, separators=(",", ":"), ensure_ascii=False)

    size_kb = week_path.stat().st_size / 1024
    print(f"\nWrote {week_path} ({size_kb:.0f} KB, {len(all_blocks)} parks)")

    # Also update park_locations.json
    locations = sorted(live_blocks.values(), key=lambda b: b["id"])
    # Strip slots from locations file
    locations_clean = []
    for b in locations:
        locations_clean.append({
            "id": b["id"],
            "lat": b["lat"],
            "lng": b["lng"],
            "meters": b["meters"],
            "street": b["street"],
            "hood": b["hood"],
        })

    with open(locations_path, "w") as f:
        json.dump(locations_clean, f, separators=(",", ":"), ensure_ascii=False)

    print(f"Wrote {locations_path} ({len(locations_clean)} parks)")
    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

#!/usr/bin/env python3
"""
Aggregate İSPARK scraped occupancy data into 168-slot weekly profiles.
Equivalent of the original aggregate_parking.py but reads from local SQLite
instead of SODA API.

Input: data/ispark_history.db (populated by scrape_ispark.py)
       public/data/park_locations.json (from fetch_park_locations.py)
Output: public/data/parking_week.json

The scraper must have been running for at least 1 week to produce meaningful
profiles. More data = smoother averages.

Usage: python3 scripts/aggregate_ispark.py [--days 30] [--db data/ispark_history.db]
"""

import json
import sqlite3
import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_args():
    p = ArgumentParser(description="Aggregate İSPARK occupancy into weekly profiles")
    p.add_argument("--days", type=int, default=30, help="Lookback window in days")
    p.add_argument("--db", type=str, default=None, help="SQLite database path")
    return p.parse_args()


def load_park_locations(path):
    """Load park locations from fetch_park_locations.py output."""
    with open(path) as f:
        parks = json.load(f)
    return {p["id"]: p for p in parks}


def fetch_aggregated_occupancy(conn, since_date):
    """
    Aggregate occupancy by park_id / day-of-week / hour from SQLite.
    Returns list of (park_id, iso_dow, hour, avg_occupancy, sample_count).

    SQLite strftime('%w') returns: 0=Sunday, 1=Monday, ..., 6=Saturday
    We remap to ISO: 0=Monday, 1=Tuesday, ..., 6=Sunday
    """
    query = """
        SELECT
            park_id,
            CAST(strftime('%w', scraped_at) AS INTEGER) AS sqlite_dow,
            CAST(strftime('%H', scraped_at) AS INTEGER) AS hour,
            AVG(occupancy_pct) AS avg_occ,
            COUNT(*) AS samples
        FROM occupancy
        WHERE scraped_at >= ?
        GROUP BY park_id, sqlite_dow, hour
        ORDER BY park_id, sqlite_dow, hour
    """

    cursor = conn.execute(query, (since_date,))
    rows = cursor.fetchall()
    return rows


def build_weekly_profiles(rows, park_lookup):
    """
    Build 168-slot occupancy profiles for each park.
    Returns dict: park_id -> 168-element list of occupancy values (0-1).
    """
    # SQLite strftime('%w'): 0=Sun, 1=Mon, ..., 6=Sat
    # ISO: 0=Mon, 1=Tue, ..., 6=Sun
    SQLITE_DOW_TO_ISO = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}

    profiles = {}
    matched = 0
    unmatched = set()

    for park_id, sqlite_dow, hour, avg_occ, samples in rows:
        park_id_str = str(park_id)

        if park_id_str not in park_lookup:
            unmatched.add(park_id_str)
            continue

        iso_dow = SQLITE_DOW_TO_ISO.get(sqlite_dow)
        if iso_dow is None or not (0 <= hour <= 23):
            continue

        if park_id_str not in profiles:
            profiles[park_id_str] = [0.0] * 168
            matched += 1

        idx = iso_dow * 24 + hour
        profiles[park_id_str][idx] = round(min(1.0, avg_occ), 3)

    print(f"  Matched {matched} parks, {len(unmatched)} unmatched")
    return profiles


def validate_output(blocks):
    """Sanity-check the output data."""
    if not blocks:
        print("ERROR: No blocks produced!", file=sys.stderr)
        return False

    all_occ = [s for b in blocks for s in b["slots"] if s > 0]
    if not all_occ:
        print("WARNING: All occupancy values are zero", file=sys.stderr)
        return True

    avg_occ = sum(all_occ) / len(all_occ)
    max_occ = max(all_occ)
    nonzero_pct = len(all_occ) / (len(blocks) * 168) * 100

    print(f"\nValidation:")
    print(f"  Parks with data: {len(blocks)}")
    print(f"  Non-zero slots: {len(all_occ)} ({nonzero_pct:.1f}%)")
    print(f"  Avg occupancy (non-zero): {avg_occ:.2f}")
    print(f"  Max occupancy: {max_occ:.2f}")

    # Spot-check: Wed 2pm (dow=2, hour=14, idx=62) vs Sun 6am (dow=6, hour=6, idx=150)
    wed_2pm = [b["slots"][2 * 24 + 14] for b in blocks if b["slots"][2 * 24 + 14] > 0]
    sun_6am = [b["slots"][6 * 24 + 6] for b in blocks if b["slots"][6 * 24 + 6] > 0]

    if wed_2pm:
        print(f"  Wed 2pm avg: {sum(wed_2pm)/len(wed_2pm):.2f} ({len(wed_2pm)} parks)")
    if sun_6am:
        print(f"  Sun 6am avg: {sum(sun_6am)/len(sun_6am):.2f} ({len(sun_6am)} parks)")

    return True


def main():
    args = parse_args()

    project_root = Path(__file__).parent.parent
    data_dir = project_root / "public" / "data"

    if args.db:
        db_path = Path(args.db)
    else:
        db_path = project_root / "data" / "ispark_history.db"

    park_path = data_dir / "park_locations.json"
    out_path = data_dir / "parking_week.json"

    if not db_path.exists():
        print(f"Error: {db_path} not found.", file=sys.stderr)
        print("Run scrape_ispark.py first to collect occupancy data.", file=sys.stderr)
        sys.exit(1)

    if not park_path.exists():
        print(f"Error: {park_path} not found.", file=sys.stderr)
        print("Run fetch_park_locations.py first.", file=sys.stderr)
        sys.exit(1)

    park_lookup = load_park_locations(park_path)
    print(f"Loaded {len(park_lookup)} parks from {park_path}")

    conn = sqlite3.connect(db_path)

    # Check data availability
    total = conn.execute("SELECT COUNT(*) FROM occupancy").fetchone()[0]
    distinct_times = conn.execute(
        "SELECT COUNT(DISTINCT strftime('%Y-%m-%d %H', scraped_at)) FROM occupancy"
    ).fetchone()[0]
    print(f"Database: {total} records, {distinct_times} distinct hourly slots")

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=args.days)
    since_date = since.strftime("%Y-%m-%dT00:00:00")

    print(f"Aggregating {args.days} days of data (since {since_date[:10]})")

    print("\nFetching aggregated occupancy...")
    rows = fetch_aggregated_occupancy(conn, since_date)
    print(f"  Total: {len(rows)} aggregated rows")

    print("\nBuilding weekly profiles...")
    profiles = build_weekly_profiles(rows, park_lookup)

    # Build output blocks
    results = []
    for park_id, park_info in park_lookup.items():
        slots = profiles.get(park_id, [0.0] * 168)

        block = {
            "id": park_id,
            "lng": park_info["lng"],
            "lat": park_info["lat"],
            "meters": park_info["meters"],  # capacity
            "street": park_info.get("street", ""),
            "hood": park_info.get("hood", ""),
            "slots": slots,
        }

        results.append(block)

    results.sort(key=lambda x: x["id"])

    if not validate_output(results):
        sys.exit(1)

    output = {
        "generated": now.isoformat(),
        "dateRange": {"from": since_date[:10], "to": now.strftime("%Y-%m-%d")},
        "blocks": results,
    }

    with open(out_path, "w") as f:
        json.dump(output, f, separators=(",", ":"), ensure_ascii=False)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\nWrote {out_path} ({size_mb:.1f} MB, {len(results)} parks)")

    conn.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

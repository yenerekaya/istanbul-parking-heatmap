#!/usr/bin/env python3
"""
İSPARK anlık doluluk verisi scraper.

API: https://api.ibb.gov.tr/ispark/Park
Her çağrıda tüm otoparkların anlık doluluk yüzdesini alır ve SQLite'a kaydeder.

Cron ile her saat başı çalıştırılması önerilir:
  0 * * * * python3 /path/to/scripts/scrape_ispark.py

Yeterli veri toplandıktan sonra (en az 1 hafta) aggregate_ispark.py ile
168-slotluk haftalık profil oluşturulabilir.

Usage: python3 scripts/scrape_ispark.py [--db data/ispark_history.db]
"""

import json
import sqlite3
import sys
import time
import urllib.request
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path

ISPARK_API = "https://api.ibb.gov.tr/ispark/Park"


def parse_args():
    p = ArgumentParser(description="Scrape İSPARK parking occupancy")
    p.add_argument(
        "--db",
        type=str,
        default=None,
        help="SQLite database path (default: <project>/data/ispark_history.db)",
    )
    return p.parse_args()


def init_db(db_path):
    """Create tables if they don't exist."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parks (
            park_id INTEGER PRIMARY KEY,
            park_name TEXT,
            location_name TEXT,
            lat REAL,
            lng REAL,
            capacity INTEGER,
            work_hours TEXT,
            park_type TEXT,
            district TEXT,
            free_time INTEGER,
            address TEXT,
            area_polygon TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS occupancy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            park_id INTEGER,
            occupancy_pct REAL,
            empty_capacity INTEGER,
            scraped_at TEXT,
            api_update_date TEXT,
            FOREIGN KEY (park_id) REFERENCES parks(park_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_occupancy_park_time
        ON occupancy(park_id, scraped_at)
    """)
    conn.commit()
    return conn


def fetch_all_parks():
    """Fetch all İSPARK parks from the API."""
    req = urllib.request.Request(
        ISPARK_API,
        headers={
            "Accept": "application/json",
            "User-Agent": "istanbul-parking-heatmap/1.0",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data


def upsert_parks(conn, parks):
    """Insert or update park metadata."""
    for p in parks:
        conn.execute(
            """
            INSERT INTO parks (park_id, park_name, location_name, lat, lng,
                             capacity, work_hours, park_type, district,
                             free_time, address, area_polygon, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(park_id) DO UPDATE SET
                park_name=excluded.park_name,
                location_name=excluded.location_name,
                lat=excluded.lat,
                lng=excluded.lng,
                capacity=excluded.capacity,
                work_hours=excluded.work_hours,
                park_type=excluded.park_type,
                district=excluded.district,
                free_time=excluded.free_time,
                address=excluded.address,
                area_polygon=excluded.area_polygon,
                updated_at=excluded.updated_at
            """,
            (
                p.get("parkID"),
                p.get("parkName", ""),
                p.get("locationName", ""),
                float(p.get("lat", 0)),
                float(p.get("lng", 0)),
                int(p.get("capacity", 0)),
                p.get("workHours", ""),
                p.get("parkType", ""),
                p.get("district", ""),
                int(p.get("freeTime", 0)),
                p.get("address", ""),
                p.get("areaPolygon", ""),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    conn.commit()


def insert_occupancy(conn, parks, scraped_at):
    """Insert occupancy snapshot for all parks."""
    rows = []
    for p in parks:
        park_id = p.get("parkID")
        capacity = int(p.get("capacity", 0))
        empty = int(p.get("emptyCapacity", 0))

        if capacity > 0:
            occupancy_pct = round((capacity - empty) / capacity, 3)
        else:
            occupancy_pct = 0.0

        rows.append((
            park_id,
            occupancy_pct,
            empty,
            scraped_at,
            p.get("updateDate", ""),
        ))

    conn.executemany(
        """
        INSERT INTO occupancy (park_id, occupancy_pct, empty_capacity,
                              scraped_at, api_update_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def main():
    args = parse_args()

    if args.db:
        db_path = Path(args.db)
    else:
        db_path = Path(__file__).parent.parent / "data" / "ispark_history.db"

    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"İSPARK Scraper - {datetime.now(timezone.utc).isoformat()}")
    print(f"Database: {db_path}")

    conn = init_db(db_path)

    print("Fetching İSPARK data...")
    start = time.time()

    try:
        parks = fetch_all_parks()
    except Exception as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start
    print(f"  Received {len(parks)} parks ({elapsed:.1f}s)")

    # Filter out parks with no valid coordinates
    valid_parks = [
        p for p in parks
        if p.get("lat") and p.get("lng")
        and float(p.get("lat", 0)) > 0
        and float(p.get("lng", 0)) > 0
    ]
    print(f"  Valid parks (with coordinates): {len(valid_parks)}")

    # Update park metadata
    upsert_parks(conn, valid_parks)

    # Insert occupancy snapshot
    scraped_at = datetime.now(timezone.utc).isoformat()
    count = insert_occupancy(conn, valid_parks, scraped_at)
    print(f"  Inserted {count} occupancy records")

    # Stats
    total_records = conn.execute("SELECT COUNT(*) FROM occupancy").fetchone()[0]
    distinct_times = conn.execute(
        "SELECT COUNT(DISTINCT scraped_at) FROM occupancy"
    ).fetchone()[0]
    print(f"\nDatabase stats:")
    print(f"  Total occupancy records: {total_records}")
    print(f"  Distinct scrape times: {distinct_times}")
    print(f"  Parks tracked: {len(valid_parks)}")

    # Park type breakdown
    types = {}
    for p in valid_parks:
        pt = p.get("parkType", "UNKNOWN")
        types[pt] = types.get(pt, 0) + 1
    for pt, count in sorted(types.items()):
        print(f"    {pt}: {count}")

    conn.close()
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

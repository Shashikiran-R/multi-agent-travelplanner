#!/usr/bin/env python3
"""
Data Verification & Integrity Auditor
Runs comprehensive health checks on the downloaded & enriched Dubai travel database
(data/dubai_travel.db) before downstream agents execute.
"""

import os
import sys
import sqlite3

DB_PATH = "data/dubai_travel.db"

# Dubai Geographic Bounds
MIN_LAT, MAX_LAT = 24.80, 25.40
MIN_LNG, MAX_LNG = 54.90, 55.70

def run_verification():
    print("==================================================")
    print("🔍 Running Data Integrity & Coverage Health Check...")
    print(f"📁 Target Database: {DB_PATH}")
    print("==================================================")

    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database file {DB_PATH} does not exist! Run enrichment pipeline first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    errors = []
    warnings = []

    # 1. Attractions Table Check
    cursor.execute("SELECT COUNT(*) FROM attractions")
    total_attractions = cursor.fetchone()[0]
    print(f"• Total Attractions: {total_attractions}")
    if total_attractions < 20:
        errors.append(f"Expected at least 20 attractions, found only {total_attractions}.")

    # Coordinate validity & non-null price check
    cursor.execute("SELECT id, name, lat, lng, admission_fee_aed, district FROM attractions")
    for row in cursor.fetchall():
        if not (MIN_LAT <= row["lat"] <= MAX_LAT and MIN_LNG <= row["lng"] <= MAX_LNG):
            warnings.append(f"Attraction '{row['name']}' has out-of-bounds coordinates: ({row['lat']}, {row['lng']})")
        if row["admission_fee_aed"] is None or row["admission_fee_aed"] < 0:
            errors.append(f"Attraction '{row['name']}' has invalid fee: {row['admission_fee_aed']}")
        if not row["district"]:
            errors.append(f"Attraction '{row['name']}' is missing a district.")

    # 2. Restaurants Table Check
    cursor.execute("SELECT COUNT(*) FROM restaurants")
    total_restaurants = cursor.fetchone()[0]
    print(f"• Total Dining Venues: {total_restaurants}")
    if total_restaurants < 10:
        errors.append(f"Expected at least 10 restaurants, found only {total_restaurants}.")

    cursor.execute("SELECT DISTINCT price_tier FROM restaurants")
    tiers = [r[0] for r in cursor.fetchall()]
    print(f"• Dining Price Tiers Represented: {tiers}")
    if not all(t in tiers for t in ["budget", "midscale", "luxury"]):
        warnings.append(f"Missing one or more required price tiers in restaurants. Found: {tiers}")

    # 3. Hotel Baselines Check
    cursor.execute("SELECT COUNT(*) FROM hotel_baselines")
    total_hotels = cursor.fetchone()[0]
    print(f"• Hotel Baseline Pricing Records: {total_hotels}")
    if total_hotels < 6:
        errors.append(f"Expected at least 6 hotel baseline rows, found only {total_hotels}.")

    # 4. Metro Stations Check
    cursor.execute("SELECT COUNT(*) FROM metro_stations")
    total_stations = cursor.fetchone()[0]
    print(f"• Dubai Metro Stations Loaded: {total_stations}")
    if total_stations < 5:
        errors.append(f"Expected at least 5 metro stations, found only {total_stations}.")

    # 5. District Coverage Check
    cursor.execute("SELECT DISTINCT district FROM attractions")
    districts = [r[0] for r in cursor.fetchall()]
    print(f"• Districts Covered: {districts}")
    required_districts = ["Old Dubai & Creek", "Downtown & DIFC", "Dubai Marina & JBR"]
    for rd in required_districts:
        if rd not in districts:
            errors.append(f"Required district '{rd}' has no attractions assigned.")

    # 6. Climate Profiles Check
    cursor.execute("SELECT COUNT(*) FROM climate_profiles")
    total_months = cursor.fetchone()[0]
    print(f"• Climate Monthly Profiles Loaded: {total_months}")
    if total_months != 12:
        errors.append(f"Expected 12 monthly climate profiles, found {total_months}.")

    conn.close()

    # 7. RTA Transit Matrix JSON Check
    rta_matrix_file = "data/rta_transit_matrix.json"
    if not os.path.exists(rta_matrix_file):
        errors.append(f"Missing RTA transit matrix file at {rta_matrix_file}")
    else:
        print(f"• RTA Transit Matrix JSON: Present ({os.path.getsize(rta_matrix_file):,} bytes)")

    print("\n--------------------------------------------------")
    if warnings:
        print(f"⚠️ {len(warnings)} Non-Critical Warning(s):")
        for w in warnings:
            print(f"   - {w}")

    if errors:
        print(f"❌ Verification FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)
    else:
        print("🎉 ALL DATA INTEGRITY CHECKS PASSED SUCCESSFULLY!")
        print("✅ The database is ready for multi-agent graph execution.")
        print("--------------------------------------------------\n")


if __name__ == "__main__":
    run_verification()

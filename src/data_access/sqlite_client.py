#!/usr/bin/env python3
"""
High-Performance Local SQLite Repository for Dubai Travel Data
Provides instant (< 5ms) querying of attractions, dining, hotels, metro stations, and climate profiles.
Automatically initializes and seeds tables from data/seed_data.json on first launch.
"""

import os
import json
import sqlite3
from typing import List, Dict, Any, Optional

DB_PATH = "data/dubai_travel.db"
SEED_PATH = "data/seed_data.json"

class DubaiSQLiteClient:
    def __init__(self, db_path: str = DB_PATH, seed_path: str = SEED_PATH):
        self.db_path = db_path
        self.seed_path = seed_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_schema(self):
        """Creates tables if they don't exist and seeds data if empty."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Attractions Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS attractions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                district TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                admission_fee_aed REAL DEFAULT 0.0,
                recommended_duration_mins INTEGER DEFAULT 90,
                crowd_level TEXT DEFAULT 'medium',
                is_indoor INTEGER DEFAULT 0,
                opening_hours_json TEXT,
                tags_json TEXT,
                description TEXT
            );
            """)

            # 2. Restaurants Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS restaurants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                cuisine TEXT,
                district TEXT NOT NULL,
                price_tier TEXT NOT NULL,
                avg_cost_aed REAL NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                tags_json TEXT
            );
            """)

            # 3. Hotel Baselines Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hotel_baselines (
                district TEXT NOT NULL,
                tier TEXT NOT NULL,
                avg_rate_aed REAL NOT NULL,
                examples TEXT,
                PRIMARY KEY (district, tier)
            );
            """)

            # 4. Metro Stations Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS metro_stations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                line TEXT NOT NULL,
                zone INTEGER NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL
            );
            """)

            # 5. Climate Profiles Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS climate_profiles (
                month INTEGER PRIMARY KEY,
                avg_high_c REAL NOT NULL,
                peak_apparent_temp_c REAL NOT NULL,
                is_extreme_summer INTEGER NOT NULL,
                outdoor_recommendation TEXT
            );
            """)
            
            # Check if seeding is required
            cursor.execute("SELECT COUNT(*) FROM attractions;")
            count = cursor.fetchone()[0]
            if count == 0 and os.path.exists(self.seed_path):
                self._seed_database(conn)
            conn.commit()

    def _seed_database(self, conn: sqlite3.Connection):
        """Loads data from seed_data.json into SQLite."""
        print(f"🌱 Seeding database from {self.seed_path}...")
        try:
            with open(self.seed_path, "r", encoding="utf-8") as f:
                seed_data = json.load(f)
            
            cursor = conn.cursor()
            
            # Insert attractions
            for a in seed_data.get("attractions", []):
                cursor.execute("""
                INSERT OR REPLACE INTO attractions 
                (id, name, category, district, lat, lng, admission_fee_aed, recommended_duration_mins, crowd_level, is_indoor, opening_hours_json, tags_json, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    a["id"], a["name"], a.get("category", "attraction"), a["district"],
                    a["lat"], a["lng"], a.get("admission_fee_aed", 0.0),
                    a.get("recommended_duration_mins", 90), a.get("crowd_level", "medium"),
                    1 if a.get("is_indoor", False) else 0,
                    json.dumps(a.get("opening_hours", {})),
                    json.dumps(a.get("tags", [])),
                    a.get("description", "")
                ))

            # Insert restaurants
            for r in seed_data.get("restaurants", []):
                cursor.execute("""
                INSERT OR REPLACE INTO restaurants
                (id, name, cuisine, district, price_tier, avg_cost_aed, lat, lng, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r["id"], r["name"], r.get("cuisine", "International"), r["district"],
                    r["price_tier"], r["avg_cost_aed"], r["lat"], r["lng"],
                    json.dumps(r.get("tags", []))
                ))

            # Insert hotel baselines
            for h in seed_data.get("hotel_baselines", []):
                cursor.execute("""
                INSERT OR REPLACE INTO hotel_baselines
                (district, tier, avg_rate_aed, examples)
                VALUES (?, ?, ?, ?)
                """, (
                    h["district"], h["tier"], h["avg_rate_aed"], h.get("examples", "")
                ))

            # Insert metro stations
            for s in seed_data.get("metro_stations", []):
                cursor.execute("""
                INSERT OR REPLACE INTO metro_stations
                (id, name, line, zone, lat, lng)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    s["id"], s["name"], s["line"], s["zone"], s["lat"], s["lng"]
                ))

            # Insert climate profiles
            climate_dict = seed_data.get("climate_profiles", {})
            for m_str, prof in climate_dict.items():
                m_int = int(m_str)
                cursor.execute("""
                INSERT OR REPLACE INTO climate_profiles
                (month, avg_high_c, peak_apparent_temp_c, is_extreme_summer, outdoor_recommendation)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    m_int, prof.get("avg_high_c", 30.0), prof.get("peak_apparent_temp_c", 35.0),
                    1 if prof.get("is_extreme_summer", False) else 0,
                    prof.get("outdoor_recommendation", "")
                ))
                
            print("✅ Seeding completed successfully.")
        except Exception as e:
            print(f"⚠️ Error seeding database: {e}")

    # =========================================================================
    # High-Performance Query APIs
    # =========================================================================
    def get_attractions(self, district: Optional[str] = None,
                        interest_tags: Optional[List[str]] = None,
                        max_fee: Optional[float] = None,
                        is_indoor: Optional[bool] = None,
                        limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Queries attractions with optional filters for district, tags, price, indoor status, and limit."""
        query = "SELECT * FROM attractions WHERE 1=1"
        params = []

        if district:
            query += " AND district = ?"
            params.append(district)

        if max_fee is not None:
            query += " AND admission_fee_aed <= ?"
            params.append(max_fee)

        if is_indoor is not None:
            query += " AND is_indoor = ?"
            params.append(1 if is_indoor else 0)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                item = dict(row)
                item["opening_hours"] = json.loads(item["opening_hours_json"] or "{}")
                item["tags"] = json.loads(item["tags_json"] or "[]")
                item["is_indoor"] = bool(item["is_indoor"])
                del item["opening_hours_json"]
                del item["tags_json"]
                
                # Tag relevance filter
                if interest_tags:
                    searchable = " ".join(item["tags"] + [item["category"], item["name"], item["description"]]).lower()
                    if any(t.lower() in searchable for t in interest_tags):
                        results.append(item)
                else:
                    results.append(item)

            if limit is not None:
                return results[:limit]
            return results

    def get_attraction_by_id(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a specific attraction by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attractions WHERE id = ?", (place_id,))
            row = cursor.fetchone()
            if row:
                item = dict(row)
                item["opening_hours"] = json.loads(item["opening_hours_json"] or "{}")
                item["tags"] = json.loads(item["tags_json"] or "[]")
                item["is_indoor"] = bool(item["is_indoor"])
                del item["opening_hours_json"]
                del item["tags_json"]
                return item
            return None

    def get_restaurants(self, district: Optional[str] = None,
                        price_tier: Optional[str] = None,
                        cuisine: Optional[str] = None,
                        max_cost: Optional[float] = None,
                        limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Queries dining venues with district, price, cuisine filters, and optional limit."""
        query = "SELECT * FROM restaurants WHERE 1=1"
        params = []

        if district:
            query += " AND district = ?"
            params.append(district)

        if price_tier:
            query += " AND price_tier = ?"
            params.append(price_tier)

        if cuisine:
            query += " AND cuisine LIKE ?"
            params.append(f"%{cuisine}%")

        if max_cost is not None:
            query += " AND avg_cost_aed <= ?"
            params.append(max_cost)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["tags"] = json.loads(item["tags_json"] or "[]")
                del item["tags_json"]
                results.append(item)

            if limit is not None:
                return results[:limit]
            return results

    def get_hotel_rate(self, district: str, tier: str) -> float:
        """Looks up the average nightly rate in AED for a district and tier."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT avg_rate_aed FROM hotel_baselines WHERE district = ? AND tier = ?",
                (district, tier)
            )
            row = cursor.fetchone()
            if row:
                return float(row["avg_rate_aed"])
            fallback_rates = {"budget": 250.0, "midscale": 600.0, "luxury": 1600.0}
            return fallback_rates.get(tier.lower(), 400.0)

    def get_hotel_options(self, district: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns hotel options and pricing across tiers."""
        query = "SELECT * FROM hotel_baselines"
        params = []
        if district:
            query += " WHERE district = ?"
            params.append(district)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_metro_stations(self, line: Optional[str] = None, zone: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns metro stations, optionally filtered by line or zone."""
        query = "SELECT * FROM metro_stations WHERE 1=1"
        params = []
        if line:
            query += " AND line LIKE ?"
            params.append(f"%{line}%")
        if zone:
            query += " AND zone = ?"
            params.append(zone)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_climate_profile(self, month: int) -> Optional[Dict[str, Any]]:
        """Returns the climate risk assessment and temperatures for a specific month (1-12)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM climate_profiles WHERE month = ?", (month,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["is_extreme_summer"] = bool(d["is_extreme_summer"])
                return d
            return None

    def get_all_districts(self) -> List[str]:
        """Returns list of distinct districts available in database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT district FROM attractions ORDER BY district")
            return [r[0] for r in cursor.fetchall()]


if __name__ == "__main__":
    client = DubaiSQLiteClient()
    districts = client.get_all_districts()
    attractions = client.get_attractions()
    restaurants = client.get_restaurants()
    stations = client.get_metro_stations()
    july_climate = client.get_climate_profile(7)
    print(f"📊 Available Districts: {districts}")
    print(f"📊 Total Attractions in SQLite: {len(attractions)}")
    print(f"📊 Total Restaurants in SQLite: {len(restaurants)}")
    print(f"📊 Total Metro Stations in SQLite: {len(stations)}")
    print(f"☀️ July Climate Profile: {july_climate}")

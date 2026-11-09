# src/propintel/db.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "propintel.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    with get_db() as c:
        c.executescript("""
        -- 1. Master Localities
        CREATE TABLE IF NOT EXISTS localities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            district TEXT NOT NULL DEFAULT 'Lucknow',
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            circle_rate_sqft REAL,
            UNIQUE(name, district)
        );

        -- 2. Developers / Promoters
        CREATE TABLE IF NOT EXISTS developers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            name_key TEXT NOT NULL,
            rera_promoter_no TEXT
        );

        -- 3. Projects (Private & Public Developments)
        CREATE TABLE IF NOT EXISTS developments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            developer_id INTEGER NOT NULL REFERENCES developers(id) ON DELETE CASCADE,
            locality_id INTEGER REFERENCES localities(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            name_key TEXT NOT NULL,
            rera_reg_no TEXT UNIQUE,
            district TEXT NOT NULL DEFAULT 'Lucknow',
            project_type TEXT DEFAULT 'Residential',
            rera_status TEXT DEFAULT 'REGISTERED',
            lat REAL,
            lon REAL,
            completion_date DATE
        );

        -- 4. Multi-tier Project Prices
        CREATE TABLE IF NOT EXISTS development_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            development_id INTEGER NOT NULL REFERENCES developments(id) ON DELETE CASCADE,
            unit_type TEXT,
            price_per_sqft REAL,
            total_min_inr REAL,
            total_max_inr REAL,
            kind TEXT DEFAULT 'developer_stated',
            observed_on DATE DEFAULT (DATE('now'))
        );

        -- 5. BhuNaksha Cadastral Parcels
        CREATE TABLE IF NOT EXISTS parcels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            locality_id INTEGER REFERENCES localities(id) ON DELETE SET NULL,
            district TEXT NOT NULL DEFAULT 'Lucknow',
            tehsil TEXT NOT NULL,
            village TEXT NOT NULL,
            khasra_no TEXT NOT NULL,
            area_sqm REAL,
            geojson_geom TEXT NOT NULL,
            UNIQUE(district, village, khasra_no)
        );

        -- 6. Raw Ingestion & Source Archive
        CREATE TABLE IF NOT EXISTS raw_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            url TEXT,
            title TEXT,
            body TEXT NOT NULL,
            content_hash TEXT UNIQUE NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 7. Market Price Observations (News, Circulars, Registries)
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            locality_id INTEGER NOT NULL REFERENCES localities(id) ON DELETE CASCADE,
            raw_doc_id INTEGER REFERENCES raw_docs(id) ON DELETE SET NULL,
            price_per_sqft REAL NOT NULL,
            property_type TEXT DEFAULT 'plot',
            kind TEXT NOT NULL,
            evidence_quote TEXT,
            observed_on DATE DEFAULT (DATE('now')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 8. LLM Extraction Tracking
        CREATE TABLE IF NOT EXISTS extraction_log (
            raw_doc_id INTEGER PRIMARY KEY REFERENCES raw_docs(id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_dev_locality ON developments(locality_id);
        CREATE INDEX IF NOT EXISTS idx_parcels_lookup ON parcels(village, khasra_no);
        CREATE INDEX IF NOT EXISTS idx_dev_prices ON development_prices(development_id);
        CREATE INDEX IF NOT EXISTS idx_obs_locality ON observations(locality_id);
        """)

if __name__ == "__main__":
    init_db()
    print("Database schema successfully consolidated.")
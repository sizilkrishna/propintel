# src/propintel/engine.py
import os
import json
import time
from pathlib import Path
import httpx
from dotenv import load_dotenv
from propintel.db import get_db

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

PRICE_KEYWORDS = [
    "circle rate", "sq ft", "sqft", "square feet", "per sq", 
    "plot", "land rate", "registry", "property", "lda", "housing", "rera",
    "bhk", "crore", "lakh", "launch", "project"
]

def has_price_signal(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in PRICE_KEYWORDS)

def resolve_or_create_locality(c, name: str) -> int:
    """Finds a locality, or geocodes and inserts it dynamically on the fly."""
    clean_name = name.strip()
    row = c.execute("SELECT id FROM localities WHERE lower(name) = lower(?)", (clean_name,)).fetchone()
    if row:
        return row["id"]

    lat, lon = 26.8467, 80.9462  # Default to Lucknow center if geocoding fails
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={clean_name},+Lucknow,+India&format=json&limit=1"
        res = httpx.get(url, headers={"User-Agent": "PropIntel-DynamicEngine/1.0"}, timeout=5.0)
        data = res.json()
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
    except Exception:
        pass

    c.execute("""
        INSERT OR IGNORE INTO localities (name, district, lat, lon, circle_rate_sqft)
        VALUES (?, 'Lucknow', ?, ?, 5000)
    """, (clean_name, lat, lon))
    return c.execute("SELECT id FROM localities WHERE lower(name) = lower(?)", (clean_name,)).fetchone()["id"]

def resolve_or_create_project(c, project_name: str, developer_name: str, locality_id: int):
    """Dynamically registers projects and developer records, inheriting parent locality coordinates."""
    if not project_name:
        return None

    dev_name = developer_name.strip() if developer_name else "Independent / Authority"
    c.execute("INSERT OR IGNORE INTO developers (name, name_key) VALUES (?, ?)", (dev_name, dev_name.lower()))
    dev_id = c.execute("SELECT id FROM developers WHERE lower(name)=lower(?)", (dev_name,)).fetchone()["id"]

    # Inherit coordinates from parent locality so project displays on map
    loc_row = c.execute("SELECT lat, lon FROM localities WHERE id = ?", (locality_id,)).fetchone()
    lat = loc_row["lat"] if loc_row else 26.8467
    lon = loc_row["lon"] if loc_row else 80.9462

    c.execute("""
        INSERT OR IGNORE INTO developments (developer_id, locality_id, name, name_key, district, lat, lon)
        VALUES (?, ?, ?, ?, 'Lucknow', ?, ?)
    """, (dev_id, locality_id, project_name.strip(), project_name.strip().lower(), lat, lon))
    
    row = c.execute("SELECT id FROM developments WHERE lower(name)=lower(?)", (project_name.strip(),)).fetchone()
    return row["id"] if row else None

def extract_prices_from_pending():
    if not API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in .env")

    with get_db() as c:
        pending = c.execute("""
            SELECT id, title, body FROM raw_docs 
            WHERE id NOT IN (SELECT raw_doc_id FROM extraction_log)
            ORDER BY id ASC LIMIT 25
        """).fetchall()

    if not pending:
        return 0

    extracted_count = 0
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

    for doc in pending:
        doc_id = doc["id"]
        text = f"{doc['title']}\n{doc['body']}"

        if not has_price_signal(text):
            with get_db() as c:
                c.execute("INSERT OR REPLACE INTO extraction_log (raw_doc_id, status) VALUES (?, 'no_signals')", (doc_id,))
            continue

        prompt = f"""You are a specialized real estate intelligence parser for Lucknow, Uttar Pradesh.
Extract EVERY real estate price, plot rate, registry rate, or new project mentioned in the text.
Discover both localities (e.g. sectors, villages, colonies) and real estate projects/builders.

Return ONLY a JSON array of objects. Format:
[
  {{
    "locality": "Name of area, village, or sector in Lucknow",
    "project_name": "Name of project if mentioned, or null",
    "developer_name": "Name of builder/promoter if mentioned, or null",
    "price_per_sqft": 6500,
    "property_type": "plot",
    "kind": "news_reported",
    "evidence_quote": "exact quote from text showing this rate"
  }}
]
Rules:
1. Property types: "plot", "apartment", "commercial", "villa".
2. Kind: "circle_rate", "registry", "news_reported", "listing_ask".
3. Return [] if no specific price or per-sq-ft rate can be extracted.

Text:
{text[:5000]}
"""

        try:
            res = httpx.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
                },
                headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
                timeout=25
            )

            if res.status_code != 200:
                continue

            raw_json = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            items = json.loads(raw_json)

            with get_db() as c:
                for it in items:
                    loc_name = it.get("locality")
                    psf = it.get("price_per_sqft")
                    if not loc_name or not psf or psf <= 0:
                        continue

                    loc_id = resolve_or_create_locality(c, loc_name)

                    if it.get("project_name"):
                        resolve_or_create_project(c, it["project_name"], it.get("developer_name"), loc_id)

                    c.execute("""
                        INSERT INTO observations (locality_id, raw_doc_id, price_per_sqft, property_type, kind, evidence_quote)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        loc_id, doc_id, float(psf),
                        it.get("property_type", "plot"),
                        it.get("kind", "news_reported"),
                        it.get("evidence_quote", "")
                    ))
                    extracted_count += 1

                c.execute("INSERT OR REPLACE INTO extraction_log (raw_doc_id, status) VALUES (?, 'success')", (doc_id,))
                time.sleep(1.0)

        except Exception as e:
            with get_db() as c:
                c.execute("INSERT OR REPLACE INTO extraction_log (raw_doc_id, status) VALUES (?, 'failed')", (doc_id,))

    return extracted_count
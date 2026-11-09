# src/propintel/main.py
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from propintel.db import get_db, init_db

app = FastAPI(title="PropIntel Enterprise Geospatial")

@app.on_event("startup")
def startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = Path(__file__).resolve().parents[2] / "web" / "index.html"
    return html_path.read_text()

@app.get("/api/projects.geojson")
def get_projects():
    with get_db() as c:
        rows = c.execute("""
            SELECT d.id, d.name AS project, dv.name AS developer, d.rera_reg_no,
                   d.project_type, d.rera_status, d.lat, d.lon, l.name AS locality,
                   (
                       SELECT json_group_array(json_object(
                           'unit_type', dp.unit_type,
                           'price_sqft', dp.price_per_sqft,
                           'total_min', dp.total_min_inr,
                           'total_max', dp.total_max_inr
                       ))
                       FROM development_prices dp 
                       WHERE dp.development_id = d.id
                   ) AS price_brackets
            FROM developments d
            JOIN developers dv ON dv.id = d.developer_id
            LEFT JOIN localities l ON l.id = d.locality_id
            WHERE d.lat IS NOT NULL
        """).fetchall()

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {
                "id": r["id"],
                "project": r["project"],
                "developer": r["developer"],
                "rera_reg_no": r["rera_reg_no"],
                "project_type": r["project_type"],
                "status": r["rera_status"],
                "locality": r["locality"],
                "prices": json.loads(r["price_brackets"]) if r["price_brackets"] else []
            }
        })
    return {"type": "FeatureCollection", "features": features}

@app.get("/api/parcels.geojson")
def get_parcels():
    with get_db() as c:
        rows = c.execute("""
            SELECT p.id, p.khasra_no, p.village, p.tehsil, p.area_sqm, p.geojson_geom,
                   l.name AS locality, l.circle_rate_sqft
            FROM parcels p
            LEFT JOIN localities l ON l.id = p.locality_id
        """).fetchall()

    features = []
    for r in rows:
        geom = json.loads(r["geojson_geom"])
        sqft = round(r["area_sqm"] * 10.7639, 1) if r["area_sqm"] else None
        rate = r["circle_rate_sqft"] or 4500
        indicative_val = round(sqft * rate) if sqft else None

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "khasra_no": r["khasra_no"],
                "village": r["village"],
                "tehsil": r["tehsil"],
                "area_sqft": sqft,
                "circle_rate_sqft": rate,
                "indicative_valuation_inr": indicative_val
            }
        })
    return {"type": "FeatureCollection", "features": features}

@app.get("/api/observations.geojson")
def get_observations():
    with get_db() as c:
        rows = c.execute("""
            SELECT o.id, o.price_per_sqft, o.property_type, o.kind, o.evidence_quote, o.observed_on,
                   l.name AS locality, l.lat, l.lon, rd.title AS doc_title, rd.url AS doc_url
            FROM observations o
            JOIN localities l ON l.id = o.locality_id
            LEFT JOIN raw_docs rd ON rd.id = o.raw_doc_id
            WHERE l.lat IS NOT NULL
        """).fetchall()

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {
                "id": r["id"],
                "locality": r["locality"],
                "price_sqft": r["price_per_sqft"],
                "property_type": r["property_type"],
                "kind": r["kind"],
                "evidence_quote": r["evidence_quote"],
                "doc_title": r["doc_title"],
                "doc_url": r["doc_url"],
                "observed_on": r["observed_on"]
            }
        })
    return {"type": "FeatureCollection", "features": features}
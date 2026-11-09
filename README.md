The pipeline is now completely dynamic. All hardcoded seed arrays, static parcel mocks, and manual locality registries have been eliminated.

---

### How the Autonomous Loop Operates

1. **Macro Discovery:** `search_engine.py` executes broad queries against unblocked Google News RSS endpoints to pick up state policy revisions, LDA (Lucknow Development Authority) land auctions, UP-RERA registrations, and real estate news.


2. **Raw Ingestion & Deduplication:** Content is parsed with BeautifulSoup and stored in `raw_docs` with SHA-256 hash checks to prevent duplicate token spend.


3. **Information Extraction:** `engine.py` calls Gemini (`gemini-2.5-flash`) to parse prices per sq ft, property types, evidence quotes, locality names, and project/builder identities.


4. **On-the-Fly Geocoding:** When an unfamiliar locality is encountered, `resolve_or_create_locality()` queries OpenStreetMap's Nominatim geocoder, extracts latitude and longitude, and registers it in `localities`. Discovered projects inherit these coordinates so they immediately appear on maps.


5. **Dynamic Self-Feeding:** On the next cycle, `search_engine.py` reads the newly discovered localities directly from SQLite (`SELECT name FROM localities ... ORDER BY id DESC LIMIT 8`) to initiate targeted micro-market searches.


6. **Continuous Scheduling:** `worker.py` runs this cycle continuously in an infinite loop every 1,800 seconds (30 minutes).



---

### BEGIN
```bash
    # 1. Initialize DB and run the first search & extraction cycle
    PYTHONPATH=src .venv/bin/python -c "from propintel.db import init_db; init_db()"
    PYTHONPATH=src .venv/bin/python -c "from propintel.search_engine import search_and_ingest; search_and_ingest()"
    PYTHONPATH=src .venv/bin/python -c "from propintel.engine import extract_prices_from_pending; extract_prices_from_pending()"

    # 2. Start the server (Terminal 1)
    PYTHONPATH=src .venv/bin/python -m uvicorn propintel.main:app --host 0.0.0.0 --port 8000 --reload

    # 3. Release the continuous crawler daemon (Terminal 2)
    PYTHONPATH=src .venv/bin/python -m propintel.worker
```

### How to Restart and Run the System

Whenever you restart your machine or restart the project, start the two processes in separate terminal tabs or inside a terminal multiplexer like `tmux`.

#### 1. Start the Geospatial API Server

Runs FastAPI and serves the map interface and GeoJSON feeds on port 8000.

```bash
cd ~/Desktop/Projects/propintel_clean
PYTHONPATH=src .venv/bin/python -m uvicorn propintel.main:app --host 0.0.0.0 --port 8000 --reload

```

* **Map Dashboard:** `http://localhost:8000/`


* **Price Observations Endpoint:** `http://localhost:8000/api/observations.geojson`


* **Projects Endpoint:** `http://localhost:8000/api/projects.geojson`



#### 2. Release the Autonomous Worker Daemon

Crawls news feeds, runs LLM extractions, geocodes locations, and updates SQLite every 30 minutes.

```bash
cd ~/Desktop/Projects/propintel_clean
PYTHONPATH=src .venv/bin/python -m propintel.worker

```

#### Running Headless in the Background (Optional)

If you want the worker to keep running after closing the terminal:

```bash
cd ~/Desktop/Projects/propintel_clean
PYTHONPATH=src nohup .venv/bin/python -m propintel.worker > worker.log 2>&1 &

```

To check logs:

```bash
tail -f worker.log

```

To stop the background worker:

```bash
pkill -f "propintel.worker"

```

---

### Project Documentation (`PROJECT_INFO.md`)

Save the following markdown as `PROJECT_INFO.md` in the project root:

```markdown
# PropIntel — Autonomous Real Estate Geospatial Intelligence Engine

PropIntel is a continuous real estate data collection, entity-extraction, and geospatial mapping system for Lucknow, Uttar Pradesh, India. The engine requires zero manual data entry; it crawls public news feeds, uses an LLM to extract transactional values and project data, geocodes coordinates on the fly, and serves live GeoJSON layers.

## System Components

- **`src/propintel/db.py`**: SQLite database initialization configured in WAL mode. Tracks master localities, developers, development projects, raw documents, and price observations.
- **`src/propintel/search_engine.py`**: Autonomous crawler utilizing Google News RSS search endpoints. Avoids bot-blocking and CAPTCHAs while crawling full article text when accessible. Dynamically seeds subsequent queries with previously discovered localities.
- **`src/propintel/engine.py`**: Intelligence extraction module powered by Google Gemini (`gemini-2.5-flash`). Identifies price-per-square-foot metrics, projects, and builders. Integrates OSM Nominatim geocoding for runtime spatial coordinate resolution.
- **`src/propintel/worker.py`**: Scheduled ingestion daemon running automated continuous crawls and extraction cycles on a 30-minute interval.
- **`src/propintel/main.py`**: FastAPI geospatial application serving an interactive frontend and dynamic GeoJSON feature collections for live observations, projects, and cadastral boundaries.

## Architecture Dataflow


```

[City News & RSS] ──> [search_engine.py] ──> [raw_docs Table]
│
▼
[Nominatim API] <─── [engine.py (Gemini)] <─────────┘
│                    │
▼                    ▼
[localities Table]   [observations Table] & [developments Table]
│                                         │
└─────────────────┬───────────────────────┘
│
▼
[main.py (FastAPI GeoJSON)]
│
▼
[Web Geospatial Interface]

```

## Running the Engine

1. **Environment Setup**:
   Ensure `.env` contains:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash

```

2. **Launch Server**:
```bash
PYTHONPATH=src .venv/bin/python -m uvicorn propintel.main:app --host 0.0.0.0 --port 8000 --reload

```


3. **Launch Worker**:
```bash
PYTHONPATH=src .venv/bin/python -m propintel.worker

```



```

---

### Detailed Prompt to Recreate This Project From Scratch

Save the following specification as `AI_BUILD_PROMPT.md`:

```markdown
Build a production-ready, autonomous real estate geospatial intelligence engine in Python named "PropIntel" focused on Lucknow, Uttar Pradesh, India.

SYSTEM PHILOSOPHY:
Zero static data. No hardcoded arrays of localities, builders, or project names. The system must autonomously search the web, ingest text, extract structured data via LLM, geocode locations on the fly, and continuously feed its own search queue.

TECH STACK:
- Python 3.11+
- SQLite3 with WAL mode enabled
- FastAPI & Uvicorn
- Google Gemini API (`gemini-2.5-flash`) via `httpx`
- `feedparser`, `beautifulsoup4`, `lxml`
- OpenStreetMap Nominatim API for geocoding

REQUIRED MODULES & SPECIFICATIONS:

1. `src/propintel/db.py`:
   - Initialize SQLite with WAL mode and foreign keys enabled.
   - Tables:
     * `localities`: `id`, `name`, `district` (default 'Lucknow'), `lat`, `lon`, `circle_rate_sqft`, UNIQUE(`name`, `district`).
     * `developers`: `id`, `name` (UNIQUE), `name_key`, `rera_promoter_no`.
     * `developments`: `id`, `developer_id` (FK), `locality_id` (FK), `name`, `name_key`, `rera_reg_no` (UNIQUE), `district`, `project_type`, `rera_status`, `lat`, `lon`, `completion_date`.
     * `development_prices`: `id`, `development_id` (FK), `unit_type`, `price_per_sqft`, `total_min_inr`, `total_max_inr`, `kind`, `observed_on`.
     * `parcels`: `id`, `locality_id` (FK), `district`, `tehsil`, `village`, `khasra_no`, `area_sqm`, `geojson_geom`, UNIQUE(`district`, `village`, `khasra_no`).
     * `raw_docs`: `id`, `source`, `url`, `title`, `body`, `content_hash` (UNIQUE), `fetched_at`.
     * `observations`: `id`, `locality_id` (FK), `raw_doc_id` (FK), `price_per_sqft`, `property_type`, `kind`, `evidence_quote`, `observed_on`, `created_at`.
     * `extraction_log`: `raw_doc_id` (PK, FK), `status`, `processed_at`.

2. `src/propintel/search_engine.py`:
   - Must use Google News RSS search endpoints (`https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en`) via `feedparser` to avoid bot blocks and CAPTCHAs.
   - Broad discovery topics: LDA plot schemes, Lucknow DM circle rates, UP-RERA launches, registry price revisions.
   - Dynamic query queue: Fetch the last 8 discovered localities from the database and generate micro-market queries (`"{locality} Lucknow property rate sq ft"`).
   - Attempt to fetch article body using `httpx` with short timeouts (3s connect, 4s read). Fall back to the RSS snippet if blocked or timed out.
   - Clean HTML with BeautifulSoup and insert into `raw_docs` using SHA-256 hashing on `url + title` for deduplication.

3. `src/propintel/engine.py`:
   - Fetch up to 25 pending documents from `raw_docs` not yet logged in `extraction_log`.
   - Pre-filter documents for real estate keywords (`circle rate`, `sq ft`, `sqft`, `plot`, `rera`, `bhk`, `launch`, etc.) before calling the LLM.
   - Prompt Gemini (`gemini-2.5-flash`) with structured JSON schema output:
     `[{"locality": str, "project_name": str|null, "developer_name": str|null, "price_per_sqft": float, "property_type": str, "kind": str, "evidence_quote": str}]`.
   - `resolve_or_create_locality()`: Check if locality exists in DB. If not, geocode via Nominatim OSM (`https://nominatim.openstreetmap.org/search?q={name},+Lucknow,+India&format=json&limit=1`) with a custom User-Agent, insert into `localities`, and return the ID.
   - `resolve_or_create_project()`: Register developer and development project. Automatically inherit parent locality `lat` and `lon` so newly discovered developments plot properly on maps.
   - Record extracted prices in `observations` and update `extraction_log`.

4. `src/propintel/worker.py`:
   - Daemon running an infinite loop with a 1,800-second (30-minute) sleep interval.
   - In each cycle, call `search_and_ingest()` followed by `extract_prices_from_pending()`. Log results.

5. `src/propintel/main.py`:
   - FastAPI application.
   - `GET /`: Serve `web/index.html`.
   - `GET /api/observations.geojson`: Return a GeoJSON FeatureCollection of price observations with properties (`price_sqft`, `locality`, `property_type`, `kind`, `evidence_quote`, `doc_url`, `doc_title`, `observed_on`). Filter `WHERE l.lat IS NOT NULL`.
   - `GET /api/projects.geojson`: Return a GeoJSON FeatureCollection of registered developments with project name, developer, RERA status, and pricing brackets. Filter `WHERE d.lat IS NOT NULL`.
   - `GET /api/parcels.geojson`: Return cadastral geometries with estimated valuations.

Ensure all imports are aligned, error handling prevents thread crashes, and code executes cleanly under `PYTHONPATH=src`.

```
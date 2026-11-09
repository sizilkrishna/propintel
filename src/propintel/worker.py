# src/propintel/worker.py
import time
import logging
from propintel.engine import extract_prices_from_pending
from propintel.search_engine import search_and_ingest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def run_pipeline_cycle():
    logging.info("--- Starting Autonomous Ingestion Cycle ---")
    
    # 1. Dynamic Search Ingestion
    searched_docs = search_and_ingest(max_results_per_query=2)
    logging.info(f"[Worker] Ingested {searched_docs} documents via live web search.")

    # 2. LLM Extraction & Geo-Indexing
    extracted = extract_prices_from_pending()
    logging.info(f"[Worker] Extracted {extracted} verified price observations into DB.")

def start_worker(interval_seconds: int = 1800):
    """Runs continuous background searches and extractions."""
    logging.info(f"Worker service running. Interval: {interval_seconds}s.")
    while True:
        try:
            run_pipeline_cycle()
        except Exception as e:
            logging.error(f"[Worker Failure] {e}", exc_info=True)
        
        logging.info(f"Sleeping for {interval_seconds}s before next cycle...")
        time.sleep(interval_seconds)

if __name__ == "__main__":
    start_worker(interval_seconds=1800)
"""
One-off script to backfill the SQL `schemes` table with official_url values.

Why this exists: ingest_directory() (used both here and at server startup)
only writes to ChromaDB - it never touches the SQL Scheme table. Only the
/schemes/upload admin route did that. So official_url was never getting
saved to SQL via auto-ingest, which is why /schemes/urls was returning {}.

Run once from your project root (same folder as main.py):
    python backfill_urls.py

Safe to re-run - it upserts (updates existing rows instead of duplicating).
"""
from pathlib import Path

from app.rag.ingest import ingest_directory
from app.models import Scheme
from app.db import get_db

SAMPLE_SCHEMES_DIR = "./data/sample_schemes"


def main():
    summary = ingest_directory(SAMPLE_SCHEMES_DIR)
    if not summary:
        print(f"No .pdf/.txt/.md files found in {SAMPLE_SCHEMES_DIR}")
        return

    db_gen = get_db()
    db = next(db_gen)
    try:
        for filename, result in summary.items():
            # Same name-derivation ingest_directory() uses internally, so
            # this matches whatever scheme name it already indexed under.
            scheme_name = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
            existing = db.query(Scheme).filter(Scheme.name == scheme_name).first()
            if existing:
                existing.official_url = result["official_url"]
                existing.source_file = filename
            else:
                db.add(Scheme(name=scheme_name, official_url=result["official_url"], source_file=filename))
            print(f"  {scheme_name}: official_url={result['official_url']!r}")
        db.commit()
    finally:
        db_gen.close()

    print("Backfill complete.")


if __name__ == "__main__":
    main()

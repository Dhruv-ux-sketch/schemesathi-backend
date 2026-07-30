from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.config import settings
from app.db import init_db
from app.rate_limit import limiter
from app.routes import chat, schemes, auth, chats, bookmarks

print(f"[DEBUG] ALLOWED_ORIGINS raw: {settings.ALLOWED_ORIGINS!r}")
print(f"[DEBUG] allowed_origins_list: {settings.allowed_origins_list!r}")

app = FastAPI(
    title="SchemeSathi API",
    description="AI assistant for discovering and understanding government schemes",
    version="0.2.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Absolute path to the bundled sample schemes, regardless of the working
# directory the server process was started from (this matters on hosts like
# Render, where the CWD during startup isn't always the repo root).
SAMPLE_SCHEMES_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_schemes"


@app.on_event("startup")
def on_startup():
    init_db()

    # On free-tier hosting (e.g. Render), the disk is wiped on every cold
    # start/restart, which would empty the vector database. Since the base
    # scheme documents are bundled with the code (not the disk), we can
    # safely re-index them automatically whenever the collection is empty.
    # Schemes added later via the admin panel are NOT bundled with the code,
    # so they will NOT survive a restart on free-tier hosting - see README.
    from app.rag.vector_store import list_schemes
    from app.rag.ingest import ingest_directory
    from app.models import Scheme
    from app.db import get_db

    has_vector_data = bool(list_schemes())

    # Checking ChromaDB alone isn't enough: it and the SQL `schemes` table
    # (which is what actually stores official_url, served by /schemes/urls)
    # can get out of sync - e.g. chroma_db/ persists across a restart while
    # schemesathi.db gets reset, or vice versa. If either store is missing
    # official_url data, re-ingest so both stay consistent.
    db_gen = get_db()
    db = next(db_gen)
    try:
        has_url_data = db.query(Scheme).filter(Scheme.official_url.isnot(None)).first() is not None
    finally:
        db_gen.close()

    if has_vector_data and has_url_data:
        print("[startup] Vector store and scheme URLs already present, skipping auto-ingest.")
        return

    if not SAMPLE_SCHEMES_DIR.exists():
        print(f"[startup] WARNING: sample schemes directory not found at {SAMPLE_SCHEMES_DIR}")
        return

    print(f"[startup] Vector store is empty. Auto-ingesting from {SAMPLE_SCHEMES_DIR} ...")
    summary = ingest_directory(str(SAMPLE_SCHEMES_DIR))
    if not summary:
        print(f"[startup] WARNING: no .pdf/.txt/.md files found in {SAMPLE_SCHEMES_DIR}")
    else:
        # NOTE: ingest_directory returns {filename: {"chunks_added": int, "official_url": str|None}}
        # per file, not a plain chunk count - so we unpack the dict here instead of
        # printing it raw (that was the earlier bug: `count` was the whole dict).
        for filename, result in summary.items():
            print(
                f"[startup] Indexed {filename}: {result['chunks_added']} chunks, "
                f"official_url={result['official_url']!r}"
            )


app.include_router(chat.router)
app.include_router(schemes.router)
app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(bookmarks.router)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "SchemeSathi API",
        "llm_provider": settings.LLM_PROVIDER,
    }

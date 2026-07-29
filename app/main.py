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

    from app.rag.vector_store import list_schemes
    from app.rag.ingest import ingest_directory, extract_text, extract_official_url
    from app.db import SessionLocal
    from app.models import Scheme

    def backfill_scheme_urls():
        """Populate/refresh official_url in the Scheme table from the bundled
        sample scheme files, without touching the vector store."""
        if not SAMPLE_SCHEMES_DIR.exists():
            return
        db = SessionLocal()
        try:
            for path in SAMPLE_SCHEMES_DIR.glob("*"):
                if path.suffix.lower() not in (".pdf", ".txt", ".md"):
                    continue
                scheme_name = path.stem.replace("_", " ").replace("-", " ").strip()
                try:
                    text = extract_text(str(path))
                except Exception as e:
                    print(f"[startup] Could not read {path.name}: {e}")
                    continue
                official_url = extract_official_url(text)
                if not official_url:
                    continue
                existing = db.query(Scheme).filter(Scheme.name == scheme_name).first()
                if existing:
                    existing.official_url = official_url
                    existing.source_file = path.name
                else:
                    db.add(Scheme(name=scheme_name, official_url=official_url, source_file=path.name))
            db.commit()
            print("[startup] Scheme URLs backfilled.")
        finally:
            db.close()

    if list_schemes():
        print("[startup] Vector store already has schemes indexed, skipping auto-ingest.")
        backfill_scheme_urls()
        return

    if not SAMPLE_SCHEMES_DIR.exists():
        print(f"[startup] WARNING: sample schemes directory not found at {SAMPLE_SCHEMES_DIR}")
        return

    print(f"[startup] Vector store is empty. Auto-ingesting from {SAMPLE_SCHEMES_DIR} ...")
    summary = ingest_directory(str(SAMPLE_SCHEMES_DIR))
    if not summary:
        print(f"[startup] WARNING: no .pdf/.txt/.md files found in {SAMPLE_SCHEMES_DIR}")
    else:
        for filename, result in summary.items():
            print(f"[startup] Indexed {filename}: {result['chunks_added']} chunks")

    backfill_scheme_urls()


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

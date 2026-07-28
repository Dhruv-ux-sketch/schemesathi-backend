from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.config import settings
from app.db import init_db
from app.rate_limit import limiter
from app.routes import chat, schemes, auth, chats, bookmarks

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


@app.on_event("startup")
def on_startup():
    init_db()


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

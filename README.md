# SchemeSathi Backend

FastAPI + RAG backend for the AI government scheme assistant.

## How this is designed for "no API key yet"

The RAG pipeline is split into two independent stages:

1. **Retrieval** (embeddings + ChromaDB) — runs **100% locally** using
   `sentence-transformers`. No API key, no cost. This is most of the actual
   engineering work in a RAG system, and you can build/test/demo it today.
2. **Generation** (turning retrieved chunks into a natural-language answer) —
   this is the only part that needs an LLM API key. Until you add one,
   `LLM_PROVIDER=none` and the API returns the raw retrieved excerpts instead
   of a generated answer, so the rest of the pipeline (and your frontend) can
   be built and tested end-to-end right now.

## Setup

```bash
cd schemesathi-backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

First run will download the local embedding model (~80MB, one-time).

## Ingest the sample scheme documents

Three sample schemes (PM-Kisan, Ayushman Bharat, NMMSS Scholarship) are
included in `data/sample_schemes/` so you can test retrieval immediately.

```bash
python -m app.rag.ingest
```

You should see output like:
```
Ingestion complete:
  PM-Kisan.txt: 3 chunks
  Ayushman-Bharat.txt: 3 chunks
  NMMSS-Scholarship.txt: 4 chunks
```

## Run the server

```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive Swagger docs.

## Try it

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What documents do I need for Ayushman Bharat?"}'
```

With `LLM_PROVIDER=none`, you'll get the raw matched excerpts back with
source attribution — proof the retrieval half of RAG is working.

## Adding an LLM key later (for natural-language generation)

You have two straightforward options:

**Option A — OpenAI**
1. Go to https://platform.openai.com/api-keys, create a key.
2. Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=sk-...` in `.env`.
3. Pay-as-you-go; `gpt-4o-mini` (the default here) is inexpensive, good for
   a project like this.

**Option B — Anthropic (Claude)**
1. Go to https://console.anthropic.com, create a key.
2. Set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=sk-ant-...` in `.env`.
3. Also pay-as-you-go, similar pricing tier to OpenAI's small models.

Either works — the code in `app/rag/llm.py` already supports both, so it's
just an env variable change, no code changes needed. If you're a student,
check whether OpenAI/Anthropic have education credits available, or start
with free tiers/trial credits to test before committing to a paid key.

## Adding your own real scheme PDFs

Drop `.pdf` files into `data/sample_schemes/` (filename becomes the scheme
name, e.g. `PM-Awas-Yojana.pdf`) and re-run:
```bash
python -m app.rag.ingest
```

Or use the admin API once the server is running:
```bash
curl -X POST http://localhost:8000/schemes/upload \
  -F "scheme_name=PM Awas Yojana" \
  -F "file=@/path/to/scheme.pdf"
```

## Project structure

```
app/
  main.py              FastAPI app + CORS + router registration
  config.py            Settings loaded from .env
  schemas.py           Pydantic request/response models
  rag/
    chunker.py         Splits document text into overlapping chunks
    vector_store.py    ChromaDB wrapper (local embeddings, add/query/delete)
    ingest.py           PDF/text extraction -> chunk -> embed -> store
    llm.py              Provider-agnostic answer generation (OpenAI/Anthropic/none)
  routes/
    chat.py             POST /chat - the core RAG query endpoint
    schemes.py          GET/POST/DELETE /schemes - admin scheme management
data/
  sample_schemes/       Sample scheme docs to test with
  chroma_db/             Persistent vector store (gitignored)
```

## Endpoints

| Method | Path              | Purpose                                  |
|--------|-------------------|-------------------------------------------|
| GET    | `/`               | Health check                              |
| POST   | `/chat`           | Ask a question, get answer + sources      |
| GET    | `/schemes`        | List all indexed scheme names             |
| POST   | `/schemes/upload` | Admin: upload + index a new scheme doc    |
| DELETE | `/schemes/{name}` | Admin: remove a scheme                    |

## Notes / next steps

- **Auth**: The admin endpoints (`/schemes/upload`, `/schemes/{name}` DELETE)
  have no auth yet — add an API key or JWT dependency before deploying.
- **Chat history / bookmarks**: Not in this scaffold yet — needs a real
  database (Postgres recommended over Firebase for relational data like
  users/chats/bookmarks) and user auth first.
- **Multilingual**: `ChatRequest.language` field exists, but the sample
  embedding model (`all-MiniLM-L6-v2`) is English-only. For Hindi support,
  swap `EMBEDDING_MODEL` to a multilingual model e.g.
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.

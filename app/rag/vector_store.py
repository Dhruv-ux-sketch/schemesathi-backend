"""
Vector store wrapper around ChromaDB.

Embeddings are generated locally via sentence-transformers, so this whole
module works with NO API key. Only the answer-generation step (llm.py)
needs a paid key, and only once you're ready for that.
"""
import uuid
from functools import lru_cache

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings


@lru_cache(maxsize=1)
def get_embedding_function():
    """
    Cached so the (fairly large) sentence-transformers model is loaded once
    per process, not once per request.
    """
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.EMBEDDING_MODEL
    )


@lru_cache(maxsize=1)
def get_client():
    return chromadb.PersistentClient(path=settings.CHROMA_DIR)


def get_collection():
    client = get_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(chunks: list[str], scheme_name: str, source_file: str) -> int:
    """Embed and store a list of text chunks tied to one scheme document."""
    if not chunks:
        return 0

    collection = get_collection()
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"scheme_name": scheme_name, "source_file": source_file} for _ in chunks]

    collection.add(documents=chunks, ids=ids, metadatas=metadatas)
    return len(chunks)


def query(question: str, top_k: int | None = None, where: dict | None = None) -> list[dict]:
    """
    Return the top_k most relevant chunks for a question.
    `where` can filter by metadata, e.g. {"scheme_name": "PM-Kisan"}.
    """
    collection = get_collection()
    top_k = top_k or settings.TOP_K

    results = collection.query(
        query_texts=[question],
        n_results=top_k,
        where=where,
    )

    hits = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, distances):
        hits.append({
            "text": doc,
            "scheme_name": meta.get("scheme_name", "Unknown"),
            "source_file": meta.get("source_file", "Unknown"),
            "score": 1 - dist,  # convert cosine distance to a similarity-like score
        })
    return hits


def delete_scheme(scheme_name: str) -> int:
    """Remove all chunks belonging to a scheme (for admin 'remove outdated scheme')."""
    collection = get_collection()
    existing = collection.get(where={"scheme_name": scheme_name})
    ids = existing.get("ids", [])
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def list_schemes() -> list[str]:
    """Return the distinct scheme names currently stored."""
    collection = get_collection()
    all_meta = collection.get(include=["metadatas"]).get("metadatas", [])
    return sorted({m["scheme_name"] for m in all_meta if m and "scheme_name" in m})

"""
Ingestion pipeline: file -> text -> chunks -> embeddings -> ChromaDB.
Handles .pdf and .txt scheme documents.
"""
import re
from pathlib import Path

from pypdf import PdfReader

from app.rag.chunker import chunk_text
from app.rag.vector_store import add_chunks


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif path.suffix.lower() in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")


def extract_official_url(text: str) -> str | None:
    """Pull out a line like 'Official Website: https://...' if present."""
    match = re.search(r"Official Website:\s*(\S+)", text, re.IGNORECASE)
    return match.group(1) if match else None


def ingest_file(file_path: str, scheme_name: str) -> dict:
    """
    Extract, chunk, embed, and store a single scheme document.
    Returns {"chunks_added": int, "official_url": str | None}.
    """
    text = extract_text(file_path)
    chunks = chunk_text(text)
    source_file = Path(file_path).name
    chunks_added = add_chunks(chunks, scheme_name=scheme_name, source_file=source_file)
    return {"chunks_added": chunks_added, "official_url": extract_official_url(text)}


def ingest_directory(directory: str) -> dict[str, dict]:
    """
    Bulk-ingest every .pdf/.txt/.md file in a directory.
    """
    results = {}
    for path in Path(directory).glob("*"):
        if path.suffix.lower() in (".pdf", ".txt", ".md"):
            scheme_name = path.stem.replace("_", " ").replace("-", " ").strip()
            result = ingest_file(str(path), scheme_name=scheme_name)
            results[path.name] = result
    return results


if __name__ == "__main__":
    import sys
    directory = sys.argv[1] if len(sys.argv) > 1 else "./data/sample_schemes"
    summary = ingest_directory(directory)
    print("Ingestion complete:")
    for filename, result in summary.items():
        print(f"  {filename}: {result['chunks_added']} chunks, url={result['official_url']}")
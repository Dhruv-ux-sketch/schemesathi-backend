"""
Ingestion pipeline: file -> text -> chunks -> embeddings -> ChromaDB.
Handles .pdf and .txt scheme documents.
"""
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


def ingest_file(file_path: str, scheme_name: str) -> int:
    """
    Extract, chunk, embed, and store a single scheme document.
    Returns the number of chunks added.
    """
    text = extract_text(file_path)
    chunks = chunk_text(text)
    source_file = Path(file_path).name
    return add_chunks(chunks, scheme_name=scheme_name, source_file=source_file)


def ingest_directory(directory: str) -> dict[str, int]:
    """
    Bulk-ingest every .pdf/.txt/.md file in a directory.
    Uses the filename (without extension) as the scheme name unless you
    rename files sensibly first, e.g. 'PM-Kisan.txt' -> scheme_name 'PM-Kisan'.
    """
    results = {}
    for path in Path(directory).glob("*"):
        if path.suffix.lower() in (".pdf", ".txt", ".md"):
            scheme_name = path.stem.replace("_", " ").replace("-", " ").strip()
            count = ingest_file(str(path), scheme_name=scheme_name)
            results[path.name] = count
    return results


if __name__ == "__main__":
    # Quick manual run: python -m app.rag.ingest
    import sys
    directory = sys.argv[1] if len(sys.argv) > 1 else "./data/sample_schemes"
    summary = ingest_directory(directory)
    print("Ingestion complete:")
    for filename, count in summary.items():
        print(f"  {filename}: {count} chunks")

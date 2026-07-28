"""
Simple character-based chunker with overlap.
Good enough for scheme PDFs/text where paragraphs are the natural unit.
For production, consider a sentence-aware splitter (e.g. nltk / spacy sentence tokenizer)
so chunks don't cut mid-sentence.
"""
from app.config import settings


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    text = " ".join(text.split())  # normalize whitespace
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # try not to cut mid-word: extend to next space if we're not at the end
        if end < len(text):
            last_space = chunk.rfind(" ")
            if last_space > chunk_size * 0.5:  # don't shrink chunk too aggressively
                chunk = chunk[:last_space]
                end = start + last_space

        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap
        if start <= 0:
            start = end  # safety against infinite loop on tiny chunk_size

    return chunks

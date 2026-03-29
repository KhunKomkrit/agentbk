"""Text chunker — split documents into overlapping fixed-size chunks."""
from __future__ import annotations

_CHUNK_SIZE    = 500   # characters
_CHUNK_OVERLAP = 50


def chunk_text(
    text: str,
    size: int = _CHUNK_SIZE,
    overlap: int = _CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks of ~size characters.

    Tries to break at paragraph/sentence boundaries first;
    falls back to hard character split if the segment is too long.
    """
    # Split on double-newlines first (paragraph boundaries)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks: list[str] = []
    buf = ""

    for para in paragraphs:
        # If paragraph itself exceeds chunk size, break it by sentences then chars
        if len(para) > size:
            sentences = _split_sentences(para)
            for sent in sentences:
                if len(buf) + len(sent) + 1 <= size:
                    buf = (buf + " " + sent).strip() if buf else sent
                else:
                    if buf:
                        chunks.append(buf)
                    # Sentence itself too long — hard break
                    if len(sent) > size:
                        for start in range(0, len(sent), size - overlap):
                            chunks.append(sent[start : start + size])
                        buf = sent[-(overlap):]
                    else:
                        buf = sent
        else:
            if len(buf) + len(para) + 2 <= size:
                buf = (buf + "\n\n" + para).strip() if buf else para
            else:
                if buf:
                    chunks.append(buf)
                buf = para

    if buf:
        chunks.append(buf)

    return [c for c in chunks if c.strip()]


def _split_sentences(text: str) -> list[str]:
    """Naive sentence splitter on Thai/English punctuation."""
    import re
    parts = re.split(r"(?<=[.!?।\u0e2f])\s+", text)
    return [p.strip() for p in parts if p.strip()]

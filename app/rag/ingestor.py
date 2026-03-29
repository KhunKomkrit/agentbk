"""File ingestor — PDF/TXT/MD → RAGStore."""
from __future__ import annotations
from pathlib import Path


def ingest_file(path: Path, store: "RAGStore") -> str:  # type: ignore[name-defined]
    """Read a file, chunk, embed, and add to RAGStore. Returns doc_id."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _read_pdf(path)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")

    doc_id = path.name
    store.add_document(
        doc_id   = doc_id,
        text     = text,
        metadata = {"source": path.name, "path": str(path)},
    )
    return doc_id


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    pages  = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            pages.append(t)
    return "\n\n".join(pages)

"""RAGStore — ChromaDB-backed vector store for AgentBK knowledge base."""
from __future__ import annotations
from pathlib import Path

_DB_PATH    = Path("~/.agentbk/rag").expanduser()
_COLLECTION = "agentbk_kb"


class RAGStore:
    def __init__(self, path: Path = _DB_PATH) -> None:
        import chromadb
        self._client = chromadb.PersistentClient(path=str(path))
        self._col    = self._client.get_or_create_collection(
            name=_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    # ── write ─────────────────────────────────────────────────────────────────

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: dict | None = None,
    ) -> int:
        """Chunk text, embed, and upsert into the collection. Returns chunk count."""
        from app.rag.chunker import chunk_text
        from app.rag.embedder import embed

        chunks = chunk_text(text)
        if not chunks:
            return 0

        embeddings = embed(chunks)
        ids        = [f"{doc_id}__chunk{i}" for i in range(len(chunks))]
        metas      = [{**(metadata or {}), "doc_id": doc_id, "chunk": i}
                      for i in range(len(chunks))]

        self._col.upsert(
            ids        = ids,
            documents  = chunks,
            embeddings = embeddings,
            metadatas  = metas,
        )
        return len(chunks)

    def delete_document(self, doc_id: str) -> None:
        """Remove all chunks belonging to doc_id."""
        results = self._col.get(where={"doc_id": doc_id})
        if results["ids"]:
            self._col.delete(ids=results["ids"])

    def clear(self) -> None:
        """Drop and recreate the collection."""
        self._client.delete_collection(_COLLECTION)
        self._col = self._client.get_or_create_collection(
            name=_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    # ── read ──────────────────────────────────────────────────────────────────

    def search(self, query: str, k: int = 4) -> list[str]:
        """Return top-k most relevant text chunks for the query."""
        if self._col.count() == 0:
            return []
        from app.rag.embedder import embed
        q_vec = embed([query])[0]
        results = self._col.query(
            query_embeddings=[q_vec],
            n_results=min(k, self._col.count()),
        )
        return results["documents"][0] if results["documents"] else []

    def list_documents(self) -> list[dict]:
        """Return unique documents with metadata (name, chunk_count)."""
        if self._col.count() == 0:
            return []
        all_items = self._col.get(include=["metadatas"])
        seen: dict[str, dict] = {}
        for meta in all_items["metadatas"]:
            doc_id = meta.get("doc_id", "")
            if doc_id not in seen:
                seen[doc_id] = {
                    "doc_id":      doc_id,
                    "source":      meta.get("source", doc_id),
                    "chunk_count": 0,
                }
            seen[doc_id]["chunk_count"] += 1
        return list(seen.values())

    def has_documents(self) -> bool:
        return self._col.count() > 0

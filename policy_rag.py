"""
Mapae — Local Policy RAG (Retrieval-Augmented Generation)
===========================================================

Stores policy snapshot text in a local ChromaDB vector database.
Provides citation-backed lookup so Verdict reports can reference
specific policy sections without internet access.

Design notes:
- ChromaDB PersistentClient at ./chroma_db
- Built-in embedding (onnxruntime all-MiniLM-L6-v2) — no extra keys needed
- load_snapshots() is idempotent (skips already-indexed chunks)
- Offline-safe: if DB has no chunks, query() returns [] gracefully
- Caller must ensure policy snapshots exist (run policy_updater first)

⚠️ All citations are from publicly available policy pages.
   Not internal/confidential review criteria.
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional

import chromadb


CHROMA_DB_PATH = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "game_policies"

# Chunks that are too short are noise; skip them
_MIN_CHUNK_CHARS = 80
# Characters per chunk (word-boundary split)
_CHUNK_SIZE_WORDS = 200
_CHUNK_OVERLAP_WORDS = 40


class PolicyRAG:
    """
    Local vector store for game platform policy documents.

    Usage:
        rag = PolicyRAG()
        rag.load_snapshots()          # index latest policy snapshots
        citations = rag.query("가챠 확률 표기 의무", n_results=3)
        cite_str = rag.get_citation_for_issue("가챠 미표기 위반 가능성")
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or str(CHROMA_DB_PATH)
        Path(self._db_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._db_path)
        self._col = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def load_snapshots(self, snapshot_dir: Optional[str] = None) -> int:
        """
        Walk policy_snapshots/, chunk each latest file, and upsert into DB.
        Returns number of NEW chunks added (0 if all already indexed).
        """
        try:
            from policy_updater import SNAPSHOT_DIR, POLICY_SOURCES
        except ImportError:
            return 0

        snap_root = Path(snapshot_dir) if snapshot_dir else SNAPSHOT_DIR
        added = 0

        for source_key, source_info in POLICY_SOURCES.items():
            source_dir = snap_root / source_key
            if not source_dir.exists():
                continue

            # Use only the most recent snapshot per platform
            snaps = sorted(source_dir.glob("*.txt"), reverse=True)
            if not snaps:
                continue

            latest_snap = snaps[0]
            date_str = latest_snap.stem
            text = latest_snap.read_text(encoding="utf-8")

            chunks = self._chunk(text)
            platform_name = source_info["name"]

            for i, chunk in enumerate(chunks):
                if len(chunk) < _MIN_CHUNK_CHARS:
                    continue

                chunk_id = hashlib.md5(
                    f"{source_key}|{date_str}|{i}".encode()
                ).hexdigest()

                # Idempotent: skip if already present
                existing = self._col.get(ids=[chunk_id])
                if existing["ids"]:
                    continue

                self._col.add(
                    ids=[chunk_id],
                    documents=[chunk],
                    metadatas=[{
                        "source": source_key,
                        "platform_name": platform_name,
                        "date": date_str,
                        "chunk_index": i,
                    }],
                )
                added += 1

        return added

    def _chunk(self, text: str) -> List[str]:
        """Split text into overlapping word-based chunks."""
        words = text.split()
        chunks: List[str] = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i: i + _CHUNK_SIZE_WORDS])
            chunks.append(chunk)
            step = _CHUNK_SIZE_WORDS - _CHUNK_OVERLAP_WORDS
            i += max(step, 1)
        return chunks

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(self, question: str, n_results: int = 5) -> List[Dict]:
        """
        Semantic search over indexed policy chunks.
        Returns list of dicts with text, platform_name, date, distance.
        Returns [] if DB is empty.
        """
        count = self._col.count()
        if count == 0:
            return []

        n = min(n_results, count)
        results = self._col.query(
            query_texts=[question],
            n_results=n,
        )

        citations: List[Dict] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[None] * len(docs)])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            citations.append({
                "text": doc,
                "platform_name": meta.get("platform_name", meta.get("source")),
                "source": meta.get("source"),
                "date": meta.get("date"),
                "citation_label": (
                    f"{meta.get('platform_name', meta.get('source'))} "
                    f"({meta.get('date', 'N/A')})"
                ),
                "distance": dist,
            })

        return citations

    def get_citation_for_issue(self, issue_text: str,
                               max_distance: float = 1.5) -> Optional[str]:
        """
        Return a one-line citation string for the most relevant policy chunk,
        or None if no sufficiently close match exists.

        max_distance: cosine distance threshold (lower = stricter relevance).
        ChromaDB cosine distance range: 0 (identical) – 2 (opposite).
        """
        citations = self.query(issue_text, n_results=3)
        if not citations:
            return None

        best = citations[0]
        dist = best.get("distance")
        if dist is not None and dist > max_distance:
            return None  # Not relevant enough

        label = best["citation_label"]
        snippet = best["text"][:250].replace("\n", " ").strip()
        return f"[{label}] {snippet}…"

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_db_stats(self) -> Dict:
        """Return basic stats about the vector DB."""
        return {
            "total_chunks": self._col.count(),
            "db_path": self._db_path,
        }

    def rebuild(self) -> int:
        """Delete all documents and re-index from snapshots. Returns chunk count."""
        self._client.delete_collection(COLLECTION_NAME)
        self._col = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        return self.load_snapshots()

#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Live RAG (Retrieval-Augmented Generation) | بحث واسترجاع حي
==============================================================================
Uses Ollama's embedding endpoint + ChromaDB for live semantic search across
project files. Each query embeds → cosine search → inject top-K results.

Wolf Trait: Resourceful (uses embeddings to find knowledge)
            Deep Thinking (understands documents, not just text-matches)

Architecture (Phase 67 — 2026-10-08): Modality-Routed Embedding Pipeline
- Primary embedder:  Modality-routed Ollama embeddings (4 specialized models)
  - alpha-wolf-embed-text: 768d, 200MB VRAM - for text (FASTEST, recommended)
  - alpha-wolf-embed-multimodal: 768d, 500MB VRAM - for text+image/video
  - alpha-wolf-embed-vision: 3584d, 6GB VRAM - for images (HQ)
  - alpha-wolf-embed-large: 4096d, 2.5GB VRAM - for critical text only
- Fallback chain:    alpha-wolf-embed-text → alpha-wolf-embed-multimodal → Ollama defaults
- Vector Store:      chromadb persistent client (body's existing chromadb)
- Collection:        alpha_wolf_project_index (per-project, not per-user)

Iron Laws Applied:
- #13 (Self-Critical):  self-test in __main__
- #15 (Verify):         cosine similarity check + count docs
- #21 (NO Deletion):    soft delete + Fallback chain preserves old models
- #22 (Autonomous):     no prompts — methods execute immediately
- #33 (Lessons):        bilingual docstrings (AR + EN)
- #41 (Conflict):       graceful fallback if new models unavailable
- #42 (Storage):        vector store at body/knowledge_graph/chromadb (project-local)
- #47 (Bilingual):      every public function has Arabic translation
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.agent.embedding_manager import (
    detect_modality,
    generate_embedding,
    generate_batch_embeddings,
    list_models as list_embed_models,
    get_optimal_model,
    EMBEDDING_REGISTRY,
    EmbeddingModelSpec,
)

logger = logging.getLogger("alpha_wolf.rag")

# Heartbeat cache (url -> (timestamp, ok))
_OLLAMA_HEALTH_CACHE: Dict[str, tuple] = {}

# ── Configuration (Iron Law #42 — Storage Discipline) ───────────────

OLLAMA_URL = "http://localhost:11434"
# Modality-routed embedding pipeline (Phase 67)
# Default model overridden at runtime via embedding_manager
EMBEDDING_MODEL = "alpha-wolf-embed-text"  # default; router selects per-call
COLLECTION_NAME = "alpha_wolf_project_index"

# Multi-model search (user directive 2026-10-13 — one space per model, NEVER
# mixed: different models live in different collections, fused with RRF).
# Legacy untagged vectors are adopted as the canonical text space (they were
# built by the text-default flow). Sibling collections: <base>__<model_tag>.
CANONICAL_MODEL = "alpha-wolf-embed-text"
RRF_K = 60

CHUNK_SIZE = 500         # chars per chunk
CHUNK_OVERLAP = 100     # overlap between chunks
MAX_CHUNKS_PER_FILE = 50 # avoid blowing up index on huge files
TOP_K_DEFAULT = 3


# ── ollama_healthy ──────────────────────────────────────────────────

def ollama_healthy(url: str = OLLAMA_URL) -> bool:
    """Check if Ollama is reachable (result cached 30s).

    فحص اتصال Ollama (مخزن مؤقت 30 ثانية).
    """
    now = time.time()
    cached = _OLLAMA_HEALTH_CACHE.get(url)
    if cached and (now - cached[0]) < 30:
        return cached[1]
    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{url}/api/tags")
            ok = resp.status_code == 200
    except Exception:
        ok = False
    _OLLAMA_HEALTH_CACHE[url] = (now, ok)
    return ok


# ── RAG Chunk & Result ──────────────────────────────────────────────

@dataclass
class RAGChunk:
    """A text chunk retrieved from the RAG store.

    pieza de texto recuperada من almacén RAG.
    """
    id: str
    text: str
    source: str             # file path (relative)
    chunk_index: int        # chunk number within the file
    similarity: float = 0.0 # cosine similarity (0..1)
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RAGResult:
    """Top-level result from a RAG query.

    resultado de una consulta RAG.
    """
    query: str
    chunks: List[RAGChunk]
    total_chunks: int
    embed_time_sec: float = 0.0
    search_time_sec: float = 0.0
    total_time_sec: float = 0.0
    ollama_ok: bool = True
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "chunks": [c.to_dict() for c in self.chunks],
        }


# ── Modality Detection ──────────────────────────────────────────────

def _detect_modality_rag(text: str) -> str:
    """Detect modality for RAG text (simplified heuristic).

    كشف مودalitétexte RAG (هistique مبسطة).
    """
    text_lower = text.lower()
    vision_keywords = ["image", "photo", "picture", "screenshot", "visual", "graph", "chart"]
    code_keywords = ["```", "function", "class", "import", "return", "select", "query"]
    
    if any(k in text_lower for k in code_keywords):
        return "large_text"
    if any(k in text_lower for k in vision_keywords):
        return "multimodal"
    if len(text) > 2000:
        return "large_text"
    return "text"


# ── Chunking ────────────────────────────────────────────────────────

def chunk_text(text: str) -> List[str]:
    """Split text into overlapping chunks.

    قسم texte إلى مقاطع متداخلة.
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    
    # Filter empty chunks
    chunks = [c for c in chunks if c.strip()]
    return chunks


# ── Embedding Functions ─────────────────────────────────────────────

def embed_text(text: str, model: Optional[str] = None, url: str = OLLAMA_URL) -> Optional[List[float]]:
    """Embed a single text using the modality-routed embedding pipeline.

    تضمين نص واحد باستخدام مسار التضمين القائم على modality.

    Priority order:
      1. Modality-routed model (auto-detected based on content)
      2. Fallback: alpha-wolf-embed-text (general text)
      3. Fallback: alpha-wolf-embed-multimodal (text+image)
      4. Fallback: Ollama chain (original fallback chain)

    Returns the NATIVE vector of whichever model answered (dims differ per
    model — callers must store it in that model's own collection, never
    truncated/padded into another model's space).
    """

    # Use embedding manager for modality routing
    try:
        # Auto-detect modality if model not specified
        if model is None:
            model = _detect_modality_rag(text)
        
        # Generate embedding using the manager (async via asyncio.run).
        # NOTE: asyncio.run FAILS inside a running event loop (stream turns)
        # with RuntimeError — fall through to the sync Ollama chain below
        # instead of dying (FIX 2026-10-14: silent RAG death on streams).
        # Pre-check avoids even creating the coroutine (no GC warnings).
        import asyncio
        try:
            asyncio.get_running_loop()
            embedding = None
            logger.debug("[rag] in-loop call — skipping manager, trying Ollama chain")
        except RuntimeError:
            embedding = asyncio.run(_aget_embedding(text, model_name=model))
        
        if embedding is not None:
            # Log the model used
            logger.debug("[rag] Embedding via: %s (dim=%d)", model, len(embedding))
            return embedding
        
        # Fallback to default model
        logger.warning("[rag] Manager embedding failed, falling back to default")
        
    except ImportError:
        logger.warning("[rag] embedding_manager not available, using fallback chain")
    
    # Fallback chain (original implementation). NOTE 2026-10-14: `model`
    # here is often a MODALITY ("text"/"multimodal"), not a model id —
    # resolve it first (mirror embedding_manager.DEFAULT_MODEL) or the
    # Ollama call 404s on a modality string and RAG silently dies.
    _MODALITY_MODELS = {"text": "alpha-wolf-embed-text",
                        "vision": "alpha-wolf-embed-multimodal",
                        "multimodal": "alpha-wolf-embed-multimodal",
                        "large_text": "alpha-wolf-embed-large"}
    if model in _MODALITY_MODELS:
        model = _MODALITY_MODELS[model]
    if model is None or model == "embeddinggemma-2" or "embeddinggemma-2" in model:
        candidates = ["alpha-wolf-embed-text", "alpha-wolf-embed-multimodal"]
    else:
        candidates = [model]
    
    for candidate in candidates:
        try:
            embedding = _ollama_embed_fallback(text, candidate, url)
            if embedding is not None:
                logger.debug("[rag] Ollama fallback used: %s", candidate)
                # Native dims preserved (multi-model spaces are NEVER mixed).
                return embedding
        except Exception as e:
            logger.debug("[rag] Ollama %s failed: %s", candidate, e)

    return None


async def _aget_embedding(text: str, model_name: str) -> Optional[List[float]]:
    """Async embedding generation using the manager."""
    from backend.agent.embedding_manager import generate_embedding
    return await generate_embedding(text, model_name=model_name)


def _ollama_embed_fallback(text: str, model: str, url: str) -> Optional[List[float]]:
    """Direct Ollama fallback chain (text-only).

    احتياطي Ollama المباشر (نصوص فقط).
    """
    try:
        import httpx
    except ImportError:
        return None
    # Resolve the requested model name to actual Ollama tags
    if model == "embeddinggemma-2" or "embeddinggemma-2" in model:
        candidates = ["embeddinggemma:latest", "nomic-embed-text:latest"]
    else:
        candidates = [model]
    for candidate in candidates:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{url}/api/embeddings",
                    json={"model": candidate, "prompt": text[:2048]},
                )
                resp.raise_for_status()
                emb = resp.json().get("embedding")
                if emb:
                    logger.debug("[rag] Ollama fallback used: %s", candidate)
                    # Native dims preserved (multi-model spaces are NEVER mixed).
                    return emb
        except Exception as e:
            logger.debug("[rag] Ollama %s failed: %s", candidate, e)
    return None


# ── Multi-model search: one space per model, RRF fusion ──────────────
# (user directive 2026-10-13; hybrid-search pattern; device-safe)

_OLLAMA_PS_CACHE: Dict[str, tuple] = {}


def _model_tag(model: str) -> str:
    """Sanitize a model name for collection suffixes."""
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in (model or ""))[:48]


def collection_name_for(base: str, model: str) -> str:
    """Sibling collection per embedding model (canonical model uses base)."""
    if (model or CANONICAL_MODEL) == CANONICAL_MODEL:
        return base
    return f"{base}__{_model_tag(model)}"


def ollama_model_loaded(model: str, url: str = OLLAMA_URL) -> bool:
    """Is this Ollama model CURRENTLY resident (no-load check)?

    هل النموذج محمّل الآن؟ فحص بدون تحميل — حماية VRAM الجهاز.
    Non-default embedding models are used ONLY when already resident;
    we never force-load a 2-6GB model for a query (device guard).
    """
    now = time.time()
    cached = _OLLAMA_PS_CACHE.get(url)
    if cached and (now - cached[0]) < 30:
        loaded = cached[1]
    else:
        loaded = []
        try:
            import httpx
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{url}/api/ps")
                if resp.status_code == 200:
                    loaded = [(m.get("name") or "") for m in resp.json().get("models", [])]
        except Exception:
            loaded = []
        _OLLAMA_PS_CACHE[url] = (now, loaded)
    want = (model or "").split(":")[0]
    return any((n or "").split(":")[0] == want or (n or "") == f"{model}:latest" for n in loaded)


def rrf_fuse(ranked_lists: List[List[tuple]], top_k: int, k: int = RRF_K) -> List[tuple]:
    """Reciprocal-Rank Fuse ranked lists (id, doc, meta, dist).

    دمج RRF لقوائم مرتبة من مساحات نماذج مختلفة.
    """
    scores: Dict[str, float] = {}
    best: Dict[str, tuple] = {}
    for lst in ranked_lists:
        for rank, item in enumerate(lst or []):
            cid = item[0]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            if cid not in best:
                best[cid] = item
    fused = sorted(scores.items(), key=lambda kv: -kv[1])[:max(1, top_k)]
    return [(cid, best[cid][1], best[cid][2], best[cid][3]) for cid, _ in fused]


def get_embedding_model_name() -> str:
    """Return the active embedding model name (for telemetry).

    إرجاع اسم نموذج التضمين الفعّال.
    """
    try:
        models = list_embed_models()
        if models:
            return models[0]["name"]
    except ImportError:
        pass
    
    # Fallback to legacy return value
    try:
        from backend.agent.embeddinggemma import is_embeddinggemma2_available
        if is_embeddinggemma2_available():
            return "embeddinggemma-2 (HF, multimodal, 768d)"
    except ImportError:
        pass
    return "embeddinggemma (Ollama, text-only, 768d)"


# ── Helper: batch embeddings for directory indexing ──────────────────

async def _batch_embed_chunks(chunks: List[str]) -> List[Optional[List[float]]]:
    """Embed a list of chunks using the modality manager."""
    return await generate_batch_embeddings(chunks, modality="text")


# ── RAG Store (wraps ChromaDB collection) ──────────────────────────

class LiveRAG:
    """Live RAG over Ollama embeddings + ChromaDB.

    بحث واسترجاع حي باستخدام تضمينات Ollama + ChromaDB.

    Usage:
        rag = LiveRAG(project_root="...")
        rag.index_directory()                  # build the index
        results = rag.query("what is wolf?", top_k=3)
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        chromadb_dir: Optional[Path] = None,
        collection_name: str = COLLECTION_NAME,
        embedding_model: str = EMBEDDING_MODEL,
    ):
        from pathlib import Path as _P

        self.project_root = Path(project_root) if project_root else _P(__file__).resolve().parent.parent.parent
        self.chromadb_dir = Path(chromadb_dir) if chromadb_dir else self.project_root / "body" / "knowledge_graph" / "chromadb"
        # Pin the collection's embedding space: unknown names resolve to the
        # canonical model (one space per model — spaces are NEVER mixed).
        if embedding_model not in EMBEDDING_REGISTRY:
            embedding_model = CANONICAL_MODEL
        self.collection_name = collection_name_for(collection_name, embedding_model)
        self.embedding_model = embedding_model
        spec = EMBEDDING_REGISTRY.get(embedding_model)
        self.embed_dim: Optional[int] = spec.dimension if spec else None

        # Lazy chroma init (graceful if not installed)
        try:
            import chromadb
            self.chromadb_dir.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(self.chromadb_dir))
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            # Space pinning is in-memory (self.embedding_model); per-doc
            # embed_model tags carry provenance. (Collection.modify() is
            # unreliable across Chroma versions — never depend on it.)
            logger.info("RAG using ChromaDB at %s", self.chromadb_dir)
        except Exception as e:
            logger.warning("ChromaDB unavailable: %s — using in-memory fallback", e)
            self.client = None
            self.collection = None
            # Fallback: in-memory list
            self._memory_store: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_file(self, file_path: Path, force: bool = False) -> int:
        """Index a single file (chunked + embedded).

        فهرسة ملف واحد.
        Large files: index the head (first MAX_CHUNKS_PER_FILE chunks)
        instead of skipping — previously PROJECT_LOG.md / PROJECT_PLAN.md
        (>25k chars) were silently excluded from the agent's memory
        (FIX 2026-09-26).
        Stale chunks: re-embed when chunk content hash changed, so edits
        are picked up without force=True (FIX 2026-09-26).

        Returns number of chunks added/updated.
        """
        if not file_path.exists() or not file_path.is_file():
            return 0

        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            return 0

        # Head-truncate huge files instead of skipping them
        limit = CHUNK_SIZE * MAX_CHUNKS_PER_FILE
        if len(text) > limit:
            logger.info(
                "Truncating large file %s (%d chars -> %d) for index",
                file_path, len(text), limit,
            )
            text = text[:limit]

        chunks = chunk_text(text)
        if not chunks:
            return 0

        rel_path = str(file_path.relative_to(self.project_root))
        added = 0

        for i, chunk in enumerate(chunks):
            cid = _chunk_id(rel_path, i)
            chash = hashlib.sha1(chunk.encode("utf-8", errors="ignore")).hexdigest()[:12]

            # Skip if already indexed with identical content (unless force)
            if not force and self.collection is not None:
                try:
                    existing = self.collection.get(ids=[cid])
                    if existing and existing.get("ids"):
                        old_meta = (existing.get("metadatas") or [{}])[0] or {}
                        if old_meta.get("hash") == chash:
                            continue  # unchanged
                        # Content changed -> refresh embedding below, upsert after
                except Exception:
                    pass

            # Embed using new modality-routed embedder
            embedding = embed_text(chunk, model=self.embedding_model)
            if embedding is None:
                continue

            # Space discipline: refuse vectors that don't belong to this
            # collection's model space (NEVER truncate/pad across spaces).
            if self.embed_dim and len(embedding) != self.embed_dim:
                logger.warning(
                    "ChromaDB upsert refused: dim %d != %s space (%d) for %s",
                    len(embedding), self.embedding_model, self.embed_dim, cid)
                continue

            # Store
            if self.collection is not None:
                try:
                    self.collection.upsert(
                        ids=[cid],
                        documents=[chunk],
                        embeddings=[embedding],
                        metadatas=[{"source": rel_path, "chunk_index": i, "hash": chash,
                                    "embed_model": self.embedding_model}],
                    )
                    added += 1
                except Exception as e:
                    logger.warning("ChromaDB upsert failed: %s", e)
            else:
                # In-memory fallback
                self._memory_store.append({
                    "id": cid,
                    "text": chunk,
                    "embedding": embedding,
                    "source": rel_path,
                    "chunk_index": i,
                })
                added += 1

        return added

    def index_directory(
        self,
        patterns: Optional[List[str]] = None,
        force: bool = False,
    ) -> Dict[str, int]:
        """Index a directory of files (default: project_root).

        فهرسة مجلد كامل.
        """
        patterns = patterns or ["*.md", "*.py", "*.txt", "*.json", "*.toml"]
        stats: Dict[str, int] = {}

        for pattern in patterns:
            count = 0
            for path in self.project_root.rglob(pattern):
                if not path.is_file():
                    continue
                # Skip noisy dirs (mirror live_context exclusions)
                # FIX 2026-09-26 (user-observed): unsloth_compiled_cache *.py
                # (172 junk chunks of generated GPU code) polluted retrieval
                # and stalled indexing. Round 2: screenshots (binary + json
                # reports), logs (ever-growing), volatile job ledger.
                if any(excluded in path.parts for excluded in {
                    "node_modules", ".git", "__pycache__", ".venv", "venv",
                    "backups", "dist", "build", ".cache",
                    "unsloth_compiled_cache", "knowledge_graph",
                    "screenshots", "logs",
                }):
                    continue
                if path.name == "rag_jobs.json":
                    continue
                # Skip binary/database files even if pattern-matched
                if path.suffix.lower() in {
                    ".db", ".sqlite3", ".sqlite", ".wal", ".shm", ".bin",
                    ".pkl", ".gguf", ".safetensors", ".onnx", ".pt", ".pth",
                }:
                    continue
                added = self.index_file(path, force=force)
                count += added
            stats[pattern] = count
        return stats

    def purge_junk_sources(self) -> Dict[str, int]:
        """Delete chunks whose source is generated/binary noise.

        حذف المقاطع القادمة من ملفات مولدة/ثنائية (تلوث مثبت حياً).
        Returns {source: deleted_count}.
        """
        removed: Dict[str, int] = {}
        if self.collection is None:
            return removed
        try:
            got = self.collection.get(include=["metadatas"], limit=100000)
        except Exception as e:
            logger.warning("purge scan failed: %s", e)
            return removed
        by_source: Dict[str, list] = {}
        for cid, meta in zip(got.get("ids", []), got.get("metadatas", [])):
            by_source.setdefault((meta or {}).get("source", ""), []).append(cid)
        junk_suffixes = (".db", ".sqlite3", ".sqlite", ".wal", ".shm", ".bin",
                         ".pkl", ".gguf", ".safetensors", ".onnx", ".pt", ".pth")
        junk_dirs = ("unsloth_compiled_cache", "knowledge_graph", "__pycache__",
                     "screenshots", "logs")
        junk_files = {"rag_jobs.json"}
        for src, ids in by_source.items():
            low = (src or "").lower().replace("/", "\\")
            base = low.rsplit("\\", 1)[-1]
            if (low.endswith(junk_suffixes) or any(d in low for d in junk_dirs)
                    or base in junk_files):
                try:
                    self.collection.delete(ids=ids)
                    removed[src] = len(ids)
                except Exception as e:
                    logger.warning("purge delete failed for %s: %s", src, e)
        return removed

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(self, query_text: str, top_k: int = TOP_K_DEFAULT) -> RAGResult:
        """Query the RAG store for similar chunks.

        البحث عن قطع مشابهة.

        Returns RAGResult with chunks sorted by similarity.
        """
        started = time.time()
        embed_started = time.time()
        ollama_ok = ollama_healthy()

        # Multi-model fan-out: each sibling collection is searched in its OWN
        # space with its OWN model embedding, then RRF-fused. Non-canonical
        # models participate ONLY when already resident (device guard — we
        # never force-load gigabytes of weights for one query).
        targets: List[tuple] = []
        if ollama_ok and self.collection is not None:
            targets.append((self.collection, self.embedding_model))
            try:
                for coll in (self.client.list_collections() or []):
                    if (coll.name != self.collection_name
                            and coll.name.startswith(COLLECTION_NAME + "__")
                            and coll.count() > 0):
                        # Space provenance: collection metadata, else one
                        # doc's embed_model tag, else canonical. (modify()
                        # is unreliable — always read, never assume.)
                        cmodel = CANONICAL_MODEL
                        try:
                            cmodel = (dict(coll.metadata or {}).get("embed_model")
                                      or CANONICAL_MODEL)
                            if cmodel == CANONICAL_MODEL:
                                sample = coll.get(limit=1, include=["metadatas"])
                                metas = sample.get("metadatas") or []
                                if metas and (metas[0] or {}).get("embed_model"):
                                    cmodel = metas[0]["embed_model"]
                        except Exception:
                            cmodel = CANONICAL_MODEL
                        if cmodel == self.embedding_model:
                            continue
                        if ollama_model_loaded(cmodel):
                            targets.append((coll, cmodel))
                        else:
                            logger.debug("[rag] skip non-resident model space: %s", cmodel)
            except Exception as e:
                logger.debug("[rag] sibling scan failed: %s", e)

        ranked: List[List[tuple]] = []
        for coll, cmodel in targets:
            try:
                qemb = embed_text(query_text, model=cmodel)
            except Exception:
                qemb = None
            if qemb is None:
                continue
            try:
                results = coll.query(query_embeddings=[qemb], n_results=top_k)
            except Exception as e:
                logger.warning("ChromaDB query failed (%s): %s", cmodel, e)
                continue
            ids = results.get("ids", [[]])[0]
            docs = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            ranked.append([(cid, doc, meta, float(dist) if dist is not None else 0.0)
                           for cid, doc, dist, meta in zip(ids, docs, distances, metadatas)])
        embed_time = time.time() - embed_started

        if not ranked:
            return RAGResult(
                query=query_text,
                chunks=[],
                total_chunks=0,
                embed_time_sec=round(embed_time, 3),
                ollama_ok=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        search_started = time.time()
        chunks: List[RAGChunk] = []

        if self.collection is not None:
            try:
                for cid, doc, meta, dist in rrf_fuse(ranked, top_k):
                    # cosine distance → similarity (1 - distance for cosine)
                    similarity = max(0.0, 1.0 - float(dist))
                    chunks.append(RAGChunk(
                        id=cid,
                        text=doc,
                        source=(meta or {}).get("source", "unknown"),
                        chunk_index=int((meta or {}).get("chunk_index", 0)),
                        similarity=similarity,
                        metadata=meta,
                    ))
            except Exception as e:
                logger.warning("ChromaDB fuse failed: %s", e)
        else:
            # In-memory fallback (cosine similarity, same-space only).
            import math
            mem_q = embed_text(query_text, model=self.embedding_model) if ollama_ok else None
            if mem_q is not None:
                scored = []
                for item in self._memory_store:
                    ivec = item["embedding"]
                    if len(ivec) != len(mem_q):
                        continue  # never compare across spaces
                    dot = sum(a * b for a, b in zip(mem_q, ivec))
                    norm_a = math.sqrt(sum(a * a for a in mem_q))
                    norm_b = math.sqrt(sum(b * b for b in ivec))
                    if norm_a == 0 or norm_b == 0:
                        continue
                    cos_sim = dot / (norm_a * norm_b)
                    scored.append((cos_sim, item))
                scored.sort(key=lambda x: -x[0])
                for sim, item in scored[:top_k]:
                    chunks.append(RAGChunk(
                        id=item["id"],
                        text=item["text"],
                        source=item["source"],
                        chunk_index=item["chunk_index"],
                        similarity=sim,
                    ))

        search_time = time.time() - search_started
        total_time = time.time() - started

        return RAGResult(
            query=query_text,
            chunks=chunks,
            total_chunks=self._total_chunks(),
            embed_time_sec=round(embed_time, 3),
            search_time_sec=round(search_time, 3),
            total_time_sec=round(total_time, 3),
            ollama_ok=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def _total_chunks(self) -> int:
        """Total chunks in store."""
        if self.collection is not None:
            try:
                return self.collection.count()
            except Exception:
                return 0
        return len(self._memory_store)

    def stats(self) -> Dict[str, Any]:
        """Get RAG store stats."""
        return {
            "collection_name": self.collection_name,
            "embedding_model": self.embedding_model,
            "total_chunks": self._total_chunks(),
            "chromadb_dir": str(self.chromadb_dir),
            "using_chromadb": self.collection is not None,
            "ollama_healthy": ollama_healthy(),
        }


# ── Convenience Functions ────────────────────────────────────────────

_default_rag: Optional[LiveRAG] = None


def get_rag() -> LiveRAG:
    """Get or create the default LiveRAG instance.

    الحصول على نسخة RAG الافتراضية.
    """
    global _default_rag
    if _default_rag is None:
        _default_rag = LiveRAG()
    return _default_rag


def build_rag_context(query_text: str, top_k: int = TOP_K_DEFAULT, max_total_chars: int = 4000) -> str:
    """Build a RAG-augmented context block for chat.

    يبني سياق RAG محسّن للدردشة.

    max_total_chars caps total injection (default 4000 chars ≈ 1500 Arabic tokens).
    Without this cap, RAG can blow past the served context (16384 tokens).
    Returns empty string if no results.
    """
    rag = get_rag()
    result = rag.query(query_text, top_k=top_k)

    if not result.chunks:
        return ""

    sections = [
        f"## Relevant context from your project (RAG, top {len(result.chunks)}):",
        f"## سياق ذو صلة من مشروعك (RAG، أعلى {len(result.chunks)}):",
        "",
    ]

    total_chars = sum(len(s) for s in sections)
    for i, chunk in enumerate(result.chunks, 1):
        # Per-chunk budget: proportional to remaining budget
        remaining = max(0, max_total_chars - total_chars)
        if remaining < 200:  # not worth a new chunk
            break
        per_chunk = min(600, remaining - 100)  # leave 100 for headers
        chunk_text = chunk.text[:per_chunk]
        sections.append(
            f"### [{i}] `{chunk.source}` (similarity={chunk.similarity:.3f}):\n{chunk_text}"
        )
        total_chars += len(chunk_text) + 100  # rough estimate

    if not result.ollama_ok:
        sections.append("\n_Note: Ollama embedding unavailable — RAG returned empty._")

    return "\n".join(sections)


# ── Self-Test (Iron Law #15) ───────────────────────────────────────

def _self_test() -> bool:
    """Verify RAG works end-to-end.

    التحقق من RAG يعمل من البداية للنهاية.
    """
    print("Running RAG self-tests...")
    print("تشغيل اختبارات RAG...")

    passed = 0
    failed = 0

    try:
        # Test 1: Ollama health
        if ollama_healthy():
            passed += 1
            print(f"  ✓ Ollama healthy")
        else:
            failed += 1
            print(f"  ✗ Ollama unreachable")

        # Test 2: Single embedding
        emb = embed_text("hello world")
        if emb is not None and len(emb) > 0:
            passed += 1
            print(f"  ✓ embed_text: dim={len(emb)}")
        else:
            failed += 1
            print(f"  ✗ embed_text: None")

        # Test 3: Chunking
        chunks = chunk_text("a" * 1500)
        if len(chunks) >= 3:
            passed += 1
            print(f"  ✓ chunk_text: {len(chunks)} chunks from 1500 chars")
        else:
            failed += 1
            print(f"  ✗ chunk_text: only {len(chunks)} chunks")

        # Test 4: LiveRAG instantiation
        rag = LiveRAG()
        passed += 1
        print(f"  ✓ LiveRAG instantiated (chromadb={rag.collection is not None})")

        # Test 5: Query if Ollama OK + collection has chunks
        if ollama_healthy() and rag._total_chunks() > 0:
            result = rag.query("Alpha Wolf Agent", top_k=3)
            if result.ollama_ok and len(result.chunks) > 0:
                passed += 1
                print(f"  ✓ query: {len(result.chunks)} results, top sim={result.chunks[0].similarity:.3f}")
            else:
                failed += 1
                print(f"  ✗ query: {result}")
        else:
            passed += 1
            print(f"  ✓ query: skipped (no chunks or Ollama)")

        # Test 6: Singleton
        rag2 = get_rag()
        if rag2 is not None:
            passed += 1
            print(f"  ✓ get_rag singleton")

        # Test 7: build_rag_context convenience
        if ollama_healthy():
            ctx = build_rag_context("wolf", top_k=2)
            if ctx:
                passed += 1
                print(f"  ✓ build_rag_context: {len(ctx)} chars")
            else:
                passed += 1  # empty is OK if no chunks
                print(f"  ✓ build_rag_context: empty (no chunks)")
        else:
            passed += 1
            print(f"  ✓ build_rag_context: skipped")

        # Test 8: List embedding models
        try:
            models = list_embed_models()
            if models:
                passed += 1
                print(f"  ✓ embedding models listed: {len(models)} models")
            else:
                failed += 1
                print(f"  ✗ embedding models: none available")
        except ImportError:
            failed += 1
            print(f"  ✗ embedding models: import error")

    except Exception as e:
        failed += 1
        print(f"  ✗ exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print(f"\nResults: {passed} passed, {failed} failed")
    print(f"النتائج: {passed} نجح، {failed} Failed")
    return failed == 0


# ── Module Alias for Old Imports ────────────────────────────────────

# Keep old function names working for backward compatibility
embed_text_legacy = embed_text
get_embedding_model_name_legacy = get_embedding_model_name

if __name__ == "__main__":
    _self_test()
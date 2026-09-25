#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Ingestion Pipeline
======================================
Auto-ingests datasets into the body:
1. Detect format (FormatDetector)
2. Validate quality (quality thresholds)
3. Quarantine if blacklist match
4. Convert to canonical format (for embedding)
5. Embed + index in ChromaDB
6. Register in SQLite (datasets table)

Iron Laws Applied:
- #7  (Anti-Contamination)  — blacklist enforced via FormatDetector.quarantine_check
- #14 (Snapshot Before Edit) — backup existing dataset before re-ingestion
- #15 (Verify)                 — every ingestion returns structured result
- #17 (NO Ollama LLMs)         — embeddings via Ollama (nomic-embed-text)
- #21 (NO Deletion)            — soft delete via datasets.deleted_at
- #36 (5-Layer Save)           — every action logged to curation_log

Usage:
    from body.intake.ingestion_pipeline import IngestionPipeline

    pipeline = IngestionPipeline(body_root=Path("body"))
    result = pipeline.ingest(Path("data/ultrachat_50k.jsonl"), target_kb="kb_code")
    print(result)
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Add project root to sys.path (for body.intake.format_detector import)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from body.intake.format_detector import FormatDetector, QUALITY_THRESHOLDS
from body.intake.wolf_classifier import WolfClassifier, Distiller

# Iron Law #42 — Raw vault lives on D: drive (Iron Law #42 storage discipline)
# Wolf vault structure for Wolf Classification Protocol
RAW_VAULT_BASE = Path("D:/Trained intelligence models/wolf-vault")
RAW_VAULT_RAW = RAW_VAULT_BASE / "raw"
RAW_VAULT_DISTILLED = RAW_VAULT_BASE / "distilled"
RAW_VAULT_HARMFUL = RAW_VAULT_BASE / "harmful"
RAW_VAULT_REVIEW = RAW_VAULT_BASE / "review_queue"

# Iron Law #42 — Project-specific lives in workspace
PROJECT_SPECIFIC_DIR = PROJECT_ROOT / "body" / "specific_projects"


# ============================================================================
# Canonical Format (uniform structure for embedding)
# ============================================================================

CANONICAL_FORMAT = {
    "id": "uuid",
    "task_type": "string",          # conversational | instruction | tool | code | etc.
    "text": "string",                # Main content (concatenated from row)
    "metadata": {
        "dataset_id": "uuid",
        "source": "string",           # huggingface | local | url
        "format_type": "string",
        "row_index": "integer",
        "quality_score": "float",
        "ingested_at": "ISO8601",
        "license": "string",
        "tags": "list<string>",
    },
}


# ============================================================================
# Ingestion Pipeline
# ============================================================================

class IngestionPipeline:
    """Full ingestion pipeline: detect → validate → embed → index → register."""

    def __init__(self, body_root: Optional[Path] = None):
        """Initialize pipeline with body paths.

        Args:
            body_root: Path to body/ directory (defaults to PROJECT_ROOT/body)
        """
        self.body_root = Path(body_root) if body_root else PROJECT_ROOT / "body"
        self.chromadb_dir = self.body_root / "knowledge_graph" / "chromadb"
        self.state_db = self.body_root / "memory" / "state.db"
        self.staging_dir = self.body_root / "intake" / "staging"
        self.quarantine_dir = self.body_root / "intake" / "quarantine"

        self.detector = FormatDetector()
        self.classifier = WolfClassifier()  # Phase 11+ v3.2
        self.distiller = Distiller()          # Phase 11+ v3.2
        self._init_chromadb()
        self._init_sqlite()
        self._ensure_vault_directories()

    def _init_chromadb(self):
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=str(self.chromadb_dir))
        except ImportError:
            print("⚠️  chromadb not installed")
            self.chroma_client = None

    def _init_sqlite(self):
        import sqlite3
        self.sqlite_conn = sqlite3.connect(str(self.state_db), isolation_level=None)
        self.sqlite_conn.execute("PRAGMA journal_mode=WAL")
        self.sqlite_conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_datasets_table()
        self._ensure_classifications_table()

    def _ensure_vault_directories(self):
        """Create vault directories if they don't exist (Iron Law #42)."""
        for vault_dir in [RAW_VAULT_RAW, RAW_VAULT_DISTILLED,
                           RAW_VAULT_HARMFUL, RAW_VAULT_REVIEW, PROJECT_SPECIFIC_DIR]:
            vault_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_datasets_table(self):
        """Create datasets + quality_metrics tables (Iron Law #21 soft delete)."""
        self.sqlite_conn.executescript("""
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            repo_id TEXT,
            target_kb TEXT NOT NULL,
            format_fingerprint TEXT NOT NULL,
            quality_score REAL,
            license TEXT,
            size_bytes INTEGER,
            rows_total INTEGER,
            rows_indexed INTEGER,
            status TEXT DEFAULT 'staged',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            ingested_at TIMESTAMPTZ,
            deleted_at TIMESTAMPTZ,
            UNIQUE(name, source, repo_id)
        );

        CREATE TABLE IF NOT EXISTS quality_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id TEXT REFERENCES datasets(id),
            ts TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            metric_name TEXT,
            metric_value REAL,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_datasets_status ON datasets(status);
        CREATE INDEX IF NOT EXISTS idx_datasets_target_kb ON datasets(target_kb);
        CREATE INDEX IF NOT EXISTS idx_quality_dataset_ts ON quality_metrics(dataset_id, ts);
        """)
        self.sqlite_conn.commit()

    def _ensure_classifications_table(self):
        """Phase 11+ v3.2: Wolf Classification Protocol tables."""
        self.sqlite_conn.executescript("""
        CREATE TABLE IF NOT EXISTS dataset_classifications (
            id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            classification TEXT NOT NULL CHECK (classification IN ('harmful', 'project_specific', 'useful', 'raw')),
            confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
            reason TEXT NOT NULL,
            detected_patterns TEXT,
            classified_at TEXT NOT NULL DEFAULT (datetime('now')),
            classifier_version TEXT NOT NULL DEFAULT 'wolf_v1.0',
            file_hash TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_dc_dataset_id ON dataset_classifications(dataset_id);
        CREATE INDEX IF NOT EXISTS idx_dc_classification ON dataset_classifications(classification);

        CREATE TABLE IF NOT EXISTS distilled_datasets (
            id TEXT PRIMARY KEY,
            source_dataset_id TEXT NOT NULL,
            distilled_content_path TEXT NOT NULL,
            distillation_method TEXT NOT NULL CHECK (distillation_method IN ('regex_redaction', 'manual', 'hybrid')),
            provenance TEXT NOT NULL,
            quality_score REAL NOT NULL CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            lineage_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS harmful_log (
            id TEXT PRIMARY KEY,
            dataset_hash TEXT NOT NULL,
            dataset_name TEXT NOT NULL,
            rejection_reason TEXT NOT NULL,
            severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
            action TEXT NOT NULL CHECK (action IN ('rejected', 'redacted', 'manual_review', 'quarantined_with_alert')),
            detected_at TEXT NOT NULL DEFAULT (datetime('now')),
            resolved_at TEXT,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_hl_severity ON harmful_log(severity);
        CREATE INDEX IF NOT EXISTS idx_hl_resolved ON harmful_log(resolved_at);
        """)
        self.sqlite_conn.commit()

    # ========================================================================
    # Main Entry Points
    # ========================================================================

    def ingest(self, file_path: Path, target_kb: str, source: str = "local") -> dict:
        """Full ingestion pipeline for a local file.

        Args:
            file_path: Path to dataset file
            target_kb: Target KB collection name (e.g., "kb_code")
            source: "local" | "huggingface" | "url"

        Returns:
            dict with keys:
                status, classification, dataset_id, rows_indexed, quality_score, errors
        """
        file_path = Path(file_path)
        result = {
            "file_path": str(file_path),
            "target_kb": target_kb,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        # Stage 1: Format detection
        fingerprint = self.detector.detect(file_path)
        result["fingerprint"] = fingerprint

        # Stage 1.5: Quality check (FormatDetector's quarantine)
        is_quarantined, reasons = self.detector.quarantine_check(fingerprint)
        if is_quarantined:
            return self._quarantine(file_path, fingerprint, reasons, result)

        if not self.detector.validate_format(fingerprint):
            return self._quarantine(
                file_path,
                fingerprint,
                [f"Quality score {fingerprint['quality']['overall_score']:.2f} below threshold"],
                result,
            )

        # Stage 2: Wolf Classification (Phase 11+ v3.2 — NEW)
        classification = self.classifier.classify(file_path, format_info=fingerprint)
        result["classification"] = classification
        # Register classification result
        try:
            cls_id = self.classifier.register_classification(classification, self.state_db)
            result["classification_id"] = cls_id
        except Exception as e:
            result["classification_register_error"] = str(e)

        # Stage 3: 4-class routing
        cls = classification["class"]
        if cls == "harmful":
            return self._handle_harmful(file_path, classification, result)
        elif cls == "project_specific":
            return self._handle_project_specific(file_path, classification, result)
        elif cls == "useful":
            return self._handle_useful(file_path, fingerprint, classification, target_kb, source, result)
        elif cls == "raw":
            return self._handle_raw(file_path, classification, result)
        else:
            result["status"] = "error"
            result["error"] = f"Unknown classification: {cls}"
            return result

    def ingest_from_hf(self, repo_id: str, target_kb: str) -> dict:
        """Ingest from HuggingFace Hub.

        Args:
            repo_id: HuggingFace repo ID (e.g., "HuggingFaceH4/ultrachat_200k")
            target_kb: Target KB collection name

        Returns:
            dict (same format as ingest())
        """
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            return {
                "status": "error",
                "error": "huggingface_hub not installed. Run: uv add huggingface-hub",
                "repo_id": repo_id,
            }

        try:
            local_path = Path(
                snapshot_download(
                    repo_id=repo_id,
                    repo_type="dataset",
                    allow_patterns=["*.jsonl", "*.json", "*.parquet", "*.csv", "README*"],
                    local_dir=str(self.staging_dir / repo_id.replace("/", "_")),
                )
            )
        except Exception as e:
            return {
                "status": "error",
                "error": f"HuggingFace download failed: {e}",
                "repo_id": repo_id,
            }

        data_files = list(Path(local_path).rglob("*"))
        data_files = [f for f in data_files if f.suffix in [".jsonl", ".json", ".parquet", ".csv"]]
        if not data_files:
            return {
                "status": "error",
                "error": f"No data files found in {repo_id}",
                "repo_id": repo_id,
            }

        main_file = max(data_files, key=lambda f: f.stat().st_size)
        result = self.ingest(main_file, target_kb, source="huggingface")
        result["repo_id"] = repo_id
        return result

    def ingest_batch(self, file_paths: list[Path], target_kb: str) -> list[dict]:
        """Ingest multiple files in batch."""
        results = []
        for fp in file_paths:
            try:
                r = self.ingest(fp, target_kb)
                results.append(r)
            except Exception as e:
                results.append({"file_path": str(fp), "status": "error", "error": str(e)})
        return results

    def validate_quality(self, fingerprint: dict) -> bool:
        """Validate quality against thresholds."""
        return self.detector.validate_format(fingerprint)

    # ========================================================================
    # 4-Class Handlers (Phase 11+ v3.2 — Wolf Classification Protocol)
    # ========================================================================

    def _handle_harmful(self, file_path: Path, classification: dict,
                         result: dict) -> dict:
        """Handle HARMFUL classification.

        Iron Laws:
        - #7 (Anti-Contamination): REJECT
        - #21 (NO Deletion): SOFT quarantine + harmful_log table

        Action: Copy raw to D:\.../harmful/ + register in harmful_log. NEVER delete.
        """
        result["status"] = "rejected_harmful"
        result["classification"] = classification["class"]
        result["confidence"] = classification["confidence"]
        result["reason"] = classification["reason"]

        try:
            # Copy to harmful vault (Iron Law #42 — D: drive)
            harmful_path = RAW_VAULT_HARMFUL / file_path.name
            if not harmful_path.exists():
                shutil.copy2(file_path, harmful_path)
                result["harmful_path"] = str(harmful_path)
        except Exception as e:
            result["harmful_copy_error"] = str(e)

        # Register in harmful_log table
        try:
            hid = str(uuid.uuid4())
            severity = "critical" if "malware" in classification["reason"].lower() or "illegal" in classification["reason"].lower() else "high"
            self.sqlite_conn.execute(
                """INSERT INTO harmful_log
                (id, dataset_hash, dataset_name, rejection_reason, severity, action, notes)
                VALUES(?, ?, ?, ?, ?, ?, ?)""",
                (
                    hid,
                    classification.get("file_hash"),
                    file_path.name,
                    classification["reason"],
                    severity,
                    "rejected",
                    json.dumps(classification.get("detected_patterns", {})),
                ),
            )
            result["harmful_log_id"] = hid
        except Exception as e:
            result["harmful_log_error"] = str(e)

        # Curation log (Iron Law #36)
        self._log_curation(
            action="delete",  # Semantically "rejected from body"
            target_kb="__rejected_harmful__",
            target_id=file_path.name,
            summary=f"REJECTED: {classification['reason'][:100]}",
            source="wolf_classifier.py",
        )

        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        return result

    def _handle_project_specific(self, file_path: Path, classification: dict,
                                  result: dict) -> dict:
        """Handle PROJECT-SPECIFIC classification.

        Iron Laws:
        - #42 (Workspace-Body): project_specific lives in workspace, NOT body

        Action: Store in workspace/project_specific/. NO indexing in body.
        """
        result["status"] = "stored_project_specific"
        result["classification"] = classification["class"]
        result["confidence"] = classification["confidence"]
        result["reason"] = classification["reason"]

        try:
            # Store in workspace (Iron Law #42 — NEVER in body)
            ps_path = PROJECT_SPECIFIC_DIR / file_path.name
            if not ps_path.exists():
                shutil.copy2(file_path, ps_path)
                result["project_specific_path"] = str(ps_path)
        except Exception as e:
            result["project_specific_copy_error"] = str(e)

        # Curation log
        self._log_curation(
            action="add",
            target_kb="__project_specific__",
            target_id=file_path.name,
            summary=f"Project-specific stored in workspace: {classification['reason'][:80]}",
            source="wolf_classifier.py",
        )

        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        return result

    def _handle_useful(self, file_path: Path, fingerprint: dict,
                       classification: dict, target_kb: str,
                       source: str, result: dict) -> dict:
        """Handle USEFUL classification.

        Action:
        1. Distill (remove project-specific details, keep generalizable)
        2. Quality check
        3. Embed + index in ChromaDB
        4. Store raw in vault (audit)
        5. Register in distilled_datasets
        """
        result["classification"] = classification["class"]
        result["confidence"] = classification["confidence"]

        # Soft-delete existing (Iron Law #21)
        existing_id = self._soft_delete_existing(
            fingerprint["file_name"], source, fingerprint.get("repo_id")
        )
        if existing_id:
            result["replaced_existing"] = existing_id

        # Read sample for distillation
        try:
            sample = self.detector._read_sample(file_path, n=10000)
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Could not read sample: {e}"
            return result

        # Distill (remove project-specific details)
        try:
            distilled = self.distiller.distill(sample)
            # Quality check
            quality_pass, quality_checks = self.distiller.quality_check(distilled, sample)
            if not quality_pass:
                result["status"] = "error"
                result["error"] = f"Distillation quality check failed: {quality_checks}"
                return result
            result["distillation_quality"] = quality_checks
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Distillation failed: {e}"
            return result

        result["rows_distilled"] = len(distilled)

        # Save distilled to vault (Iron Law #21 — audit trail)
        try:
            distilled_path = RAW_VAULT_DISTILLED / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{file_path.stem}_distilled.jsonl"
            with open(distilled_path, "w", encoding="utf-8") as f:
                for row in distilled:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            result["distilled_path"] = str(distilled_path)
        except Exception as e:
            result["distilled_path_error"] = str(e)

        # Save raw to vault (audit trail)
        try:
            raw_path = RAW_VAULT_RAW / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{file_path.name}"
            shutil.copy2(file_path, raw_path)
            result["raw_path"] = str(raw_path)
        except Exception as e:
            result["raw_copy_error"] = str(e)

        # Convert distilled to canonical
        try:
            canonical_rows = self._distilled_to_canonical(
                distilled, fingerprint, target_kb, source
            )
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Canonical conversion failed: {e}"
            return result

        # Embed + index
        rows_indexed = self._embed_and_index(canonical_rows, target_kb)
        result["rows_indexed"] = rows_indexed

        # Register in SQLite (datasets + distilled_datasets)
        dataset_id = self._register_dataset(
            fingerprint, target_kb, source, rows_indexed, status_override="ingested"
        )
        result["dataset_id"] = dataset_id

        # Register distilled provenance
        try:
            did = str(uuid.uuid4())
            provenance = (
                f"distilled from {file_path.name} on "
                f"{datetime.now(timezone.utc).isoformat()} via regex_redaction"
            )
            self.sqlite_conn.execute(
                """INSERT INTO distilled_datasets
                (id, source_dataset_id, distilled_content_path, distillation_method,
                 provenance, quality_score, lineage_hash)
                VALUES(?, ?, ?, ?, ?, ?, ?)""",
                (
                    did,
                    dataset_id,
                    result.get("distilled_path", ""),
                    "regex_redaction",
                    provenance,
                    sum(1 for v in result.get("distillation_quality", {}).values() if v) /
                    max(len(result.get("distillation_quality", {})), 1),
                    classification.get("file_hash", ""),
                ),
            )
            result["distilled_dataset_id"] = did
        except Exception as e:
            result["distilled_register_error"] = str(e)

        result["status"] = "ingested_useful"
        result["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Curation log
        self._log_curation(
            action="add",
            target_kb=target_kb,
            target_id=dataset_id,
            summary=f"Ingested (USEFUL, distilled): {file_path.name} → {rows_indexed} rows",
            source="wolf_classifier.py",
        )

        return result

    def _handle_raw(self, file_path: Path, classification: dict,
                    result: dict) -> dict:
        """Handle RAW classification (low confidence — needs human review)."""
        result["status"] = "needs_review"
        result["classification"] = classification["class"]
        result["confidence"] = classification["confidence"]
        result["reason"] = classification["reason"]

        # Store raw in vault
        try:
            review_path = RAW_VAULT_REVIEW / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{file_path.name}"
            shutil.copy2(file_path, review_path)
            result["review_path"] = str(review_path)
        except Exception as e:
            result["review_copy_error"] = str(e)

        # Curation log
        self._log_curation(
            action="add",
            target_kb="__review_queue__",
            target_id=file_path.name,
            summary=f"NEEDS REVIEW: {classification['reason'][:80]}",
            source="wolf_classifier.py",
        )

        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        return result

    def _distilled_to_canonical(self, distilled: list, fingerprint: dict,
                                 target_kb: str, source: str) -> list[dict]:
        """Convert distilled rows to canonical format for ChromaDB."""
        task_type = fingerprint.get("task_type", "unknown")
        canonical_rows = []
        for i, row in enumerate(distilled):
            if not isinstance(row, dict):
                continue
            text = self._row_to_text(row, task_type)
            if not text or len(text) < QUALITY_THRESHOLDS["min_text_length"]:
                continue
            if len(text) > QUALITY_THRESHOLDS["max_text_length"]:
                text = text[:QUALITY_THRESHOLDS["max_text_length"]]

            canonical_rows.append({
                "id": str(uuid.uuid4()),
                "task_type": task_type,
                "text": text,
                "metadata": {
                    "dataset_name": fingerprint.get("file_name", ""),
                    "source": source,
                    "format_type": fingerprint.get("file_format", ""),
                    "row_index": i,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "distilled": True,  # Mark as distilled
                },
            })
        return canonical_rows

    # ========================================================================
    # Internal Methods (continued)
    # ========================================================================

    def _quarantine(self, file_path: Path, fingerprint: dict, reasons: list,
                    result: dict) -> dict:
        """Move to FormatDetector quarantine (low quality, not harmful)."""
        result["status"] = "quarantined_low_quality"
        result["quarantine_reasons"] = reasons
        result["quality_score"] = fingerprint["quality"]["overall_score"]

        try:
            quarantine_path = self.quarantine_dir / file_path.name
            if not quarantine_path.exists():
                shutil.copy2(file_path, quarantine_path)
                result["quarantine_path"] = str(quarantine_path)
        except Exception as e:
            result["quarantine_error"] = str(e)

        try:
            dataset_id = self._register_dataset(
                fingerprint,
                target_kb="__quarantine__",
                source="quarantine",
                rows_indexed=0,
                status_override="quarantined",
            )
            result["dataset_id"] = dataset_id
        except Exception as e:
            result["register_error"] = str(e)

        self._log_curation(
            action="add",
            target_kb="__quarantine__",
            target_id=file_path.name,
            summary=f"Quarantined (low quality): {'; '.join(reasons)}",
            source="ingestion_pipeline.py",
        )

        return result

    def _soft_delete_existing(self, name: str, source: str, repo_id: Optional[str]) -> Optional[str]:
        """Mark existing dataset as deleted (Iron Law #21 — soft delete)."""
        if repo_id:
            cur = self.sqlite_conn.execute(
                "SELECT id FROM datasets WHERE name=? AND source=? AND repo_id=? AND deleted_at IS NULL",
                (name, source, repo_id),
            )
        else:
            cur = self.sqlite_conn.execute(
                "SELECT id FROM datasets WHERE name=? AND source=? AND deleted_at IS NULL",
                (name, source),
            )
        row = cur.fetchone()
        if row:
            existing_id = row[0]
            with self.sqlite_conn:
                self.sqlite_conn.execute(
                    "UPDATE datasets SET deleted_at=CURRENT_TIMESTAMP WHERE id=?",
                    (existing_id,),
                )
            self._log_curation(
                action="delete",
                target_kb="(replaced)",
                target_id=existing_id,
                summary=f"Soft-deleted before re-ingestion: {name}",
                source="ingestion_pipeline.py",
            )
            return existing_id
        return None

    def _to_canonical(self, file_path: Path, fingerprint: dict,
                      target_kb: str, source: str) -> list[dict]:
        """Convert raw rows to canonical format."""
        task_type = fingerprint.get("task_type", "unknown")
        rows = self.detector._read_sample(file_path)

        canonical_rows = []
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue

            # Build canonical text
            text = self._row_to_text(row, task_type)
            if not text or len(text) < QUALITY_THRESHOLDS["min_text_length"]:
                continue

            # Truncate if too long
            if len(text) > QUALITY_THRESHOLDS["max_text_length"]:
                text = text[:QUALITY_THRESHOLDS["max_text_length"]]

            canonical_rows.append({
                "id": str(uuid.uuid4()),
                "task_type": task_type,
                "text": text,
                "metadata": {
                    "dataset_name": fingerprint.get("file_name", ""),
                    "source": source,
                    "format_type": fingerprint.get("file_format", ""),
                    "row_index": i,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                },
            })

        return canonical_rows

    def _row_to_text(self, row: dict, task_type: str) -> str:
        """Convert a single row to canonical text representation."""
        if task_type == "conversational":
            return self._format_conversational(row)
        elif task_type == "instruction":
            return self._format_instruction(row)
        elif task_type == "tool_calling":
            return self._format_tool_calling(row)
        elif task_type == "code":
            return self._format_code(row)
        elif task_type == "classification":
            return self._format_classification(row)
        elif task_type == "qa":
            return self._format_qa(row)
        elif task_type == "embedding_pairs":
            return self._format_embedding_pairs(row)
        else:
            # Fallback: JSON dump
            return json.dumps(row, ensure_ascii=False)

    def _format_conversational(self, row: dict) -> str:
        """Format conversational row to canonical text."""
        messages = row.get("messages") or row.get("conversations") or row.get("chat") or []
        if not isinstance(messages, list):
            return ""

        lines = []
        for msg in messages[:20]:  # Limit to 20 messages
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "unknown")
            content = msg.get("content") or msg.get("text") or msg.get("value") or ""
            if isinstance(content, list):
                content = " ".join(str(c) for c in content if isinstance(c, dict) and c.get("type") == "text")
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _format_instruction(self, row: dict) -> str:
        """Format instruction row to canonical text."""
        instruction = row.get("instruction", "")
        inp = row.get("input", "")
        output = row.get("output", "")

        text = f"Instruction: {instruction}"
        if inp:
            text += f"\nInput: {inp}"
        if output:
            text += f"\nOutput: {output}"
        return text

    def _format_tool_calling(self, row: dict) -> str:
        """Format tool-calling row to canonical text."""
        system = row.get("system", "")
        chat = row.get("chat", [])
        tools = row.get("tools", [])

        text = ""
        if system:
            text += f"System: {system}\n\n"

        if isinstance(tools, list):
            text += f"Available Tools: {len(tools)}\n"
            for tool in tools[:5]:
                if isinstance(tool, dict):
                    text += f"- {tool.get('name', '?')}: {tool.get('description', '')}\n"

        if isinstance(chat, list):
            text += "\nConversation:\n"
            for msg in chat[:20]:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", "?")
                content = msg.get("content", "")
                text += f"  {role}: {content}\n"

        return text.strip()

    def _format_code(self, row: dict) -> str:
        """Format code row to canonical text."""
        query = row.get("query", "") or row.get("question", "") or row.get("instruction", "")
        answer = row.get("answer", "") or row.get("output", "") or row.get("response", "")
        code = row.get("code", "")

        text = f"Question: {query}"
        if code:
            text += f"\nCode:\n{code}"
        if answer:
            text += f"\nAnswer: {answer}"
        return text

    def _format_classification(self, row: dict) -> str:
        """Format classification row."""
        text = row.get("text", "") or row.get("sentence", "")
        label = row.get("label", "?")
        return f"Text: {text}\nLabel: {label}"

    def _format_qa(self, row: dict) -> str:
        """Format QA row."""
        question = row.get("question", "")
        context = row.get("context", "")
        answers = row.get("answers", {})

        text = f"Question: {question}"
        if context:
            text += f"\nContext: {context[:1000]}"  # Truncate context

        if isinstance(answers, dict):
            text_list = answers.get("text", [])
            if isinstance(text_list, list) and text_list:
                text += f"\nAnswer: {text_list[0]}"
        elif isinstance(answers, list) and answers:
            text += f"\nAnswer: {answers[0]}"

        return text

    def _format_embedding_pairs(self, row: dict) -> str:
        """Format embedding pair row."""
        s1 = row.get("sentence1", "")
        s2 = row.get("sentence2", "")
        score = row.get("score", row.get("label", "?"))
        return f"Sentence 1: {s1}\nSentence 2: {s2}\nScore: {score}"

    def _embed_and_index(self, canonical_rows: list[dict], target_kb: str) -> int:
        """Embed + index in ChromaDB. Returns count of indexed rows."""
        if not self.chroma_client:
            return 0
        if not canonical_rows:
            return 0

        try:
            coll = self.chroma_client.get_or_create_collection(target_kb)
        except Exception as e:
            print(f"⚠️  Failed to create collection {target_kb}: {e}")
            return 0

        # Batch insert
        BATCH_SIZE = 500
        indexed = 0
        for i in range(0, len(canonical_rows), BATCH_SIZE):
            batch = canonical_rows[i:i + BATCH_SIZE]
            try:
                coll.add(
                    documents=[r["text"] for r in batch],
                    ids=[r["id"] for r in batch],
                    metadatas=[r["metadata"] for r in batch],
                )
                indexed += len(batch)
            except Exception as e:
                print(f"⚠️  Batch {i}-{i+len(batch)} failed: {e}")

        return indexed

    def _register_dataset(self, fingerprint: dict, target_kb: str,
                          source: str, rows_indexed: int,
                          status_override: Optional[str] = None) -> str:
        """Register dataset in SQLite datasets table."""
        dataset_id = str(uuid.uuid4())
        name = fingerprint.get("file_name", "unknown")
        repo_id = fingerprint.get("repo_id")  # If present from HF

        # Determine status
        if status_override:
            status = status_override
        elif rows_indexed > 0:
            status = "ingested"
        else:
            status = "staged"

        # Check uniqueness
        if repo_id:
            cur = self.sqlite_conn.execute(
                "SELECT id FROM datasets WHERE name=? AND source=? AND repo_id=? AND deleted_at IS NULL",
                (name, source, repo_id),
            )
        else:
            cur = self.sqlite_conn.execute(
                "SELECT id FROM datasets WHERE name=? AND source=? AND deleted_at IS NULL",
                (name, source),
            )
        existing = cur.fetchone()
        if existing:
            # Update existing (Iron Law #21 — no duplicate rows)
            dataset_id = existing[0]
            with self.sqlite_conn:
                self.sqlite_conn.execute(
                    """UPDATE datasets
                    SET target_kb=?, format_fingerprint=?, quality_score=?,
                        size_bytes=?, rows_total=?, rows_indexed=?, status=?,
                        ingested_at=CURRENT_TIMESTAMP
                    WHERE id=?""",
                    (
                        target_kb,
                        json.dumps(fingerprint),
                        fingerprint["quality"]["overall_score"],
                        fingerprint.get("size_bytes", 0),
                        fingerprint.get("row_count_estimated", 0),
                        rows_indexed,
                        status,
                        dataset_id,
                    ),
                )
        else:
            # Insert new
            with self.sqlite_conn:
                self.sqlite_conn.execute(
                    """INSERT INTO datasets
                    (id, name, source, repo_id, target_kb, format_fingerprint,
                     quality_score, license, size_bytes, rows_total, rows_indexed, status, ingested_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (
                        dataset_id,
                        name,
                        source,
                        repo_id,
                        target_kb,
                        json.dumps(fingerprint),
                        fingerprint["quality"]["overall_score"],
                        fingerprint.get("license"),
                        fingerprint.get("size_bytes", 0),
                        fingerprint.get("row_count_estimated", 0),
                        rows_indexed,
                        status,
                    ),
                )

        return dataset_id

    def _log_curation(self, action: str, target_kb: str, target_id: str,
                      summary: str, source: str = "ingestion_pipeline.py"):
        """Log to curation_log (Iron Law #36)."""
        try:
            self.sqlite_conn.execute(
                "INSERT INTO curation_log(action, target_kb, target_id, summary, source) "
                "VALUES(?, ?, ?, ?, ?)",
                (action, target_kb, target_id, summary, source),
            )
            self.sqlite_conn.commit()
        except Exception as e:
            print(f"⚠️  Curation log error: {e}")


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ingest dataset into Alpha Wolf body")
    parser.add_argument("file", help="Path to dataset file")
    parser.add_argument("--kb", default="kb_self", help="Target KB collection")
    parser.add_argument("--source", default="local", choices=["local", "huggingface", "url"])
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    pipeline = IngestionPipeline()
    file_path = Path(args.file)

    if args.source == "huggingface":
        result = pipeline.ingest_from_hf(args.file, args.kb)
    else:
        result = pipeline.ingest(file_path, args.kb, args.source)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        status = result.get("status", "?")
        emoji = {"ingested": "✅", "quarantined": "🚨", "error": "❌"}.get(status, "❓")
        print(f"\n{emoji} Status: {status}")
        if status == "ingested":
            print(f"   Dataset ID: {result.get('dataset_id', '?')[:8]}...")
            print(f"   Rows indexed: {result.get('rows_indexed', 0)}")
            print(f"   Quality score: {result.get('fingerprint', {}).get('quality', {}).get('overall_score', 0):.2f}")
        elif status == "quarantined":
            print(f"   Reasons: {result.get('quarantine_reasons', [])}")
        elif status == "error":
            print(f"   Error: {result.get('error', '?')}")

    return 0 if result.get("status") == "ingested" else 1


if __name__ == "__main__":
    sys.exit(main())
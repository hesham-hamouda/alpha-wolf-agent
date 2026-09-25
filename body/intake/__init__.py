r"""Alpha Wolf Agent — Intake Module (Format Detection + Ingestion).

Modules:
    format_detector.py   — Auto-detect dataset format + schema + quality
    ingestion_pipeline.py — Full ingestion (detect → quality → embed → index)
    auto_learn.py        — Continuous learning (P2 — future work)

Iron Laws Applied:
- #7  (Anti-Contamination)  — blacklist enforced in format_detector.quarantine_check
- #14 (Snapshot)             — soft-delete before re-ingest (Iron Law #21)
- #15 (Verify)                — every operation returns structured dict
- #17 (NO Ollama LLMs)        — embeddings only via Ollama nomic-embed-text
- #21 (NO Deletion)           — datasets.deleted_at soft delete column
- #36 (5-Layer Save)          — every action logged to curation_log
- #42 (Workspace-Body)        — body in workspace, NOT in E:\Agents\

Usage:
    from body.intake.format_detector import FormatDetector
    from body.intake.ingestion_pipeline import IngestionPipeline

    # Detect format
    detector = FormatDetector()
    fingerprint = detector.detect(Path("data/ultrachat.jsonl"))
    print(fingerprint["task_type"], fingerprint["quality"]["overall_score"])

    # Ingest
    pipeline = IngestionPipeline()
    result = pipeline.ingest(Path("data/ultrachat.jsonl"), target_kb="kb_self")
    print(result["status"], result["rows_indexed"])
"""
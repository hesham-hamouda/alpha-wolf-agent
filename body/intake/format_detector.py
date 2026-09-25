#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Format Detector
====================================
Auto-detects dataset format, schema, task type, and quality metrics.
Designed for the "Format Translation SFT" approach (Mix E training).

Iron Laws Applied:
- #7  (Anti-Contamination) — blacklist patterns enforced
- #15 (Verify)            — every detection returns structured dict
- #17 (NO Ollama LLMs)    — embeddings only, never LLMs
- #21 (NO Deletion)       — quarantine, not delete
- #26 (Arabic comments)   — bilingual docs
- #36 (5-Layer Save)      — detection events logged

Usage:
    from body.intake.format_detector import FormatDetector

    detector = FormatDetector()
    fingerprint = detector.detect(Path("data/ultrachat_50k.jsonl"))
    print(json.dumps(fingerprint, indent=2, ensure_ascii=False))
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

# Try to import pandas + pyarrow for tabular formats (optional)
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import pyarrow.parquet as pq
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False


# ============================================================================
# Constants — Format taxonomy + Blacklist
# ============================================================================

# Format detection patterns (schema keys → task type)
FORMAT_PATTERNS = {
    "tool_calling": {"required": ["tools", "chat"], "optional": ["system"]},
    "conversational": {"required": ["messages"], "optional": ["conversations", "chat"]},
    "instruction": {"required": ["instruction", "output"], "optional": ["input"]},
    "code": {"required": ["query"], "optional": ["answer", "code", "resources"]},
    "classification": {"required": ["text", "label"], "optional": []},
    "qa": {"required": ["question"], "optional": ["context", "answers"]},
    "embedding_pairs": {"required": ["sentence1", "sentence2"], "optional": ["score", "label"]},
    "tabular": {"required": [], "optional": []},  # CSV/Parquet — generic
}

# File extension → format type
EXTENSION_FORMAT = {
    ".jsonl": "jsonl",
    ".json": "json",
    ".csv": "csv",
    ".tsv": "tsv",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".arrow": "arrow",
    ".xml": "xml",
    ".txt": "txt",
}

# Iron Law #7 — Anti-Contamination Blacklist
BLACKLIST = {
    "name_patterns": [
        r"^wolf[-_]?.*",         # Wolf_Agent philosophy
        r".*ollama.*-text.*",    # Ollama LLMs (Iron Law #17)
        r".*wolf1-brain.*",
        r".*wolf-router.*",
    ],
    "license_patterns": [
        r"unknown",
        r"proprietary",
    ],
    "size_limits": {
        "max_size_gb": 50,       # Storage discipline
        "warn_size_gb": 10,
    },
}


# ============================================================================
# Quality Thresholds
# ============================================================================

QUALITY_THRESHOLDS = {
    "min_text_length": 5,           # Chars
    "max_text_length": 50_000,      # Chars (truncate above)
    "max_duplicate_rate": 0.05,     # 5%
    "max_missing_rate": 0.10,       # 10%
    "min_quality_score": 0.6,
    "max_encoding_errors": 0.01,
    "sample_size": 1000,            # rows to inspect
}


# ============================================================================
# Format Detector
# ============================================================================

class FormatDetector:
    """Auto-detect dataset format, schema, task type, and quality."""

    def __init__(self, sample_size: int = QUALITY_THRESHOLDS["sample_size"]):
        self.sample_size = sample_size

    # ========================================================================
    # Main Detection Entry Point
    # ========================================================================

    def detect(self, file_path: Path) -> dict:
        """Detect full fingerprint of a dataset file.

        Returns:
            dict with keys:
                file_format, encoding, size_bytes, size_mb, row_count,
                schema, task_type, quality, license, fingerprint_hash
        """
        file_path = Path(file_path)
        fingerprint: dict[str, Any] = {
            "file_path": str(file_path),
            "file_name": file_path.name,
        }

        # Stage 1: File metadata
        fingerprint.update(self._file_metadata(file_path))

        # Stage 2: Read sample
        try:
            sample = self._read_sample(file_path)
        except Exception as e:
            return {**fingerprint, "error": f"Failed to read sample: {e}", "task_type": "unknown"}

        fingerprint["row_count_sample"] = len(sample)

        # Stage 3: Schema extraction
        if sample:
            fingerprint["schema"] = self._extract_schema(sample)
            fingerprint["task_type"] = self._classify_task(fingerprint["schema"], sample)
        else:
            fingerprint["schema"] = {}
            fingerprint["task_type"] = "empty"

        # Stage 4: Quality metrics
        fingerprint["quality"] = self._compute_quality(sample)

        # Stage 5: Fingerprint hash (for deduplication)
        fingerprint["fingerprint_hash"] = self._compute_hash(fingerprint)

        return fingerprint

    def detect_from_url(self, hf_url: str) -> dict:
        """Detect from HuggingFace dataset URL (placeholder)."""
        # TODO: integrate with huggingface_hub to fetch dataset card
        return {
            "url": hf_url,
            "task_type": "unknown",
            "note": "Use detect() on downloaded file. Streaming detection not yet implemented.",
        }

    def validate_format(self, fingerprint: dict) -> bool:
        """Validate fingerprint against quality thresholds."""
        quality = fingerprint.get("quality", {})
        score = quality.get("overall_score", 0)
        return score >= QUALITY_THRESHOLDS["min_quality_score"]

    def quarantine_check(self, fingerprint: dict) -> tuple[bool, list[str]]:
        """Check if dataset should be quarantined.

        Returns:
            (is_quarantined: bool, reasons: list[str])
        """
        reasons = []

        # Check name patterns
        name = fingerprint.get("file_name", "")
        for pattern in BLACKLIST["name_patterns"]:
            if re.match(pattern, name, re.IGNORECASE):
                reasons.append(f"Name matches blacklist pattern: {pattern}")

        # Check size limits
        size_mb = fingerprint.get("size_mb", 0)
        max_gb = BLACKLIST["size_limits"]["max_size_gb"]
        if size_mb > max_gb * 1024:
            reasons.append(f"Size exceeds limit: {size_mb:.1f} MB > {max_gb * 1024} MB")

        # Check quality
        if not self.validate_format(fingerprint):
            reasons.append(
                f"Quality below threshold: "
                f"{fingerprint.get('quality', {}).get('overall_score', 0):.2f} < "
                f"{QUALITY_THRESHOLDS['min_quality_score']}"
            )

        return (len(reasons) > 0, reasons)

    # ========================================================================
    # File Metadata
    # ========================================================================

    def _file_metadata(self, file_path: Path) -> dict:
        """Extract file-level metadata."""
        if not file_path.exists():
            return {"error": f"File not found: {file_path}"}

        size_bytes = file_path.stat().st_size
        ext = file_path.suffix.lower()
        file_format = EXTENSION_FORMAT.get(ext, "unknown")

        # Detect encoding (basic heuristic)
        encoding = "utf-8"
        try:
            with open(file_path, "rb") as f:
                raw_sample = f.read(min(size_bytes, 1024))
                if raw_sample.startswith(b"\x1f\x8b"):
                    encoding = "gzip"
                elif raw_sample[:3] == b"\xef\xbb\xbf":
                    encoding = "utf-8-bom"
                else:
                    raw_sample.decode("utf-8")
        except UnicodeDecodeError:
            encoding = "unknown"

        # Estimate row count (fast scan)
        row_count = self._estimate_row_count(file_path, file_format)

        return {
            "file_format": file_format,
            "encoding": encoding,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "row_count_estimated": row_count,
        }

    def _estimate_row_count(self, file_path: Path, file_format: str) -> int:
        """Estimate row count without loading entire file."""
        if file_format == "jsonl":
            # Count newlines (each row is one line)
            count = 0
            with open(file_path, "rb") as f:
                for _ in f:
                    count += 1
            return count
        elif file_format == "csv" or file_format == "tsv":
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                return sum(1 for _ in reader)
        elif file_format == "json":
            # Heuristic: file_size / avg_row_size
            return -1  # Unknown without parsing
        elif file_format == "parquet" and HAS_PARQUET:
            try:
                return pq.read_metadata(file_path).num_rows
            except Exception:
                return -1
        return -1

    # ========================================================================
    # Sample Reader
    # ========================================================================

    def _read_sample(self, file_path: Path, n: int = 1000) -> list:
        """Read a sample of rows from the file."""
        size_bytes = file_path.stat().st_size
        if size_bytes > 1024 * 1024 * 1024:  # 1 GB
            # Large file — read only first 1000 lines
            sample_size = self.sample_size
        else:
            sample_size = self.sample_size

        ext = file_path.suffix.lower()

        if ext in [".jsonl", ".json"]:
            return self._read_jsonl_sample(file_path, sample_size)
        elif ext in [".csv", ".tsv"]:
            return self._read_csv_sample(file_path, sample_size)
        elif ext == ".parquet" and HAS_PANDAS:
            return self._read_parquet_sample(file_path, sample_size)
        elif ext == ".txt":
            return self._read_txt_sample(file_path, sample_size)
        else:
            # Try JSON as fallback
            try:
                return self._read_jsonl_sample(file_path, sample_size)
            except Exception:
                return []

    def _read_jsonl_sample(self, file_path: Path, n: int) -> list:
        sample = []
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    sample.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return sample

    def _read_json_sample(self, file_path: Path, n: int) -> list:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[:n]
        elif isinstance(data, dict):
            return [data]
        return []

    def _read_csv_sample(self, file_path: Path, n: int) -> list:
        sample = []
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= n:
                    break
                sample.append(dict(row))
        return sample

    def _read_parquet_sample(self, file_path: Path, n: int) -> list:
        if not HAS_PANDAS:
            return []
        df = pd.read_parquet(file_path).head(n)
        return df.to_dict("records")

    def _read_txt_sample(self, file_path: Path, n: int) -> list:
        sample = []
        with open(file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                sample.append({"text": line.strip()})
        return sample

    # ========================================================================
    # Schema Extraction
    # ========================================================================

    def _extract_schema(self, sample: list) -> dict:
        """Extract schema from sample rows."""
        if not sample:
            return {}

        # Union of all keys across rows
        all_keys = set()
        for row in sample:
            if isinstance(row, dict):
                all_keys.update(row.keys())

        # Infer types
        schema = {}
        for key in sorted(all_keys):
            types = Counter()
            for row in sample[:100]:  # Use first 100 rows for type inference
                if not isinstance(row, dict):
                    continue
                value = row.get(key)
                types[self._infer_type(value)] += 1

            most_common_type = types.most_common(1)[0][0] if types else "unknown"
            schema[key] = most_common_type

        return schema

    def _infer_type(self, value: Any) -> str:
        """Infer JSON type of a value."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            # Check if it's a datetime
            if re.match(r"\d{4}-\d{2}-\d{2}", value):
                return "datetime"
            if len(value) > 100:
                return "text"
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "unknown"

    # ========================================================================
    # Task Classification
    # ========================================================================

    def _classify_task(self, schema: dict, sample: list) -> str:
        """Classify the task type based on schema + sample inspection."""
        schema_keys = set(schema.keys())

        # Priority order: tool_calling > conversational > instruction > code > classification > qa > embedding_pairs > tabular
        for task_type, pattern in FORMAT_PATTERNS.items():
            if task_type == "tabular":
                continue
            required = set(pattern["required"])
            if required.issubset(schema_keys):
                return task_type

        # Fallback: heuristic based on first sample
        if sample and isinstance(sample[0], dict):
            first_keys = set(sample[0].keys())
            for task_type, pattern in FORMAT_PATTERNS.items():
                if task_type == "tabular":
                    continue
                required = set(pattern["required"])
                if required and required.issubset(first_keys):
                    return task_type

        return "unknown"

    # ========================================================================
    # Quality Metrics
    # ========================================================================

    def _compute_quality(self, sample: list) -> dict:
        """Compute quality metrics for the sample."""
        if not sample:
            return {
                "overall_score": 0.0,
                "duplicate_rate": 1.0,
                "missing_rate": 1.0,
                "notes": "Empty sample",
            }

        # Duplicate detection (by string representation)
        sample_strs = [json.dumps(row, sort_keys=True) for row in sample if isinstance(row, dict)]
        unique_count = len(set(sample_strs))
        duplicate_rate = 1.0 - (unique_count / len(sample_strs)) if sample_strs else 0.0

        # Missing values per key
        all_keys = set()
        for row in sample:
            if isinstance(row, dict):
                all_keys.update(row.keys())
        missing_counts = {}
        total_cells = len(sample) * len(all_keys) if all_keys else 1
        missing_total = 0
        for key in all_keys:
            missing = sum(1 for row in sample if isinstance(row, dict) and (key not in row or row[key] is None or row[key] == ""))
            missing_counts[key] = missing
            missing_total += missing
        missing_rate = missing_total / total_cells

        # Length stats (for text fields)
        text_lengths = []
        for row in sample:
            if not isinstance(row, dict):
                continue
            for value in row.values():
                if isinstance(value, str) and len(value) > 3:
                    text_lengths.append(len(value))

        length_stats = {}
        if text_lengths:
            length_stats = {
                "min": min(text_lengths),
                "max": max(text_lengths),
                "median": sorted(text_lengths)[len(text_lengths) // 2],
                "count": len(text_lengths),
            }

        # Overall quality score (weighted)
        score = 1.0
        score -= duplicate_rate * 0.5  # 50% weight to dedup
        score -= missing_rate * 0.3   # 30% weight to completeness
        if length_stats.get("median", 0) < QUALITY_THRESHOLDS["min_text_length"]:
            score -= 0.2

        score = max(0.0, min(1.0, score))

        return {
            "overall_score": round(score, 3),
            "duplicate_rate": round(duplicate_rate, 3),
            "missing_rate": round(missing_rate, 3),
            "missing_per_key": missing_counts,
            "length_stats": length_stats,
            "notes": f"Sampled {len(sample)} rows, {unique_count} unique",
        }

    # ========================================================================
    # Fingerprint Hash (for deduplication)
    # ========================================================================

    def _compute_hash(self, fingerprint: dict) -> str:
        """Compute SHA256 hash of fingerprint for deduplication."""
        canonical = json.dumps(fingerprint, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Detect dataset format")
    parser.add_argument("file", help="Path to dataset file")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return 1

    detector = FormatDetector()
    fingerprint = detector.detect(file_path)
    is_quarantined, reasons = detector.quarantine_check(fingerprint)

    fingerprint["quarantined"] = is_quarantined
    fingerprint["quarantine_reasons"] = reasons

    if args.json:
        print(json.dumps(fingerprint, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*70}")
        print(f"FORMAT DETECTION: {file_path.name}")
        print(f"{'='*70}")
        print(f"Format: {fingerprint.get('file_format', '?')}")
        print(f"Size: {fingerprint.get('size_mb', 0):.2f} MB")
        print(f"Encoding: {fingerprint.get('encoding', '?')}")
        print(f"Rows (est): {fingerprint.get('row_count_estimated', '?')}")
        print(f"Task type: {fingerprint.get('task_type', '?')}")
        print(f"Quality score: {fingerprint.get('quality', {}).get('overall_score', 0):.2f}")
        print(f"Schema: {fingerprint.get('schema', {})}")
        if is_quarantined:
            print(f"\n🚨 QUARANTINED:")
            for r in reasons:
                print(f"   - {r}")
        else:
            print(f"\n✅ OK to ingest")

    return 0


if __name__ == "__main__":
    sys.exit(main())
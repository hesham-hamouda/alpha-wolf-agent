#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Wolf Classifier (WCP)
=======================================
4-class classifier that distinguishes:
1. HARMFUL (security threats, PII, illegal content) → REJECT + soft quarantine
2. PROJECT-SPECIFIC (configs, endpoints, credentials) → workspace storage
3. USEFUL (generalizable patterns, concepts, techniques) → distill → body
4. RAW (low confidence) → body/raw/ for human review

Hybrid approach: Rules + Heuristic (NO Ollama LLM per Iron Law #17)

Iron Laws Applied:
- #7  (Anti-Contamination) — harmful class IS the enforcement layer
- #17 (NO Ollama LLMs)    — Hybrid uses rules + heuristics only
- #21 (NO Deletion)         — harmful = soft quarantine, NEVER delete
- #36 (5-Layer Save)        — every classification logged
- #42 (Workspace-Body)      — project_specific lives in workspace only
- #47 (Wolf Classification) — THIS MODULE

Usage:
    from body.intake.wolf_classifier import WolfClassifier

    classifier = WolfClassifier()
    result = classifier.classify(Path("data/new_dataset.jsonl"))
    print(result["class"], result["confidence"])
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Detection Patterns (Rules Engine)
# ============================================================================

# Patterns that indicate HARMFUL content
HARMFUL_PATTERNS = {
    # Security threats
    "malware_signature": [
        r"\b(Mimikatz|Meterpreter|Cobalt Strike|Empire|pupy|zeus)\b",
        r"exploit[_\s-]?(cve-\d{4}-\d+|0day|weaponized)",
        r"(?i)ransomware[_\s-]?encrypt[_\s-]?(files|victim)",
        r"(?i)keylogger|trojan[_\s-]?horse|rootkit|backdoor",
    ],
    # PII patterns (high density)
    "pii_high_density": [
        r"\b\d{3}-\d{2}-\d{4}\b",                    # SSN
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", # Credit Card
        r"(?i)\b\d{16}\b",                              # Raw CC
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email (high density)
        r"\b\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b",          # Phone
        r"\b\d{1,5}\s\w+\s(Street|St|Avenue|Ave|Road|Rd)\b",  # Address
    ],
    # Credentials / Leaked
    "credentials": [
        r"sk-[A-Za-z0-9]{20,}",                  # OpenAI-style API key
        r"hf_[A-Za-z0-9]{20,}",                  # HuggingFace token
        r"AKIA[0-9A-Z]{16}",                     # AWS Access Key
        r"ghp_[A-Za-z0-9]{36}",                  # GitHub PAT
        r"xox[baprs]-[A-Za-z0-9-]+",            # Slack token
        r"(?i)password\s*[:=]\s*\S+",            # Plain password
    ],
    # Illegal content markers (immediate reject + escalate)
    "illegal": [
        # CSAM — handled separately by content moderation system, NOT here
        r"(?i)\b(weapon|explosive|synthesis)\s+(guide|tutorial|instructions)",
        r"(?i)how\s+to\s+(make|build|synthesize)\s+(drugs|explosives|weapons)",
    ],
    # Misinformation / propaganda
    "misinformation": [
        # Detected via pattern density, not single markers
    ],
}

# Patterns that indicate PROJECT-SPECIFIC content
PROJECT_SPECIFIC_PATTERNS = {
    "config_files": [
        r"\.env(\.|$|\b)",
        r"config\.(yml|yaml|json|toml)",
        r"(?i)\bapi[_\s-]?key\b",
        r"(?i)\bsecret[_\s-]?key\b",
        r"(?i)database[_\s-]?url\b",
        r"(?i)endpoint[s]?[\s]*[:=]",
        r"\bhttps?://[^\s]+\.(internal|local|corp|company)\b",  # Internal URLs
    ],
    "credentials_direct": [
        # Already covered in HARMFUL_PATTERNS["credentials"]
        # but these are NOT necessarily harmful — just project-specific
        # E.g., a developer sharing their own dev keys = project_specific, not harmful
    ],
    "business_specific": [
        r"(?i)\b(contract|quarterly|annual)\s+(report|revenue|earnings)\b",
        r"(?i)\binternal\s+(employee|user|customer)\s+(id|data|info)",
        r"(?i)\bproject\s+(timeline|deadline|milestone)\b",
        r"\b\d{4}-\d{2}-\d{2}\s+(deadline|release|launch)",  # Specific dates
    ],
    "company_identifiers": [
        r"\b(OpenAI|Anthropic|Google|Microsoft|Apple|Amazon|Meta|Netflix)\s+(API|key|secret|token)",
        # Quхائd-specific: "Quхائد", "Alpha Wolf", specific user names
    ],
    "paths_and_endpoints": [
        r"[A-Z]:\\[^\s]+",                    # Windows paths
        r"/home/[^\s]+/",                       # Linux home paths
        r"https?://(localhost|127\.0\.0\.1)",   # Localhost URLs
        r"https?://[^/]*\.(corp|internal)",     # Internal domains
    ],
}

# Patterns that indicate USEFUL content (generalizable)
USEFUL_INDICATORS = {
    "generalizable_patterns": [
        r"\b(algorithm|complexity|big[\s-]?o)\b",
        r"\b(principle|law|theorem|equation)\b",
        r"\b(pattern|recipe|technique|method)\b",
        r"\b(framework|architecture|design)\b",
    ],
    "abstract_content": [
        r"\b(general|abstract|theoretical|generic)\b",
        r"\b(concept|idea|theory)\b",
    ],
}

# Blacklist (Iron Law #7)
BLACKLIST_NAMES = [
    r"^wolf[-_]?.*",                          # Wolf_Agent philosophy
    r".*ollama.*-text.*",                     # Ollama LLMs (Iron Law #17)
    r".*wolf1-brain.*",
    r".*wolf-router.*",
    r"^.*[\s_-]?proprietary[\s_-]?.*$",       # Proprietary (without license)
]


# ============================================================================
# Heuristic Classifier (Domain Blacklist + TF-IDF + Entropy)
# ============================================================================

# Domain blacklists (signals project_specific OR low quality)
PROJECT_SPECIFIC_DOMAINS = [
    "company.com", "corp.local", "internal.com",
    "localhost", "127.0.0.1", "192.168.",
]

# Stop words for classification (low signal)
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at",
    "to", "for", "of", "with", "by", "is", "are", "was",
}


# ============================================================================
# Wolf Classifier
# ============================================================================

class WolfClassifier:
    """4-class classifier: Harmful / Project-specific / Useful / Raw."""

    def __init__(self, confidence_threshold: float = 0.6):
        self.confidence_threshold = confidence_threshold
        # Compile regex patterns for performance
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile all regex patterns."""
        self.harmful_compiled = {}
        for category, patterns in HARMFUL_PATTERNS.items():
            self.harmful_compiled[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns if patterns
            ]
        self.project_compiled = {}
        for category, patterns in PROJECT_SPECIFIC_PATTERNS.items():
            self.project_compiled[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns if patterns
            ]
        self.useful_compiled = {}
        for category, patterns in USEFUL_INDICATORS.items():
            self.useful_compiled[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns if patterns
            ]
        self.blacklist_compiled = [
            re.compile(p, re.IGNORECASE) for p in BLACKLIST_NAMES
        ]

    # ========================================================================
    # Main Entry Point
    # ========================================================================

    def classify(self, file_path: Path, format_info: Optional[dict] = None) -> dict:
        """Classify a dataset file into one of 4 classes.

        Args:
            file_path: Path to dataset file
            format_info: Optional pre-computed format detection result

        Returns:
            dict with keys:
                class: 'harmful' | 'project_specific' | 'useful' | 'raw'
                confidence: float 0-1
                reason: human-readable explanation
                detected_patterns: dict of {pattern_type: count}
                file_hash: SHA256 (for audit)
                file_size_mb: float
        """
        file_path = Path(file_path)
        result = {
            "file_path": str(file_path),
            "file_name": file_path.name,
        }

        # Stage 0: File metadata (Iron Law #15)
        if not file_path.exists():
            result.update({
                "class": "harmful",
                "confidence": 0.0,
                "reason": f"File not found: {file_path}",
            })
            return result

        size_bytes = file_path.stat().st_size
        file_hash = self._compute_file_hash(file_path)
        result["file_hash"] = file_hash
        result["file_size_mb"] = round(size_bytes / (1024 * 1024), 2)

        # Stage 1: Name-based blacklist (Iron Law #7)
        is_blacklisted, blacklist_reason = self._check_blacklist(file_path.name)
        if is_blacklisted:
            result.update({
                "class": "harmful",
                "confidence": 1.0,
                "reason": f"Name matches blacklist: {blacklist_reason}",
                "detected_patterns": {"blacklist_name": 1},
            })
            return result

        # Stage 2: Read sample for analysis
        try:
            sample = self._read_sample(file_path, max_rows=500)
        except Exception as e:
            result.update({
                "class": "raw",
                "confidence": 0.0,
                "reason": f"Could not read sample: {e}",
                "detected_patterns": {"read_error": 1},
            })
            return result

        if not sample:
            result.update({
                "class": "raw",
                "confidence": 0.0,
                "reason": "Empty dataset",
                "detected_patterns": {"empty": 1},
            })
            return result

        # Stage 3: Harmful pattern scan (security-first)
        harmful_score, harmful_findings = self._scan_harmful(sample)
        if harmful_score >= 0.5:  # High confidence harmful
            result.update({
                "class": "harmful",
                "confidence": harmful_score,
                "reason": f"Detected {sum(harmful_findings.values())} harmful patterns: {list(harmful_findings.keys())}",
                "detected_patterns": harmful_findings,
            })
            return result

        # Stage 4: Project-specific pattern scan
        project_score, project_findings = self._scan_project_specific(sample)
        if project_score >= 0.5:  # High confidence project-specific
            result.update({
                "class": "project_specific",
                "confidence": project_score,
                "reason": f"Detected {sum(project_findings.values())} project-specific patterns: {list(project_findings.keys())}",
                "detected_patterns": project_findings,
            })
            return result

        # Stage 5: Useful content check
        useful_score, useful_findings = self._scan_useful(sample)

        # Stage 6: Confidence calculation
        # Use heuristic: useful_score + generalizability heuristic
        confidence = useful_score
        # Boost confidence if dataset has good structure (format-detected)
        if format_info and format_info.get("task_type") != "unknown":
            confidence = min(1.0, confidence + 0.1)

        if confidence >= self.confidence_threshold:
            result.update({
                "class": "useful",
                "confidence": confidence,
                "reason": f"Detected {sum(useful_findings.values())} useful patterns: {list(useful_findings.keys())[:5]}",
                "detected_patterns": useful_findings,
            })
            return result

        # Default: RAW (needs human review)
        result.update({
            "class": "raw",
            "confidence": confidence,
            "reason": f"Low confidence ({confidence:.2f} < {self.confidence_threshold}). Useful patterns found: {useful_findings}. Project patterns: {project_findings}. Harmful patterns: {harmful_findings}. Needs manual review.",
            "detected_patterns": {
                "useful": useful_findings,
                "project_specific": project_findings,
                "harmful": harmful_findings,
            },
        })
        return result

    # ========================================================================
    # Detection Stages
    # ========================================================================

    def _check_blacklist(self, name: str) -> tuple[bool, str]:
        """Check if name matches blacklist patterns (Iron Law #7)."""
        for pattern in self.blacklist_compiled:
            if pattern.match(name):
                return True, pattern.pattern
        return False, ""

    def _scan_harmful(self, sample: list) -> tuple[float, dict]:
        """Scan sample for harmful patterns.

        Returns:
            (confidence, findings_dict)
        """
        findings = {}
        total_text = " ".join(str(row) for row in sample if isinstance(row, (dict, str)))[:100_000]

        for category, compiled_patterns in self.harmful_compiled.items():
            count = 0
            for pattern in compiled_patterns:
                matches = pattern.findall(total_text)
                count += len(matches)
            if count > 0:
                findings[category] = count

        # Confidence: weighted by severity
        # malware_signature and illegal = critical (high confidence)
        # credentials = high (any match is significant)
        # pii_high_density = medium (could be synthetic)
        weights = {
            "malware_signature": 0.95,
            "illegal": 1.0,
            "credentials": 0.92,  # ANY credentials match is high confidence
            "pii_high_density": 0.55,
            "misinformation": 0.6,
        }
        confidence = 0.0
        for category, count in findings.items():
            weight = weights.get(category, 0.5)
            # For credentials/illegal: even 1 match = high confidence (weight itself is enough)
            # For others: normalize by sample size
            if category in ("credentials", "illegal", "malware_signature"):
                normalized = 1.0 if count >= 1 else 0.0
            else:
                # Normalize by sample size (5+ matches in 500 rows = high confidence)
                normalized = min(1.0, count / 5.0)
            confidence = max(confidence, weight * normalized)

        return confidence, findings

    def _scan_project_specific(self, sample: list) -> tuple[float, dict]:
        """Scan sample for project-specific patterns.

        Returns:
            (confidence, findings_dict)
        """
        findings = {}
        total_text = " ".join(str(row) for row in sample if isinstance(row, (dict, str)))[:100_000]

        for category, compiled_patterns in self.project_compiled.items():
            count = 0
            for pattern in compiled_patterns:
                matches = pattern.findall(total_text)
                count += len(matches)
            if count > 0:
                findings[category] = count

        # Project-specific signals
        confidence = 0.0
        if "config_files" in findings or "paths_and_endpoints" in findings:
            confidence = 0.7
        if "business_specific" in findings:
            confidence = 0.6
        if "company_identifiers" in findings:
            confidence = 0.65

        # Normalize by density
        total_matches = sum(findings.values())
        if total_matches > 10:
            confidence = min(0.95, confidence + 0.1)

        return confidence, findings

    def _scan_useful(self, sample: list) -> tuple[float, dict]:
        """Scan sample for useful content indicators.

        Returns:
            (confidence, findings_dict)
        """
        findings = {}
        total_text = " ".join(str(row) for row in sample if isinstance(row, (dict, str)))[:100_000]
        total_words = len(total_text.split())

        for category, compiled_patterns in self.useful_compiled.items():
            count = 0
            for pattern in compiled_patterns:
                matches = pattern.findall(total_text)
                count += len(matches)
            if count > 0:
                findings[category] = count

        # Useful signals: high density of generalizable terms
        confidence = 0.0
        if "generalizable_patterns" in findings:
            pattern_count = findings["generalizable_patterns"]
            density = pattern_count / max(total_words, 1) * 1000  # per 1000 words
            if density > 5:  # High
                confidence = 0.85
            elif density > 2:  # Medium
                confidence = 0.7
            elif density > 0.5:  # Low
                confidence = 0.6

        if "abstract_content" in findings:
            confidence = max(confidence, 0.65)

        return confidence, findings

    # ========================================================================
    # Utilities
    # ========================================================================

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash for audit trail."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]  # First 16 chars for brevity

    def _read_sample(self, file_path: Path, max_rows: int = 500) -> list:
        """Read sample for classification."""
        ext = file_path.suffix.lower()
        if ext in [".jsonl", ".json"]:
            sample = []
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if i >= max_rows:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        sample.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return sample
        elif ext == ".csv":
            import csv
            sample = []
            with open(file_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break
                    sample.append(dict(row))
            return sample
        elif ext in [".txt"]:
            sample = []
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if i >= max_rows:
                        break
                    sample.append({"text": line.strip()})
            return sample
        return []

    def register_classification(self, classification_result: dict, body_db_path: Path):
        """Register classification result in SQLite (Iron Law #36 5-Layer Save)."""
        conn = sqlite3.connect(str(body_db_path), isolation_level=None)
        try:
            # Ensure tables exist
            conn.executescript("""
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
            """)
            import uuid
            cid = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO dataset_classifications
                (id, dataset_id, classification, confidence, reason, detected_patterns, file_hash)
                VALUES(?, ?, ?, ?, ?, ?, ?)""",
                (
                    cid,
                    classification_result.get("file_path", "unknown"),
                    classification_result["class"],
                    classification_result["confidence"],
                    classification_result["reason"],
                    json.dumps(classification_result.get("detected_patterns", {})),
                    classification_result.get("file_hash"),
                ),
            )
            return cid
        finally:
            conn.close()


# ============================================================================
# Distiller (USEFUL class only — removes project-specific details)
# ============================================================================

class Distiller:
    """Distill USEFUL datasets by removing project-specific details.

    Iron Laws Applied:
    - #17 (NO Ollama LLMs) — uses regex + heuristics only
    - #21 (NO Deletion) — original raw is kept, distillation creates new content
    - #36 (5-Layer Save) — provenance tracked
    """

    # Patterns to remove (with placeholder preservation)
    REMOVE_PATTERNS = {
        "api_key": (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[API_KEY]"),
        "hf_token": (re.compile(r"hf_[A-Za-z0-9]{20,}"), "[HF_TOKEN]"),
        "aws_key": (re.compile(r"AKIA[0-9A-Z]{16}"), "[AWS_KEY]"),
        "github_pat": (re.compile(r"ghp_[A-Za-z0-9]{36}"), "[GITHUB_PAT]"),
        "email": (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
        "ip_address": (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[IP_ADDR]"),
        "windows_path": (re.compile(r"[A-Z]:\\[^\s'\"]+"), "[WINDOWS_PATH]"),
        "linux_path": (re.compile(r"/home/[^\s'\"]+/"), "[HOME_PATH]"),
        "localhost_url": (re.compile(r"https?://(localhost|127\.0\.0\.1)[^\s'\"]*"), "[LOCAL_URL]"),
        "internal_url": (re.compile(r"https?://[^\s'\"]*\.(corp|internal)[^\s'\"]*"), "[INTERNAL_URL]"),
        "specific_date": (re.compile(r"\b20\d{2}-\d{2}-\d{2}\b"), "[DATE]"),
    }

    # Company names (replace with generic)
    COMPANY_REPLACEMENTS = {
        "OpenAI": "[COMPANY_LLM]",
        "Anthropic": "[COMPANY_LLM]",
        "Google": "[COMPANY_BIGTECH]",
        "Microsoft": "[COMPANY_BIGTECH]",
        "Apple": "[COMPANY_BIGTECH]",
        "Amazon": "[COMPANY_BIGTECH]",
        "Meta": "[COMPANY_BIGTECH]",
        "Netflix": "[COMPANY_STREAMING]",
        "قائد هشام": "[USER]",
        "Alpha Wolf": "[SYSTEM_NAME]",
    }

    def distill(self, sample: list) -> list[dict]:
        """Distill sample by removing project-specific details.

        Args:
            sample: list of row dicts

        Returns:
            list of distilled row dicts
        """
        distilled = []
        for row in sample:
            if not isinstance(row, dict):
                continue

            new_row = {}
            for key, value in row.items():
                if isinstance(value, str):
                    # Apply removals + replacements
                    new_value = self._redact_value(value)
                    new_row[key] = new_value
                elif isinstance(value, list):
                    # Recursively distill list items
                    new_row[key] = [
                        self._redact_value(item) if isinstance(item, str) else item
                        for item in value
                    ]
                elif isinstance(value, dict):
                    # Recursively distill nested dict
                    new_row[key] = {k: self._redact_value(v) if isinstance(v, str) else v for k, v in value.items()}
                else:
                    new_row[key] = value
            distilled.append(new_row)

        return distilled

    def _redact_value(self, value: str) -> str:
        """Apply redactions + replacements to a single string value."""
        new_value = value
        for pattern, replacement in self.REMOVE_PATTERNS.values():
            new_value = pattern.sub(replacement, new_value)
        for old, new in self.COMPANY_REPLACEMENTS.items():
            new_value = new_value.replace(old, new)
        return new_value

    def quality_check(self, distilled: list, original: list) -> tuple[bool, dict]:
        """3-layer quality check on distilled output."""
        checks = {}

        # 1. Completeness (length preservation, ±10%)
        if original:
            ratio = len(distilled) / len(original) if original else 0
            checks["completeness"] = 0.85 <= ratio <= 1.0
        else:
            checks["completeness"] = True

        # 2. No PII leaked (re-scan for redacted patterns)
        all_text = " ".join(str(row) for row in distilled if isinstance(row, (dict, str)))
        pii_leaked = sum(
            len(pattern.findall(all_text))
            for pattern, _ in self.REMOVE_PATTERNS.values()
        )
        checks["no_pii_leaked"] = pii_leaked == 0

        # 3. Structure preserved (same keys count)
        if distilled and original:
            orig_keys = set().union(*[set(row.keys()) for row in original if isinstance(row, dict)])
            dist_keys = set().union(*[set(row.keys()) for row in distilled if isinstance(row, dict)])
            checks["structure_preserved"] = len(orig_keys - dist_keys) == 0
        else:
            checks["structure_preserved"] = True

        return all(checks.values()), checks


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Wolf Classifier")
    parser.add_argument("file", help="Path to dataset file")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return 1

    classifier = WolfClassifier()
    result = classifier.classify(file_path)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        emoji = {
            "harmful": "🚨",
            "project_specific": "📁",
            "useful": "✅",
            "raw": "❓",
        }
        icon = emoji.get(result["class"], "?")
        print(f"\n{icon} Class: {result['class'].upper()}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Reason: {result['reason']}")
        if result.get("detected_patterns"):
            print(f"   Patterns: {result['detected_patterns']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
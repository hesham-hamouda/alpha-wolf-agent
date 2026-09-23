#!/usr/bin/env python3
r"""
storage_audit.py — Periodic storage health check for D:\Intelligence Models\

Purpose (per Quхائd's directive 2026-09-23):
- Detect AI models OUTSIDE D:\Intelligence Models\ (must move them)
- Find duplicate models (must delete)
- Report disk usage breakdown
- Alert when C: drive < 10GB free (protect Windows)

Usage:
    python storage_audit.py                    # Full audit
    python storage_audit.py --quick           # Disk space only
    python storage_audit.py --csv             # CSV output for tracking
    python storage_audit.py --json            # JSON output

Returns exit code 0 if clean, 1 if violations found.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Hardcoded paths (per Quهائد directive — these don't change)
PROTECTED_PATH = Path(r"D:\Intelligence Models")
C_DRIVE_PATH = Path("C:/")
PROHIBITED_LOCATIONS = [
    Path("C:/Users"),
    Path("C:/ProgramData"),
    Path("C:/Windows/System32"),
]
FILE_SIZE_THRESHOLD_GB = 0.5  # Files >500MB = "model-sized"


@dataclass
class ModelLocation:
    """A suspicious AI model file found outside the protected path."""
    path: Path
    size_gb: float
    file_type: str  # 'gguf', 'safetensors', 'bin', 'onnx', 'pt', etc.
    likely_content: str  # 'text-llm', 'vision', 'embedding', etc.


@dataclass
class DuplicateReport:
    """Models appearing in multiple locations on disk."""
    name: str
    locations: list[Path]
    total_size_gb: float
    recommendation: str  # 'keep-primary', 'delete-duplicates', or 'review'


@dataclass
class AuditReport:
    """Complete audit results."""
    drive_c_free_gb: float = 0.0
    drive_d_free_gb: float = 0.0
    drive_d_used_gb: float = 0.0
    drive_d_total_gb: float = 0.0
    protected_path_size_gb: float = 0.0
    out_of_place_models: list[ModelLocation] = field(default_factory=list)
    duplicates: list[DuplicateReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def get_disk_usage() -> dict[str, float]:
    """Get disk usage for C: and D: on Windows using PowerShell."""
    usage = {}
    ps_template = (
        "Get-PSDrive -PSProvider FileSystem | "
        "Where-Object { $_.Name -eq '__LETTER__' } | "
        "Select-Object Name, "
        "@{N='free_gb';E={[math]::Round($_.Free/1GB,2)}}, "
        "@{N='used_gb';E={[math]::Round($_.Used/1GB,2)}}, "
        "@{N='total_gb';E={[math]::Round(($_.Used+$_.Free)/1GB,2)}} | "
        "ConvertTo-Json -Compress"
    )
    try:
        import subprocess
        for drive_letter in ["C", "D"]:
            ps_cmd = ps_template.replace("__LETTER__", drive_letter)
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    usage[drive_letter + ":"] = {
                        "free_gb": float(data.get("free_gb", 0)),
                        "used_gb": float(data.get("used_gb", 0)),
                        "total_gb": float(data.get("total_gb", 0)),
                    }
                except (json.JSONDecodeError, KeyError) as e:
                    usage[drive_letter + ":"] = {"error": f"parse: {e}"}
            else:
                usage[drive_letter + ":"] = {"error": f"powershell failed: {result.stderr[:200]}"}
    except Exception as e:
        usage["error"] = str(e)
    return usage


def detect_file_type(path: Path) -> str:
    """Detect model file format by extension."""
    ext = path.suffix.lower()
    return {
        ".gguf": "gguf",
        ".safetensors": "safetensors",
        ".bin": "bin",
        ".onnx": "onnx",
        ".pt": "pt",
        ".pth": "pth",
        ".pkl": "pkl",
    }.get(ext, "unknown")


def categorize_file(size_gb: float) -> bool:
    """Return True if file size suggests AI model (skip small configs)."""
    return size_gb >= FILE_SIZE_THRESHOLD_GB


def find_models_outside_protected_path() -> list[ModelLocation]:
    r"""Walk 'C:\Users' for large AI model files. Skips Windows system folders."""
    findings = []
    extensions = {".gguf", ".safetensors", ".bin", ".onnx", ".pt", ".pth"}

    # Skip system directories that have large binaries but aren't models
    SKIP_DIRS = {
        "node_modules",
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "site-packages",
        "$RECYCLE.BIN",
        "System Volume Information",
        "Windows",
        "Program Files",
        "Program Files (x86)",
        "ProgramData",
        "Recovery",
        "PerfLogs",
    }

    MAX_DEPTH = 6  # C:\Users\Hesham\<app>\<subdir>\file is depth 4; cap at 6
    FILE_LIMIT = 5000  # safety cap to avoid hangs

    count = 0

    def walk_limited(base: Path, depth: int = 0):
        nonlocal count
        if count > FILE_LIMIT or depth > MAX_DEPTH:
            return
        try:
            for entry in base.iterdir():
                if count > FILE_LIMIT:
                    return
                if entry.is_dir():
                    if entry.name in SKIP_DIRS:
                        continue
                    walk_limited(entry, depth + 1)
                elif entry.is_file():
                    count += 1
                    if entry.suffix.lower() in extensions:
                        size_gb = entry.stat().st_size / 1024**3
                        if categorize_file(size_gb):
                            file_type = detect_file_type(entry)
                            findings.append(
                                ModelLocation(
                                    path=entry,
                                    size_gb=round(size_gb, 2),
                                    file_type=file_type,
                                    likely_content=guess_content(file_type),
                                )
                            )
        except (PermissionError, OSError):
            return

    for base in [Path("C:/Users")]:  # Only C:\Users (not Windows/ProgramData — those are safe)
        if base.exists():
            walk_limited(base)

    return findings


def guess_content(file_type: str) -> str:
    """Guess model type by extension. Customize per project."""
    return {
        "gguf": "LLM/quantized (could be text or vision)",
        "safetensors": "HuggingFace model (text/vision/multimodal)",
        "bin": "Legacy transformer weights",
        "onnx": "ONNX runtime model",
        "pt": "PyTorch checkpoint",
        "pth": "PyTorch state dict",
    }.get(file_type, "Unknown")


def find_duplicate_models_in_d() -> list[DuplicateReport]:
    r"""Find HF model directories that exist as both legacy (root) and hub/ sub-dir.

    Only counts REAL duplicates — i.e., a model in both:
    - huggingface/models--{org}--{name}/ (legacy root)
    - huggingface/hub/models--{org}--{name}/ (newer hub)
    Excludes sub-directories (blobs, refs, snapshots, .locks) which are normal HF cache structure.
    """
    base_name_locations: dict[str, list[Path]] = defaultdict(list)
    base_name_size: dict[str, int] = defaultdict(int)

    if not PROTECTED_PATH.exists():
        return []

    # Only check top-level subdirs (huggingface, hub, etc.), not nested ones
    # and skip .locks, blobs, refs, snapshots sub-dirs which are normal HF cache parts
    SKIP_NAMES = {".locks", "blobs", "refs", "snapshots", "modules", "xet", "datasets"}

    def scan_dir(parent: Path, prefix: str = ""):
        if not parent.exists() or not parent.is_dir():
            return
        for entry in parent.iterdir():
            if not entry.is_dir():
                continue
            if entry.name in SKIP_NAMES:
                continue
            if entry.name.startswith("models--"):
                full_name = entry.name[len("models--"):]
                # Compute directory size (one level deep — blobs/references/etc.)
                dir_size = 0
                try:
                    for f in entry.rglob("*"):
                        if f.is_file():
                            dir_size += f.stat().st_size
                except (PermissionError, OSError):
                    pass
                base_name_locations[full_name].append(entry)
                base_name_size[full_name] += dir_size

    # Scan both legacy (root) and hub/ patterns
    for subdir in [PROTECTED_PATH / "huggingface", PROTECTED_PATH / "huggingface" / "hub"]:
        scan_dir(subdir)

    duplicates = []
    for name, locs in base_name_locations.items():
        if len(locs) > 1:
            total_size = base_name_size[name] / 1024**3
            duplicates.append(
                DuplicateReport(
                    name=name,
                    locations=locs,
                    total_size_gb=round(total_size, 2),
                    recommendation="review",
                )
            )
    return duplicates


def run_audit(quick: bool = False) -> AuditReport:
    """Main audit function."""
    report = AuditReport()

    # Step 1: Disk usage
    usage = get_disk_usage()
    if "C:" in usage:
        c = usage["C:"]
        report.drive_c_free_gb = c.get("free_gb", 0)
    if "D:" in usage:
        d = usage["D:"]
        report.drive_d_free_gb = d.get("free_gb", 0)
        report.drive_d_used_gb = d.get("used_gb", 0)
        report.drive_d_total_gb = d.get("total_gb", 0)

    # Step 2: Protected path size
    total_protected = sum(
        f.stat().st_size for f in PROTECTED_PATH.rglob("*") if f.is_file()
    )
    report.protected_path_size_gb = round(total_protected / 1024**3, 2)

    # Step 3: C: drive protection (Quهائd's hard rule)
    if report.drive_c_free_gb < 10:
        report.warnings.append(
            f"⚠️  C: drive free space CRITICAL: {report.drive_c_free_gb:.1f} GB (<10GB)"
        )
    elif report.drive_c_free_gb < 20:
        report.warnings.append(
            f"⚠️  C: drive free space LOW: {report.drive_c_free_gb:.1f} GB (<20GB)"
        )

    # Skip detailed checks if --quick
    if quick:
        return report

    # Step 4: Find models outside protected path
    report.out_of_place_models = find_models_outside_protected_path()
    if report.out_of_place_models:
        report.recommendations.append(
            f"Move {len(report.out_of_place_models)} model file(s) to D:\\Intelligence Models\\"
        )

    # Step 5: Find duplicates within D
    report.duplicates = find_duplicate_models_in_d()
    if report.duplicates:
        report.recommendations.append(
            f"Review {len(report.duplicates)} potential duplicate model group(s)"
        )

    # Step 6: Final recommendations
    if report.drive_d_free_gb < 20:
        report.recommendations.append(
            "D: drive free space LOW. Consider removing unused models."
        )

    return report


def format_report_text(report: AuditReport) -> str:
    """Human-readable summary."""
    lines = []
    lines.append("=" * 60)
    lines.append("STORAGE AUDIT REPORT — Alpha Wolf Agent")
    lines.append(f"Run date: {Path(__file__).stat().st_mtime}")
    lines.append("=" * 60)
    lines.append("")
    lines.append("📊 DISK USAGE")
    lines.append(f"  C: drive free:    {report.drive_c_free_gb:>8.1f} GB  {'⚠️' if report.drive_c_free_gb < 20 else '✓'}")
    lines.append(f"  D: drive free:    {report.drive_d_free_gb:>8.1f} GB")
    lines.append(f"  D: drive used:    {report.drive_d_used_gb:>8.1f} GB / {report.drive_d_total_gb:.1f} GB")
    lines.append(f"  D:\\Intelligence Models\\ size: {report.protected_path_size_gb:>8.1f} GB")
    lines.append("")

    if report.warnings:
        lines.append("⚠️  WARNINGS")
        for w in report.warnings:
            lines.append(f"  {w}")
        lines.append("")

    if report.out_of_place_models:
        lines.append(f"🚨 OUT-OF-PLACE MODELS: {len(report.out_of_place_models)} found")
        for m in report.out_of_place_models[:5]:
            lines.append(f"  - {m.path} ({m.size_gb} GB, {m.file_type}, {m.likely_content})")
        if len(report.out_of_place_models) > 5:
            lines.append(f"  ... and {len(report.out_of_place_models) - 5} more")
        lines.append("")

    if report.duplicates:
        lines.append(f"📑 POTENTIAL DUPLICATES: {len(report.duplicates)} groups")
        for d in report.duplicates[:3]:
            lines.append(f"  - {d.name}")
            for loc in d.locations:
                lines.append(f"    • {loc}")
        if len(report.duplicates) > 3:
            lines.append(f"  ... and {len(report.duplicates) - 3} more")
        lines.append("")

    if report.recommendations:
        lines.append("💡 RECOMMENDATIONS")
        for r in report.recommendations:
            lines.append(f"  → {r}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Alpha Wolf Agent storage audit")
    parser.add_argument("--quick", action="store_true", help="Disk usage only")
    parser.add_argument("--csv", action="store_true", help="CSV output")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    report = run_audit(quick=args.quick)

    if args.json:
        print(json.dumps(asdict(report), indent=2, default=str))
    elif args.csv:
        # Simple CSV: drive,free_gb,used_gb,total_gb,protected_size_gb,out_of_place_models_count,duplicates_count,warnings_count
        print("drive,free_gb,used_gb,total_gb,protected_size_gb,out_of_place,duplicates,warnings")
        print(f"C,{report.drive_c_free_gb},,,,")
        print(f"D,{report.drive_d_free_gb},{report.drive_d_used_gb},{report.drive_d_total_gb},{report.protected_path_size_gb},{len(report.out_of_place_models)},{len(report.duplicates)},{len(report.warnings)}")
    else:
        print(format_report_text(report))

    # Exit code: 1 if violations, 0 if clean
    has_violations = (
        report.out_of_place_models
        or report.duplicates
        or any("CRITICAL" in w for w in report.warnings)
    )
    sys.exit(1 if has_violations else 0)


if __name__ == "__main__":
    main()

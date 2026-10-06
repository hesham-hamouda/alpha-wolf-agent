#!/usr/bin/env python3
r"""
Alpha Wolf Agent — Skill Forge | مصنع المهارات
===============================================
Fetches external skills (skills.sh / GitHub / any trusted https URL) and
ADAPTS them to the Wolf's system, philosophy, and identity.

يجلب المهارات الخارجية ويكيفها مع نظام الذئب وفلسفته وهويته.

Two source kinds:
1. Direct Python (.py with run()) → safety gate → install as-is.
2. Agent-Skills packs (SKILL.md + scripts, e.g. skills.sh / anthropics spec)
   → saved under backend/skills/<name>_pack/ + a generated Wolf wrapper
   <name>.py whose run(task) returns the playbook (Wolf header + instructions
   + file map) so the MODEL executes it with its own tools. Markdown is DATA,
   never executed; bundled scripts run only if the model explicitly runs them.

Trusted hosts for packs: skills.sh, github.com, raw.githubusercontent.com.
Direct .py: any https URL (safety gate still applies).

Iron Laws: #15 verify (self-test), #22 autonomous, #33 bilingual (#47),
#41 conflict (provenance always reported), #7 anti-contamination (packs are
quarantined data until adapted).
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

BOT_AGENT = "AlphaWolfAgent/0.1 (skill-forge)"
PACK_HOSTS = {"skills.sh", "www.skills.sh", "github.com",
              "raw.githubusercontent.com", "codeload.github.com",
              "objects.githubusercontent.com"}
MAX_DOWNLOAD_BYTES = 2_000_000
MAX_PACK_FILES = 25
MAX_TEXT_FILE_BYTES = 200_000


@dataclass
class SkillPack:
    """Fetched external skill before adaptation."""
    name: str
    kind: str  # 'py' | 'skill_md'
    source_url: str
    files: Dict[str, str] = None  # relpath -> text content
    title: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("files"):
            d["files"] = {k: (v[:500] + "..." if len(v) > 500 else v)
                          for k, v in d["files"].items()}
            d["file_count"] = len(self.files)
        return d


# ============================================================================
# Download helpers
# ============================================================================

def _http_bytes(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": BOT_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(MAX_DOWNLOAD_BYTES + 1)


def _is_trusted_pack_url(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return False
    return host.lower() in PACK_HOSTS


def _github_tree(owner: str, repo: str) -> List[Dict[str, Any]]:
    """List repo files via GitHub API (main, fallback master)."""
    for branch in ("main", "master"):
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BOT_AGENT,
                                                        "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data.get("tree"), list):
                return data["tree"]
        except Exception:
            continue
    raise RuntimeError(f"Cannot list GitHub tree for {owner}/{repo} (API blocked or repo missing)")


def _raw_github(owner: str, repo: str, branch: str, path: str) -> str:
    for br in (branch, "main", "master"):
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{br}/{path}"
        try:
            return _http_bytes(url).decode("utf-8", errors="replace")
        except Exception:
            continue
    raise RuntimeError(f"Cannot download {path} from {owner}/{repo}")


# ============================================================================
# Fetchers
# ============================================================================

def fetch_skill_pack(url: str, name: str = "") -> SkillPack:
    """Fetch a skill from a URL. Supports:
    - https://www.skills.sh/<owner>/<repo>/<skill> (resolves via GitHub)
    - https://github.com/<owner>/<repo>[/tree/<br>/<path>] (skill dir or .py)
    - direct https .py / SKILL.md URLs
    - file:// URLs (tests / local trusted files)
    """
    url = (url or "").strip()
    if url.startswith("file://"):
        # FIX 2026-09-26: urlparse gives '/C:/...' on Windows — url2pathname
        # converts correctly (\C:\... would be an invalid path).
        import urllib.request as _urlreq
        p = Path(_urlreq.url2pathname(urllib.parse.urlparse(url).path))
        if not p.is_file():
            raise RuntimeError(f"Local file not found: {p}")
        text = p.read_text(encoding="utf-8", errors="ignore")
        nm = name or p.stem
        if p.suffix == ".py":
            return SkillPack(name=nm, kind="py", source_url=url, files={p.name: text})
        return SkillPack(name=nm, kind="skill_md", source_url=url,
                         files={"SKILL.md": text}, description=text[:200])

    if not url.startswith("https://"):
        raise RuntimeError("URL must be https (or file:// for local)")
    parts = urllib.parse.urlparse(url)
    host, path = (parts.hostname or "").lower(), parts.path.strip("/")

    # skills.sh/<owner>/<repo>/<skill>[...]  (also /site/<host>/... vendor pages)
    m = re.match(r"([^/]+)/([^/]+)/([^/]+)", path)
    if host in ("skills.sh", "www.skills.sh") and m and not path.startswith("site/"):
        owner, repo, skill = m.group(1), m.group(2), m.group(3)
        return _fetch_github_skill(owner, repo, skill, name, branch="main",
                                   source_url=url)
    if host == "github.com":
        segs = path.split("/")
        if len(segs) >= 2:
            owner, repo = segs[0], segs[1]
            if len(segs) >= 5 and segs[2] in ("tree", "blob") and segs[3] in ("main", "master", "main "):
                sub = "/".join(segs[4:])
                if sub.endswith(".py"):
                    text = _raw_github(owner, repo, segs[3].strip(), sub)
                    return SkillPack(name=name or Path(sub).stem, kind="py",
                                     source_url=url, files={Path(sub).name: text})
                return _fetch_github_skill(owner, repo, "", name, branch=segs[3].strip(),
                                           source_url=url, subdir=sub)
            # repo root: find SKILL.md dirs or single skill
            return _fetch_github_skill(owner, repo, "", name, branch="main", source_url=url)

    # Direct file URL (.py or SKILL.md / markdown)
    data = _http_bytes(url)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("File too large")
    text = data.decode("utf-8", errors="replace")
    nm = name or Path(parts.path).stem or "remote_skill"
    if url.endswith(".py") or ("def run" in text and "SKILL.md" not in text[:500]):
        return SkillPack(name=nm, kind="py", source_url=url, files={nm + ".py": text})
    return SkillPack(name=nm, kind="skill_md", source_url=url,
                     files={"SKILL.md": text}, description=text[:200])


def _fetch_github_skill(owner: str, repo: str, skill: str, name: str,
                        branch: str = "main", source_url: str = "",
                        subdir: str = "") -> SkillPack:
    """Fetch an Agent-Skills pack from a GitHub repo (skills.sh backend)."""
    tree = _github_tree(owner, repo)
    blobs = [e["path"] for e in tree if e.get("type") == "blob"]
    sk_files = [p for p in blobs if p.upper().endswith("SKILL.MD")]
    if subdir:
        cands = [p for p in sk_files if p.startswith(subdir.rstrip("/") + "/")]
    elif skill:
        cands = [p for p in sk_files
                 if Path(p).parent.name.lower() == skill.lower()
                 or p.lower().endswith(f"/{skill.lower()}/skill.md")]
        if not cands:  # single-skill repo: any SKILL.md
            cands = sk_files[:1]
    else:
        cands = sk_files[:1]
    if not cands:
        # Maybe a lone .py skill file?
        pys = [p for p in blobs if p.endswith(".py") and (not skill or skill.lower() in p.lower())]
        if pys and (subdir or not skill):
            target = next((p for p in pys if subdir and p.startswith(subdir)), pys[0])
            text = _raw_github(owner, repo, branch, target)
            nm = name or Path(target).stem
            return SkillPack(name=nm, kind="py", source_url=source_url or f"github:{owner}/{repo}",
                             files={Path(target).name: text})
        raise RuntimeError(f"No SKILL.md found in {owner}/{repo}" + (f" for '{skill}'" if skill else ""))
    sk_path = cands[0]
    base = str(Path(sk_path).parent)
    files: Dict[str, str] = {}
    try:
        files["SKILL.md"] = _raw_github(owner, repo, branch, sk_path)
    except Exception as e:
        raise RuntimeError(f"SKILL.md download failed: {e}")
    prefix = "" if base in (".", "") else base + "/"
    for p in blobs:
        if len(files) >= MAX_PACK_FILES:
            break
        if not p.startswith(prefix) or p == sk_path:
            continue
        rel = p[len(prefix):]
        if "/" in rel or not rel.lower().endswith((".md", ".py", ".sh", ".js", ".ts", ".txt", ".yaml", ".yml", ".json")):
            continue
        try:
            content = _raw_github(owner, repo, branch, p)
            if len(content) <= MAX_TEXT_FILE_BYTES:
                files[rel] = content
        except Exception:
            continue
    nm = name or (Path(sk_path).parent.name if base not in (".", "") else repo)
    nm = re.sub(r"[^A-Za-z0-9_]+", "_", nm).strip("_") or "remote_skill"
    title = ""
    mt = re.search(r"^#\s+(.+)$", files.get("SKILL.md", ""), re.MULTILINE)
    if mt:
        title = mt.group(1).strip()[:120]
    return SkillPack(name=nm, kind="skill_md",
                     source_url=source_url or f"github:{owner}/{repo}",
                     files=files, title=title, description=files.get("SKILL.md", "")[:300])


# ============================================================================
# Adaptation: external pack -> Wolf skill (philosophy + identity injected)
# ============================================================================

WOLF_ADAPTER_HEADER = """\
# 🐺 Wolf Adaptation (الهوية)
This external skill was adopted by Alpha Wolf Agent and adapted to its system:
- Calm persistence over aggression; mistakes are data (Tenacity).
- Verify by RUNNING (Mistake Hunter) — never claim without executed proof.
- Match the user's language (Arabic/English); bilingual output preferred.
- Body (memory/knowledge) stays read-only for projects; projects live OUTSIDE.
Original source: {source_url} (quarantined pack data, never auto-executed).
"""


def adapt_to_wolf_skill(pack: SkillPack, skills_dir: Path) -> Dict[str, Any]:
    """Adapt a fetched pack into an installable Wolf skill.

    - kind 'py' → validated by the safety gate, installed as-is (metadata
      normalized to carry Name/Description for the registry).
    - kind 'skill_md' → pack saved to <name>_pack/ + generated wrapper
      <name>.py whose run(task) returns the Wolf playbook.
    Returns {skill, kind, installed_path, metadata}.
    """
    from backend.agent import tools as _tools  # local import: tools owns the gate

    skills_dir = Path(skills_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", pack.name).strip("_") or "remote_skill"

    if pack.kind == "py":
        source = next(iter(pack.files.values()))
        violations = _tools._skill_safety_check(source)
        if violations:
            return {"success": False, "error": f"Safety gate rejected: {violations[0]}",
                    "violations": violations}
        target = skills_dir / f"{safe_name}.py"
        if target.exists():
            return {"success": False, "error": f"Skill {safe_name} already exists"}
        # Normalize metadata header so the registry parses Name/Description
        if "Name:" not in source[:1500]:
            source = (f'"""\nName: {safe_name}\nDescription: {pack.description[:150] or "Adapted remote skill"}\n'
                      f'Author: skill-forge ({pack.source_url})\nVersion: 1.0.0\n"""\n' + source)
        target.write_text(source, encoding="utf-8")
        return {"success": True, "skill": safe_name, "kind": "py",
                "installed_path": str(target)}

    # skill_md → quarantined pack + Wolf wrapper. The playbook lives in
    # PLAYBOOK.md next to the wrapper (read at runtime) — no giant string
    # literal, no escaping hell (FIX 2026-09-26: JSON-in-triple-quote broke
    # because Python decodes escapes before json.loads sees them).
    import json as _json  # noqa: F401 (kept for future pack indexes)

    pack_dir = skills_dir / f"{safe_name}_pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    for rel, content in (pack.files or {}).items():
        dest = pack_dir / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        except OSError:
            continue
    skill_md = (pack.files or {}).get("SKILL.md", "")[:6000]
    file_map = "\n".join(f"- {k} ({len(v)} chars)" for k, v in (pack.files or {}).items())
    header = WOLF_ADAPTER_HEADER.format(source_url=pack.source_url)
    playbook = (header + skill_md + "\n---\nPack files (execute bundled scripts ONLY "
                "via run_shell when the task needs them):\n" + file_map)
    try:
        (pack_dir / "PLAYBOOK.md").write_text(playbook, encoding="utf-8")
    except OSError as e:
        return {"success": False, "error": f"Cannot write playbook: {e}"}
    desc = (pack.title or pack.description[:150] or f"Adapted skill {safe_name}").replace("\n", " ")
    desc = desc.replace("{", "").replace("}", "")  # f-string safety for wrapper gen
    wrapper = f'''"""
Name: {safe_name}
Description: {desc}
Description_AR: مهارة مكيفة من مصدر خارجي للذئب ألفا
Author: Alpha Wolf skill-forge
Version: 1.0.0
Parameters: {{"task": "string"}}
"""
from pathlib import Path as _Path

WOLF_PACK_DIR = {str(pack_dir)!r}
WOLF_SOURCE_URL = {pack.source_url!r}


def _playbook():
    """Read the adapted playbook (quarantined pack data, never executed)."""
    try:
        return (_Path(WOLF_PACK_DIR) / "PLAYBOOK.md").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "(playbook missing)"


def run(task="", **kwargs):
    """Return the adapted playbook for the model to execute with its tools.

    يرجع دليل التشغيل المكيف لينفذه النموذج بأدواته.
    The Wolf READS this and performs the steps via write_file/run_shell/etc.
    """
    extra = ""
    if kwargs:
        extra = "\\nTask arguments: " + str(kwargs)[:500]
    user_task = task or str(kwargs.get("goal", "")) or "(no task given)"
    return (
        "ADAPTED SKILL PLAYBOOK — follow these steps using your tools "
        "(write_file/run_shell/execute_python), verifying each by RUNNING:\\n\\n"
        "USER TASK: " + user_task[:1000] + extra + "\\n\\n" + _playbook()
    )
'''
    target = skills_dir / f"{safe_name}.py"
    if target.exists():
        return {"success": False, "error": f"Skill {safe_name} already exists"}
    target.write_text(wrapper, encoding="utf-8")

    # Validate the generated wrapper actually imports + runs
    import importlib.util as _ilu
    import sys as _sys
    try:
        spec = _ilu.spec_from_file_location(f"skill_{safe_name}", target)
        mod = _ilu.module_from_spec(spec)
        _sys.modules[f"skill_{safe_name}"] = mod
        spec.loader.exec_module(mod)
        probe = mod.run(task="self-test probe")
        assert isinstance(probe, str) and "ADAPTED SKILL PLAYBOOK" in probe
    except Exception as e:
        try:
            target.unlink()
        except OSError:
            pass
        return {"success": False, "error": f"Wrapper validation failed: {type(e).__name__}: {e}"}
    return {"success": True, "skill": safe_name, "kind": "skill_md",
            "installed_path": str(target), "pack_dir": str(pack_dir),
            "pack_files": sorted((pack.files or {}).keys())}


def self_test() -> bool:
    """Verify forge pieces that need no network (Iron Law #15)."""
    print("Running skill-forge self-tests...")
    ok = True
    # Name sanitization
    nm = re.sub(r"[^A-Za-z0-9_]+", "_", "my-cool.skill!").strip("_")
    assert nm == "my_cool_skill", nm
    print("  ✓ name sanitize")
    # Wrapper validation path is exercised in adapt(); check safety gate import
    try:
        from backend.agent import tools as _t
        assert hasattr(_t, "_skill_safety_check")
        print("  ✓ safety gate reachable")
    except Exception as e:
        print(f"  ✗ gate import: {e}")
        ok = False
    print("SELF-TEST:", "PASSED" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if self_test() else 1)

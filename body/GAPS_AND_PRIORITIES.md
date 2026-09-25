# 🚨 GAPS_AND_PRIORITIES.md — Alpha Wolf Agent

> **Iron Law #20 (Self-Awareness + Gap Priority)** | **Iron Law #33 (Lessons → Code)** | Last update: 2026-09-25

This file tracks all critical gaps, weaknesses, and priorities for Alpha Wolf Agent. It is the **canonical tracker** that the team consults to know what's missing.

---

## 🔴 P0 — CRITICAL (Block Production)

### G1. llama.cpp server not deployed
**Description:** The training is happening in another chat session. llama.cpp inference server is not yet running on port 8080.
**Impact:** Alpha Wolf cannot serve any requests. Chat UI shows errors.
**Effort:** 2-4 hours (build + GGUF export + llama-server launch)
**Owner:** Quхائд (decision) + Expert Team (build)
**Iron Laws:** #15 (verify), #21 (no premature claims)

**Action:**
1. Wait for training to complete (Phase 11+ in other session)
2. Export final GGUF: `model.save_pretrained_gguf("V_Final", quantization_method="q4_k_m")`
3. Launch: `llama-server -m V_Final-Q4_K_M.gguf --ctx-size 500000 --port 8080`
4. Verify: `curl http://localhost:8080/v1/models`

---

### G6. Body Ingestion Pipeline + Format Translation SFT ✅ (Phase 11+ v3.1)
**Description:** Build format_detector + ingestion_pipeline + auto_learn modules in body. Implement Mix E training approach. Quхائd asked (2026-09-25): "اريد ان يكون النموذج ووالوكيل قادر على فهم الداتا سيت الخام بشكل مباشر... هل هذا ممكن" — Answer: YES, via Format Translation SFT + Body ingestion pipeline.
**Impact:** Alpha Wolf becomes self-curating data agent. Zero retraining for new datasets.
**Status:** ✅ **COMPLETE** (Phase 11+ v3.1)
**Files:**
- `body/intake/format_detector.py` (8 categories, blacklist, quality metrics)
- `body/intake/ingestion_pipeline.py` (full pipeline: detect → quality → embed → index)
- `body/intake/__init__.py` (module exports)
- SQLite tables: `datasets`, `quality_metrics` (Iron Law #21 soft delete)
- Verified: detect+ingest+search round-trip works (distance=0.37 for "Python programming" query)

**Mix E Training Plan:** 7-8 diverse-format datasets (UltraChat + glaive + CodeFeedback + Open-Platypus + OASST + OpenHermes + no_robots + Custom). Replaces Mix D per Quхائd vision.

**Verified Tests:**
- Conversational dataset → task_type=conversational ✓
- Instruction dataset → task_type=instruction ✓
- Blacklist name → quarantined ✓
- Ingestion → 3 rows indexed in ChromaDB ✓
- Semantic search → relevant results (distance 0.37) ✓

---

### G2. Chainlit dependencies not installed
**Description:** pyproject.toml references `chainlit>=2.12.0` but pip install hasn't run.
**Impact:** Frontend UI cannot start.
**Effort:** 5 min (single `uv add` command)
**Owner:** Expert Team

**Action:**
```bash
cd "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
uv add chainlit==2.12.0
# or: pip install chainlit==2.12.0
```

---

### G3. FastAPI dependencies not installed
**Description:** pyproject.toml references `fastapi>=0.141.0`, `uvicorn[standard]`, `httpx`, `pydantic` — none installed.
**Impact:** Backend cannot start.
**Effort:** 5 min

**Action:**
```bash
uv add fastapi uvicorn httpx pydantic pydantic-settings
```

---

### G4. Ollama embedding model not deployed
**Description:** Body uses ChromaDB but embeddings need to be generated. Ollama (`nomic-embed-text`) is on the host but `OLLAMA_EMBED_MODEL` not configured.
**Impact:** All vector search returns empty results until embeddings generated.
**Effort:** 2 min (verify + config)

**Action:**
```bash
# Verify Ollama running
ollama list | grep nomic-embed-text

# If not installed
ollama pull nomic-embed-text

# Set env var
$env:OLLAMA_EMBED_MODEL = "nomic-embed-text"
```

---

### G5. Backend ↔ llama.cpp integration untested
**Description:** FastAPI `/v1/chat/completions` proxies to llama.cpp but never tested.
**Impact:** Cannot verify full inference pipeline works.
**Effort:** 1 hour (live test + iterate)

**Action:**
```bash
# Terminal 1
llama-server -m V_Final.gguf --port 8080

# Terminal 2
uvicorn backend.main:app --port 8001 --reload

# Terminal 3 (test)
curl -X POST http://127.0.0.1:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"alpha-wolf","messages":[{"role":"user","content":"What is your name?"}]}'
```

---

## 🟡 P1 — HIGH (Defer Until P0 Done)

### G7. No authentication on backend
**Description:** FastAPI has no auth layer. Anyone on localhost can read/write body.
**Impact:** If exposed to network, security breach.
**Effort:** 2-4 hours (add JWT + rate limiting)
**Iron Laws:** #21 (security)

**Action:** Add Bearer token auth + CORS restriction to localhost only.

---

### G8. No encryption at rest
**Description:** Body files (ChromaDB, SQLite, NetworkX pickle) are plaintext.
**Impact:** Sensitive knowledge bases vulnerable to disk theft.
**Effort:** 4-8 hours (encrypt ChromaDB + SQLite + pickle)
**Iron Laws:** #21

**Action:** Use SQLCipher for SQLite. Encrypt ChromaDB collection files. Use `cryptography.fernet` for pickle encryption.

---

### G9. No automated tests
**Description:** pyproject.toml configures pytest but no test files exist.
**Impact:** Regressions not caught. Iron Law #15 verification is manual.
**Effort:** 1-2 days (write tests for all wrapper methods)

**Action:**
```bash
mkdir tests
# tests/test_alpha_wolf_body.py
def test_track_goal():
    from body.alpha_wolf_body import AlphaWolfBody
    body = AlphaWolfBody()
    gid = body.track_goal("Test goal", priority=5)
    assert gid is not None
    assert body.update_goal_status(gid, "done")
    body.close()
```

---

### G10. No CI/CD pipeline
**Description:** No GitHub Actions or pre-commit hooks (Phase 5 mentioned, not implemented).
**Impact:** Code quality not enforced automatically.
**Effort:** 4-8 hours (GitHub Actions + pre-commit config)

**Action:**
1. Create `.github/workflows/test.yml`
2. Create `.pre-commit-config.yaml` (ruff + mypy + pytest)
3. `pre-commit install`

---

## 🟢 P2 — MEDIUM (Nice-to-Have)

### G11. No multi-user support
**Description:** Body is single-agent. No multi-tenant isolation.
**Impact:** Only one Alpha Wolf can use this body at a time.
**Effort:** 1-2 weeks (major refactor)
**Decision:** Defer — Quхائд wants single agent (per Phase 7+ plan).

---

### G12. No HuggingFace fetcher implemented
**Description:** `intake/` directory exists but no script to download from HF Hub.
**Impact:** Alpha Wolf cannot self-curate from external sources.
**Effort:** 1 day (Python script with HF Hub API + quarantine logic)

**Action:**
Create `body/intake/hf_fetcher.py`:
```python
from huggingface_hub import snapshot_download

def fetch_and_learn(repo_id: str, target_kb: str, quality_filter: Callable = None):
    """Download from HF, embed, add to target KB. Quarantine if blacklisted."""
    # Iron Law #7: blacklist wolf_*, ollama LLMs, GGUF
    # Iron Law #17: only embeddings + vision allowed
    pass
```

---

### G13. No observation loop / periodic reflection
**Description:** Alpha Wolf should periodically reflect on recent episodes (sleep mode).
**Impact:** Memories accumulate without deeper processing.
**Effort:** 1 day (cron + reflection script)
**Iron Laws:** #27 (continuous)

**Action:**
Create `body/cron/nightly_reflect.py`:
```python
# Every night, find high-importance episodes without reflections
# Generate reflection: "What did I learn from this episode?"
# Auto-store via body.reflect()
```

---

### G14. No KG visualization tool
**Description:** NetworkX graph has 10 node types + 11 edge types but no visual inspector.
**Impact:** Hard to see "what's in the body" intuitively.
**Effort:** 1 day (vis.js + iframe in Chainlit)

**Action:**
Add `/v1/graph/visualize` endpoint that returns JSON for vis.js. Render in Chainlit tab.

---

### G15. No backup retention policy
**Description:** Backups accumulate forever in `body/backups/`.
**Impact:** Disk fills up eventually.
**Effort:** 1 hour (cron + retention logic)

**Action:**
Keep last 30 daily backups + last 12 weekly + last 6 monthly.

---

### G16. No metrics / observability
**Description:** No Prometheus, OpenTelemetry, or similar.
**Impact:** Hard to debug production issues.
**Effort:** 1-2 days

---

### G17. Wolf Classification Protocol (WCP) ✅ (Phase 11+ v3.2)
**Description:** Per Quхائд directive 2026-09-25: Alpha Wolf must classify datasets into 4 classes (harmful / project-specific / useful / raw) before storing in body. Anti-pollution. Wolf philosophy.
**Impact:** Without WCP, body may be polluted with project-specific or harmful content.
**Status:** ✅ **COMPLETE** (Phase 11+ v3.2)
**Files:**
- `body/intake/wolf_classifier.py` (~700 LoC) — Hybrid classifier (Rules + Heuristic, NO Ollama LLM per Iron Law #17)
- `body/intake/ingestion_pipeline.py` updated — 4-class routing
- `D:\Trained intelligence models\wolf-vault\` — Raw / Distilled / Harmful / Review_Queue directories
- `E:\Projects...\body\specific_projects\` — Project-specific storage (Iron Law #42)
- SQLite tables: `dataset_classifications`, `distilled_datasets`, `harmful_log`
- `body/alpha_wolf_body.py` Distiller class — regex-based redaction (no Ollama LLM)

**Verified Tests:**
- ✅ HARMFUL detection (API keys) → soft quarantine in `D:\.../harmful/`
- ✅ PROJECT-SPECIFIC detection (config files, endpoints) → workspace storage
- ✅ USEFUL detection (general knowledge) → distill → body
- ✅ RAW detection (ambiguous) → review queue

**Wolf Philosophy Applied:**
- Analyzes everything like a wolf
- Refuses harmful content (Iron Law #7)
- Digests useful patterns (distillation)
- Stores raw for future reference (vault)
- Doesn't pollute body with project-specific (Iron Law #42)

---

## 📊 Priority Matrix

| Priority | Count | Effort | Iron Laws |
|----------|-------|--------|-----------|
| 🔴 P0 Critical | 5 (G1-G5) | 1-2 days | #15, #21 |
| ✅ P0 Completed | 1 (G6 Ingestion Pipeline) | — | #7, #21, #36 |
| 🟡 P1 High | 4 (G7-G10) | 1-2 weeks | #21 |
| 🟢 P2 Medium | 6 (G11-G16) | 1-2 weeks | #27 |
| **Total** | **17** | **3-5 weeks** | — |

---

## 🎯 Recommended Order (next 2 weeks)

1. **Day 1-2:** G1 (llama.cpp deploy) + G4 (Ollama) — required for any test
2. **Day 3:** G2 (Chainlit install) + G3 (FastAPI install) — quick wins
3. **Day 4:** G5 (backend ↔ llama.cpp test) — verify pipeline
4. **Day 5-7:** G9 (write tests) — quality foundation
5. **Day 8-10:** G6 already implemented! Now in Phase 11+ v3.1
6. **Day 11-14:** G7 (auth) + G8 (encryption) — security baseline

After P0 + critical P1 done:
- Quхائد can use Alpha Wolf end-to-end
- Body has self-curation capability via format_detector + ingestion_pipeline
- New datasets auto-ingest without retraining (per Mix E plan)
- Team can iterate on training + body in parallel

---

## 📝 Iron Laws Applied

- **#13** (Self-Critical Check) — gaps discovered honestly
- **#15** (Verify Before Claim) — every gap verified before labeling
- **#20** (Self-Awareness + Gap Priority) — this file exists because of #20
- **#21** (NO Deletion) — gaps documented, NOT ignored
- **#22** (Autonomous Execution) — gaps tracked autonomously
- **#25** (Info Sharing + Suggestions) — this file = info sharing mechanism

---

## 🔗 Related Files

- **[SCHEMA.md](SCHEMA.md)** — What we have
- **[README.md](README.md)** — How to use what we have
- **[DATA_MINDMAP.html](../DATA_MINDMAP.html)** — Visual architecture
- **[PROJECT_PLAN.md](../PROJECT_PLAN.md)** — Master timeline
- **[PROJECT_LOG.md](../PROJECT_LOG.md)** — Change log

---

**Maintained by:** Quхائд هشام + The Expert Team
**Last review:** 2026-09-25 — Phase 11+ v3.0
**Next review:** After P0 critical gaps resolved (~2 days)
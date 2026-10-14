# Alpha Wolf Agent

The language the Wolf and its humans share. Implementation details live in code and ADRs — never here.

## Language

**Body**:
The Wolf itself: its knowledge, capabilities, memory, and code.
_Avoid_: workspace, backend, the system

**Project**:
User work outside the Body, under PROJECTS_ROOT. The only place raw tools may write.
_Avoid_: task folder, outside files, TESTS

**Self-Capability**:
A tool, skill, or memory inside the Body, installed only through safety-gated paths with registry.
_Avoid_: self-tool, internal plugin, extension

**Project-Artifact**:
Any file the Wolf creates for user work. Lives under PROJECTS_ROOT, never inside the Body.
_Avoid_: output file, deliverable, generated file

**Curation**:
Cleaning data (secrets redacted, junk dropped, deduped) before it enters any Wolf database.
_Avoid_: filtering, preprocessing, sanitization

**Self-Development**:
The Wolf growing its own capabilities through plan → gate → install → test → review → repair.
_Avoid_: self-modification, auto-update, self-training

**Prompt-Forging**:
Turning the leader's short/dialectal request into a professional prompt routed to the right capability, without asking him to write better.
_Avoid_: prompt engineering (as a human chore), rewriting the request

# Subject: Freak Fields Handoff – From spooky spreadsheets to a sane dispute engine

From spooky spreadsheets to a sane dispute engine—Freak Fields is alive (and friendly). Below is everything you need to integrate, deploy, and evolve the SeeHealth claims dispute triage system inside `microsoft/dispute-fab`.

---
## 1. Executive Snapshot
- Name: **Freak Fields** (claims dispute triage + AI evidence & classification pipeline)
- Core Stack: Python (FastAPI + data processing scripts) + React/Vite dashboard
- What You Get: Sanitized code (no secrets), reproducible generation of classification outputs, private archives of docs & reference data
- Primary Artifact Generated: `outputs/all_vendors_classification_results.csv` (plus per-vendor CSVs)
- Security Posture: No API keys or PHI committed; `.env` (local only) + removed Key Vault code

---
## 2. Attached Archives (out-of-band transfer)
| Archive | Purpose | Where to Unzip |
|---------|---------|----------------|
| `docs.zip` | Internal deep-dive & architecture narratives | `freaky-fields/docs/` |
| `data.zip` | Reference inputs (crosswalks, sample vendor data) | `freaky-fields/data/reference/` |
| `copilot-instructions.zip` | Internal prompt/automation guidance | Consider `freaky-fields/internal/` or move curated parts to `.github/` |

(Archives intentionally excluded from sanitized branch.)

---
## 3. Directory Layout (Target State in `microsoft/dispute-fab`)
```
/dispute-fab
  /fabric/               <- Existing dispute-fab original content (moved here if at root)
  /freaky-fields/        <- Imported subtree (this repo history preserved)
    backend + scripts + core modules
    frontend/ (Vite dashboard)
    outputs/ (generated, gitignored)
    data/ (after you unzip data.zip: reference + vendors)
    docs/ (after you unzip docs.zip)
    internal/ (optional: copilot instructions)
```

---
## 4. Migration Strategy (Pick One)
| Option | Command Complexity | Preserves History | Pros | Cons |
|--------|--------------------|-------------------|------|------|
| A. Subtree Add (Recommended) | Medium | Yes | Clean separation, auditable lineage | Slightly verbose git flow |
| B. Simple Copy | Low | No | Fast | Loses authorship/history |
| C. Squash Merge | Medium | Partially (single commit) | Compact history | Loses granular traceability |
| D. Filter-Branch/Rewrite | High | Custom | Can redact history selectively | Time-consuming; risk of mistakes |

Recommended: **Option A (git subtree)** for clarity + full provenance.

---
## 5. Git Integration (Subtree Method)
Assumptions: You have push rights to `microsoft/dispute-fab`. Current repo = `seehealth-claims-triage` (branch: `demo-v3-handoff`).

```bash
# Clone target repository
git clone git@github.com:microsoft/dispute-fab.git
cd dispute-fab

# (Optional) Move existing root content into fabric/ if not already
mkdir -p fabric
# If files exist at root that belong to old structure:
git mv existing_root_file.ext fabric/ 2>/dev/null || true
# Commit reorganization if performed
git commit -m "chore: move legacy dispute-fab root content into fabric/" || true

# Add source repository as remote
git remote add freak-fields git@github.com:idanshimon/seehealth-claims-triage.git
git fetch freak-fields demo-v3-handoff

# Add subtree under freaky-fields/
mkdir -p freaky-fields
# Use subtree add (one-time import)
git subtree add --prefix=freaky-fields freak-fields demo-v3-handoff --squash
# NOTE: Remove --squash above if you choose to retain full commit granularity.

# Push
git push origin main
```
If you want full history (no squash):
```bash
git subtree add --prefix=freaky-fields freak-fields demo-v3-handoff
```
Later updates (if continuing development in source repo):
```bash
git fetch freak-fields demo-v3-handoff
git subtree pull --prefix=freaky-fields freak-fields demo-v3-handoff -m "chore: sync freak-fields subtree"
```

---
## 6. Unzipping Private Archives
Run these inside the repository root after subtree import:
```bash
unzip /secure-transfer/docs.zip -d freaky-fields/
unzip /secure-transfer/data.zip -d freaky-fields/
unzip /secure-transfer/copilot-instructions.zip -d freaky-fields/internal/
```
Validate placement:
```bash
ls freaky-fields/docs | head
ls freaky-fields/data/reference | head
```

---
## 7. Deployment & Local Run
1. Create and populate `.env` in repo root (not committed):
```
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_KEY=...
MODEL=gpt-4o
```
2. Python setup:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r freaky-fields/requirements.txt
```
3. Generate classification outputs (prereq for dashboard):
```bash
cd freaky-fields
python process_all_vendors.py  # produces outputs/all_vendors_classification_results.csv
```
4. Start services:
```bash
./scripts/run-services.sh
```
5. Frontend should now serve dashboard (Vite dev server) reading copied CSV from `frontend/public/outputs/`.

Regeneration Cycle:
```bash
python process_all_vendors.py
./scripts/run-services.sh  # will re-copy fresh CSV
```

---
## 8. Operational Notes
- `scripts/cleanup-for-public.sh` is idempotent for sanitizing before external sharing.
- `run-services.sh` aborts if outputs missing—intentional guardrail.
- Financial impact metric computed client-side in the dashboard from current filtered claims dataset (real-time recalculation).

---
## 9. Follow-Up Clarifications (Please Reply)
1. Should we preserve full commit history (no `--squash`) or use squashed subtree import? Default recommendation: preserve.  
2. Is there existing content already under `freaky-fields/` in `dispute-fab` we must merge or replace?  
3. Confirm you have push rights to `microsoft/dispute-fab`.  
4. Preferred destination for Copilot instructions: keep in `internal/`, or curate and move selected guidance into `.github/`?  
5. Any compliance requirements for further redaction beyond current sanitization?

---
## 10. Next Steps
- Confirm answers to clarification list.
- Execute subtree import (without `--squash` if full history desired).
- Unzip archives in place.
- (Optional) Promote selected internal guidance to `.github/` for broader team enablement.

---
## 11. Contact & Handoff Integrity
If anything fails during startup, check: venv active, `pip list` matches required libs (`fastapi`, `pandas`, `openai`, `azure.identity`), and `outputs/all_vendors_classification_results.csv` exists prior to service launch.

Happy dispute triaging—may your fields forever be freak-free.

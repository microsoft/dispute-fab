# SeeHealth Claims Triage AI Platform

**Status:** Active Development  
**Primary Stack:** FastAPI (Python 3.11+), React 19 + Vite (TypeScript), Azure OpenAI

---

## Recent Updates

**Latest Release: 1.1.0 (2025-11-05)**
- **Fix**: Prioritizes explicit `FORMULARY NON-COMPLIANCE` vendor flags before code lookups, correcting Code 201 detection.
- **Impact**: 55 Hvsq Tkrbcgf claims now surface as Code 201 (priority rank 17) instead of Code 204 (rank 20).
- **Tests**: Re-ran vendor regression script (`test_formulary_fix.py`) to confirm reassignment across the dataset.
- **Data Refresh**: Regenerated vendor result artifacts under `outputs/` with the updated classifier.

See [CHANGELOG.md](./CHANGELOG.md) for migration guidance, detailed root cause notes, and previous release history.

---

## Key Operational Metrics

- **Classification Coverage**: Real classifications increased to 84.7% (from 31.2%); Code 104 fallback reduced to 15.3% (from 68.8%).
- **Data Quality**: Valid `CLAIM_ID` detection improved to 70.8% (from 9.5%); 15/15 vendor schemas supported via AI mapping.
- **Human Review Load**: Claims requiring manual review dropped to 59.2% (from 100%) thanks to stronger evidence trails.
- **Current Hotspot**: Code 204 (Invalid NDC) and Code 201 (Formulary Non-Compliance) now represent the top remediation targets post-fix.
- **Further Details**: See `AI_COLUMN_MAPPING_RESULTS.md`, `CLASSIFICATION_RESULTS.md`, and `FORMULARY_ANALYSIS_RESULTS.md` for full analytics pending final consolidation.

---

## Classification Snapshot (2025-10-29)

- **Top Dispute Codes**: `104` (RX ID Invalid) 73%, `301` (Excluded 340B Pharmacy) 11%, `103` (Units/Day Exceeds) 5%, `306` (Pharmacy Excluded) 5%, `401` (Horizontal Duplicate) 2%.
- **Priority Mix**: 17% critical (ranks 1-8), 3% high (ranks 9-12), 80% medium (ranks 13-16); lower tiers unused in this batch.
- **Vendor Coverage**: 15 vendors processed (100-claim slices) via crosswalk, direct code, and rule-based pipelines; all completed successfully.
- **Confidence Profile**: Average 80%; 26% claims >90% confidence and none below 70%. Multi-code detection triggered on 95% of claims (2.1 codes per claim).
- **Review Evolution**: Initial regression flagged 100% of claims for manual review; updated evidence logic plus formulary fix reduced this to 59.2% in the November release.

---

## Formulary Insights

- **Schema Expansion**: Added `FORMULARY_TYPE_CDE` to the standard mapping schema with GPT-guided prompts so vendors surface formulary tiers consistently.
- **Rule Enhancements**: `_apply_business_rules()` now handles blanks, numeric/tier codes, and text indicators ("Non-Formulary", "Not Covered").
- **Explicit Vendor Flags**: Hvsq Tkrbcgf provides direct `FORMULARY NON-COMPLIANCE` (2.5%) and `FORMULARY NON-COMPLIANCE POLICY` (5.7%) flags; release 1.1.0 prioritizes these before tier lookups.
- **Testing Coverage**: Synthetic suite covers tier codes, text labels, and missing data; `test_formulary_fix.py` validates real vendor records (55 claims corrected to Code 201).
- **Next Steps**: Expand regression coverage across all vendors and align cleanup tasks per `cleanup-plan.md` before final doc/file consolidation.

---

## Business Rules & Data Schema

### Key Classification Signals

The classifier leverages these critical data columns to detect disputes:

| Column | Purpose | Examples | Detection Rule |
|--------|---------|----------|----------------|
| `CLAIM_340B_IND` | 340B program eligibility | Binary flag | Triggers Code 301 (Excluded 340B Pharmacy) - Priority Rank 1 |
| `FORMULARY_TYPE_CDE` | Formulary tier/coverage | 0-5 (tiers), blank, "Non-Formulary" | Code 201 (Formulary Non-Compliance) when 0/blank/invalid - Rank 17 |
| `EXCLUSION_TYPE_CDE` | Exclusion reason | U (Unlicensed), F (Fraud), blank | Pharmacy/provider exclusion codes 305-306 - Ranks 5-6 |
| `SERVICE_TYPE_CDE` | Dispensing channel | R (Retail), M (Mail), I (Institutional), X (Other) | Validates service type against contract terms |
| `CLAIM_COUNT_NBR` | Transaction volume | Positive/negative values | Duplicate detection (negative = reversal) - Code 401, Rank 9 |
| `PRICE_AMT` | Financial magnitude | $0 - $14,747 (avg $92) | Aberrant pricing triggers review |

### Vendor Crosswalk Mappings

The `data/crosswalks/` directory contains vendor-to-SeeHealth code translations. Example patterns:

- **Ouy Ikxsp Vendor**: `XPX` (Pharmacy/Product Combo Excluded) → Code 301, `DUP` (Duplicate) → Code 401, `AQU` (Units/Day Exceeds) → Code 103
- **Generic Crosswalk**: Maps common vendor error codes (e.g., "RX_INVALID", "NDC_NOT_FOUND") to SeeHealth's 23-code taxonomy

See `config/vendor_configs.py` for per-vendor column mappings and `core/crosswalk_mapper.py` for translation logic.

---

## 1. Overview
The SeeHealth Claims Triage AI Platform streamlines pharmacy benefit dispute review by classifying claims, assigning priority, generating structured AI summaries, and surfacing human-review flags. It combines data processing, rule-based + AI-enhanced classification, and an interactive dashboard.

Key capabilities:
- Dispute classification and multi-code attribution
- Priority ranking & confidence scoring
- AI-generated claim summaries (Azure OpenAI)
- Side-panel UI for claim details + AI insights
- Evidence generation for audit transparency

See `docs/ARCHITECTURE.md` and `WORKFLOW_EXPLANATION.md` for deep technical flow. All business rules are documented in `docs/BUSINESS_RULES.md`.

---
## 2. Repository Structure (High-Level)
```
core/                Classification & evidence modules
frontend/            React + Vite dashboard (Chakra UI)
infra/               Bicep infra templates (Azure resources)
outputs/             Generated analysis & classification artifacts (ignored where appropriate)
scripts/             Helper scripts (env sync, service orchestration)
.devcontainer/       Codespaces / container setup automation
api_server.py        FastAPI service (claim summary endpoint)
process_all_vendors.py  Batch classification driver
```

---
## 3. Prerequisites
- Python 3.11+
- Node.js 20+
- Azure OpenAI Service with deployments (GPT-4o, GPT-5-mini)

---
## 4. Environment Variables
Two categories: secrets (store securely) and non-secrets (can be variables).

### Required Backend (place in `.env` or Codespaces Secrets/Variables)
| Name | Type | Description |
|------|------|-------------|
| `AZURE_OPENAI_API_KEY` | Secret | Azure OpenAI access key |
| `AZURE_OPENAI_ENDPOINT` | Non-secret | Base endpoint URL |
| `AZURE_OPENAI_API_VERSION` | Non-secret | API version (e.g. `2024-08-01-preview`) |
| `AZURE_OPENAI_DEPLOYMENT_GPT4O` | Non-secret | Deployment name for GPT-4o model |
| `AZURE_OPENAI_DEPLOYMENT_GPT5` | Optional | Deployment name for GPT-5 variant |
| `AZURE_ENVIRONMENT` | Non-secret | Environment label (e.g. `dev`) |
| `LOG_LEVEL` | Non-secret | Logging level (default `INFO`) |

Optional (future expansion): blob storage, app insights.

### Frontend (`frontend/.env`) – generated automatically
| Name | Source | Purpose |
|------|--------|---------|
| `VITE_API_BASE` | manual/default | Backend base URL (default `http://localhost:8000`) |
| `VITE_AI_SUMMARY_ENDPOINT` | manual/default | Summary route (`/api/claim-summary`) |
| `VITE_AZURE_OPENAI_ENDPOINT` | derived | For potential future model metadata display |
| `VITE_AZURE_OPENAI_MODEL` | derived | Current model deployment label |
| `VITE_AZURE_OPENAI_API_VERSION` | derived | API version for UI reference |
| `VITE_APP_ENV` | derived | Environment indicator (badge/display) |

`scripts/sync-env.sh` writes a safe `frontend/.env` with no secrets.

See `.env.example` and `frontend/.env.example` for templates.

---
## 5. Installation & Setup

### Quick Start (Local Development)
```bash
# 1. Clone repository
git clone <private_repo_url> seehealth-claims-triage
cd seehealth-claims-triage

# 2. Create backend .env (DO NOT commit secrets)
cp .env.example .env
# Edit .env to include real values

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install frontend dependencies
npm install --prefix frontend

# 5. Start services (auto-generates frontend/.env)
bash scripts/run-services.sh

# 6. (Alternative manual start)
set -a; source .env; set +a
uvicorn api_server:app --reload --port 8000 &
cd frontend && npm run dev
```

---
## 6. Running & Stopping Services
Unified script (auto-copies classification results to frontend):
```bash
# Start (copies outputs/all_vendors_classification_results.csv to frontend/public/outputs/)
bash scripts/run-services.sh

# Stop
bash scripts/run-services.sh stop
```
Logs & PIDs stored in `scripts/logs/`.

Manual stop (if needed):
```bash
kill $(cat scripts/logs/backend.pid) $(cat scripts/logs/frontend.pid)
```

---
## 7. Testing
Tests live in the project root (`test_*.py`).
```bash
pytest -q
```
Recommended to add targeted unit tests for classification logic in `core/` (future expansion).

---
## 8. Architecture & Workflow
- Classification pipeline: See `WORKFLOW_EXPLANATION.md`
- Core modules: `core/column_mapper.py`, `core/dispute_classifier.py`, `core/enhanced_dispute_classifier.py`, `core/evidence_generator.py`
- API layer: `api_server.py` (FastAPI – claim summary endpoint)
- Frontend UI: `frontend/src/` (Dashboard + side panels)
- Infrastructure (Azure): `infra/main.bicep` – (deployment template; refine before production)

---
## 9. Azure Integration
**Development:** Uses Azure OpenAI Service directly via API key stored in `.env`

**Production Considerations:**
- Store API keys in Azure App Service Configuration (application settings)
- Enable managed identity for Azure OpenAI access (recommended over API keys)
- Add Application Insights for observability
- Store classification artifacts in Azure Blob Storage
- Enable RBAC, network restrictions, and audit logging

---
## 10. Security & Secrets Handling

### 10.1 Configuration Architecture
The project uses a **secure by default** configuration approach:

**`azure_config.py`** (Safe to commit ✅)
- Contains NO hardcoded secrets
- All sensitive values loaded from environment variables
- Provides default placeholders for non-secret values
- Can be version-controlled safely

**`.env`** (NEVER commit ❌)
- Contains actual API keys and sensitive credentials
- Loaded automatically by `python-dotenv`
- Listed in `.gitignore` to prevent accidental commits
- Use `.env.example` as template

### 10.2 Environment Variables by Sensitivity Level

**🔴 CRITICAL SECRETS** (Store securely, never commit)
```bash
AZURE_OPENAI_API_KEY              # Azure OpenAI access key
```

**🟡 SEMI-SENSITIVE** (Can use GitHub Variables)
```bash
AZURE_SUBSCRIPTION_ID             # Your Azure subscription
AZURE_RESOURCE_GROUP              # Resource group name
```

**🟢 NON-SENSITIVE** (Safe for documentation)
```bash
AZURE_OPENAI_ENDPOINT             # Public endpoint URL
AZURE_OPENAI_API_VERSION          # API version string
AZURE_OPENAI_DEPLOYMENT_GPT4O     # Deployment names
AZURE_LOCATION                    # Azure region
AZURE_ENVIRONMENT                 # Environment label (dev/prod)
```

### 10.3 Setup Instructions

**For Local Development:**
```bash
# 1. Copy template
cp .env.example .env

# 2. Edit .env with your actual values
nano .env

# 3. NEVER commit .env
git status  # Should show .env as ignored
```

**For Production (Azure):**
1. Use Azure App Service Configuration or environment variables for secrets
2. Enable managed identity for Azure OpenAI access (if using Azure AD authentication)
3. Never commit `.env` files or hardcode API keys

### 10.4 Security Best Practices
✅ **DO:**
- Use `.env` for local development secrets
- Store production secrets in Azure Key Vault
- Rotate API keys every 90 days
- Use different keys for dev/staging/prod
- Enable Azure AD authentication when possible
- Review `.gitignore` before committing

❌ **DON'T:**
- Commit `.env` files to Git
- Hardcode secrets in Python files
- Share API keys in chat/email
- Use production keys in development
- Store secrets in CI/CD logs
- Push secrets to public repositories

### 10.5 Checking for Leaked Secrets
Before pushing code:
```bash
# Check what would be committed
git status
git diff --staged

# Verify .env is ignored
git check-ignore .env  # Should output: .env

# Search for potential secrets in tracked files
git grep -i "api.key\|secret\|password" -- '*.py' '*.ts' '*.json'
```

If you accidentally commit a secret:
1. **Immediately rotate the compromised credential**
2. Remove from Git history: `git filter-branch` or BFG Repo-Cleaner
3. Force push after cleaning (coordinate with team)
4. Review GitHub secret scanning alerts

### 10.6 How azure_config.py Works
```python
# Safe default - no secret exposed
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://your-openai-resource.openai.azure.com/")

# Resolution order for API key:
# 1. Check AZURE_OPENAI_API_KEY env var
# 2. Check OPENAI_API_KEY env var  
# 3. Fail with clear error message
```

This design allows:
- ✅ Local development with `.env`
- ✅ CI/CD with environment variables
- ✅ Production with Azure App Service configuration
- ✅ Safe version control of config code

---
## 11. Common Issues & Troubleshooting
| Issue | Cause | Fix |
|-------|-------|-----|
| 401 / OpenAI auth fail | Missing or invalid API key | Check `.env` file and verify `AZURE_OPENAI_API_KEY` is correct |
| Empty AI summary | Model deployment mismatch | Verify `AZURE_OPENAI_DEPLOYMENT_GPT4O` matches your Azure OpenAI deployment name |
| Frontend cannot reach backend | Incorrect `VITE_API_BASE` | Edit `frontend/.env` or regenerate with `bash scripts/sync-env.sh` |
| Stale env values | Manual changes not synced | Re-run `bash scripts/sync-env.sh` to sync backend → frontend env vars |
| Missing reference files | Files not in data/reference/ | Ensure `Pharma_Crosswalk.xlsx` and `Exclusion Reason Codes.xlsx` exist in `data/reference/` |

---
## 12. Roadmap (Selected)
- Category override workflow (user intervention & audit trail)
- Structured metrics dashboard (classification accuracy trend)
- Bulk claim summary batching endpoint
- Model fallback logic (GPT-5 → GPT-4o)
- Key Vault managed identity integration

---
## 13. Contributing
Internal project – direct commits by authorized maintainers only.
1. Branch naming: `feat/<feature-name>` / `fix/<short-description>`
2. Prefer small PRs with clear description and test evidence.
3. Keep architecture docs updated when major flow changes occur.

---
## 14. License / Usage
Proprietary / Internal Use Only. Not for external distribution.

---
## 15. Additional Documentation

**Key Documentation Files:**
- **[HANDOFF.md](./docs/HANDOFF.md)** - Developer handoff guide with operational runbooks
- **[BUSINESS_RULES.md](./docs/BUSINESS_RULES.md)** - Classification rule definitions (single source of truth)
- **[REPRODUCTION_GUIDE.md](./docs/REPRODUCTION_GUIDE.md)** - Step-by-step guide to reproduce results with production data
- **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - System architecture and decision history
- **[CHANGELOG.md](./docs/CHANGELOG.md)** - Version history and migration guides
- **[.github/copilot-instructions.md](./.github/copilot-instructions.md)** - Development guidelines for code generation

---

---
## 16. Ingesting New Input Data & Generating Classification Results

This section explains how to bring a new raw claims extract into the pipeline, classify it, and surface results in the dashboard.

### 16.1 Required Input Format
Place your source file (CSV) in `data/` (example: `data/Masked_Invoice_Claims_Extract.csv`). Minimum recommended columns (header names):

| Column | Purpose |
|--------|---------|
| `CLAIM_ID` | Unique identifier for the claim |
| `VENDOR` | Vendor / PBM / partner identifier |
| `PRIMARY_DISPUTE_CODE` | Leading dispute code used for prioritization |
| `DESCRIPTION` | Text description / narrative of claim event |
| `RAW_CODES` or `ALL_APPLICABLE_CODES` | Comma-separated list of all codes discovered |
| `AMOUNT` (optional) | Financial magnitude for potential weighting |
| `ORIGINAL_CATEGORY` (optional) | Source category before re-classification |

The classifier will enrich / derive additional fields like `CATEGORY`, `PRIORITY_RANK`, `CONFIDENCE`, `REQUIRES_REVIEW`, `EVIDENCE`.

If your raw column names differ, adjust mappings in:
- `core/column_mapper.py`
- `config/vendor_configs.py` (vendor-specific overrides)

### 16.2 Running the Classification Pipeline
For a multi-vendor batch:
```bash
python process_all_vendors.py \
   --input data/Masked_Invoice_Claims_Extract.csv \
   --scrub data/Masked_Scrub_File_15.xlsx \
   --outdir outputs/ \
   --overwrite
```
Flags:
- `--input` Path to historical claims CSV
- `--scrub` Path to multi-vendor scrub file (Excel with vendor sheets)
- `--outdir` Destination directory for result artifacts (`outputs/`)
- `--overwrite` Replace existing result files if present

Result artifacts created:
- `outputs/all_vendors_classification_results.csv` (aggregated standardized output)
- Per-vendor CSVs like `outputs/<Vendor>_results.csv`
- Column mappings in `data/column_mappings/<Vendor>_mapping.json` (auto-generated on first run)

### 16.3 Classification Output Schema
Expected columns exposed to the dashboard (superset):
| Column | Description |
|--------|-------------|
| `CLAIM_ID` | Original claim identifier |
| `VENDOR` | Normalized vendor name |
| `PRIMARY_DISPUTE_CODE` | Primary code chosen for user focus |
| `CATEGORY` | Derived dispute category label |
| `PRIORITY_RANK` | Integer rank bucket (lower = higher urgency) |
| `CONFIDENCE` | 0–1 score of classification certainty |
| `REQUIRES_REVIEW` | Boolean flag if human validation is advised |
| `ALL_APPLICABLE_CODES` | Comma-separated list of candidate codes |
| `EVIDENCE` | Structured rationale or extracted signals |

### 16.4 Refreshing the Dashboard with New Data
1. Run the classification script to produce updated CSV(s).
2. Ensure the primary aggregated file exists: `outputs/all_vendors_classification_results.csv`
3. Restart services (script automatically copies results to `frontend/public/outputs/`):
    ```bash
    bash scripts/run-services.sh stop
    bash scripts/run-services.sh
    ```
4. Open `http://localhost:5173` and verify new rows & priority distribution.

**Note:** `run-services.sh` automatically copies classification results to the frontend before starting services.

### 16.5 Adding / Adjusting Mapping Logic
- **Column mapping rules:** `core/column_mapper.py` (AI-powered semantic mapping)
- **Reference files:** `data/reference/Pharma_Crosswalk.xlsx`, `data/reference/Exclusion Reason Codes.xlsx`
- **Vendor mappings:** `data/column_mappings/` (auto-generated JSON)
- **Vendor-specific configs:** `config/vendor_configs.py`

After changes, re-run classification to propagate updated logic.

### 16.6 Troubleshooting Data Ingestion
| Symptom | Cause | Resolution |
|---------|-------|------------|
| Missing columns error | Header mismatch | Update `column_mapper.py` or rename source headers |
| Empty `CATEGORY` values | No matching rule | Add/adjust mapping rule or fallback category |
| Low confidence globally | Signal dilution / column noise | Review evidence generation and prune weak inputs |
| Duplicate vendor rows | Vendor normalization inconsistency | Ensure trimming & consistent case in vendor preprocessing |

### 16.7 Best Practices
- Keep raw extract immutable; derive all enrichments in outputs.
- Version output artifacts (e.g., timestamped copies) before overwriting for audit.
- Consider adding a lightweight provenance JSON recording script run parameters.

---

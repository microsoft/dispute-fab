#!/usr/bin/env bash
# Sync safe backend environment variables into a frontend/.env file for Vite.
# Excludes any secret values (API keys, connection strings).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_ENV="$ROOT_DIR/.env"
FRONTEND_ENV="$ROOT_DIR/frontend/.env"

if [[ ! -f "$BACKEND_ENV" ]]; then
  echo "[sync-env] No .env found at $BACKEND_ENV" >&2
  exit 1
fi

# Load backend env (safe; we won't export secrets to frontend)
set -a
source "$BACKEND_ENV"
set +a

# Preserve existing values if file exists (avoid nuking manually added non-secret vars)
EXISTING_API_BASE=""
EXISTING_SUMMARY_ENDPOINT=""
if [[ -f "$FRONTEND_ENV" ]]; then
  EXISTING_API_BASE="$(grep '^VITE_API_BASE=' "$FRONTEND_ENV" | cut -d'=' -f2-)" || true
  EXISTING_SUMMARY_ENDPOINT="$(grep '^VITE_AI_SUMMARY_ENDPOINT=' "$FRONTEND_ENV" | cut -d'=' -f2-)" || true
fi

# Default fallbacks
API_BASE_DEFAULT="http://localhost:8000"
SUMMARY_ENDPOINT_DEFAULT="/api/claim-summary"

VITE_API_BASE_VALUE="${VITE_API_BASE:-${EXISTING_API_BASE:-$API_BASE_DEFAULT}}"
VITE_AI_SUMMARY_ENDPOINT_VALUE="${VITE_AI_SUMMARY_ENDPOINT:-${EXISTING_SUMMARY_ENDPOINT:-$SUMMARY_ENDPOINT_DEFAULT}}"

# Write non-secret, UI-needed values including API base & summary endpoint
cat > "$FRONTEND_ENV" <<EOF
# Auto-generated frontend environment file
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
VITE_API_BASE=${VITE_API_BASE_VALUE//\"/}
VITE_AI_SUMMARY_ENDPOINT=${VITE_AI_SUMMARY_ENDPOINT_VALUE//\"/}
VITE_AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT:-}
VITE_AZURE_OPENAI_MODEL=${AZURE_OPENAI_DEPLOYMENT_GPT4O:-gpt-4o}
VITE_AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION:-2024-08-01-preview}
VITE_APP_ENV=${AZURE_ENVIRONMENT:-dev}
EOF

echo "[sync-env] Wrote safe frontend env to frontend/.env (no secrets)."

#!/usr/bin/env bash
# update-env.sh - Refresh .env with current Azure OpenAI resource details without redeploying
#
# Usage:
#   ./infra/update-env.sh [options]
#
# Common examples:
#   ./infra/update-env.sh --resource-group rg-openai-dev --name openai-dev-nt6mukageprxm
#   ./infra/update-env.sh --dry-run --verbose
#   ./infra/update-env.sh              # auto-detect RG + account
#
# Options:
#   --resource-group, -g <name>   Resource group (if omitted: auto-detect)
#   --name, -n <openai-name>      Azure OpenAI account name (if omitted: auto-detect)
#   --env-file, -f <path>         Target .env file (default: project root ./.env)
#   --dry-run                     Show resolved values; do not write file
#   --verbose                     Extra log output
#   --help, -h                    Show this help and exit
#
# Auto-detect logic:
#   - If RG/account not provided, tries existing .env vars first.
#   - Falls back to querying subscription for first CognitiveServices OpenAI account.
#
# Requirements: Azure CLI (az), jq
# Exit codes: 0 success, 1 error (missing tools / no resources), 2 help displayed
set -euo pipefail

VERBOSE=0
DRY_RUN=0
ENV_FILE="$(dirname "$0")/../.env"
RESOURCE_GROUP=""
OPENAI_NAME=""

log() { printf "[update-env] %s\n" "$*"; }
info() { [[ $VERBOSE -eq 1 ]] && log "INFO: $*" || true; }
err() { log "ERROR: $*" >&2; }

usage() {
  cat <<'EOF'
update-env.sh - Refresh .env with current Azure OpenAI resource details

Usage:
  ./infra/update-env.sh [options]

Options:
  -g, --resource-group <name>   Resource group containing the OpenAI account
  -n, --name <openai-name>      Azure OpenAI account name to target
  -f, --env-file <path>         Path to write .env (default: ../.env)
      --dry-run                 Show values only; do not write file
      --verbose                 Extra logging
  -h, --help                    Show this help and exit

Auto-detect:
  If RG or name omitted, attempts existing .env values; else queries subscription
  for first CognitiveServices OpenAI account.

Examples:
  ./infra/update-env.sh -g rg-openai-dev -n openai-dev-abcd123
  ./infra/update-env.sh --dry-run --verbose
  ./infra/update-env.sh  # fully auto-detect

Exit codes:
  0 success
  1 error (missing tools / not found)
  2 help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group|-g) RESOURCE_GROUP="$2"; shift 2 ;;
    --name|-n) OPENAI_NAME="$2"; shift 2 ;;
    --env-file|-f) ENV_FILE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --verbose) VERBOSE=1; shift ;;
    --help|-h) usage; exit 2 ;;
    *) err "Unknown arg: $1"; echo "Use --help for usage."; exit 1 ;;
  esac
done

if ! command -v az >/dev/null; then err "Azure CLI not installed"; exit 1; fi
if ! command -v jq >/dev/null; then err "jq is required"; exit 1; fi

# Try to source existing .env for defaults (ignore errors)
if [[ -f "$ENV_FILE" ]]; then
  set +u
  source <(grep -v '^#' "$ENV_FILE" | sed 's/^/export /') || true
  set -u
  [[ -z "$RESOURCE_GROUP" && -n "${AZURE_RESOURCE_GROUP:-}" ]] && RESOURCE_GROUP="$AZURE_RESOURCE_GROUP"
  [[ -z "$OPENAI_NAME" && -n "${AZURE_OPENAI_RESOURCE_NAME:-}" ]] && OPENAI_NAME="$AZURE_OPENAI_RESOURCE_NAME"
fi

# Auto-detect resource group if missing (choose first group containing a CognitiveServices account)
if [[ -z "$RESOURCE_GROUP" ]]; then
  info "Auto-detecting resource group..."
  RG_CANDIDATES=$(az resource list --resource-type Microsoft.CognitiveServices/accounts --query '[].resourceGroup' -o tsv | sort -u)
  if [[ -z "$RG_CANDIDATES" ]]; then err "No CognitiveServices accounts found in subscription"; exit 1; fi
  RESOURCE_GROUP=$(echo "$RG_CANDIDATES" | head -n1)
  log "Using detected resource group: $RESOURCE_GROUP"
fi

# Auto-detect account name if missing (pick first OpenAI kind in RG)
if [[ -z "$OPENAI_NAME" ]]; then
  info "Auto-detecting OpenAI account name in $RESOURCE_GROUP..."
  OPENAI_NAME=$(az resource list --resource-group "$RESOURCE_GROUP" --resource-type Microsoft.CognitiveServices/accounts --query "[?kind=='OpenAI'].name | [0]" -o tsv)
  if [[ -z "$OPENAI_NAME" ]]; then err "No OpenAI account found in $RESOURCE_GROUP"; exit 1; fi
  log "Using detected account: $OPENAI_NAME"
fi

ENDPOINT=$(az cognitiveservices account show --name "$OPENAI_NAME" --resource-group "$RESOURCE_GROUP" --query 'properties.endpoint' -o tsv)
if [[ -z "$ENDPOINT" ]]; then err "Failed to get endpoint"; exit 1; fi

KEY1=$(az cognitiveservices account keys list --name "$OPENAI_NAME" --resource-group "$RESOURCE_GROUP" --query key1 -o tsv)
KEY2=$(az cognitiveservices account keys list --name "$OPENAI_NAME" --resource-group "$RESOURCE_GROUP" --query key2 -o tsv)
[[ -z "$KEY1" ]] && { err "Failed to get key1"; exit 1; }

# List deployments (names)
DEPLOYMENTS=$(az resource list --resource-group "$RESOURCE_GROUP" --resource-type Microsoft.CognitiveServices/accounts/deployments --query "[?contains(id, '$OPENAI_NAME')].name" -o tsv || true)
GPT4O_DEP=""; GPT5_DEP=""
for d in $DEPLOYMENTS; do
  [[ "$d" == "gpt-4o" ]] && GPT4O_DEP="$d"
  [[ "$d" == "gpt-5-mini" ]] && GPT5_DEP="$d"
  # Fallback variations
  [[ -z "$GPT5_DEP" && "$d" == "gpt4o-mini" ]] && GPT5_DEP="$d"
  [[ -z "$GPT5_DEP" && "$d" == "gpt-4o-mini" ]] && GPT5_DEP="$d"
  [[ -z "$GPT4O_DEP" && "$d" == "gpt-4o-1" ]] && GPT4O_DEP="$d"
done

log "Endpoint: $ENDPOINT"
log "Key1 (masked): ${KEY1:0:6}********${KEY1: -4}"
log "Key2 (masked): ${KEY2:0:6}********${KEY2: -4}" || true
log "Deployments detected: ${DEPLOYMENTS:-none}" 

[[ -z "$GPT4O_DEP" ]] && GPT4O_DEP="gpt-4o" # Default assumption
[[ -z "$GPT5_DEP" ]] && GPT5_DEP="gpt-5-mini" # Default assumption

if [[ $DRY_RUN -eq 1 ]]; then
  log "Dry run enabled; not writing $ENV_FILE"
  cat <<EOF
Would write:
AZURE_OPENAI_ENDPOINT=$ENDPOINT
AZURE_OPENAI_RESOURCE_NAME=$OPENAI_NAME
AZURE_OPENAI_API_KEY=$KEY1
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT_GPT5=$GPT5_DEP
AZURE_OPENAI_DEPLOYMENT_GPT4O=$GPT4O_DEP
AZURE_RESOURCE_GROUP=$RESOURCE_GROUP
EOF
  exit 0
fi

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
cat > "$ENV_FILE" <<EOF
# Updated by update-env.sh $(date -u +%Y-%m-%dT%H:%M:%SZ)
AZURE_OPENAI_ENDPOINT=$ENDPOINT
AZURE_OPENAI_RESOURCE_NAME=$OPENAI_NAME
AZURE_OPENAI_API_KEY=$KEY1
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT_GPT5=$GPT5_DEP
AZURE_OPENAI_DEPLOYMENT_GPT4O=$GPT4O_DEP
AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID
AZURE_RESOURCE_GROUP=$RESOURCE_GROUP
AZURE_LOCATION=${AZURE_LOCATION:-eastus}
AZURE_ENVIRONMENT=${AZURE_ENVIRONMENT:-dev}
# Secondary key retained for manual rotation reference
AZURE_OPENAI_SECONDARY_API_KEY=$KEY2
EOF

log "Wrote environment file: $ENV_FILE"
exit 0

#!/usr/bin/env bash
# ============================================================================
# Azure Infrastructure Cleanup Script (Canonical Env Version)
# ============================================================================
# Safely removes the resource group and optionally only the OpenAI account.
# Supports canonical variable names from .env.example.
#
# Usage:
#   ./infra/cleanup.sh [--env dev] [--resource-group rg-openai-dev] [--only-openai] [--yes]
#   ./infra/cleanup.sh --env prod --yes --force   # non-interactive prod deletion
# Flags:
#   --env                Environment name (fallback to AZURE_ENVIRONMENT or dev)
#   --resource-group     Explicit resource group (fallback to AZURE_RESOURCE_GROUP)
#   --only-openai        Delete just the Azure OpenAI account (keep RG)
#   --yes                Skip confirmation prompts (except prod safety unless --force)
#   --force              Skip production typed confirmation
#   --dry-run            Show what would be deleted
#
# Reads .env if present for AZURE_* canonical variables.
# ============================================================================
set -euo pipefail

ENVIRONMENT="dev"
RESOURCE_GROUP=""
ONLY_OPENAI=0
YES=0
FORCE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env) ENVIRONMENT="$2"; shift 2 ;;
        --resource-group) RESOURCE_GROUP="$2"; shift 2 ;;
        --only-openai) ONLY_OPENAI=1; shift ;;
        --yes) YES=1; shift ;;
        --force) FORCE=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# Load .env if available for canonical variables
if [[ -f "$(dirname "$0")/../.env" ]]; then
    # shellcheck disable=SC2046
    source <(grep -v '^#' "$(dirname "$0")/../.env" | sed 's/^/export /') || true
    [[ "$ENVIRONMENT" == "dev" && -n "${AZURE_ENVIRONMENT:-}" ]] && ENVIRONMENT="$AZURE_ENVIRONMENT"
    [[ -z "$RESOURCE_GROUP" && -n "${AZURE_RESOURCE_GROUP:-}" ]] && RESOURCE_GROUP="$AZURE_RESOURCE_GROUP"
fi

[[ -z "$RESOURCE_GROUP" ]] && RESOURCE_GROUP="rg-openai-${ENVIRONMENT}" # fallback naming pattern

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }

if ! command -v az >/dev/null; then err "Azure CLI not installed"; exit 1; fi
if ! az account show >/dev/null 2>&1; then err "Not logged in (az login)"; exit 1; fi
SUBSCRIPTION=$(az account show --query id -o tsv)
info "Subscription: $SUBSCRIPTION"

TARGET_DESC="Resource Group: $RESOURCE_GROUP (env=$ENVIRONMENT)"
[[ $ONLY_OPENAI -eq 1 ]] && TARGET_DESC="Azure OpenAI account inside RG: $RESOURCE_GROUP"

echo -e "${RED}==================== DELETION PLAN ====================${NC}"
echo -e "${RED}$TARGET_DESC${NC}"
if [[ $ONLY_OPENAI -eq 1 ]]; then
    echo -e "${RED}Will delete: Azure OpenAI account (kind=OpenAI) only${NC}"
else
    echo -e "${RED}Will delete: Entire resource group and contained resources${NC}"
fi
echo -e "${RED}=======================================================${NC}"

# Production safety
if [[ "$ENVIRONMENT" == "prod" && $FORCE -ne 1 ]]; then
    if [[ $YES -ne 1 ]]; then
        read -p "Type DELETE PRODUCTION to continue: " PROD_CONFIRM
        [[ "$PROD_CONFIRM" == "DELETE PRODUCTION" ]] || { warn "Aborted"; exit 0; }
    else
        warn "--yes ignored production typed confirmation. Use --force to override. Aborting."; exit 1
    fi
fi

if [[ $DRY_RUN -eq 1 ]]; then
    info "Dry run: no resources will be deleted."
    exit 0
fi

if [[ $YES -ne 1 ]]; then
    read -p "Confirm deletion (yes/no): " CONFIRM
    [[ "$CONFIRM" == "yes" ]] || { warn "Cancelled"; exit 0; }
fi

if [[ $ONLY_OPENAI -eq 1 ]]; then
    info "Locating Azure OpenAI account in $RESOURCE_GROUP"
    OPENAI_NAME=$(az resource list --resource-group "$RESOURCE_GROUP" --resource-type Microsoft.CognitiveServices/accounts --query "[?kind=='OpenAI'].name | [0]" -o tsv)
    if [[ -z "$OPENAI_NAME" ]]; then err "No OpenAI account found"; exit 1; fi
    info "Deleting OpenAI account: $OPENAI_NAME"
    az resource delete --ids $(az resource show --resource-group "$RESOURCE_GROUP" --resource-type Microsoft.CognitiveServices/accounts --name "$OPENAI_NAME" --query id -o tsv)
    ok "OpenAI account deletion requested"
else
    info "Deleting resource group: $RESOURCE_GROUP"
    az group delete --name "$RESOURCE_GROUP" --yes --no-wait
    ok "Resource group deletion initiated"
fi

echo ""
echo "Follow-up commands:"; echo "  az group show --name $RESOURCE_GROUP"; echo "  az resource list --resource-group $RESOURCE_GROUP"
echo "Done."

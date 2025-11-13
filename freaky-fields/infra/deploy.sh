#!/usr/bin/env bash
# ============================================================================
# Minimal Azure OpenAI Deployment Script
# ============================================================================
# Deploys ONLY an Azure OpenAI account + optional model deployments (controlled
# by deployModels parameter in main.bicep). Writes canonical .env and azure_config.py.
#
# New Feature: Interactive subscription confirmation with optional override.
#
# Usage (two styles supported):
#   Legacy positional: ./deploy.sh dev eastus openai
#   Flag style:         ./deploy.sh --env dev --location eastus --name openai \
#                       [--subscription <id|name>] [--restore] [--yes] [--auto-env]
#
# Flags:
#   --env            Environment name (default: dev)
#   --location       Azure region (default: eastus)
#   --name           Base name for resource naming (default: openai)
#   --subscription   Explicit subscription id or name to use (optional)
#   --yes            Non-interactive; skip confirmations (uses provided / active subscription)
#   --auto-env       Auto-populate .env without prompting
#
# Prerequisites:
#   - Azure CLI installed & logged in (az login)
#   - 'jq' installed
# ============================================================================
set -euo pipefail

# Clean Azure OpenAI deployment script (minimal)
# Usage:
#   ./infra/deploy.sh [--env dev] [--location eastus] [--name openai] [--yes] [--auto-env]
# Flags:
#   --yes        Skip interactive confirmations
#   --auto-env   Auto-populate .env from deployed resource (no prompts)

ENVIRONMENT="dev"
LOCATION="eastus"
BASE_NAME="openai"
YES=0
AUTO_ENV=0
SUBSCRIPTION_OVERRIDE=""
RESTORE=0

POS_COUNT=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env) ENVIRONMENT="$2"; shift 2 ;;
        --location) LOCATION="$2"; shift 2 ;;
        --name) BASE_NAME="$2"; shift 2 ;;
        --subscription) SUBSCRIPTION_OVERRIDE="$2"; shift 2 ;;
        --restore) RESTORE=1; shift ;;
        --yes) YES=1; shift ;;
        --auto-env) AUTO_ENV=1; shift ;;
        --help|-h)
            echo "Usage: ./deploy.sh [--env dev] [--location eastus] [--name openai] [--subscription <id|name>] [--restore] [--yes] [--auto-env]";
            echo "Positional style also supported: ./deploy.sh dev eastus openai";
            exit 0 ;;
        -* ) echo "Unknown flag: $1"; exit 1 ;;
        *) # positional
            case $POS_COUNT in
                0) ENVIRONMENT="$1" ;;
                1) LOCATION="$1" ;;
                2) BASE_NAME="$1" ;;
                *) echo "Unexpected extra positional arg: $1"; exit 1 ;;
            esac
            POS_COUNT=$((POS_COUNT+1))
            shift ;;
    esac
done

RESOURCE_GROUP="rg-${BASE_NAME}-${ENVIRONMENT}"
DEPLOYMENT_NAME="openai-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
BICEP_FILE="$(dirname "$0")/main.bicep"
ENV_FILE="$(dirname "$0")/../.env"
PY_CONFIG="$(dirname "$0")/../azure_config.py"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }
ok() { echo -e "${GREEN}[OK]${NC} $1"; }

if ! command -v az >/dev/null; then err "Azure CLI not found"; exit 1; fi
ok "Azure CLI found"

if ! az account show >/dev/null 2>&1; then err "Not logged in. Run 'az login'"; exit 1; fi

# Capture current subscription context
CURRENT_SUB_NAME=$(az account show --query name -o tsv)
CURRENT_SUB_ID=$(az account show --query id -o tsv)

# Override if flag provided
if [[ -n "$SUBSCRIPTION_OVERRIDE" ]]; then
    info "Setting subscription to: $SUBSCRIPTION_OVERRIDE"
    if ! az account set --subscription "$SUBSCRIPTION_OVERRIDE" 2>/dev/null; then
        err "Failed to set subscription '$SUBSCRIPTION_OVERRIDE'"; exit 1
    fi
    CURRENT_SUB_NAME=$(az account show --query name -o tsv)
    CURRENT_SUB_ID=$(az account show --query id -o tsv)
fi

if [[ $YES -ne 1 && -z "$SUBSCRIPTION_OVERRIDE" ]]; then
    echo "Subscription detected: $CURRENT_SUB_NAME ($CURRENT_SUB_ID)"
    read -p "Use this subscription? [Y/n/change]: " sub_ans
    if [[ "$sub_ans" =~ ^[Nn]$ || "$sub_ans" == "change" ]]; then
        echo "Available subscriptions:";
        az account list --query '[].{name:name,id:id,isDefault:isDefault}' -o table
        read -p "Enter subscription name or id to use: " NEW_SUB
        if [[ -z "$NEW_SUB" ]]; then err "No subscription entered"; exit 1; fi
        if ! az account set --subscription "$NEW_SUB" 2>/dev/null; then
            err "Could not switch to subscription '$NEW_SUB'"; exit 1
        fi
        CURRENT_SUB_NAME=$(az account show --query name -o tsv)
        CURRENT_SUB_ID=$(az account show --query id -o tsv)
        info "Switched to subscription: $CURRENT_SUB_NAME ($CURRENT_SUB_ID)"
    fi
fi

info "Using subscription: $CURRENT_SUB_NAME ($CURRENT_SUB_ID)"

if az group exists --name "$RESOURCE_GROUP" | grep -qi true; then
  warn "Resource group $RESOURCE_GROUP exists"
else
  info "Creating resource group $RESOURCE_GROUP in $LOCATION"
  az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --tags Environment="$ENVIRONMENT" ManagedBy="Bicep" >/dev/null
  ok "Resource group created"
fi

info "Validating Bicep template"
az bicep build --file "$BICEP_FILE" >/dev/null
ok "Bicep build succeeded"

CONFIRM_MSG="Deploy Azure OpenAI to RG=$RESOURCE_GROUP env=$ENVIRONMENT loc=$LOCATION baseName=$BASE_NAME restore=$RESTORE?"
if [[ $YES -ne 1 ]]; then
  read -p "$CONFIRM_MSG [y/N]: " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { err "Aborted"; exit 1; }
fi

info "Starting deployment ($DEPLOYMENT_NAME) with env=$ENVIRONMENT location=$LOCATION name=$BASE_NAME restore=$RESTORE"
PARAMS=(environment="$ENVIRONMENT" location="$LOCATION" openAIAccountBaseName="$BASE_NAME")
if [[ $RESTORE -eq 1 ]]; then
    PARAMS+=(restoreDeletedAccount=true)
else
    PARAMS+=(restoreDeletedAccount=false)
fi
DEPLOY_JSON=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$DEPLOYMENT_NAME" \
    --template-file "$BICEP_FILE" \
    --parameters "${PARAMS[@]}" \
    --query '{outputs:properties.outputs}' -o json 2>&1) || DEPLOY_ERROR=$?

if [[ -n "${DEPLOY_ERROR:-}" ]]; then
    err "Deployment failed"
    # Surface inner error hint if present
    echo "$DEPLOY_JSON" | grep -E 'FlagMustBeSetForRestore|InvalidTemplateDeployment' || true
    [[ $RESTORE -eq 0 ]] && echo -e "\nHint: The account name may be soft-deleted. Re-run with --restore or purge the deleted resource before retrying." && echo -e "To retry with restore: ./deploy.sh --restore" && exit 1
    exit 1
fi
ok "Deployment complete"

OPENAI_NAME=$(echo "$DEPLOY_JSON" | jq -r '.outputs.openAIResourceName.value')
ENDPOINT=$(echo "$DEPLOY_JSON" | jq -r '.outputs.openAIEndpoint.value')
GPT4O_NAME=$(echo "$DEPLOY_JSON" | jq -r '.outputs.gpt4oDeploymentName.value')
GPT5MINI_NAME=$(echo "$DEPLOY_JSON" | jq -r '.outputs.gpt5miniDeploymentName.value')

if [[ -z "$OPENAI_NAME" || -z "$ENDPOINT" ]]; then
  err "Failed to parse deployment outputs"
  exit 1
fi

API_KEY=$(az cognitiveservices account keys list --name "$OPENAI_NAME" --resource-group "$RESOURCE_GROUP" --query key1 -o tsv)
[[ -z "$API_KEY" ]] && { err "Could not retrieve API key"; exit 1; }

SUBSCRIPTION_ID=$CURRENT_SUB_ID
cat > "$ENV_FILE" <<EOF
AZURE_OPENAI_ENDPOINT=$ENDPOINT
AZURE_OPENAI_RESOURCE_NAME=$OPENAI_NAME
AZURE_OPENAI_API_KEY=$API_KEY
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT_GPT5=$GPT5MINI_NAME
AZURE_OPENAI_DEPLOYMENT_GPT4O=$GPT4O_NAME
AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID
AZURE_RESOURCE_GROUP=$RESOURCE_GROUP
AZURE_LOCATION=$LOCATION
AZURE_ENVIRONMENT=$ENVIRONMENT
EOF
ok ".env updated with canonical variable names: $ENV_FILE"

cat > "$PY_CONFIG" <<PYEOF
import os
from dotenv import load_dotenv
load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_RESOURCE_NAME = os.getenv('AZURE_OPENAI_RESOURCE_NAME')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-08-01-preview')
AZURE_OPENAI_DEPLOYMENT_GPT5 = os.getenv('AZURE_OPENAI_DEPLOYMENT_GPT5')
AZURE_OPENAI_DEPLOYMENT_GPT4O = os.getenv('AZURE_OPENAI_DEPLOYMENT_GPT4O')
AZURE_SUBSCRIPTION_ID = os.getenv('AZURE_SUBSCRIPTION_ID')
AZURE_RESOURCE_GROUP = os.getenv('AZURE_RESOURCE_GROUP')
AZURE_LOCATION = os.getenv('AZURE_LOCATION')
AZURE_ENVIRONMENT = os.getenv('AZURE_ENVIRONMENT')
PYEOF
ok "azure_config.py updated to canonical variable names"

echo ""; echo "=========================================="; echo "Deployment Summary:"; echo "Resource Group: $RESOURCE_GROUP"; echo "OpenAI Account: $OPENAI_NAME"; echo "Endpoint: $ENDPOINT"; echo "GPT-4o Deployment: $GPT4O_NAME"; echo "GPT-5-Mini Deployment: $GPT5MINI_NAME"; echo "=========================================="; echo "Done.";
exit 0
# ============================================================================    exit 1    print_error "Azure CLI is not installed. Please install it first."

# Retrieve Outputs

# ============================================================================fi    echo "Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"



print_header "Deployment Outputs"print_success "Azure CLI is installed"    exit 1



OUTPUTS=$(az deployment group show \fi

    --name "$DEPLOYMENT_NAME" \

    --resource-group "$RESOURCE_GROUP_NAME" \# Check if logged inprint_success "Azure CLI is installed"

    --query properties.outputs -o json)

if ! az account show &> /dev/null; then

OPENAI_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.openAIEndpoint.value')

OPENAI_RESOURCE=$(echo "$OUTPUTS" | jq -r '.openAIResourceName.value')    print_error "Not logged in to Azure. Please run: az login"# Check if logged in

GPT5_DEPLOYMENT=$(echo "$OUTPUTS" | jq -r '.gpt5miniDeploymentName.value')

GPT4O_DEPLOYMENT=$(echo "$OUTPUTS" | jq -r '.gpt4oDeploymentName.value')    exit 1if ! az account show &> /dev/null; then



print_info "OpenAI Endpoint: $OPENAI_ENDPOINT"fi    print_error "Not logged in to Azure. Please run: az login"

print_info "Resource Name: $OPENAI_RESOURCE"

print_info "GPT-5-mini Deployment: $GPT5_DEPLOYMENT"print_success "Logged in to Azure"    exit 1

print_info "GPT-4o Deployment: $GPT4O_DEPLOYMENT"

fi

# ============================================================================

# Get API Keys# Display current subscriptionprint_success "Logged in to Azure"

# ============================================================================

SUBSCRIPTION_NAME=$(az account show --query name -o tsv)

print_header "Retrieving API Keys"

SUBSCRIPTION_ID=$(az account show --query id -o tsv)# Display admin email

API_KEYS=$(az cognitiveservices account keys list \

    --name "$OPENAI_RESOURCE" \print_info "Subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"print_success "Admin email: $ADMIN_EMAIL"

    --resource-group "$RESOURCE_GROUP_NAME" \

    -o json)



API_KEY1=$(echo "$API_KEYS" | jq -r '.key1')# ============================================================================# Display current subscription

API_KEY2=$(echo "$API_KEYS" | jq -r '.key2')

# Resource GroupSUBSCRIPTION_NAME=$(az account show --query name -o tsv)

print_success "API keys retrieved"

# ============================================================================SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# ============================================================================

# Configure .env Fileprint_info "Subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"

# ============================================================================

print_header "Creating Resource Group"

print_header "Configuration Setup"

# ============================================================================

echo ""

read -p "Would you like to update the .env file with these credentials? (yes/no): " UPDATE_ENVif az group exists --name "$RESOURCE_GROUP_NAME" | grep -q "true"; then# Resource Group



if [ "$UPDATE_ENV" = "yes" ]; then    print_warning "Resource group '$RESOURCE_GROUP_NAME' already exists"# ============================================================================

    ENV_FILE="../.env"

    else

    if [ -f "$ENV_FILE" ]; then

        print_info "Backing up existing .env to .env.backup"    az group create \print_header "Creating Resource Group"

        cp "$ENV_FILE" "${ENV_FILE}.backup"

    fi        --name "$RESOURCE_GROUP_NAME" \

    

    # Update or create .env file        --location "$LOCATION" \if az group exists --name "$RESOURCE_GROUP_NAME" | grep -q "true"; then

    cat > "$ENV_FILE" << EOF

# ============================================================================        --tags Environment="$ENVIRONMENT" Project="SeeHealth Claims Triage" ManagedBy="Bicep"    print_warning "Resource group '$RESOURCE_GROUP_NAME' already exists"

# Azure OpenAI Configuration

# ============================================================================    print_success "Resource group '$RESOURCE_GROUP_NAME' created in $LOCATION"else

# Auto-generated: $(date)

# Environment: $ENVIRONMENTfi    az group create \

# ============================================================================

        --name "$RESOURCE_GROUP_NAME" \

# Azure OpenAI Endpoint

AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT# ============================================================================        --location "$LOCATION" \



# Azure OpenAI API Key# Deployment Confirmation        --tags Environment="$ENVIRONMENT" Project="SeeHealth Claims Triage" ManagedBy="Bicep"

AZURE_OPENAI_API_KEY=$API_KEY1

# ============================================================================    print_success "Resource group '$RESOURCE_GROUP_NAME' created in $LOCATION"

# Model Deployments

AZURE_OPENAI_DEPLOYMENT_GPT5=$GPT5_DEPLOYMENTfi

AZURE_OPENAI_DEPLOYMENT_GPT4O=$GPT4O_DEPLOYMENT

print_header "Deployment Confirmation"

# API Version

AZURE_OPENAI_API_VERSION=2024-08-01-preview# ============================================================================



# Resource Detailsprint_info "Resources to be deployed:"# Bicep Validation

AZURE_OPENAI_RESOURCE_NAME=$OPENAI_RESOURCE

AZURE_RESOURCE_GROUP=$RESOURCE_GROUP_NAMEecho "  ✅ Azure OpenAI (gpt-4o-mini deployment named 'gpt-5-mini', 120K TPM)"# ============================================================================

ENVIRONMENT=$ENVIRONMENT

echo "  ✅ Azure OpenAI (gpt-4o deployment, 80K TPM)"

# ============================================================================

# Backup API Key (Key 2)echo ""print_header "Validating Bicep Template"

# ============================================================================

# AZURE_OPENAI_API_KEY_BACKUP=$API_KEY2print_info "Environment: $ENVIRONMENT"

EOF

print_info "Location: $LOCATION"print_info "Skipping separate validation due to SSL certificate issues..."

    print_success ".env file created/updated at $ENV_FILE"

    print_info "Resource Group: $RESOURCE_GROUP_NAME"print_info "Validation will occur during deployment"

    # Create azure_config.py

    cat > ../azure_config.py << 'EOF'echo ""

"""

Azure Configuration for SeeHealth AI Claims Triageprint_warning "Estimated cost: ~\$10-50/month depending on usage"# ============================================================================

Loads configuration from .env file

"""echo ""# Deployment Confirmation



import osread -p "Do you want to proceed with deployment? (yes/no): " PROCEED# ============================================================================

from pathlib import Path

from dotenv import load_dotenv



# Load environment variablesif [ "$PROCEED" != "yes" ]; thenprint_header "Deployment Confirmation"

env_path = Path(__file__).parent / '.env'

load_dotenv(dotenv_path=env_path)    print_warning "Deployment cancelled by user"



# Azure OpenAI Configuration    exit 0print_info "Resources to be created:"

AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')

AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')fiecho "  ✅ Azure OpenAI account with gpt-5-mini deployment (120K TPM)"

AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-08-01-preview')

AZURE_OPENAI_DEPLOYMENT_GPT5 = os.getenv('AZURE_OPENAI_DEPLOYMENT_GPT5', 'gpt-5-mini')echo "  ✅ Key Vault with RBAC authorization (for storing API keys)"

AZURE_OPENAI_DEPLOYMENT_GPT4O = os.getenv('AZURE_OPENAI_DEPLOYMENT_GPT4O', 'gpt-4o')

AZURE_OPENAI_RESOURCE_NAME = os.getenv('AZURE_OPENAI_RESOURCE_NAME')# ============================================================================echo ""

AZURE_RESOURCE_GROUP = os.getenv('AZURE_RESOURCE_GROUP')

ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')# Deploymentecho "  Optional resources (disabled by default):"

EOF

# ============================================================================echo "  ❌ Storage Account - enable with: enableStorage=true"

    print_success "Python config file created at ../azure_config.py"

elseecho "  ❌ App Service - enable with: enableAppService=true"

    print_info "Skipping .env update. You can manually configure using these values:"

    echo ""print_header "Deploying Azure OpenAI"echo "  ❌ Log Analytics + App Insights - enable with: enableMonitoring=true"

    echo "AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT"

    echo "AZURE_OPENAI_API_KEY=$API_KEY1"echo ""

    echo "AZURE_OPENAI_DEPLOYMENT_GPT5=$GPT5_DEPLOYMENT"

    echo "AZURE_OPENAI_DEPLOYMENT_GPT4O=$GPT4O_DEPLOYMENT"print_info "Deployment name: $DEPLOYMENT_NAME"print_info "Environment: $ENVIRONMENT"

fi

print_info "This may take 3-5 minutes..."print_info "Location: $LOCATION"

# ============================================================================

# Next Stepsecho ""print_info "Resource Group: $RESOURCE_GROUP_NAME"

# ============================================================================

echo ""

print_header "Deployment Complete! 🎉"

az deployment group create \read -p "Do you want to proceed with deployment? (yes/no): " PROCEED

echo ""

echo -e "${GREEN}Your Azure OpenAI is ready to use!${NC}"    --name "$DEPLOYMENT_NAME" \

echo ""

echo "Quick test:"    --resource-group "$RESOURCE_GROUP_NAME" \if [ "$PROCEED" != "yes" ]; then

echo -e "  ${BLUE}python -c \"from azure_config import *; print(f'Endpoint: {AZURE_OPENAI_ENDPOINT}')\"${NC}"

echo ""    --template-file main.bicep \    print_warning "Deployment cancelled by user"

echo "View in Azure Portal:"

echo -e "  ${BLUE}https://portal.azure.com/#@/resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.CognitiveServices/accounts/$OPENAI_RESOURCE${NC}"    --parameters environment="$ENVIRONMENT" \    exit 0

echo ""

echo -e "${YELLOW}Security Note:${NC}"    --output tablefi

echo "  - Keep your .env file secure (already in .gitignore)"

echo "  - Rotate keys regularly from Azure Portal"

echo "  - Use Managed Identity for production deployments"

echo ""if [ $? -ne 0 ]; then# ============================================================================


    print_error "Deployment failed!"# Deployment

    exit 1# ============================================================================

fi

print_header "Deploying Infrastructure"

print_success "Deployment completed successfully!"

print_info "Deployment name: $DEPLOYMENT_NAME"

# ============================================================================print_info "This may take 5-10 minutes..."

# Retrieve Outputsecho ""

# ============================================================================

az deployment group create \

print_header "Deployment Outputs"    --name "$DEPLOYMENT_NAME" \

    --resource-group "$RESOURCE_GROUP_NAME" \

OUTPUTS=$(az deployment group show \    --template-file main.bicep \

    --name "$DEPLOYMENT_NAME" \    --parameters environment="$ENVIRONMENT" location="$LOCATION" adminEmail="$ADMIN_EMAIL" \

    --resource-group "$RESOURCE_GROUP_NAME" \    --output table

    --query properties.outputs -o json)

print_success "Deployment completed successfully!"

OPENAI_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.openAIEndpoint.value')

OPENAI_RESOURCE=$(echo "$OUTPUTS" | jq -r '.openAIResourceName.value')# ============================================================================

GPT5_DEPLOYMENT=$(echo "$OUTPUTS" | jq -r '.gpt5miniDeploymentName.value')# Retrieve Outputs

GPT4O_DEPLOYMENT=$(echo "$OUTPUTS" | jq -r '.gpt4oDeploymentName.value')# ============================================================================



print_info "OpenAI Endpoint: $OPENAI_ENDPOINT"print_header "Deployment Outputs"

print_info "Resource Name: $OPENAI_RESOURCE"

print_info "GPT-5-mini Deployment: $GPT5_DEPLOYMENT"OUTPUTS=$(az deployment group show \

print_info "GPT-4o Deployment: $GPT4O_DEPLOYMENT"    --name "$DEPLOYMENT_NAME" \

    --resource-group "$RESOURCE_GROUP_NAME" \

# ============================================================================    --query properties.outputs -o json)

# Get API Keys

# ============================================================================echo "$OUTPUTS" | jq -r 'to_entries[] | "\(.key): \(.value.value)"' | while read line; do

    print_info "$line"

print_header "Retrieving API Keys"done



API_KEYS=$(az cognitiveservices account keys list \# ============================================================================

    --name "$OPENAI_RESOURCE" \# Save Configuration

    --resource-group "$RESOURCE_GROUP_NAME" \# ============================================================================

    -o json)

print_header "Saving Configuration"

API_KEY1=$(echo "$API_KEYS" | jq -r '.key1')

API_KEY2=$(echo "$API_KEYS" | jq -r '.key2')# Extract key values

OPENAI_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.openAIEndpoint.value')

print_success "API keys retrieved"OPENAI_RESOURCE=$(echo "$OUTPUTS" | jq -r '.openAIResourceName.value')

STORAGE_ACCOUNT=$(echo "$OUTPUTS" | jq -r '.storageAccountName.value')

# ============================================================================KEY_VAULT_NAME=$(echo "$OUTPUTS" | jq -r '.keyVaultName.value')

# Configure .env FileKEY_VAULT_URI=$(echo "$OUTPUTS" | jq -r '.keyVaultUri.value')

# ============================================================================

# Create .env file for local development

print_header "Configuration Setup"cat > ../.env << EOF

# ============================================================================

echo ""# SeeHealth AI Claims Triage - Azure Configuration

read -p "Would you like to update the .env file with these credentials? (yes/no): " UPDATE_ENV# ============================================================================

# Generated: $(date)

if [ "$UPDATE_ENV" = "yes" ]; then# Environment: $ENVIRONMENT

    ENV_FILE="../.env"# ============================================================================

    

    if [ -f "$ENV_FILE" ]; then# Azure OpenAI

        print_info "Backing up existing .env to .env.backup"AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT

        cp "$ENV_FILE" "${ENV_FILE}.backup"AZURE_OPENAI_RESOURCE_NAME=$OPENAI_RESOURCE

    fiAZURE_OPENAI_API_VERSION=2024-02-15-preview

    AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

    # Update or create .env file

    cat > "$ENV_FILE" << EOF# Azure Storage

# ============================================================================AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT

# Azure OpenAI ConfigurationAZURE_STORAGE_CONNECTION_STRING_SECRET=Storage-ConnectionString

# ============================================================================

# Auto-generated: $(date)# Azure Key Vault

# Environment: $ENVIRONMENTAZURE_KEY_VAULT_NAME=$KEY_VAULT_NAME

# ============================================================================AZURE_KEY_VAULT_URI=$KEY_VAULT_URI



# Azure OpenAI Endpoint# Environment

AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINTENVIRONMENT=$ENVIRONMENT

AZURE_LOCATION=$LOCATION

# Azure OpenAI API KeyAZURE_RESOURCE_GROUP=$RESOURCE_GROUP_NAME

AZURE_OPENAI_API_KEY=$API_KEY1

# For local development, get the OpenAI key with:

# Model Deployments# az keyvault secret show --name OpenAI-ApiKey --vault-name $KEY_VAULT_NAME --query value -o tsv

AZURE_OPENAI_DEPLOYMENT_GPT5=$GPT5_DEPLOYMENTEOF

AZURE_OPENAI_DEPLOYMENT_GPT4O=$GPT4O_DEPLOYMENT

print_success "Configuration saved to ../.env"

# API Version

AZURE_OPENAI_API_VERSION=2024-08-01-preview# Create Python config file

cat > ../azure_config.py << EOF

# Resource Details"""

AZURE_OPENAI_RESOURCE_NAME=$OPENAI_RESOURCEAzure Configuration for SeeHealth AI Claims Triage

AZURE_RESOURCE_GROUP=$RESOURCE_GROUP_NAME

ENVIRONMENT=$ENVIRONMENTAuto-generated configuration from Bicep deployment.

Generated: $(date)

# ============================================================================Environment: $ENVIRONMENT

# Backup API Key (Key 2)"""

# ============================================================================

# AZURE_OPENAI_API_KEY_BACKUP=$API_KEY2import os

EOFfrom pathlib import Path

from dotenv import load_dotenv

    print_success ".env file created/updated at $ENV_FILE"

    # Load environment variables

    # Create azure_config.pyenv_path = Path(__file__).parent / '.env'

    cat > ../azure_config.py << 'EOF'load_dotenv(dotenv_path=env_path)

"""

Azure Configuration for SeeHealth AI Claims Triage# Azure OpenAI Configuration

Loads configuration from .env fileAZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', '$OPENAI_ENDPOINT')

"""AZURE_OPENAI_RESOURCE_NAME = os.getenv('AZURE_OPENAI_RESOURCE_NAME', '$OPENAI_RESOURCE')

AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')

import osAZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')

from pathlib import Path

from dotenv import load_dotenv# Azure Storage Configuration

AZURE_STORAGE_ACCOUNT_NAME = os.getenv('AZURE_STORAGE_ACCOUNT_NAME', '$STORAGE_ACCOUNT')

# Load environment variables

env_path = Path(__file__).parent / '.env'# Azure Key Vault Configuration  

load_dotenv(dotenv_path=env_path)AZURE_KEY_VAULT_NAME = os.getenv('AZURE_KEY_VAULT_NAME', '$KEY_VAULT_NAME')

AZURE_KEY_VAULT_URI = os.getenv('AZURE_KEY_VAULT_URI', '$KEY_VAULT_URI')

# Azure OpenAI Configuration

AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')# Environment

AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')ENVIRONMENT = os.getenv('ENVIRONMENT', '$ENVIRONMENT')

AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-08-01-preview')AZURE_LOCATION = os.getenv('AZURE_LOCATION', '$LOCATION')

AZURE_OPENAI_DEPLOYMENT_GPT5 = os.getenv('AZURE_OPENAI_DEPLOYMENT_GPT5', 'gpt-5-mini')AZURE_RESOURCE_GROUP = os.getenv('AZURE_RESOURCE_GROUP', '$RESOURCE_GROUP_NAME')

AZURE_OPENAI_DEPLOYMENT_GPT4O = os.getenv('AZURE_OPENAI_DEPLOYMENT_GPT4O', 'gpt-4o')

AZURE_OPENAI_RESOURCE_NAME = os.getenv('AZURE_OPENAI_RESOURCE_NAME')# Get OpenAI API key from Key Vault (requires Azure authentication)

AZURE_RESOURCE_GROUP = os.getenv('AZURE_RESOURCE_GROUP')def get_openai_api_key():

ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')    """Get OpenAI API key from Azure Key Vault using DefaultAzureCredential."""

EOF    from azure.identity import DefaultAzureCredential

    from azure.keyvault.secrets import SecretClient

    print_success "Python config file created at ../azure_config.py"    

else    credential = DefaultAzureCredential()

    print_info "Skipping .env update. You can manually configure using these values:"    client = SecretClient(vault_url=AZURE_KEY_VAULT_URI, credential=credential)

    echo ""    secret = client.get_secret("OpenAI-ApiKey")

    echo "AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT"    return secret.value

    echo "AZURE_OPENAI_API_KEY=$API_KEY1"

    echo "AZURE_OPENAI_DEPLOYMENT_GPT5=$GPT5_DEPLOYMENT"# Get Storage connection string from Key Vault

    echo "AZURE_OPENAI_DEPLOYMENT_GPT4O=$GPT4O_DEPLOYMENT"def get_storage_connection_string():

fi    """Get Storage connection string from Azure Key Vault."""

    from azure.identity import DefaultAzureCredential

# ============================================================================    from azure.keyvault.secrets import SecretClient

# Next Steps    

# ============================================================================    credential = DefaultAzureCredential()

    client = SecretClient(vault_url=AZURE_KEY_VAULT_URI, credential=credential)

print_header "Deployment Complete! 🎉"    secret = client.get_secret("Storage-ConnectionString")

    return secret.value

echo ""EOF

echo -e "${GREEN}Your Azure OpenAI is ready to use!${NC}"

echo ""print_success "Python configuration saved to ../azure_config.py"

echo "Quick test:"

echo -e "  ${BLUE}python -c \"from azure_config import *; print(f'Endpoint: {AZURE_OPENAI_ENDPOINT}')\"${NC}"# ============================================================================

echo ""# Next Steps

echo "View in Azure Portal:"# ============================================================================

echo -e "  ${BLUE}https://portal.azure.com/#@/resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.CognitiveServices/accounts/$OPENAI_RESOURCE${NC}"

echo ""print_header "Deployment Complete! 🎉"

echo -e "${YELLOW}Security Note:${NC}"

echo "  - Keep your .env file secure (already in .gitignore)"echo ""

echo "  - Rotate keys regularly from Azure Portal"echo -e "${GREEN}Your Azure infrastructure is ready!${NC}"

echo "  - Use Managed Identity for production deployments"echo ""

echo ""echo "Next steps:"

echo ""
echo "1. Install required Python packages:"
echo -e "   ${BLUE}pip install openai azure-identity azure-keyvault-secrets azure-storage-blob python-dotenv${NC}"
echo ""
echo "2. Authenticate with Azure (for local development):"
echo -e "   ${BLUE}az login${NC}"
echo ""
echo "3. Test the AI column mapper:"
echo -e "   ${BLUE}cd .. && python -c 'from azure_config import get_openai_api_key; print(\"API Key:\", get_openai_api_key()[:10] + \"...\")'${NC}"
echo ""
echo "4. Run the AI-powered column mapping:"
echo -e "   ${BLUE}python ai_reasoner.py${NC}"
echo ""
echo "5. Monitor resources in Azure Portal:"
echo -e "   ${BLUE}https://portal.azure.com/#@/resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME${NC}"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- API keys are stored in Key Vault: $KEY_VAULT_NAME"
echo "- Use Managed Identity in production (no keys needed)"
echo "- Review network security settings before production deployment"
echo ""

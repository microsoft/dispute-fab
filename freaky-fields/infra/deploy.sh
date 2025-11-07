#!/bin/bash
# ============================================================================
# Azure Infrastructure Deployment Script
# ============================================================================
# Description: Deploys the SeeHealth AI Claims Triage infrastructure to Azure
#
# Prerequisites:
# - Azure CLI installed (az --version)
# - Logged in to Azure (az login)
# - Appropriate subscription selected (az account set -s <subscription-id>)
#
# Usage:
#   ./deploy.sh <environment> <location> <admin-email>
#
# Examples:
#   ./deploy.sh dev eastus admin@example.com
#   ./deploy.sh prod eastus2 admin@example.com
#
# Date: October 29, 2025
# ============================================================================

set -e  # Exit on error

# Add local bin to PATH for Bicep
export PATH="$HOME/.local/bin:$PATH"

# ============================================================================
# Configuration
# ============================================================================

ENVIRONMENT=${1:-dev}
LOCATION=${2:-eastus}
ADMIN_EMAIL=${3:-admin@example.com}
RESOURCE_GROUP_NAME="rg-seehealth-claims-${ENVIRONMENT}"
DEPLOYMENT_NAME="seehealth-claims-deployment-$(date +%Y%m%d-%H%M%S)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# ============================================================================
# Validation
# ============================================================================

print_header "Validating Prerequisites"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    print_error "Azure CLI is not installed. Please install it first."
    echo "Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi
print_success "Azure CLI is installed"

# Check if logged in
if ! az account show &> /dev/null; then
    print_error "Not logged in to Azure. Please run: az login"
    exit 1
fi
print_success "Logged in to Azure"

# Display admin email
print_success "Admin email: $ADMIN_EMAIL"

# Display current subscription
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
print_info "Subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"

# ============================================================================
# Resource Group
# ============================================================================

print_header "Creating Resource Group"

if az group exists --name "$RESOURCE_GROUP_NAME" | grep -q "true"; then
    print_warning "Resource group '$RESOURCE_GROUP_NAME' already exists"
else
    az group create \
        --name "$RESOURCE_GROUP_NAME" \
        --location "$LOCATION" \
        --tags Environment="$ENVIRONMENT" Project="SeeHealth Claims Triage" ManagedBy="Bicep"
    print_success "Resource group '$RESOURCE_GROUP_NAME' created in $LOCATION"
fi

# ============================================================================
# Bicep Validation
# ============================================================================

print_header "Validating Bicep Template"

print_info "Skipping separate validation due to SSL certificate issues..."
print_info "Validation will occur during deployment"

# ============================================================================
# Deployment Confirmation
# ============================================================================

print_header "Deployment Confirmation"

print_info "Resources to be created:"
echo "  • Azure OpenAI account with GPT-4 and GPT-4 Turbo deployments"
echo "  • Storage Account (Data Lake Gen2) with 5 containers"
echo "  • Key Vault with RBAC authorization"
echo "  • Log Analytics workspace"
echo "  • Application Insights"
echo ""
print_info "Environment: $ENVIRONMENT"
print_info "Location: $LOCATION"
print_info "Resource Group: $RESOURCE_GROUP_NAME"
echo ""
read -p "Do you want to proceed with deployment? (yes/no): " PROCEED

if [ "$PROCEED" != "yes" ]; then
    print_warning "Deployment cancelled by user"
    exit 0
fi

# ============================================================================
# Deployment
# ============================================================================

print_header "Deploying Infrastructure"

print_info "Deployment name: $DEPLOYMENT_NAME"
print_info "This may take 5-10 minutes..."
echo ""

az deployment group create \
    --name "$DEPLOYMENT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --template-file main.bicep \
    --parameters environment="$ENVIRONMENT" location="$LOCATION" adminEmail="$ADMIN_EMAIL" \
    --output table

print_success "Deployment completed successfully!"

# ============================================================================
# Retrieve Outputs
# ============================================================================

print_header "Deployment Outputs"

OUTPUTS=$(az deployment group show \
    --name "$DEPLOYMENT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query properties.outputs -o json)

echo "$OUTPUTS" | jq -r 'to_entries[] | "\(.key): \(.value.value)"' | while read line; do
    print_info "$line"
done

# ============================================================================
# Save Configuration
# ============================================================================

print_header "Saving Configuration"

# Extract key values
OPENAI_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.openAIEndpoint.value')
OPENAI_RESOURCE=$(echo "$OUTPUTS" | jq -r '.openAIResourceName.value')
STORAGE_ACCOUNT=$(echo "$OUTPUTS" | jq -r '.storageAccountName.value')
KEY_VAULT_NAME=$(echo "$OUTPUTS" | jq -r '.keyVaultName.value')
KEY_VAULT_URI=$(echo "$OUTPUTS" | jq -r '.keyVaultUri.value')

# Create .env file for local development
cat > ../.env << EOF
# ============================================================================
# SeeHealth AI Claims Triage - Azure Configuration
# ============================================================================
# Generated: $(date)
# Environment: $ENVIRONMENT
# ============================================================================

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=$OPENAI_ENDPOINT
AZURE_OPENAI_RESOURCE_NAME=$OPENAI_RESOURCE
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# Azure Storage
AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT
AZURE_STORAGE_CONNECTION_STRING_SECRET=Storage-ConnectionString

# Azure Key Vault
AZURE_KEY_VAULT_NAME=$KEY_VAULT_NAME
AZURE_KEY_VAULT_URI=$KEY_VAULT_URI

# Environment
ENVIRONMENT=$ENVIRONMENT
AZURE_LOCATION=$LOCATION
AZURE_RESOURCE_GROUP=$RESOURCE_GROUP_NAME

# For local development, get the OpenAI key with:
# az keyvault secret show --name OpenAI-ApiKey --vault-name $KEY_VAULT_NAME --query value -o tsv
EOF

print_success "Configuration saved to ../.env"

# Create Python config file
cat > ../azure_config.py << EOF
"""
Azure Configuration for SeeHealth AI Claims Triage

Auto-generated configuration from Bicep deployment.
Generated: $(date)
Environment: $ENVIRONMENT
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', '$OPENAI_ENDPOINT')
AZURE_OPENAI_RESOURCE_NAME = os.getenv('AZURE_OPENAI_RESOURCE_NAME', '$OPENAI_RESOURCE')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')

# Azure Storage Configuration
AZURE_STORAGE_ACCOUNT_NAME = os.getenv('AZURE_STORAGE_ACCOUNT_NAME', '$STORAGE_ACCOUNT')

# Azure Key Vault Configuration  
AZURE_KEY_VAULT_NAME = os.getenv('AZURE_KEY_VAULT_NAME', '$KEY_VAULT_NAME')
AZURE_KEY_VAULT_URI = os.getenv('AZURE_KEY_VAULT_URI', '$KEY_VAULT_URI')

# Environment
ENVIRONMENT = os.getenv('ENVIRONMENT', '$ENVIRONMENT')
AZURE_LOCATION = os.getenv('AZURE_LOCATION', '$LOCATION')
AZURE_RESOURCE_GROUP = os.getenv('AZURE_RESOURCE_GROUP', '$RESOURCE_GROUP_NAME')

# Get OpenAI API key from Key Vault (requires Azure authentication)
def get_openai_api_key():
    """Get OpenAI API key from Azure Key Vault using DefaultAzureCredential."""
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
    
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=AZURE_KEY_VAULT_URI, credential=credential)
    secret = client.get_secret("OpenAI-ApiKey")
    return secret.value

# Get Storage connection string from Key Vault
def get_storage_connection_string():
    """Get Storage connection string from Azure Key Vault."""
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
    
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=AZURE_KEY_VAULT_URI, credential=credential)
    secret = client.get_secret("Storage-ConnectionString")
    return secret.value
EOF

print_success "Python configuration saved to ../azure_config.py"

# ============================================================================
# Next Steps
# ============================================================================

print_header "Deployment Complete! 🎉"

echo ""
echo -e "${GREEN}Your Azure infrastructure is ready!${NC}"
echo ""
echo "Next steps:"
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

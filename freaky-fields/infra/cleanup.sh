#!/bin/bash
# ============================================================================
# Azure Infrastructure Cleanup Script
# ============================================================================
# Description: Safely removes Azure resources for SeeHealth Claims Triage
#
# Usage:
#   ./cleanup.sh <environment>
#
# Examples:
#   ./cleanup.sh dev      # Remove dev environment
#   ./cleanup.sh test     # Remove test environment
#   ./cleanup.sh prod     # Remove production (requires confirmation)
#
# Date: October 29, 2025
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT=${1:-dev}
RESOURCE_GROUP_NAME="rg-seehealth-claims-${ENVIRONMENT}"

echo ""
echo -e "${RED}============================================================================${NC}"
echo -e "${RED}WARNING: RESOURCE DELETION${NC}"
echo -e "${RED}============================================================================${NC}"
echo ""
echo -e "${YELLOW}You are about to DELETE the following resource group:${NC}"
echo -e "${YELLOW}  Environment: ${ENVIRONMENT}${NC}"
echo -e "${YELLOW}  Resource Group: ${RESOURCE_GROUP_NAME}${NC}"
echo ""
echo -e "${RED}This will PERMANENTLY DELETE:${NC}"
echo -e "${RED}  - Azure OpenAI resources and models${NC}"
echo -e "${RED}  - Storage accounts and ALL data${NC}"
echo -e "${RED}  - Key Vault and secrets${NC}"
echo -e "${RED}  - Log Analytics workspace and logs${NC}"
echo -e "${RED}  - Application Insights data${NC}"
echo -e "${RED}  - Data Factory pipelines${NC}"
echo -e "${RED}  - Container Registry images${NC}"
echo ""

# Extra confirmation for production
if [ "$ENVIRONMENT" == "prod" ]; then
    echo -e "${RED}⚠️  YOU ARE DELETING PRODUCTION ENVIRONMENT! ⚠️${NC}"
    echo ""
    read -p "Type 'DELETE PRODUCTION' to confirm: " CONFIRM
    if [ "$CONFIRM" != "DELETE PRODUCTION" ]; then
        echo -e "${GREEN}Cleanup cancelled.${NC}"
        exit 0
    fi
fi

read -p "Are you ABSOLUTELY SURE? Type 'yes' to confirm: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${GREEN}Cleanup cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}Deleting resource group: ${RESOURCE_GROUP_NAME}...${NC}"

az group delete \
    --name "$RESOURCE_GROUP_NAME" \
    --yes \
    --no-wait

echo ""
echo -e "${GREEN}✓ Deletion initiated. Resources will be removed in the background.${NC}"
echo ""
echo "Monitor deletion status:"
echo -e "${BLUE}  az group show --name ${RESOURCE_GROUP_NAME}${NC}"
echo ""
echo "Or check in Azure Portal:"
echo -e "${BLUE}  https://portal.azure.com${NC}"
echo ""

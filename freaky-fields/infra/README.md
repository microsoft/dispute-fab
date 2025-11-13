# Minimal Azure OpenAI Infrastructure

**Last Updated:** November 13, 2025

This directory now contains a **single minimal Bicep template** plus helper scripts. It deploys **only an Azure OpenAI account** and (optionally) two model deployments. All prior extras (Key Vault, Storage, Log Analytics, App Insights, etc.) have been removed for simplicity.

## 📁 Structure

```
infra/
├── main.bicep    # Single source template (Azure OpenAI + optional models)
├── deploy.sh     # Provision RG + template + write .env
├── cleanup.sh    # Tear down RG or just OpenAI account
├── update-env.sh # Refresh .env from existing deployment
└── README.md     # This file
```

## 🎯 What Can Be Deployed

Base:
1. Azure OpenAI account (S0)

Optional (controlled by `deployModels` parameter):
2. `gpt-5-mini` (model: gpt-5-mini version 2025-08-07)
3. `gpt-4o` (model: gpt-4o version 2024-11-20)

Pass `deployModels=false` if you only want the account + keys and will add deployments later (CLI / Portal).

## 🧩 Bicep Parameters (main.bicep)

| Name | Type | Default | Description |
|------|------|---------|-------------|
| environment | string | `dev` | Environment label used in naming |
| location | string | `resourceGroup().location` | Azure region |
| uniqueSuffix | string | `uniqueString(resourceGroup().id)` | Deterministic suffix per RG |
| openAIAccountBaseName | string | `openai` | Base prefix for account name |
| deployModels | bool | `true` | Whether to deploy the two model deployments |

Resulting account name pattern: `openai-<env>-<suffix>` (lowercased, underscores swapped to hyphens).

## 🚀 Quick Start (Scripted)

```bash
cd infra
# Provision with models
./deploy.sh dev eastus

# Provision without model deployments (account only)
DEPLOY_MODELS=false ./deploy.sh dev eastus
```

The script writes a canonical `.env` with:
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_RESOURCE_NAME`
- `AZURE_OPENAI_DEPLOYMENT_GPT5` (blank if models disabled)
- `AZURE_OPENAI_DEPLOYMENT_GPT4O` (blank if models disabled)
- `AZURE_OPENAI_API_KEY` (primary key)
- `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`, `AZURE_ENVIRONMENT`

## 🛠️ Quick Start (Manual CLI)

```bash
# 1. Create resource group
az group create --name rg-openai-dev --location eastus

# 2. Deploy WITH models
az deployment group create \
  --name openaiDeploy \
  --resource-group rg-openai-dev \
  --template-file infra/main.bicep \
  --parameters environment=dev location=eastus deployModels=true

# OR deploy WITHOUT models
az deployment group create \
  --name openaiDeploy \
  --resource-group rg-openai-dev \
  --template-file infra/main.bicep \
  --parameters environment=dev location=eastus deployModels=false
```

## 🔑 Retrieve API Keys

```bash
RESOURCE_NAME=$(az deployment group show \
  --name openaiDeploy \
  --resource-group rg-openai-dev \
  --query properties.outputs.openAIResourceName.value -o tsv)

az cognitiveservices account keys list \
  --name "$RESOURCE_NAME" \
  --resource-group rg-openai-dev \
  --query key1 -o tsv
```

## 📦 Adding Models Later (If You Skipped Them)

```bash
RESOURCE_NAME=your-account-name
RG=rg-openai-dev

# Add gpt-5-mini
az cognitiveservices account deployment create \
  --resource-group $RG \
  --name $RESOURCE_NAME \
  --deployment-name gpt-5-mini \
  --model-format OpenAI \
  --model-name gpt-5-mini \
  --model-version 2025-08-07 \
  --sku-name GlobalStandard --sku-capacity 120

# Add gpt-4o
az cognitiveservices account deployment create \
  --resource-group $RG \
  --name $RESOURCE_NAME \
  --deployment-name gpt-4o \
  --model-format OpenAI \
  --model-name gpt-4o \
  --model-version 2024-11-20 \
  --sku-name GlobalStandard --sku-capacity 80
```

## 🧪 Testing Environment Variables

```bash
source .env
echo $AZURE_OPENAI_ENDPOINT
python - <<'PY'
import os
print('Endpoint:', os.getenv('AZURE_OPENAI_ENDPOINT'))
print('GPT-5 mini deployment:', os.getenv('AZURE_OPENAI_DEPLOYMENT_GPT5'))
print('GPT-4o deployment:', os.getenv('AZURE_OPENAI_DEPLOYMENT_GPT4O'))
PY
```

## 🧹 Cleanup

Use script (safer prompts):
```bash
cd infra
# Dry run
./cleanup.sh --dry-run rg-openai-dev
# Delete only OpenAI account (keep RG)
./cleanup.sh --only-openai rg-openai-dev
# Delete entire resource group
./cleanup.sh rg-openai-dev --yes
```

Manual:
```bash
az group delete --name rg-openai-dev --yes --no-wait
```

## ⚠️ Notes

- Outputs `gpt5miniDeploymentName` / `gpt4oDeploymentName` will be blank strings if `deployModels=false`.
- You can safely re-run deployment; account name stays consistent (`uniqueSuffix` derived from RG id).
- To rotate keys: `az cognitiveservices account keys regenerate --key-type primary`.

## ❓ Troubleshooting

```bash
# Show deployment error details
az deployment group show --name openaiDeploy --resource-group rg-openai-dev --query properties.error

# List deployments
az cognitiveservices account deployment list --name <resource-name> --resource-group rg-openai-dev -o table
```

## ✅ Summary

Single minimal template retained (`main.bicep`). Optional model deployments controlled by `deployModels`. Helper scripts manage lifecycle & env vars. No extraneous Azure resources.

---
Minimal OpenAI Infra • Deterministic • Auditable

## 🚀 Quick Start

### Prerequisites

1. **Azure CLI** installed ([Install Guide](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli))
2. **Azure Subscription** with appropriate permissions
3. **Logged in:** `az login`

### Deploy Infrastructure

```bash
# Navigate to infra directory
cd infra

# Deploy to development environment
./deploy.sh dev eastus

# The script will:
# 1. Create resource group
# 2. Deploy Azure OpenAI with models
# 3. Retrieve API keys
# 4. Ask if you want to update .env file automatically
./deploy.sh dev eastus your-email@example.com

# Deploy with App Service for production hosting
./deploy.sh prod eastus2 your-email@example.com --enable-app-service
```

The script will:
1. ✅ Validate prerequisites
2. ✅ Create resource group
3. ✅ Deploy Azure OpenAI with GPT-4o-mini
4. ✅ Create Key Vault and store API key
5. ✅ Output environment variables for `.env`

## 🏗️ Resources Deployed

| Resource | Purpose | When Deployed | SKU/Tier |
|----------|---------|----------|
| **Azure OpenAI** | GPT-4 for AI column mapping and reasoning | Standard (S0) |
| **Storage Account** | Data Lake Gen2 for vendor data, outputs | Standard_LRS |
| **Key Vault** | Secure storage for API keys and secrets | Standard |
| **Log Analytics** | Centralized logging and monitoring | PerGB2018 |
| **Application Insights** | Application telemetry and diagnostics | Web |
| **Data Factory** *(optional)* | Orchestration and data pipelines | - |
| **Container Registry** *(optional)* | Docker container images | Basic |

### Storage Containers Created

- `vendor-data` - Raw vendor files (15 vendors × files)
- `processed-data` - Normalized and classified claims
- `crosswalks` - Vendor-specific crosswalk tables
- `reference-data` - NDC codes, formulary lists, etc.
- `outputs` - Generated reports and results

### OpenAI Deployments

- `gpt-4` - Standard GPT-4 (10K TPM) for column mapping
- `gpt-4-turbo` - GPT-4 Turbo (30K TPM) for faster processing

## ⚙️ Configuration

### Customize Parameters

Edit `main.parameters.json`:

```json
{
  "environment": {
    "value": "dev"  // Options: dev, test, prod
  },
  "location": {
    "value": "eastus"  // Azure region
  },
  "adminEmail": {
    "value": "your-email@example.com"
  },
  "enableDataFactory": {
    "value": true  // Enable ADF for orchestration
  },
  "enableContainerRegistry": {
    "value": false  // Enable ACR for containers
  }
}
```

### Manual Deployment

```bash
# Create resource group
az group create \
  --name rg-seehealth-claims-dev \
  --location eastus

# Validate template
az deployment group validate \
  --resource-group rg-seehealth-claims-dev \
  --template-file main.bicep \
  --parameters main.parameters.json

# Deploy
az deployment group create \
  --name seehealth-claims-deployment \
  --resource-group rg-seehealth-claims-dev \
  --template-file main.bicep \
  --parameters main.parameters.json
```

## 🔐 Security

### Key Vault Secrets

The following secrets are automatically created:

- `OpenAI-ApiKey` - Azure OpenAI API key
- `Storage-ConnectionString` - Storage account connection string

### Access Secrets

```bash
# Get OpenAI API key
az keyvault secret show \
  --name OpenAI-ApiKey \
  --vault-name <key-vault-name> \
  --query value -o tsv

# Get Storage connection string
az keyvault secret show \
  --name Storage-ConnectionString \
  --vault-name <key-vault-name> \
  --query value -o tsv
```

### Managed Identity (Recommended for Production)

The deployment uses RBAC for Key Vault. Grant your application managed identity access:

```bash
# Assign Key Vault Secrets User role
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee <managed-identity-id> \
  --scope /subscriptions/<subscription-id>/resourceGroups/<rg-name>/providers/Microsoft.KeyVault/vaults/<kv-name>
```

## 🔧 Post-Deployment Setup

### 1. Install Python Dependencies

```bash
cd ..
pip install openai azure-identity azure-keyvault-secrets azure-storage-blob python-dotenv
```

### 2. Authenticate Locally

```bash
# Login to Azure
az login

# Verify access to Key Vault
az keyvault secret list --vault-name <key-vault-name>
```

### 3. Test Configuration

```python
# Test Azure configuration
python -c "
from azure_config import get_openai_api_key, AZURE_OPENAI_ENDPOINT
print(f'OpenAI Endpoint: {AZURE_OPENAI_ENDPOINT}')
print(f'API Key: {get_openai_api_key()[:10]}...')
"
```

### 4. Run AI Column Mapper

```python
from ai_reasoner import map_vendor_columns_with_ai
from azure_config import AZURE_OPENAI_ENDPOINT, get_openai_api_key

mappings = map_vendor_columns_with_ai(
    vendor_columns=['PHCY_CLAIM_ID', 'FILL_NDC_NBR', 'FILL_QTY'],
    standard_columns=['CLAIM_ID', 'DRUG_NDC', 'DISPENSED_QUANTITY'],
    vendor_name='CVS Health',
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=get_openai_api_key()
)

print(mappings)
```

## 📊 Monitoring

### View Logs

```bash
# Query Log Analytics
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query "AzureDiagnostics | where ResourceProvider == 'MICROSOFT.COGNITIVESERVICES' | take 10"
```

### Application Insights

Access Application Insights in Azure Portal:
- Live metrics
- Performance monitoring
- Failure analysis
- Custom telemetry

## 🧹 Cleanup

### Delete All Resources

```bash
# Delete resource group (WARNING: This deletes everything!)
az group delete \
  --name rg-seehealth-claims-dev \
  --yes --no-wait
```

### Selective Cleanup

```bash
# Delete specific resource
az <resource-type> delete \
  --resource-group rg-seehealth-claims-dev \
  --name <resource-name>
```

## 💰 Cost Estimation

Estimated monthly costs (USD, approximate):

| Resource | Dev | Prod |
|----------|-----|------|
| Azure OpenAI (GPT-4) | $50-200 | $500-2000 |
| Storage (Data Lake) | $5-20 | $50-200 |
| Key Vault | $1 | $1 |
| Log Analytics | $10-50 | $100-500 |
| Application Insights | $5-20 | $50-200 |
| Data Factory | $0-10 | $50-500 |
| **Total** | **$71-300/mo** | **$751-3,401/mo** |

*Costs vary based on usage patterns, data volume, and API calls.*

### Cost Optimization

- Use **Standard_LRS** for storage in dev
- Use **Standard_ZRS** or **Standard_GRS** for prod
- Monitor OpenAI token usage
- Set up cost alerts in Azure Portal
- Use reserved capacity for predictable workloads

## 🚨 Troubleshooting

### Deployment Fails

```bash
# Check deployment status
az deployment group show \
  --name <deployment-name> \
  --resource-group rg-seehealth-claims-dev

# View deployment errors
az deployment group show \
  --name <deployment-name> \
  --resource-group rg-seehealth-claims-dev \
  --query properties.error
```

### Can't Access Key Vault

```bash
# Check your permissions
az role assignment list \
  --scope /subscriptions/<subscription-id>/resourceGroups/<rg-name>/providers/Microsoft.KeyVault/vaults/<kv-name>

# Grant yourself access (if admin)
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee <your-user-id> \
  --scope /subscriptions/<subscription-id>/resourceGroups/<rg-name>/providers/Microsoft.KeyVault/vaults/<kv-name>
```

### OpenAI API Issues

```bash
# Test OpenAI endpoint
curl -X POST "$AZURE_OPENAI_ENDPOINT/openai/deployments/gpt-4/chat/completions?api-version=2024-02-15-preview" \
  -H "api-key: $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

## 📚 Additional Resources

- [Azure Bicep Documentation](https://docs.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- [Azure OpenAI Service](https://docs.microsoft.com/en-us/azure/cognitive-services/openai/)
- [Azure Data Lake Storage Gen2](https://docs.microsoft.com/en-us/azure/storage/blobs/data-lake-storage-introduction)
- [Azure Key Vault](https://docs.microsoft.com/en-us/azure/key-vault/)
- [Azure Data Factory](https://docs.microsoft.com/en-us/azure/data-factory/)

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Azure Portal for resource status
3. Check Log Analytics for error messages
4. Contact your Azure administrator

---

**Environment**: Dev | **Last Updated**: October 29, 2025

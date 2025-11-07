# Azure Infrastructure for SeeHealth AI Claims Triage

**Last Updated:** November 5, 2025

This directory contains Infrastructure as Code (IaC) using Azure Bicep to deploy Azure infrastructure for the claims triage platform.

## 📁 Structure

```
infra/
├── main.bicep                  # Simplified Bicep template (Azure OpenAI + Key Vault)
├── main.parameters.json        # Parameters file (customize before deployment)
├── deploy.sh                   # Automated deployment script
├── cleanup.sh                  # Cleanup/teardown script
└── README.md                   # This file
```

## 🎯 Current State (November 2025)

### Currently Deployed & Active:
1. **Azure OpenAI** - GPT-5-mini deployment for claim summarization
   - Resource: `Microsoft.CognitiveServices/accounts`
   - Deployment: `gpt-5-mini` (env var: AZURE_OPENAI_DEPLOYMENT_GPT5)
   - Model: `gpt-5-mini` (2024-08-01-preview)
   - Capacity: 120K TPM

### Not Currently Used
- Local development uses direct Azure OpenAI API calls
- FastAPI runs locally (`uvicorn api_server:app`)
- React frontend runs on Vite dev server (`:5173`)
- Data processing uses local files in `data/` and `outputs/`

## 🚀 Quick Start

### Prerequisites

1. **Azure CLI** installed ([Install Guide](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli))
2. **Azure Subscription** with appropriate permissions
3. **Bash shell** (macOS/Linux/WSL)

### Deploy Minimal Infrastructure (Azure OpenAI + Key Vault)

```bash
# Navigate to infra directory
cd infra

# Make deploy script executable
chmod +x deploy.sh

# Deploy to development environment (minimal setup)
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

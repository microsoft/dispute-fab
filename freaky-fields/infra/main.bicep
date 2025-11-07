// ============================================================================
// Main Bicep Template for SeeHealth AI Claims Triage Solution
// ============================================================================
// Description: Deploys Azure infrastructure for pharmacy claims dispute
//              classification and AI-powered summarization.
//
// Current Resources (Actively Used):
// - Azure OpenAI (GPT-4o-mini) for AI claim summarization
// - Azure Key Vault for API key storage
//
// Future Resources (For Production Deployment):
// - Azure App Service for FastAPI backend (api_server.py)
// - Azure Static Web App for React frontend
// - Azure Storage Account for classification outputs
// - Application Insights for monitoring
//
// Last Updated: November 5, 2025
// ============================================================================

@description('Environment name (dev, test, prod)')
@allowed([
  'dev'
  'test'
  'prod'
])
param environment string = 'dev'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Unique suffix for resource names (auto-generated if empty)')
param uniqueSuffix string = uniqueString(resourceGroup().id)

@description('Your email for alerts and notifications')
param adminEmail string

@description('Enable Azure App Service for API hosting (future)')
param enableAppService bool = false

@description('Enable Azure Storage for classification outputs (future)')
param enableStorage bool = false

@description('Enable Application Insights for monitoring (future)')
param enableMonitoring bool = false

// ============================================================================
// Variables
// ============================================================================

var resourcePrefix = 'seehealth-${environment}' // Shortened for Key Vault name length constraint (max 24 chars)
var tags = {
  Environment: environment
  Project: 'SeeHealth Claims Triage'
  ManagedBy: 'Bicep'
}

// ============================================================================
// Azure OpenAI Service
// ============================================================================

resource openAIAccount 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${resourcePrefix}-openai-${uniqueSuffix}'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: '${resourcePrefix}-openai-${uniqueSuffix}'
    networkAcls: {
      defaultAction: 'Allow' // Change to 'Deny' for production with VNet integration
    }
    publicNetworkAccess: 'Enabled'
  }
}

// GPT-5-mini Deployment for AI claim summarization
// This is the current model used by api_server.py
@description('GPT model name (currently using gpt-5-mini)')
param gptModelName string = 'gpt-5-mini'

@description('Model version for GPT-5-mini (check list-models output)')
param gptModelVersion string = '2024-08-01-preview' // Update based on available versions

@description('Deployment name used by application code (AZURE_OPENAI_DEPLOYMENT_GPT5)')
param gptDeploymentName string = 'gpt-5-mini'

@description('Tokens-per-minute capacity (thousands). 120K is typical for standard workloads.')
param gptCapacity int = 120

resource gptDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAIAccount
  name: gptDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: gptCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: gptModelName
      version: gptModelVersion
    }
  }
}

// ============================================================================
// Azure Storage Account (Optional - for future production deployment)
// ============================================================================
// Currently the application uses local file storage in data/ and outputs/
// Enable this for cloud-based deployments

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = if (enableStorage) {
  name: 'seehealth${environment}${uniqueSuffix}'
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS' // Use Standard_ZRS or Standard_GRS for production
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    networkAcls: {
      defaultAction: 'Allow' // Change to 'Deny' for production
      bypass: 'AzureServices'
    }
  }
}

// Blob service for storage account
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = if (enableStorage) {
  parent: storageAccount
  name: 'default'
}

// Container for outputs/results (classification CSVs, JSON summaries)
resource outputsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = if (enableStorage) {
  parent: blobService
  name: 'outputs'
  properties: {
    publicAccess: 'None'
  }
}

// ============================================================================
// Azure Key Vault
// ============================================================================

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-seehealth-${uniqueSuffix}' // Max 24 chars: kv-seehealth- (9) + uniqueSuffix (13) = 22 chars
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true // Use RBAC instead of access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    networkAcls: {
      defaultAction: 'Allow' // Change to 'Deny' for production
      bypass: 'AzureServices'
    }
  }
}

// Store OpenAI API key in Key Vault
resource openAIKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'OpenAI-ApiKey'
  properties: {
    value: openAIAccount.listKeys().key1
    contentType: 'text/plain'
  }
}

// Store Storage Account connection string (only if storage is enabled)
resource storageConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (enableStorage) {
  parent: keyVault
  name: 'Storage-ConnectionString'
  properties: {
    value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}'
    contentType: 'text/plain'
  }
}

// ============================================================================
// Application Insights (Optional - for monitoring)
// ============================================================================
// Enable for production to monitor API performance and errors

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (enableMonitoring) {
  name: '${resourcePrefix}-logs-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = if (enableMonitoring) {
  name: '${resourcePrefix}-insights-${uniqueSuffix}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    RetentionInDays: 30
  }
}

// ============================================================================
// Azure App Service (Optional - for hosting FastAPI backend)
// ============================================================================
// Enable for production deployment of api_server.py

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = if (enableAppService) {
  name: '${resourcePrefix}-plan-${uniqueSuffix}'
  location: location
  tags: tags
  sku: {
    name: 'B1' // Basic tier for dev/test; use P1V2+ for production
    tier: 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true // Required for Linux
  }
}

resource webApp 'Microsoft.Web/sites@2023-01-01' = if (enableAppService) {
  name: '${resourcePrefix}-api-${uniqueSuffix}'
  location: location
  tags: tags
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: true
      appSettings: [
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: openAIAccount.properties.endpoint
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: '2024-08-01-preview'
        }
        {
          name: 'AZURE_OPENAI_DEPLOYMENT_GPT4O'
          value: gptDeploymentName
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: '@Microsoft.KeyVault(SecretUri=${openAIKeySecret.properties.secretUri})'
        }
      ]
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// ============================================================================
// Remove unused resources (Data Factory, Container Registry, etc.)
// ============================================================================
// These were part of the original template but are not used in current implementation

/*
// Removed: Azure Data Factory - not used for current local processing workflow
// Removed: Azure Container Registry - not using containerized deployments yet
  name: 'seehealth${environment}acr${uniqueSuffix}'
  location: location
  tags: tags
  sku: {
    name: 'Basic' // Use Premium for production with geo-replication
  }
  properties: {
    adminUserEnabled: true
    publicNetworkAccess: 'Enabled'
  }
}

// ============================================================================
// Diagnostic Settings for OpenAI
// ============================================================================

// Diagnostic settings for OpenAI (only if monitoring is enabled)
resource openAIDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableMonitoring) {
  name: 'openai-diagnostics'
  scope: openAIAccount
  properties: {
    workspaceId: logAnalytics.id
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Azure OpenAI endpoint URL - use for AZURE_OPENAI_ENDPOINT')
output openAIEndpoint string = openAIAccount.properties.endpoint

@description('Azure OpenAI resource name')
output openAIResourceName string = openAIAccount.name

@description('GPT-5-mini deployment name - use for AZURE_OPENAI_DEPLOYMENT_GPT5')
output gptDeploymentName string = gptDeploymentName

@description('Azure OpenAI API key secret URI in Key Vault')
output openAIKeySecretUri string = openAIKeySecret.properties.secretUri

@description('Key Vault name - retrieve API key with: az keyvault secret show --name OpenAI-ApiKey --vault-name <name>')
output keyVaultName string = keyVault.name

@description('Key Vault URI')
output keyVaultUri string = keyVault.properties.vaultUri

@description('Storage account name (if enabled)')
output storageAccountName string = enableStorage ? storageAccount.name : 'Not deployed'

@description('App Service URL (if enabled)')
output appServiceUrl string = enableAppService ? 'https://${webApp.properties.defaultHostName}' : 'Not deployed'

@description('Application Insights connection string (if enabled)')
output appInsightsConnectionString string = enableMonitoring ? appInsights.properties.ConnectionString : 'Not deployed'

@description('Environment name')
output environmentName string = environment

@description('Resource group location')
output location string = location

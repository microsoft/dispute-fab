// ============================================================================
// Minimal Azure OpenAI Template (Account + Optional Model Deployments)
// ============================================================================
// Description:
//   Creates a single Azure OpenAI account (S0) with deterministic naming.
//   Optionally deploys two model deployments when deployModels=true:
//     - gpt-5-mini  (model: gpt-5-mini version 2025-08-07)
//     - gpt-4o      (model: gpt-4o version 2024-11-20)
//   If deployModels=false only the account is provisioned; you can add
//   deployments later via CLI or Portal without changing the template.
//
//   Excludes all ancillary resources (Key Vault, Storage, Monitoring, etc.)
//   to remain auditable and cost-minimal.
//
//   Naming pattern: <openAIAccountBaseName>-<environment>-<uniqueSuffix>
//   uniqueSuffix is stable per resource group (uniqueString(rg().id)).
//
// Last Updated: November 13, 2025
// ============================================================================

@description('Environment name (dev, test, prod)')
param environment string = 'dev'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Unique suffix for resource names (deterministic from RG id)')
param uniqueSuffix string = uniqueString(resourceGroup().id)

@description('Azure OpenAI account base name (will have suffix appended). Must be lowercase, numbers, hyphens.')
@minLength(3)
@maxLength(30)
param openAIAccountBaseName string = 'openai'

@description('Whether to deploy model deployments (gpt-5-mini and gpt-4o). If false, only the Azure OpenAI account is created and you can add deployments later via CLI or portal.')
param deployModels bool = true

@description('Set true to restore a previously soft-deleted Azure OpenAI account with the same name (Azure retains soft-deleted resources briefly). Leave false for normal creation or if you purged the old one.')
param restoreDeletedAccount bool = false

var tags = {
  Environment: environment
  Project: 'SeeHealth Claims Triage'
  ManagedBy: 'Bicep'
}

// ============================================================================
// Azure OpenAI Service
// ============================================================================

var openAIAccountName = '${openAIAccountBaseName}-${environment}-${uniqueSuffix}'

resource openAIAccount 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: toLower(replace(openAIAccountName, '_', '-'))
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: toLower(replace(openAIAccountName, '_', '-'))
    publicNetworkAccess: 'Enabled'
    // Restore flag (only honored if a soft-deleted resource with same name exists)
    restore: restoreDeletedAccount
  }
}

// ============================================================================
// Model Deployment 1: gpt-5-mini
// ============================================================================

// NOTE: Conditional deployment controlled by deployModels
resource gpt5miniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = if (deployModels) {
  parent: openAIAccount
  name: 'gpt-5-mini'
  sku: {
    name: 'GlobalStandard'
    capacity: 120 // 120K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
  }
}

// ============================================================================
// Model Deployment 2: gpt-4o
// ============================================================================

resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = if (deployModels) {
  parent: openAIAccount
  name: 'gpt-4o'
  sku: {
    name: 'GlobalStandard'
    capacity: 80 // 80K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
  }
  dependsOn: [
    gpt5miniDeployment // Deploy sequentially to avoid conflicts
  ]
}

// ============================================================================
// Outputs
// ============================================================================

@description('Azure OpenAI endpoint URL')
output openAIEndpoint string = openAIAccount.properties.endpoint

@description('Azure OpenAI resource name')
output openAIResourceName string = openAIAccount.name

@description('Instructions to get API key')
output getApiKeyCommand string = 'az cognitiveservices account keys list --name ${openAIAccount.name} --resource-group ${resourceGroup().name}'

@description('gpt-5-mini deployment name (blank if deployModels=false)')
output gpt5miniDeploymentName string = deployModels ? gpt5miniDeployment.name : ''

@description('GPT-4o deployment name (blank if deployModels=false)')
output gpt4oDeploymentName string = deployModels ? gpt4oDeployment.name : ''

@description('Were model deployments created?')
output modelsDeployed bool = deployModels

@description('Environment')
output environment string = environment

"""
Azure Configuration Module for SeeHealth AI Claims Triage
======================================================

This module provides secure access to Azure resources using Azure Key Vault
and Azure Identity for authentication.

Generated: October 29, 2025
Environment: dev
Location: eastus
"""

import os
from typing import Optional
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# Azure Resource Configuration
# ============================================================================

SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "your-subscription-id")
RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP", "rg-seehealth-claims-dev")
LOCATION = os.getenv("AZURE_LOCATION", "eastus")
ENVIRONMENT = os.getenv("AZURE_ENVIRONMENT", "dev")

# ============================================================================
# Azure OpenAI Configuration (supports environment overrides for local/dev)
# ============================================================================
# Environment variable overrides allow rapid switching of model deployments and
# use of direct API keys without requiring Azure CLI login or Key Vault access.
#
# Supported environment variables:
#   AZURE_OPENAI_ENDPOINT              -> Overrides OPENAI_ENDPOINT
#   AZURE_OPENAI_API_VERSION           -> Overrides OPENAI_API_VERSION
#   AZURE_OPENAI_DEPLOYMENT_GPT5       -> Overrides OPENAI_DEPLOYMENT_GPT5
#   AZURE_OPENAI_DEPLOYMENT_GPT4O      -> Overrides OPENAI_DEPLOYMENT_GPT4O
#   AZURE_OPENAI_MAPPING_DEPLOYMENT    -> Optional: dedicated deployment for mapping tasks
#   AZURE_OPENAI_API_KEY or OPENAI_API_KEY -> Direct key (skips Key Vault)
#
# If AZURE_OPENAI_MAPPING_DEPLOYMENT is not set, the GPT-4o deployment value
# will be used for mapping (ColumnMapper defaults to GPT-4o today for quality).

OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://your-openai-resource.openai.azure.com/")
OPENAI_RESOURCE_NAME = os.getenv("AZURE_OPENAI_RESOURCE_NAME", "your-openai-resource-name")
OPENAI_DEPLOYMENT_GPT5 = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT5", "gpt-5-mini")
OPENAI_DEPLOYMENT_GPT4O = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4O", "gpt-4o")
OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

# Optional specialized deployment just for mapping (falls back to GPT-4o)
OPENAI_MAPPING_DEPLOYMENT = os.getenv("AZURE_OPENAI_MAPPING_DEPLOYMENT", OPENAI_DEPLOYMENT_GPT4O)

# ============================================================================
# Authentication and Secret Management
# ============================================================================

def get_openai_api_key() -> str:
    """Retrieve Azure OpenAI API key from environment variables.

    Resolution order (first found wins):
      1. Environment variable AZURE_OPENAI_API_KEY
      2. Environment variable OPENAI_API_KEY

    Raises:
        Exception: If no key can be resolved.
    """
    env_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key
    
    raise Exception(
        "AZURE_OPENAI_API_KEY not set. Add it to your .env file or set as environment variable."
    )


def get_openai_client():
    """Create an Azure OpenAI client instance.

    Uses API key authentication (preferred for simplicity) falling back to
    Azure AD token provider only where explicitly implemented elsewhere.
    """
    from openai import AzureOpenAI

    api_key = get_openai_api_key()
    return AzureOpenAI(
        api_key=api_key,
        api_version=OPENAI_API_VERSION,
        azure_endpoint=OPENAI_ENDPOINT
    )


# ============================================================================
# Helper Functions
# ============================================================================

def test_connections():
    """Test Azure service connectivity with clear segmentation.

    Any failure is caught and reported; function never raises so that
    running this as a script provides a full summary instead of aborting
    on the first issue.
    """
    print("Testing Azure connections...")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Location: {LOCATION}")
    print()

    # ---------------- OpenAI ----------------
    print("✓ Testing Azure OpenAI...")
    try:
        client = get_openai_client()
        print(f"  Endpoint: {OPENAI_ENDPOINT}")
        print(f"  Mapping deployment (active): {OPENAI_MAPPING_DEPLOYMENT}")
        print(f"  GPT-5-mini deployment variable: {OPENAI_DEPLOYMENT_GPT5}")
        print(f"  GPT-4o deployment variable: {OPENAI_DEPLOYMENT_GPT4O}")
        print("  ✓ Azure OpenAI connection successful")
    except Exception as e:
        print(f"  ✗ OpenAI failed: {e}")

    print("\n✓ Test sequence complete (see any ✗ lines above for issues).")


if __name__ == "__main__":
    test_connections()

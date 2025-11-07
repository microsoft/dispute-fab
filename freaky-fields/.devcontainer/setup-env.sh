#!/usr/bin/env bash
set -euo pipefail

# Generate backend .env from existing Codespaces env variables if not present.
# Align variable names with api_server expectations (AZURE_OPENAI_DEPLOYMENT_GPT4O / GPT5).
if [ ! -f .env ]; then
  echo "Creating backend .env from environment variables (no echo of secret values)..."
  {
    echo "AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY:-}";                     # secret
    echo "AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT:-}";                 # endpoint (non-secret)
    echo "AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION:-2024-08-01-preview}"; # version (non-secret)
    echo "AZURE_OPENAI_DEPLOYMENT_GPT4O=${AZURE_OPENAI_DEPLOYMENT_GPT4O:-gpt-4o}";     # model deployment name
    echo "AZURE_OPENAI_DEPLOYMENT_GPT5=${AZURE_OPENAI_DEPLOYMENT_GPT5:-gpt-5-mini}";   # optional second model
    echo "LOG_LEVEL=${LOG_LEVEL:-INFO}";
  } > .env
fi

# Generate frontend .env if not present.
if [ ! -f frontend/.env ]; then
  echo "Creating frontend/.env from environment variables..."
  {
    echo "VITE_API_BASE=${VITE_API_BASE:-http://localhost:8000}";
    echo "VITE_AI_SUMMARY_ENDPOINT=${VITE_AI_SUMMARY_ENDPOINT:-/api/claim-summary}";
    echo "VITE_AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT:-}";
    echo "VITE_AZURE_OPENAI_MODEL=${AZURE_OPENAI_DEPLOYMENT_GPT4O:-gpt-4o}";
    echo "VITE_AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION:-2024-08-01-preview}";
    echo "VITE_APP_ENV=${AZURE_ENVIRONMENT:-dev}";
  } > frontend/.env
fi

# Permissions fix (Codespaces sometimes sets root ownership for generated files)
chown vscode:vscode .env frontend/.env || true

echo "Environment setup complete."
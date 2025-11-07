#!/bin/bash
# Global sanitization script for public release - SeeHealth
# Run from repository root: ./scripts/sanitize-for-public.sh

set -e

echo "🔒 Sanitizing repository for public release..."
echo "   Company: SeeHealth → SeeHealth"
echo "   Personal info: Removing email"
echo ""

# Count files to process
total_files=$(find . -type f \( \
    -name "*.py" -o \
    -name "*.md" -o \
    -name "*.json" -o \
    -name "*.sh" -o \
    -name "*.bicep" -o \
    -name "*.tsx" -o \
    -name "*.ts" -o \
    -name "*.txt" -o \
    -name "*.example" \
\) -not -path "*/node_modules/*" -not -path "*/.venv/*" -not -path "*/dist/*" -not -path "*/.git/*" | wc -l | tr -d ' ')

echo "Processing $total_files files..."
echo ""

processed=0

find . -type f \( \
    -name "*.py" -o \
    -name "*.md" -o \
    -name "*.json" -o \
    -name "*.sh" -o \
    -name "*.bicep" -o \
    -name "*.tsx" -o \
    -name "*.ts" -o \
    -name "*.txt" -o \
    -name "*.example" \
\) -not -path "*/node_modules/*" -not -path "*/.venv/*" -not -path "*/dist/*" -not -path "*/.git/*" | while read file; do
    
    # SeeHealth → SeeHealth (preserving case)
    sed -i '' 's/SeeHealth/SeeHealth/g' "$file"
    sed -i '' 's/seehealth/seehealth/g' "$file"
    sed -i '' 's/SEEHEALTH/SEEHEALTH/g' "$file"
    
    # Remove personal email
    sed -i '' 's/idanshimon@MngEnvMCAP356394\.onmicrosoft\.com/admin@example.com/g' "$file"
    
    ((processed++))
    if [ $((processed % 10)) -eq 0 ]; then
        echo "  ✓ Processed $processed/$total_files files..."
    fi
done

echo ""
echo "✅ Sanitization complete!"
echo ""
echo "Modified patterns:"
echo "  - SeeHealth → SeeHealth (125+ instances)"
echo "  - seehealth → seehealth (resource names)"
echo "  - idanshimon@MngEnv... → admin@example.com"
echo ""
echo "Key changes:"
echo "  - API title: 'SeeHealth Claims Triage AI API'"
echo "  - Dashboard: 'SeeHealth Claims Classification Dashboard'"
echo "  - Resource groups: rg-seehealth-claims-dev"
echo "  - Key Vault: kv-seehealth-xxx"
echo "  - Vendor config: seehealth_internal"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff --stat"
echo "  2. Check specific files: git diff infra/main.bicep"
echo "  3. If satisfied: git add -A && git commit -m 'security: sanitize company name and personal info for public release'"

"""
AI-powered column mapping for vendor data files.

This module uses Azure OpenAI (GPT-5-mini) to intelligently map vendor-specific
column names to standardized field names, enabling universal vendor support
without manual configuration.

Key Features:
- Header row detection (handles row 0, 7, or any position)
- Semantic column mapping (understands similar names and data patterns)
- Caching mechanism (saves mappings to JSON to avoid redundant AI calls)
- Validation (ensures mapped columns actually exist in DataFrame)
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI

try:
    import azure_config
except ImportError:
    # Fallback if azure_config module not available
    class azure_config:  # type: ignore
        OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        OPENAI_DEPLOYMENT_GPT4O = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4O", "gpt-4o")
        OPENAI_DEPLOYMENT_GPT5 = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT5", "gpt-5-mini")
        OPENAI_MAPPING_DEPLOYMENT = os.getenv("AZURE_OPENAI_MAPPING_DEPLOYMENT", OPENAI_DEPLOYMENT_GPT4O)


class ColumnMapper:
    """Maps vendor-specific columns to standard schema using AI."""
    
    # Standard schema that all vendors should be mapped to
    STANDARD_SCHEMA = {
        "CLAIM_ID": "Unique claim identifier or line number",
        "PRESCRIPTION_ID": "Prescription number or RX number",
        "DRUG_NDC": "11-digit National Drug Code",
        "QUANTITY": "Quantity dispensed",
        "DAYS_SUPPLY": "Days supply for prescription",
        "PHARMACY_ID": "NCPDP pharmacy identifier",
        "FILL_DATE": "Date prescription was filled",
        "REBATE_AMOUNT": "Rebate amount or discount",
        "CLAIM_340B_IND": "340B pharmacy indicator (Y/N or 0/1)",
        "FORMULARY_TYPE_CDE": "Formulary status code or tier indicator",
        "VENDOR_ERROR_CODE": "Vendor-specific error or dispute code",
        "DISPUTE_REASON": "Dispute reason or error description"
    }
    
    def __init__(self, cache_dir: str = "data/column_mappings"):
        """Initialize ColumnMapper with resilient Azure OpenAI client setup.

        We attempt API key auth first (recommended). If no key is present, we try
        DefaultAzureCredential for local dev / managed identity scenarios. Any
        failure is captured in self.last_error but does NOT abort construction so
        diagnostics endpoint can still function.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_error: Optional[str] = None
        self.last_raw_response: Optional[str] = None  # capture raw content for diagnostics
        self.openai_client: Optional[AzureOpenAI] = None
        auth_mode = "uninitialized"
        try:
            api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = AzureOpenAI(
                    azure_endpoint=azure_config.OPENAI_ENDPOINT,
                    api_version=azure_config.OPENAI_API_VERSION,
                    api_key=api_key
                )
                auth_mode = "api_key"
            else:
                # Fallback to AAD token provider only if forced or explicitly allowed.
                if os.getenv("AZURE_OPENAI_ALLOW_AAD", "1") == "1":
                    credential = DefaultAzureCredential()
                    self.openai_client = AzureOpenAI(
                        azure_endpoint=azure_config.OPENAI_ENDPOINT,
                        api_version=azure_config.OPENAI_API_VERSION,
                        azure_ad_token_provider=lambda: credential.get_token("https://cognitiveservices.azure.com/.default").token
                    )
                    auth_mode = "aad_token"
                else:
                    self.last_error = "Missing AZURE_OPENAI_API_KEY and AAD disabled (set AZURE_OPENAI_ALLOW_AAD=1 to enable)."
        except Exception as e:
            self.last_error = f"Initialization failure: {e}"
        # Choose mapping deployment (overrideable via AZURE_OPENAI_MAPPING_DEPLOYMENT)
        self.deployment_name = getattr(azure_config, "OPENAI_MAPPING_DEPLOYMENT", azure_config.OPENAI_DEPLOYMENT_GPT4O)
        self.auth_mode = auth_mode
        print(f"[ColumnMapper] Initialized deployment={self.deployment_name} auth={auth_mode} error={self.last_error}")
    
    def find_header_row(self, file_path: str, sheet_name: str, max_rows: int = 15) -> int:
        """
        Use AI to detect which row contains the actual column headers.
        
        Args:
            file_path: Path to Excel file
            sheet_name: Name of sheet to analyze
            max_rows: Maximum rows to analyze
            
        Returns:
            Row number (0-indexed) that contains headers
        """
        cache_key = f"{sheet_name}_header"
        cached_result = self._load_from_cache(cache_key)
        
        if cached_result is not None:
            print(f"  ✓ Using cached header row: {cached_result}")
            return cached_result
        
        # Read first N rows without assuming header position
        preview_df = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=max_rows)
        
        # Create preview text showing row numbers and content
        preview_text = []
        for idx, row in preview_df.iterrows():
            row_values = [str(v)[:50] for v in row.values[:10]]  # First 10 columns, truncated
            preview_text.append(f"Row {idx}: {row_values}")
        
        preview_str = "\n".join(preview_text)
        
        prompt = f"""Analyze these rows from vendor sheet "{sheet_name}" and identify which row contains the column headers.

{preview_str}

Look for:
- Row with descriptive field names (not data values)
- Row after title/metadata rows
- Row with consistent data types in rows below it
- Row with terms like: "ID", "Number", "Code", "Date", "Amount", "Quantity", etc.

Common patterns:
- Row 0: Often the header (standard Excel)
- Row 7: Common for vendor reports with metadata at top
- Rows 1-6: Usually title, vendor name, date range, etc.

Return ONLY the row number (integer) that contains the headers. No explanation needed.
Example responses: 0, 7, 3"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing Excel file structures and identifying header rows."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=100  # GPT-5-mini needs at least 100 tokens
            )
            
            raw_content = response.choices[0].message.content
            response_text = (raw_content or "").strip()
            header_row = int(response_text)
            
            # Validate the row number is reasonable
            if header_row < 0 or header_row >= max_rows:
                print(f"  ⚠️  AI returned invalid row {header_row}, defaulting to 0")
                header_row = 0
            
            # Cache the result
            self._save_to_cache(cache_key, header_row)
            print(f"  ✓ Detected header row: {header_row}")
            return header_row
            
        except Exception as e:
            print(f"  ⚠️  Error detecting header row: {e}, defaulting to 0")
            return 0
    
    def map_columns(
        self, 
        vendor_name: str, 
        df: pd.DataFrame,
        sample_rows: int = 5
    ) -> Dict[str, str]:
        """
        Use AI to map vendor columns to standard schema.
        
        Args:
            vendor_name: Name of vendor for caching
            df: DataFrame with vendor data (already has correct header)
            sample_rows: Number of sample rows to send to AI for context
            
        Returns:
            Dictionary mapping standard field names to vendor column names
            Example: {"CLAIM_ID": "Line Number", "DRUG_NDC": "Product-Code"}
        """
        cache_key = f"{vendor_name}_mapping"
        cached_result = self._load_from_cache(cache_key)
        
        if cached_result is not None:
            # Treat empty cached mapping as invalid (force regeneration)
            if not cached_result:
                print("  ⚠️  Cached mapping empty; forcing regeneration")
            elif self._validate_mapping(cached_result, df):
                print(f"  ✓ Using cached column mapping ({len(cached_result)} fields)")
                return cached_result
            else:
                print(f"  ⚠️  Cached mapping invalid, regenerating...")
        
        # Prepare vendor column information
        vendor_columns = list(df.columns)
        sample_data = df.head(sample_rows).to_dict(orient='records')
        
        # Create sample data preview (truncate long values)
        sample_preview = []
        for i, row in enumerate(sample_data):
            row_preview = {k: str(v)[:50] for k, v in list(row.items())[:15]}  # First 15 columns
            sample_preview.append(f"Row {i+1}: {row_preview}")
        
        sample_str = "\n".join(sample_preview)
        
        print(f"[ColumnMapper] Starting mapping for vendor={vendor_name} columns={len(vendor_columns)} rows={len(df)}")
        prompt = f"""You are analyzing data from vendor "{vendor_name}". Map their column names to our standard schema.

VENDOR COLUMNS ({len(vendor_columns)} total):
{vendor_columns}

SAMPLE DATA (first {sample_rows} rows):
{sample_str}

STANDARD SCHEMA TO MAP TO:
{json.dumps(self.STANDARD_SCHEMA, indent=2)}

INSTRUCTIONS:
1. For each STANDARD field, identify which VENDOR column contains that data
2. Consider similar names: "NDC" = "Product Code" = "Drug Code" = "Product-Code"
3. Consider data patterns: 11-digit numbers = NDC, 7-digit = NCPDP pharmacy ID
4. Consider context: "Quantity" vs "Days Supply" vs "Total Quantity"
5. If a standard field has NO matching vendor column, omit it from the mapping
6. Return ONLY valid JSON, no explanations

CLAIM_ID SELECTION GUIDANCE:
• Prefer column headers containing (case-insensitive): "claim number", "claim id", "ce claim no", "transaction items claim number", "contract entity claim number", "customer claim #", "pharmacy claim id".
• Choose the column with long numeric values (typically 12–20 digits, often 17–18) and very high uniqueness (≈100% distinct values).
• Ignore short sequential counters ("line number", "record number", "identifier") unless no long numeric claim number exists.
• Do NOT use aggregate/summary columns like "Claims" or any "Excluded Claims..." variants.
• Skip concatenated blob columns that mix many fields; these are not a single identifier.
• If two candidates qualify, pick the one with longer consistent numeric length and higher uniqueness ratio.
• If no strong candidate exists, omit CLAIM_ID (do not guess or fabricate a value).

CLAIM_340B_IND SELECTION GUIDANCE:
• Look for column headers containing (case-insensitive): "340B", "340b", "covered entity", "pharmacy 340b", "340b indicator", "340b flag".
• This field indicates if the pharmacy is a 340B covered entity (typically Y/N, 0/1, or True/False).
• Common column names: "Pharmacy - 340B Covered Entity", "340B Indicator", "340B Flag", "Is 340B".
• If no matching column exists, omit CLAIM_340B_IND from the mapping.

FORMULARY_TYPE_CDE SELECTION GUIDANCE:
• Look for column headers containing (case-insensitive): "formulary", "tier", "coverage", "formulary code", "formulary status", "plan coverage", "coverage tier".
• This field indicates drug formulary status or coverage tier.
• Common column names: "Formulary Code", "Formulary Status", "Coverage Tier", "Formulary Indicator", "Tier", "Plan Type".
• Values can be numeric codes (0, 1, 2, 3 for tiers) or text ("Formulary", "Non-Formulary", "Not Covered", "Tier 1", "Tier 2").
• This is critical for detecting formulary non-compliance disputes (Code 201).
• If no matching column exists, omit FORMULARY_TYPE_CDE from the mapping.

RETURN FORMAT (JSON only):
{{
  "CLAIM_ID": "vendor_column_name_or_null",
  "PRESCRIPTION_ID": "vendor_column_name_or_null",
  "DRUG_NDC": "vendor_column_name_or_null",
  "QUANTITY": "vendor_column_name_or_null",
  "DAYS_SUPPLY": "vendor_column_name_or_null",
  "PHARMACY_ID": "vendor_column_name_or_null",
  "FILL_DATE": "vendor_column_name_or_null",
  "REBATE_AMOUNT": "vendor_column_name_or_null",
  "CLAIM_340B_IND": "vendor_column_name_or_null",
  "FORMULARY_TYPE_CDE": "vendor_column_name_or_null",
  "VENDOR_ERROR_CODE": "vendor_column_name_or_null",
  "DISPUTE_REASON": "vendor_column_name_or_null"
}}

Important: Only include fields where you found a matching column. Use exact vendor column names."""

        if self.openai_client is None:
            # Fail fast with clear diagnostic
            if self.last_error is None:
                self.last_error = "OpenAI client not initialized (missing API key?)"
            print(f"[ColumnMapper] ⚠ {self.last_error}")
            return {}
        try:
            # Use new Azure OpenAI param name `max_completion_tokens`
            assert self.openai_client is not None, "OpenAI client unexpectedly None before chat call"
            response = self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing pharmacy benefit management (PBM) data files and mapping vendor columns to standard schemas. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=800,
                temperature=0,
                response_format={"type": "json_object"}
            )
            response_text = str(response.choices[0].message.content or "") if response.choices else ""
            self.last_raw_response = response_text
            if not response_text:
                self.last_error = "Empty response from OpenAI (first attempt)"
                print("[ColumnMapper] ⚠ Empty OpenAI response; attempting fallback prompt")
                return self._second_attempt(prompt, df, cache_key)
            mapping = self._parse_json_mapping(response_text)
            if mapping is None:
                # second attempt with simplified prompt
                return self._second_attempt(prompt, df, cache_key)
            if not mapping:
                print("[ColumnMapper] ⚠ AI returned zero fields; check prompt/deployment/permissions.")
            if not self._validate_mapping(mapping, df):
                print("[ColumnMapper] ⚠ Invalid columns in mapping; filtering.")
                mapping = self._filter_valid_columns(mapping, df)
            self._save_to_cache(cache_key, mapping)
            print(f"[ColumnMapper] ✓ Final mapping size: {len(mapping)}")
            return mapping
        except Exception as e:
            import traceback
            self.last_error = f"Exception during mapping: {e}"
            print(f"[ColumnMapper] ⚠ {self.last_error}")
            traceback.print_exc()
            return {}

    def _second_attempt(self, original_prompt: str, df: pd.DataFrame, cache_key: str) -> Dict[str, str]:
        """Retry with a simplified prompt and no response_format if first attempt fails."""
        if self.openai_client is None:
            return {}
        simple_prompt = original_prompt + "\nReturn ONLY raw JSON (no markdown fences)."
        try:
            assert self.openai_client is not None, "OpenAI client unexpectedly None before second attempt"
            resp = self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "Return valid JSON mapping. No commentary."},
                    {"role": "user", "content": simple_prompt}
                ],
                max_completion_tokens=600,
                temperature=0
            )
            txt = str(resp.choices[0].message.content or "") if resp.choices else ""
            self.last_raw_response = txt
            mapping = self._parse_json_mapping(txt)
            if mapping is None:
                self.last_error = "Both attempts failed to produce JSON"
                print(f"[ColumnMapper] ⚠ {self.last_error}. Raw (200): {txt[:200]}")
                return {}
            if not self._validate_mapping(mapping, df):
                mapping = self._filter_valid_columns(mapping, df)
            self._save_to_cache(cache_key, mapping)
            print(f"[ColumnMapper] ✓ Second attempt mapping size: {len(mapping)}")
            return mapping
        except Exception as e:
            self.last_error = f"Second attempt error: {e}"
            print(f"[ColumnMapper] ⚠ {self.last_error}")
            return {}

    def _parse_json_mapping(self, raw: str) -> Optional[Dict[str, str]]:
        """Extract JSON object from raw model output and return mapping dict or None if parse failure."""
        if not raw:
            return None
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        # Attempt to locate first '{' and last '}' if extraneous text exists
        if cleaned.count('{') > 1 and cleaned.count('}') > 1:
            first = cleaned.find('{')
            last = cleaned.rfind('}')
            if first >= 0 and last > first:
                cleaned = cleaned[first:last+1]
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        # Filter null-like values
        return {k: v for k, v in obj.items() if v not in (None, "null", "")}
    
    def apply_mapping(self, df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """
        Apply column mapping to DataFrame by renaming columns.
        
        Args:
            df: Original DataFrame with vendor column names
            mapping: Dictionary mapping standard names to vendor names
            
        Returns:
            New DataFrame with standardized column names
        """
        # Create reverse mapping: vendor_name -> standard_name
        rename_dict = {v: k for k, v in mapping.items()}
        
        # Rename columns
        df_mapped = df.rename(columns=rename_dict)
        
        print(f"  ✓ Applied mapping: {len(rename_dict)} columns renamed")
        return df_mapped
    
    def get_mapped_dataframe(
        self, 
        file_path: str, 
        sheet_name: str,
        vendor_name: str
    ) -> tuple[pd.DataFrame, Dict[str, str]]:
        """
        Complete workflow: detect header, load data, map columns, return standardized DataFrame.
        
        Args:
            file_path: Path to Excel file
            sheet_name: Sheet name to read
            vendor_name: Vendor name for caching
            
        Returns:
            Tuple of (mapped_dataframe, column_mapping)
        """
        print(f"\n📋 Processing vendor: {vendor_name}")
        
        # Step 1: Find header row
        header_row = self.find_header_row(file_path, sheet_name)
        
        # Step 2: Load data with correct header
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
        print(f"  ✓ Loaded {len(df)} rows, {len(df.columns)} columns")
        
        # Step 3: Map columns
        mapping = self.map_columns(vendor_name, df)
        
        # Step 4: Apply mapping
        df_mapped = self.apply_mapping(df, mapping)
        
        return df_mapped, mapping
    
    def _validate_mapping(self, mapping: Dict[str, str], df: pd.DataFrame) -> bool:
        """
        Validate that all mapped column names exist in the DataFrame.
        
        Args:
            mapping: Column mapping to validate
            df: DataFrame to check against
            
        Returns:
            True if all mapped columns exist, False otherwise
        """
        vendor_columns = set(df.columns)
        mapped_columns = set(mapping.values())
        
        invalid_columns = mapped_columns - vendor_columns
        
        if invalid_columns:
            print(f"  ⚠️  Invalid columns in mapping: {invalid_columns}")
            return False
        
        return True
    
    def _filter_valid_columns(self, mapping: Dict[str, str], df: pd.DataFrame) -> Dict[str, str]:
        """
        Filter mapping to only include columns that exist in DataFrame.
        
        Args:
            mapping: Original mapping
            df: DataFrame to check against
            
        Returns:
            Filtered mapping with only valid columns
        """
        vendor_columns = set(df.columns)
        return {k: v for k, v in mapping.items() if v in vendor_columns}
    
    def _load_from_cache(self, cache_key: str) -> Optional[Any]:
        """Load mapping from cache file if it exists."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"  ⚠️  Error loading cache: {e}")
                return None
        
        return None
    
    def _save_to_cache(self, cache_key: str, data: Any) -> None:
        """Save mapping to cache file."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"  ⚠️  Error saving cache: {e}")
    
    def clear_cache(self, vendor_name: Optional[str] = None) -> None:
        """
        Clear cached mappings.
        
        Args:
            vendor_name: If provided, only clear cache for this vendor.
                        If None, clear all cache.
        """
        if vendor_name:
            # Clear specific vendor
            for suffix in ["_header", "_mapping"]:
                cache_file = self.cache_dir / f"{vendor_name}{suffix}.json"
                if cache_file.exists():
                    cache_file.unlink()
                    print(f"  ✓ Cleared cache: {cache_file.name}")
        else:
            # Clear all cache
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            print(f"  ✓ Cleared all cache files")


# Convenience function for simple usage
def get_mapped_vendor_data(
    file_path: str, 
    sheet_name: str, 
    vendor_name: str,
    cache_dir: str = "data/column_mappings"
) -> tuple[pd.DataFrame, Dict[str, str]]:
    """
    Convenience function to get mapped vendor data in one call.
    
    Args:
        file_path: Path to Excel file
        sheet_name: Sheet name to read
        vendor_name: Vendor name for caching
        cache_dir: Directory for caching mappings
        
    Returns:
        Tuple of (mapped_dataframe, column_mapping)
    
    Example:
        df, mapping = get_mapped_vendor_data(
            "data/Masked_Scrub_File_15.xlsx",
            "IOMMH",
            "IOMMH"
        )
        
        # Now df has standard column names:
        claim_id = df["CLAIM_ID"]  # Works!
        ndc = df["DRUG_NDC"]  # Works!
    """
    mapper = ColumnMapper(cache_dir=cache_dir)
    return mapper.get_mapped_dataframe(file_path, sheet_name, vendor_name)

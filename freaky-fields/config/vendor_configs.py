"""
Vendor Configuration Definitions

Defines all vendor-specific settings for data normalization and processing.
Each vendor may have unique file formats, header rows, boolean flags, and
crosswalk tables.

Based on: Technical & Business Logic Specs
Date: October 29, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

from core.dispute_categories import DisputeCategory


@dataclass
class VendorConfig:
    """
    Configuration for vendor-specific data processing.
    
    Attributes:
        vendor_key: Unique identifier for vendor (e.g., "cvs", "walgreens")
        vendor_name: Human-readable vendor name
        file_pattern: Glob pattern to match vendor files (e.g., "*CVS*.xlsx")
        header_row_index: Row index where actual column headers start (0-based)
        crosswalk_table: Filename of vendor-specific crosswalk table
        boolean_flags: Dict mapping boolean flag column names to categories
        column_mappings: Dict mapping vendor column names to standard schema
        required_columns: List of columns that must be present
        skip_rows_top: Number of rows to skip at top of file
        skip_rows_bottom: Number of rows to skip at bottom of file
        sheet_name: Excel sheet name (if specific sheet needed)
    """
    vendor_key: str
    vendor_name: str
    file_pattern: str
    header_row_index: int = 0
    crosswalk_table: Optional[str] = None
    boolean_flags: Dict[str, DisputeCategory] = field(default_factory=dict)
    column_mappings: Dict[str, str] = field(default_factory=dict)
    required_columns: List[str] = field(default_factory=list)
    skip_rows_top: int = 0
    skip_rows_bottom: int = 0
    sheet_name: Optional[str] = None
    notes: str = ""


# ============================================================================
# VENDOR CONFIGURATIONS
# ============================================================================
# Add/modify vendor configurations as new vendors are onboarded

VENDOR_CONFIGS: Dict[str, VendorConfig] = {
    
    # CVS Health
    "cvs": VendorConfig(
        vendor_key="cvs",
        vendor_name="CVS Health",
        file_pattern="*CVS*.xlsx",
        header_row_index=7,  # Skip first 7 rows of report metadata
        crosswalk_table="cvs_crosswalk.xlsx",
        boolean_flags={
            "340B_Flag": DisputeCategory.CLAIM_340B,
            "Formulary_Exception": DisputeCategory.FORMULARY_VIOLATION,
        },
        column_mappings={
            "Client Name": "CLIENT_NAME",
            "Provider Name": "PROVIDER_NAME",
            "NCPDP ID": "NCPDP_ID",
            "NPI": "NPI",
            "Paid Amt": "PAID_AMOUNT",
            "Rebate Transaction ID": "TRANSACTION_ID",
        },
        required_columns=["PHCY_CLAIM_ID", "RX_NBR", "FILL_NDC_NBR", "SERVICED_DTE"],
        notes="CVS files have 7-row header with report metadata. Uses crosswalk for most categories."
    ),
    
    # Walgreens
    "walgreens": VendorConfig(
        vendor_key="walgreens",
        vendor_name="Walgreens",
        file_pattern="*Walgreens*.xlsx",
        header_row_index=0,  # Standard header row
        crosswalk_table="walgreens_crosswalk.xlsx",
        boolean_flags={
            "Is340B": DisputeCategory.CLAIM_340B,
            "IsDuplicate": DisputeCategory.DUPLICATE_CLAIM,
        },
        column_mappings={
            "Prescription Number": "RX_NBR",
            "NDC": "FILL_NDC_NBR",
            "Service Date": "SERVICED_DTE",
            "Pharmacy ID": "PHCY_PROVIDER_ID",
        },
        required_columns=["RX_NBR", "NDC", "Service Date"],
        notes="Walgreens uses boolean flags for 340B and duplicates."
    ),
    
    # Express Scripts
    "express_scripts": VendorConfig(
        vendor_key="express_scripts",
        vendor_name="Express Scripts",
        file_pattern="*ExpressScripts*.xlsx",
        header_row_index=5,  # Skip report header
        crosswalk_table="express_scripts_crosswalk.xlsx",
        boolean_flags={},  # No boolean flags, uses crosswalk only
        column_mappings={
            "Claim ID": "PHCY_CLAIM_ID",
            "Rx Number": "RX_NBR",
            "Drug Code": "FILL_NDC_NBR",
            "Fill Date": "SERVICED_DTE",
            "Error Code": "VENDOR_ERROR_CODE",
        },
        required_columns=["Claim ID", "Rx Number", "Drug Code"],
        notes="Express Scripts relies entirely on crosswalk lookups."
    ),
    
    # OptumRx
    "optum": VendorConfig(
        vendor_key="optum",
        vendor_name="OptumRx",
        file_pattern="*Optum*.xlsx",
        header_row_index=2,
        crosswalk_table="optum_crosswalk.xlsx",
        boolean_flags={
            "340B_Indicator": DisputeCategory.CLAIM_340B,
        },
        column_mappings={
            "Claim Number": "PHCY_CLAIM_ID",
            "Prescription #": "RX_NBR",
            "NDC Number": "FILL_NDC_NBR",
            "Date of Service": "SERVICED_DTE",
        },
        required_columns=["Claim Number", "NDC Number"],
        notes="OptumRx has 2-row header. Combines boolean flags with crosswalk."
    ),
    
    # SeeHealth (internal)
    "seehealth_internal": VendorConfig(
        vendor_key="seehealth_internal",
        vendor_name="SeeHealth Internal",
        file_pattern="*Masked_Invoice*.csv",
        header_row_index=0,  # CSV has normal headers
        crosswalk_table="seehealth_crosswalk.xlsx",
        boolean_flags={
            "CLAIM_340B_IND": DisputeCategory.CLAIM_340B,  # Direct 340B indicator
        },
        column_mappings={
            "PHCY_CLAIM_ID": "CLAIM_ID",
            "FILL_NDC_NBR": "DRUG_NDC",
            "FILL_QTY": "DISPENSED_QUANTITY",
            "INFERRED_FILL_QTY": "INFERRED_QUANTITY",
            "RX_NBR": "RX_NUMBER",
            "SERVICED_DTE": "SERVICE_DATE",
            "FORMULARY_TYPE_CDE": "FORMULARY_STATUS",
            "PRICE_AMT": "BILLED_AMOUNT",
            "TOTAL_REBATE_AMT": "ALLOWED_AMOUNT",
            "FILL_PHCY_PROVIDER_ROW_ID": "PROVIDER_NPI",
        },
        required_columns=["CLAIM_ID", "DRUG_NDC"],  # Use STANDARD names (after mapping)
        notes="Internal SeeHealth format from invoice claims extract. Has direct 340B indicator column."
    ),
    
    # Humana
    "humana": VendorConfig(
        vendor_key="humana",
        vendor_name="Humana",
        file_pattern="*Humana*.xlsx",
        header_row_index=0,
        crosswalk_table="humana_crosswalk.xlsx",
        boolean_flags={
            "ThreeFortyB_Flag": DisputeCategory.CLAIM_340B,
            "Medicaid_Flag": DisputeCategory.MEDICAID_EXCLUSION,
        },
        column_mappings={},
        required_columns=["ClaimID", "RxNumber", "NDC"],
        notes="Humana uses multiple boolean flags for quick categorization."
    ),
    
    # Anthem/Elevance
    "anthem": VendorConfig(
        vendor_key="anthem",
        vendor_name="Anthem/Elevance",
        file_pattern="*Anthem*.xlsx",
        header_row_index=3,
        crosswalk_table="anthem_crosswalk.xlsx",
        boolean_flags={},
        column_mappings={},
        required_columns=["CLAIM_ID", "RX_NUMBER"],
        notes="Anthem files have variable header structures. May need sheet-specific config."
    ),
    
    # Aetna
    "aetna": VendorConfig(
        vendor_key="aetna",
        vendor_name="Aetna",
        file_pattern="*Aetna*.xlsx",
        header_row_index=0,
        crosswalk_table="aetna_crosswalk.xlsx",
        boolean_flags={},
        column_mappings={},
        required_columns=["Claim_ID"],
        notes="Aetna has clean file format with standard headers."
    ),
    
    # UnitedHealthcare
    "united": VendorConfig(
        vendor_key="united",
        vendor_name="UnitedHealthcare",
        file_pattern="*United*.xlsx",
        header_row_index=1,
        crosswalk_table="united_crosswalk.xlsx",
        boolean_flags={
            "340B": DisputeCategory.CLAIM_340B,
        },
        column_mappings={},
        required_columns=["ClaimNumber"],
        notes="UHC format is relatively standard with 1-row header."
    ),
    
    # Prime Therapeutics
    "prime": VendorConfig(
        vendor_key="prime",
        vendor_name="Prime Therapeutics",
        file_pattern="*Prime*.xlsx",
        header_row_index=4,
        crosswalk_table="prime_crosswalk.xlsx",
        boolean_flags={},
        column_mappings={},
        required_columns=["CLAIM_NBR"],
        notes="Prime has 4-row metadata header before data starts."
    ),
    
    # Caremark (CVS subsidiary, different format)
    "caremark": VendorConfig(
        vendor_key="caremark",
        vendor_name="CVS Caremark",
        file_pattern="*Caremark*.xlsx",
        header_row_index=0,
        crosswalk_table="caremark_crosswalk.xlsx",
        boolean_flags={},
        column_mappings={},
        required_columns=["ClaimID"],
        notes="Caremark is separate from CVS Health format."
    ),
    
    # MedImpact
    "medimpact": VendorConfig(
        vendor_key="medimpact",
        vendor_name="MedImpact",
        file_pattern="*MedImpact*.xlsx",
        header_row_index=0,
        crosswalk_table="medimpact_crosswalk.xlsx",
        boolean_flags={},
        column_mappings={},
        required_columns=["Claim_Number"],
        notes="MedImpact provides clean, well-structured files."
    ),
    
    # Navitus
    "navitus": VendorConfig(
        vendor_key="navitus",
        vendor_name="Navitus Health Solutions",
        file_pattern="*Navitus*.xlsx",
        header_row_index=2,
        crosswalk_table="navitus_crosswalk.xlsx",
        boolean_flags={},
        column_mappings={},
        required_columns=["Claim_ID"],
        notes="Navitus has 2-row header with column descriptions."
    ),
    
    # Magellan Rx
    "magellan": VendorConfig(
        vendor_key="magellan",
        vendor_name="Magellan Rx Management",
        file_pattern="*Magellan*.xlsx",
        header_row_index=0,
        crosswalk_table="magellan_crosswalk.xlsx",
        boolean_flags={},
        column_mappings={},
        required_columns=["ClaimNumber"],
        notes="Magellan provides standard format files."
    ),
    
    # EnvisionRx
    "envision": VendorConfig(
        vendor_key="envision",
        vendor_name="EnvisionRx",
        file_pattern="*Envision*.xlsx",
        header_row_index=1,
        crosswalk_table="envision_crosswalk.xlsx",
        boolean_flags={},
        column_mappings={},
        required_columns=["CLAIM_ID"],
        notes="EnvisionRx files have 1-row metadata header."
    ),
    
    # Generic/Unknown Vendor (fallback)
    "generic": VendorConfig(
        vendor_key="generic",
        vendor_name="Generic/Unknown Vendor",
        file_pattern="*.xlsx",
        header_row_index=0,
        crosswalk_table="generic_crosswalk.xlsx",
        boolean_flags={},
        column_mappings={},
        required_columns=[],
        notes="Fallback configuration for unrecognized vendors. Requires manual review."
    ),
}


# ============================================================================
# STANDARD SCHEMA DEFINITION
# ============================================================================
# All vendor data is normalized to this schema

STANDARD_SCHEMA_COLUMNS = [
    "PHCY_CLAIM_ID",           # Unique claim identifier
    "RX_NBR",                  # Prescription number
    "FILL_NDC_NBR",            # National Drug Code
    "SERVICED_DTE",            # Service/fill date
    "FORMULARY_TYPE_CDE",      # Formulary code
    "CLAIM_340B_IND",          # 340B indicator
    "PROVIDER_NPI",            # Provider NPI
    "PROVIDER_REF_ID",         # Provider reference ID
    "NCPDP_ID",                # NCPDP pharmacy ID
    "CLIENT_ID",               # Client identifier
    "MEMBER_ID",               # Member identifier
    "PAID_AMOUNT",             # Amount paid
    "REBATE_AMOUNT",           # Rebate amount
    "TRANSACTION_ID",          # Transaction identifier
    "VENDOR_ERROR_CODE",       # Vendor-specific error code
    "VENDOR_SOURCE",           # Vendor name/key
    "FILE_NAME",               # Source filename
    "LOAD_TIMESTAMP",          # When data was loaded
]


def get_vendor_config(vendor_key: str) -> VendorConfig:
    """
    Get vendor configuration by key.
    
    Args:
        vendor_key: Vendor identifier
        
    Returns:
        VendorConfig for the vendor
        
    Raises:
        KeyError if vendor not found
    """
    if vendor_key not in VENDOR_CONFIGS:
        raise KeyError(f"Unknown vendor: {vendor_key}. Available vendors: {list(VENDOR_CONFIGS.keys())}")
    return VENDOR_CONFIGS[vendor_key]


def list_configured_vendors() -> List[str]:
    """Get list of all configured vendor keys"""
    return list(VENDOR_CONFIGS.keys())


def find_vendor_by_filename(filename: str) -> Optional[str]:
    """
    Attempt to determine vendor from filename.
    
    Args:
        filename: Name of the file
        
    Returns:
        Vendor key if match found, None otherwise
    """
    filename_lower = filename.lower()
    
    # Check each vendor's file pattern
    for vendor_key, config in VENDOR_CONFIGS.items():
        if vendor_key == "generic":  # Skip generic fallback
            continue
        
        # Simple pattern matching (could be enhanced with regex)
        pattern_keywords = config.file_pattern.replace("*", "").replace(".xlsx", "").lower()
        if pattern_keywords and pattern_keywords in filename_lower:
            return vendor_key
    
    return None

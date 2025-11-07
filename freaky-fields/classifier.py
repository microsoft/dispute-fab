"""
Classifier Module for SeeHealth Claims Triage POC

⚠️ HISTORICAL REFERENCE - NOT USED IN PRODUCTION ⚠️

This is the original POC (Proof of Concept) classifier from October 2025.
It has been superseded by the production system but is kept for:
- Educational purposes - shows the project's evolution
- Historical reference - demonstrates the initial 4-category approach
- Documentation - referenced in architecture and handoff docs

PRODUCTION SYSTEM:
For current classification logic, see: core/enhanced_dispute_classifier.py
- Supports 23 dispute codes (vs. 4 categories here)
- Priority-based ranking system (Rank 1-23)
- Multi-signal classification (boolean flags + crosswalks + rules)
- Evidence trail generation for auditability
- Vendor-specific orchestration

PROJECT EVOLUTION:
POC (classifier.py)              Production (enhanced_dispute_classifier.py)
├── 4 simple categories    →    ├── 23 dispute codes with priority ranking
├── Basic boolean logic    →    ├── Multi-signal detection engine
└── Single-file approach   →    └── Modular architecture (core/, config/)

This module implements deterministic business rules to classify pharmacy rebate claims
into dispute categories. All logic is auditable and compliant with business requirements.

Business Categories (POC - 4 Categories):
- 340B Dispute: Claims involving 340B drug pricing program entities
- Duplicate Claim: Claims with identical prescription details
- Formulary Issue: Claims missing proper formulary authorization
- Clean / No Issue: Claims that pass all validation checks
"""

from dataclasses import dataclass
from typing import Any
import pandas as pd


@dataclass
class ColumnNames:
    """
    Centralized column name mappings for claims data.
    
    This ensures consistency across all classification functions and makes
    it easy to adapt if source column names change.
    """
    CLAIM_340B_IND: str = "CLAIM_340B_IND"
    RX_NBR: str = "RX_NBR"
    FILL_NDC_NBR: str = "FILL_NDC_NBR"
    SERVICED_DTE: str = "SERVICED_DTE"
    FORMULARY_TYPE_CDE: str = "FORMULARY_TYPE_CDE"
    PHCY_CLAIM_ID: str = "PHCY_CLAIM_ID"


# Global instance for easy access
COLS = ColumnNames()


def detect_340b(row: pd.Series) -> tuple[bool, str | None]:
    """
    Detects if a claim involves the 340B drug pricing program.
    
    Business Rule:
    The 340B program allows certain healthcare organizations to purchase outpatient
    drugs at significantly reduced prices. Manufacturers may dispute rebates on these
    claims to avoid duplicate discounts.
    
    Detection Logic:
    - If CLAIM_340B_IND is blank/null OR equals 'Y', the claim is flagged as 340B
    - These claims require special handling and verification
    
    Args:
        row: A pandas Series representing a single claim record
        
    Returns:
        tuple: (is_340b: bool, reason: str | None)
            - is_340b: True if claim is identified as 340B
            - reason: Explanation string if True, None otherwise
    """
    claim_340b_value = row.get(COLS.CLAIM_340B_IND)
    
    # Check if the value is blank (None, NaN, empty string) or explicitly 'Y'
    if pd.isna(claim_340b_value) or claim_340b_value == '' or claim_340b_value == 'Y':
        return True, "Claim appears to be 340B (CLAIM_340B_IND is blank or Y)"
    
    return False, None


def detect_duplicate(row: pd.Series, seen_keys: set) -> tuple[bool, str | None]:
    """
    Detects potential duplicate claims based on prescription identifiers.
    
    Business Rule:
    A claim is considered a duplicate if another claim with the exact same combination
    of prescription number, drug NDC code, and service date has already been processed.
    This helps identify resubmissions or data entry errors.
    
    Detection Logic:
    - Creates a unique key from (RX_NBR, FILL_NDC_NBR, SERVICED_DTE)
    - First occurrence of a key: NOT a duplicate (adds key to seen_keys)
    - Subsequent occurrences: DUPLICATE (key already in seen_keys)
    
    Args:
        row: A pandas Series representing a single claim record
        seen_keys: A set tracking previously seen claim combinations
        
    Returns:
        tuple: (is_duplicate: bool, reason: str | None)
            - is_duplicate: True if this exact claim combination was seen before
            - reason: Explanation string if True, None otherwise
            
    Note:
        This function modifies the seen_keys set by adding new combinations.
    """
    # Extract the three key fields that uniquely identify a prescription fill
    rx_nbr = row.get(COLS.RX_NBR)
    fill_ndc = row.get(COLS.FILL_NDC_NBR)
    service_date = row.get(COLS.SERVICED_DTE)
    
    # Create a tuple key for this combination
    claim_key = (rx_nbr, fill_ndc, service_date)
    
    # Check if we've seen this exact combination before
    if claim_key in seen_keys:
        return True, "Duplicate combo of RX_NBR + NDC + SERVICED_DTE already seen"
    
    # First time seeing this combination - add it to our tracking set
    seen_keys.add(claim_key)
    return False, None


def detect_formulary_issue(row: pd.Series) -> tuple[bool, str | None]:
    """
    Detects claims with missing or invalid formulary authorization.
    
    Business Rule:
    All claims must have a valid formulary type code indicating which drug formulary
    (list of approved medications) applies. Missing formulary codes suggest the claim
    may lack proper authorization or the drug may not be covered under the patient's plan.
    
    Detection Logic:
    - If FORMULARY_TYPE_CDE is null, blank, or missing, flag as formulary issue
    - These claims require manual review to verify coverage
    
    Args:
        row: A pandas Series representing a single claim record
        
    Returns:
        tuple: (has_issue: bool, reason: str | None)
            - has_issue: True if formulary code is missing/blank
            - reason: Explanation string if True, None otherwise
    """
    formulary_code = row.get(COLS.FORMULARY_TYPE_CDE)
    
    # Check if formulary code is missing, null, or empty
    if pd.isna(formulary_code) or formulary_code == '':
        return True, "Missing or blank formulary type code"
    
    return False, None


def classify_row(row: pd.Series, seen_keys: set) -> dict[str, Any]:
    """
    Classifies a single claim row into a dispute category using business rules.
    
    This is the main classification function that applies all detection rules in
    priority order and returns a complete classification result.
    
    Rule Priority (checked in this order):
    1. 340B Dispute - Highest priority due to regulatory implications
    2. Duplicate Claim - Prevents double-payment scenarios
    3. Formulary Issue - Coverage verification required
    4. Clean / No Issue - Default if all checks pass
    
    Needs_Attention Flag:
    - Set to True for any category other than "Clean / No Issue"
    - These claims require manual review or follow-up action
    
    Args:
        row: A pandas Series representing a single claim record
        seen_keys: A set tracking previously seen claim combinations (for duplicate detection)
        
    Returns:
        dict with keys:
            - "Category" (str): The assigned dispute category
            - "Reason" (str): Business explanation for the classification
            - "Needs_Attention" (bool): Whether manual review is required
            
    Example:
        >>> row = pd.Series({"CLAIM_340B_IND": "Y", "RX_NBR": "12345"})
        >>> result = classify_row(row, set())
        >>> print(result)
        {
            "Category": "340B Dispute",
            "Reason": "Claim appears to be 340B (CLAIM_340B_IND is blank or Y)",
            "Needs_Attention": True
        }
    """
    # Check rules in priority order
    
    # Priority 1: 340B Detection
    is_340b, reason_340b = detect_340b(row)
    if is_340b:
        return {
            "Category": "340B Dispute",
            "Reason": reason_340b,
            "Needs_Attention": True
        }
    
    # Priority 2: Duplicate Detection
    is_duplicate, reason_duplicate = detect_duplicate(row, seen_keys)
    if is_duplicate:
        return {
            "Category": "Duplicate Claim",
            "Reason": reason_duplicate,
            "Needs_Attention": True
        }
    
    # Priority 3: Formulary Issue Detection
    has_formulary_issue, reason_formulary = detect_formulary_issue(row)
    if has_formulary_issue:
        return {
            "Category": "Formulary Issue",
            "Reason": reason_formulary,
            "Needs_Attention": True
        }
    
    # Default: No issues detected
    return {
        "Category": "Clean / No Issue",
        "Reason": "Claim passed all validation checks",
        "Needs_Attention": False
    }

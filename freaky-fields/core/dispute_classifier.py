"""
Dispute Classifier Module

Enhanced classification system supporting:
- 20+ dispute categories with priority ranking
- Crosswalk table lookups for error codes
- Boolean flag checking
- Multiple category detection with priority resolution
- Evidence trail generation

Based on: Technical & Business Logic Specs
Date: October 29, 2025
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import pandas as pd

from core.dispute_categories import DisputeCategory, CategoryMetadata

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """
    Result of classifying a single claim.
    
    Attributes:
        claim_id: Unique identifier for the claim
        primary_category: Highest priority category matched
        all_matched_categories: All categories that matched (sorted by priority)
        evidence: List of evidence strings explaining the classification
        requires_human_review: Whether human review is needed
        confidence: Classification confidence (0.0-1.0)
    """
    claim_id: str
    primary_category: DisputeCategory
    all_matched_categories: List[DisputeCategory]
    evidence: List[str]
    requires_human_review: bool
    confidence: float = 1.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for DataFrame export."""
        return {
            "CLAIM_ID": self.claim_id,
            "PRIMARY_CATEGORY": self.primary_category.name,
            "PRIMARY_CATEGORY_CODE": self.primary_category.name,
            "CATEGORY_PRIORITY": self.primary_category.metadata.priority,
            "CATEGORY_DESCRIPTION": self.primary_category.metadata.description,
            "ALL_MATCHED_CATEGORIES": ", ".join([cat.name for cat in self.all_matched_categories]),
            "EVIDENCE": " | ".join(self.evidence),
            "REQUIRES_HUMAN_REVIEW": self.requires_human_review,
            "CONFIDENCE": self.confidence,
            "BUSINESS_RATIONALE": self.primary_category.metadata.business_rationale,
            "TYPICAL_RESOLUTION_DAYS": self.primary_category.metadata.typical_resolution_days,
            "FINANCIAL_IMPACT": self.primary_category.metadata.financial_impact,
        }


class DisputeClassifier:
    """
    Enterprise dispute classification engine.
    
    Supports multiple detection methods:
    1. Crosswalk table lookups (vendor error codes → categories)
    2. Boolean flag checking (direct category indicators)
    3. Deterministic rules (business logic patterns)
    4. Priority-based resolution (highest priority wins)
    """
    
    def __init__(
        self, 
        crosswalk_df: Optional[pd.DataFrame] = None,
        boolean_flag_mappings: Optional[Dict[str, DisputeCategory]] = None,
        enable_rules: bool = True
    ):
        """
        Initialize classifier with detection methods.
        
        Args:
            crosswalk_df: DataFrame with error code to category mappings
            boolean_flag_mappings: Dict of column_name → DisputeCategory
            enable_rules: Whether to enable deterministic rule checking
        """
        self.crosswalk_df = crosswalk_df
        self.boolean_flag_mappings = boolean_flag_mappings or {}
        self.enable_rules = enable_rules
        
        # Statistics
        self.stats = {
            "claims_processed": 0,
            "categories_found": {cat.name: 0 for cat in DisputeCategory},
            "multi_category_claims": 0,
            "review_required": 0,
        }
        
        logger.info(f"Initialized DisputeClassifier")
        logger.info(f"  - Crosswalk: {'Loaded' if crosswalk_df is not None else 'Not loaded'}")
        logger.info(f"  - Boolean flags: {len(self.boolean_flag_mappings)} configured")
        logger.info(f"  - Rules: {'Enabled' if enable_rules else 'Disabled'}")
    
    def classify_row(self, row: pd.Series) -> ClassificationResult:
        """
        Classify a single claim row.
        
        Detection priority:
        1. Boolean flags (fastest, most explicit)
        2. Crosswalk lookups (vendor-specific mappings)
        3. Deterministic rules (business logic patterns)
        
        If multiple categories match, the highest priority category wins.
        
        Args:
            row: DataFrame row representing a claim
            
        Returns:
            ClassificationResult with primary category and evidence
        """
        claim_id = str(row.get("CLAIM_ID", "UNKNOWN"))
        matched_categories = []
        evidence_list = []
        
        # Step 1: Check boolean flags
        flag_results = self._check_boolean_flags(row)
        if flag_results:
            matched_categories.extend(flag_results)
            evidence_list.append(f"Boolean flags: {len(flag_results)} categories matched")
        
        # Step 2: Check crosswalk table
        crosswalk_results = self._check_crosswalk(row)
        if crosswalk_results:
            matched_categories.extend(crosswalk_results)
            evidence_list.append(f"Crosswalk: {len(crosswalk_results)} categories matched")
        
        # Step 3: Apply deterministic rules
        if self.enable_rules:
            rule_results = self._apply_rules(row)
            if rule_results:
                matched_categories.extend(rule_results)
                evidence_list.append(f"Rules: {len(rule_results)} categories matched")
        
        # Remove duplicates and sort by priority
        if matched_categories:
            # Remove duplicates
            unique_categories = list(set(matched_categories))
            # Sort by priority (lowest number = highest priority)
            sorted_categories = sorted(unique_categories, key=lambda cat: cat.metadata.priority)
            # Primary category is highest priority (first in sorted list)
            primary_category = sorted_categories[0]
            matched_categories = sorted_categories
        else:
            # No issues found - clean claim
            primary_category = DisputeCategory.CLEAN_NO_ISSUE
            matched_categories = [DisputeCategory.CLEAN_NO_ISSUE]
            evidence_list.append("No issues detected")
        
        # Determine if human review is needed
        requires_review = primary_category.metadata.requires_human_review
        
        # Build result
        result = ClassificationResult(
            claim_id=claim_id,
            primary_category=primary_category,
            all_matched_categories=matched_categories,
            evidence=evidence_list,
            requires_human_review=requires_review,
            confidence=1.0  # Deterministic rules = 100% confidence
        )
        
        # Update stats
        self.stats["claims_processed"] += 1
        self.stats["categories_found"][primary_category.name] += 1
        if len(matched_categories) > 1:
            self.stats["multi_category_claims"] += 1
        if requires_review:
            self.stats["review_required"] += 1
        
        return result
    
    def _check_boolean_flags(self, row: pd.Series) -> List[DisputeCategory]:
        """
        Check boolean flag columns for direct category indicators.
        
        Args:
            row: DataFrame row
            
        Returns:
            List of matched DisputeCategory enums
        """
        matched = []
        
        for col_name, category in self.boolean_flag_mappings.items():
            if col_name in row:
                flag_value = row[col_name]
                # Check if flag is "truthy"
                if flag_value in [1, "1", True, "True", "Y", "y", "YES", "yes"]:
                    matched.append(category)
        
        return matched
    
    def _check_crosswalk(self, row: pd.Series) -> List[DisputeCategory]:
        """
        Look up error codes in crosswalk table.
        
        Crosswalk structure (example):
        | VENDOR_ERROR_CODE | DISPUTE_CATEGORY | DESCRIPTION |
        |-------------------|------------------|-------------|
        | ERR_340B          | CLAIM_340B       | 340B pricing|
        | ERR_DUP           | DUPLICATE_CLAIM  | Duplicate   |
        
        Args:
            row: DataFrame row
            
        Returns:
            List of matched DisputeCategory enums
        """
        if self.crosswalk_df is None or self.crosswalk_df.empty:
            return []
        
        matched = []
        
        # Look for error code column
        error_code_col = None
        for col in ["ERROR_CODE", "VENDOR_ERROR_CODE", "REJECT_CODE", "REASON_CODE"]:
            if col in row and pd.notna(row[col]):
                error_code_col = col
                break
        
        if not error_code_col:
            return []
        
        error_code = str(row[error_code_col]).strip()
        
        # Look up in crosswalk
        crosswalk_matches = self.crosswalk_df[
            self.crosswalk_df["VENDOR_ERROR_CODE"] == error_code
        ]
        
        for _, match_row in crosswalk_matches.iterrows():
            category_code = match_row.get("DISPUTE_CATEGORY")
            if category_code:
                try:
                    category = DisputeCategory.from_code(category_code)
                    matched.append(category)
                except ValueError:
                    logger.warning(f"Unknown category code in crosswalk: {category_code}")
        
        return matched
    
    def _apply_rules(self, row: pd.Series) -> List[DisputeCategory]:
        """
        Apply deterministic business rules for category detection.
        
        These are the same rules from the POC classifier.py, but now mapped
        to the new DisputeCategory enum system.
        
        Args:
            row: DataFrame row
            
        Returns:
            List of matched DisputeCategory enums
        """
        matched = []
        
        # Rule 1: 340B Pricing Issues
        if self._detect_340b(row):
            matched.append(DisputeCategory.CLAIM_340B)
        
        # Rule 2: Duplicate Claims
        if self._detect_duplicate(row):
            matched.append(DisputeCategory.DUPLICATE_CLAIM)
        
        # Rule 3: Formulary Violations
        if self._detect_formulary_issue(row):
            matched.append(DisputeCategory.FORMULARY_VIOLATION)
        
        # Rule 4: Pricing Errors
        if self._detect_pricing_issue(row):
            matched.append(DisputeCategory.PRICING_ERROR)
        
        # Rule 5: Data Quality Issues
        if self._detect_missing_documentation(row):
            matched.append(DisputeCategory.DATA_QUALITY)
        
        # Rule 6: Member Eligibility
        if self._detect_incorrect_patient_responsibility(row):
            matched.append(DisputeCategory.MEMBER_ELIGIBILITY)
        
        # Add more rules as needed...
        
        return matched
    
    # ============================================================
    # Deterministic Business Rules (from POC classifier.py)
    # ============================================================
    
    def _detect_340b(self, row: pd.Series) -> bool:
        """Detect 340B pricing issues."""
        if "DRUG_NDC" not in row or "DISPENSED_QUANTITY" not in row:
            return False
        
        ndc = str(row["DRUG_NDC"])
        qty = row.get("DISPENSED_QUANTITY", 0)
        
        # 340B logic: Check if NDC suggests 340B eligible drug
        # and quantity is above threshold
        if ndc.startswith("00"):  # Simplified check
            if qty > 100:
                return True
        
        return False
    
    def _detect_duplicate(self, row: pd.Series) -> bool:
        """Detect duplicate claims."""
        # This is a simplified version - full implementation would
        # require comparing against historical claims
        
        if "CLAIM_ID" not in row:
            return False
        
        # Check for duplicate indicator flags
        duplicate_flags = [
            "DUPLICATE_FLAG",
            "IS_DUPLICATE",
            "RESUBMISSION_FLAG"
        ]
        
        for flag in duplicate_flags:
            if flag in row:
                if row[flag] in [1, "1", True, "True", "Y", "yes"]:
                    return True
        
        return False
    
    def _detect_formulary_issue(self, row: pd.Series) -> bool:
        """Detect formulary violations."""
        if "DRUG_NDC" not in row:
            return False
        
        # Check for non-formulary indicators
        formulary_flags = [
            "FORMULARY_STATUS",
            "ON_FORMULARY",
            "FORMULARY_EXCEPTION"
        ]
        
        for flag in formulary_flags:
            if flag in row:
                status = str(row[flag]).upper()
                if status in ["NON-FORMULARY", "NOT_COVERED", "EXCLUDED", "N", "NO", "0"]:
                    return True
        
        return False
    
    def _detect_pricing_issue(self, row: pd.Series) -> bool:
        """Detect pricing discrepancies."""
        if "BILLED_AMOUNT" not in row or "ALLOWED_AMOUNT" not in row:
            return False
        
        billed = row.get("BILLED_AMOUNT", 0)
        allowed = row.get("ALLOWED_AMOUNT", 0)
        
        # Check if billed significantly exceeds allowed
        if billed > 0 and allowed > 0:
            variance = abs(billed - allowed) / allowed
            if variance > 0.20:  # More than 20% variance
                return True
        
        return False
    
    def _detect_missing_documentation(self, row: pd.Series) -> bool:
        """Detect missing required documentation."""
        required_fields = [
            "PRESCRIBER_NPI",
            "PRESCRIBER_NAME",
            "PHARMACY_NPI",
            "DRUG_NDC"
        ]
        
        missing_count = sum(1 for field in required_fields if pd.isna(row.get(field)))
        
        # If more than 1 required field is missing
        if missing_count > 1:
            return True
        
        return False
    
    def _detect_incorrect_patient_responsibility(self, row: pd.Series) -> bool:
        """Detect incorrect patient responsibility calculations."""
        if "PATIENT_PAY_AMOUNT" not in row or "COPAY_AMOUNT" not in row:
            return False
        
        patient_pay = row.get("PATIENT_PAY_AMOUNT", 0)
        copay = row.get("COPAY_AMOUNT", 0)
        
        # Check if patient pay doesn't match copay
        if patient_pay != copay and abs(patient_pay - copay) > 0.01:
            return True
        
        return False
    
    def classify_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify all rows in a DataFrame.
        
        Args:
            df: DataFrame with normalized claims data
            
        Returns:
            DataFrame with classification results added
        """
        logger.info(f"Classifying {len(df)} claims...")
        
        # Classify each row
        results = [self.classify_row(row) for _, row in df.iterrows()]
        
        # Convert results to DataFrame
        results_df = pd.DataFrame([r.to_dict() for r in results])
        
        # Merge with original data
        output_df = pd.concat([df, results_df], axis=1)
        
        logger.info(f"Classification complete. {self.stats['claims_processed']} claims processed.")
        logger.info(f"  - Clean claims: {self.stats['categories_found']['CLEAN_NO_ISSUE']}")
        logger.info(f"  - Disputed claims: {self.stats['claims_processed'] - self.stats['categories_found']['CLEAN_NO_ISSUE']}")
        logger.info(f"  - Require review: {self.stats['review_required']}")
        
        return output_df
    
    def get_stats(self) -> Dict:
        """Get classification statistics."""
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.stats = {
            "claims_processed": 0,
            "categories_found": {cat.name: 0 for cat in DisputeCategory},
            "multi_category_claims": 0,
            "review_required": 0,
        }

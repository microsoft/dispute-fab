"""
Enhanced Dispute Classifier with Priority-Based Resolution
Integrates with CrosswalkMapper for vendor code translation
Supports all 23 SeeHealth internal dispute codes with priority ranking
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

import pandas as pd
import numpy as np

from core.crosswalk_mapper import CrosswalkMapper

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """
    Result of classifying a single claim
    
    Attributes:
        claim_id: Unique identifier for the claim
        vendor: Source vendor name
        primary_code: Highest priority dispute code (lowest rank)
        primary_description: Description of primary code
        primary_category: Category (Pharmacy Issue, Duplicate Issue, etc.)
        primary_rank: Priority rank (1 = highest priority)
        all_codes: All applicable dispute codes sorted by priority
        evidence: Human-readable justification
        confidence: Classification confidence (0.0-1.0)
        requires_human_review: Whether manual review is needed
    """
    claim_id: str
    vendor: str
    primary_code: int
    primary_description: str
    primary_category: str
    primary_rank: int
    all_codes: List[int]
    evidence: str
    confidence: float = 1.0
    requires_human_review: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for DataFrame export"""
        return {
            "CLAIM_ID": self.claim_id,
            "VENDOR": self.vendor,
            "PRIMARY_DISPUTE_CODE": self.primary_code,
            "DESCRIPTION": self.primary_description,
            "CATEGORY": self.primary_category,
            "PRIORITY_RANK": self.primary_rank,
            "ALL_APPLICABLE_CODES": ", ".join(map(str, self.all_codes)),
            "EVIDENCE": self.evidence,
            "CONFIDENCE": self.confidence,
            "REQUIRES_REVIEW": self.requires_human_review,
        }


class EnhancedDisputeClassifier:
    """
    Production dispute classification engine with crosswalk integration
    
    Features:
    - Translates vendor error codes using Pharma_Crosswalk.xlsx
    - Applies all 23 SeeHealth dispute code rules
    - Priority-based resolution (lowest rank wins)
    - Evidence generation with audit trail
    - Multi-code support with justification
    """
    
    def __init__(
        self,
        dispute_codes_config: str = "config/business-rules/dispute-codes.json",
        crosswalk_file: str = "data/reference/Pharma_Crosswalk.xlsx",
        exclusion_codes_file: str = "data/reference/Exclusion Reason Codes.xlsx",
        source_of_truth_df = None
    ):
        """
        Initialize classifier with crosswalk and reference data
        
        Args:
            crosswalk_file: Path to Pharma_Crosswalk.xlsx
            dispute_codes_config: Path to SeeHealth dispute codes JSON
            exclusion_codes_file: Path to Exclusion Reason Codes.xlsx
            source_of_truth_df: Historical claims for pattern learning (optional)
        """
        # Initialize crosswalk mapper
        self.crosswalk = CrosswalkMapper(crosswalk_file)
        
        # Load dispute codes configuration
        self.config = self._load_config(dispute_codes_config)
        
        # Store source of truth for pattern matching
        self.source_of_truth = source_of_truth_df
        
        # Classification statistics
        self.stats = {
            "total_claims": 0,
            "by_vendor": {},
            "by_code": {code['code']: 0 for code in self.config['codes']},
            "multi_code_claims": 0,
            "review_required": 0,
        }
        
        logger.info("Enhanced Dispute Classifier initialized")
        logger.info(f"  - Loaded {len(self.config['codes'])} dispute code definitions")
        logger.info(f"  - Crosswalk mapper ready")
        if source_of_truth_df is not None:
            logger.info(f"  - Source of truth: {len(source_of_truth_df)} historical claims")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load SeeHealth dispute codes configuration"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def classify_claim(
        self,
        vendor: str,
        claim_data: Dict,
        vendor_error_codes: Optional[str] = None
    ) -> ClassificationResult:
        """
        Classify a single claim
        
        Args:
            vendor: Vendor name (e.g., "Ouy Ikxsp", "MW", "IOMMH")
            claim_data: Dictionary with claim fields
            vendor_error_codes: Vendor-specific error codes (if applicable)
            
        Returns:
            ClassificationResult with primary code and evidence
        """
        # With AI column mapping, CLAIM_ID should be standardized
        # Keep fallbacks for backwards compatibility
        claim_id = str(claim_data.get("CLAIM_ID", claim_data.get("Claim Number", "UNKNOWN")))
        
        # Step 1: Translate vendor error codes (if applicable)
        dispute_codes = self._translate_vendor_codes(vendor, vendor_error_codes)
        
        # Step 2: Apply business rules to detect additional codes
        rule_codes = self._apply_business_rules(claim_data)
        dispute_codes.extend(rule_codes)
        
        # Step 3: Remove duplicates
        dispute_codes = list(set(dispute_codes))
        
        # Step 4: If no codes found, apply default classification
        if not dispute_codes:
            dispute_codes = self._default_classification(claim_data)
        
        # Step 5: Resolve by priority (lowest rank wins)
        primary_code, all_codes = self.crosswalk.get_primary_code_by_priority(dispute_codes)
        
        # Step 6: Get code details
        if not primary_code:
            # Should not happen, but handle gracefully
            logger.warning(f"No primary code for claim {claim_id}")
            return self._unknown_classification(claim_id, vendor, claim_data)
        
        code_details = self.crosswalk.get_code_details(primary_code)
        if not code_details:
            logger.warning(f"Unknown code {primary_code} for claim {claim_id}")
            return self._unknown_classification(claim_id, vendor, claim_data)
        
        # Step 7: Generate evidence
        evidence = self.crosswalk.generate_evidence(primary_code, all_codes, {
            **claim_data,
            "Vendor": vendor,
            "Vendor Error Codes": vendor_error_codes
        })
        
        # Step 8: Determine if human review needed
        requires_review = self._requires_human_review(primary_code, all_codes, claim_data)
        
        # Step 9: Calculate confidence
        confidence = self._calculate_confidence(primary_code, vendor_error_codes)
        
        # Update statistics
        self._update_stats(vendor, primary_code, all_codes, requires_review)
        
        return ClassificationResult(
            claim_id=claim_id,
            vendor=vendor,
            primary_code=code_details['code'],
            primary_description=code_details['description'],
            primary_category=code_details['category'],
            primary_rank=code_details['rank'],
            all_codes=all_codes,
            evidence=evidence,
            confidence=confidence,
            requires_human_review=requires_review
        )
    
    def _translate_vendor_codes(self, vendor: str, error_codes: Optional[str]) -> List[int]:
        """Translate vendor error codes to SeeHealth dispute codes"""
        if not error_codes or pd.isna(error_codes):
            return []
        
        # Apply vendor-specific translation
        if vendor == "Ouy Ikxsp":
            return self.crosswalk.translate_ouy_ikxsp_codes(error_codes)
        elif vendor == "Qiibyq":
            return self.crosswalk.translate_qiibyq_codes(error_codes)
        elif vendor in ["MW", "IOMMH", "Hvoqlgwu"]:
            # These vendors already have SeeHealth internal codes
            try:
                codes = [int(c.strip()) for c in str(error_codes).split(',')]
                return codes
            except:
                logger.warning(f"Could not parse codes for {vendor}: {error_codes}")
                return []
        else:
            logger.warning(f"Unknown vendor {vendor}, no crosswalk available")
            return []
    
    def _apply_business_rules(self, claim_data: Dict) -> List[int]:
        """
        Apply business rules to detect additional dispute codes
        These rules learn from patterns in the source of truth
        """
        codes = []
        
        # Rule: Check 340B indicator (support multiple column name variations)
        claim_340b_ind = (
            claim_data.get("CLAIM_340B_IND") or 
            claim_data.get("Pharmacy - 340B Covered Entity") or
            claim_data.get("PHARMACY_340B_IND") or
            claim_data.get("340B_INDICATOR") or
            claim_data.get("340B Indicator")
        )
        
        # Check if value indicates 340B pharmacy
        if claim_340b_ind in ["Y", "1", 1, 1.0, True, "True", "true", "YES", "yes"]:
            codes.append(301)  # Excluded 340B Pharmacy
        
        # Rule: Check quantity aberrations
        # With AI column mapping, these should be standardized
        quantity = claim_data.get("QUANTITY", claim_data.get("Quantity", claim_data.get("FILL_QTY", claim_data.get("Total Quantity"))))
        days_supply = claim_data.get("DAYS_SUPPLY", claim_data.get("Days Supply", claim_data.get("FILL_DAYS_SUPPLY_QTY", claim_data.get("Days-Supply"))))
        
        if quantity and days_supply:
            try:
                qty = float(quantity)
                days = float(days_supply)
                
                # Aberrant quantity check
                if qty < 0 or qty > 1000:
                    codes.append(101)  # Aberrant Quantity
                
                # Invalid days supply
                if days <= 0 or days > 365:
                    codes.append(102)  # Days Supply is Invalid
                
                # Units per day check
                if days > 0 and (qty / days) > 10:
                    codes.append(103)  # Units per Day Exceeds Limit
            except:
                pass
        
        # Rule: Check for invalid NDC
        # With AI column mapping, DRUG_NDC should be standardized
        ndc = claim_data.get("DRUG_NDC", claim_data.get("NDC", claim_data.get("FILL_NDC_NBR", claim_data.get("Product-Code"))))
        if not ndc or str(ndc) == "nan" or len(str(ndc)) != 11:
            codes.append(204)  # Product ID or NDC is Invalid
        
        # Rule: Check for missing RX ID
        # With AI column mapping, PRESCRIPTION_ID should be standardized
        rx_id = claim_data.get("PRESCRIPTION_ID", claim_data.get("RX ID", claim_data.get("RX_NBR", claim_data.get("Prescription-Number"))))
        if not rx_id or str(rx_id) == "nan":
            codes.append(104)  # RX ID is invalid
        
        # Rule: Check explicit formulary non-compliance flags FIRST
        # Some vendors (e.g., Hvsq Tkrbcgf) provide explicit binary flags
        formulary_nc_flag = claim_data.get("FORMULARY NON-COMPLIANCE")
        formulary_nc_policy_flag = claim_data.get("FORMULARY NON-COMPLIANCE POLICY")
        
        if formulary_nc_flag == 1.0 or formulary_nc_flag == 1 or formulary_nc_flag == "1":
            codes.append(201)  # Explicit non-compliance flag
        elif formulary_nc_policy_flag == 1.0 or formulary_nc_policy_flag == 1 or formulary_nc_policy_flag == "1":
            codes.append(201)  # Explicit non-compliance policy flag
        else:
            # Rule: Check formulary code (enhanced logic)
            # Support multiple column name variations
            # Note: Use explicit None check to avoid treating 0 as falsy
            formulary_code = None
            for key in ["FORMULARY_TYPE_CDE", "Formulary-Code", "Formulary Code", 
                        "FORMULARY_STATUS", "Formulary Status", "Coverage Tier"]:
                if key in claim_data:
                    formulary_code = claim_data[key]
                    break
            
            # Detect formulary non-compliance from codes
            if formulary_code is not None and str(formulary_code) not in ["nan", ""]:
                try:
                    # Check numeric codes
                    code_val = int(float(formulary_code))
                    if code_val == 0:
                        # Code 0 typically means non-formulary
                        codes.append(201)
                except (ValueError, TypeError):
                    # Check text values
                    formulary_str = str(formulary_code).lower()
                    if any(indicator in formulary_str for indicator in [
                        "non-formulary", "not covered", "not on formulary",
                        "excluded", "non covered", "tier 0"
                    ]):
                        codes.append(201)
        # Note: We do NOT flag missing formulary fields as Code 201
        # Missing data != non-formulary (vendor may not provide this field)
        
        return codes
    
    def _default_classification(self, claim_data: Dict) -> List[int]:
        """Default classification when no codes detected"""
        # Return empty list - will be handled as unknown
        return []
    
    def _unknown_classification(self, claim_id: str, vendor: str, claim_data: Dict) -> ClassificationResult:
        """Handle unknown classification"""
        return ClassificationResult(
            claim_id=claim_id,
            vendor=vendor,
            primary_code=999,
            primary_description="Unknown/Unable to Classify",
            primary_category="Unknown",
            primary_rank=999,
            all_codes=[999],
            evidence="No dispute codes could be determined from available data",
            confidence=0.0,
            requires_human_review=True
        )
    
    def _requires_human_review(self, primary_code: int, all_codes: List[int], claim_data: Dict) -> bool:
        """Determine if human review is required"""
        # CRITICAL priority codes (ranks 1-8) always require review
        code_details = self.crosswalk.get_code_details(primary_code)
        if code_details and code_details.get('priority') == 'CRITICAL':
            return True
        
        # Multiple codes detected requires review
        if len(all_codes) > 1:
            return True
        
        # High financial amounts require review
        # With AI column mapping, REBATE_AMOUNT should be standardized
        rebate_amt = claim_data.get("REBATE_AMOUNT", claim_data.get("Requested Rebate Amt (b)", claim_data.get("TOTAL_REBATE_AMT", claim_data.get("Rebate Amount"))))
        if rebate_amt:
            try:
                if float(rebate_amt) > 1000:
                    return True
            except:
                pass
        
        return False
    
    def _calculate_confidence(self, primary_code: int, vendor_error_codes: Optional[str]) -> float:
        """Calculate classification confidence score"""
        # High confidence if vendor provided explicit error code
        if vendor_error_codes and not pd.isna(vendor_error_codes):
            return 0.95
        
        # Medium confidence if detected via rules
        return 0.75
    
    def _update_stats(self, vendor: str, primary_code: int, all_codes: List[int], requires_review: bool):
        """Update classification statistics"""
        self.stats["total_claims"] += 1
        
        if vendor not in self.stats["by_vendor"]:
            self.stats["by_vendor"][vendor] = 0
        self.stats["by_vendor"][vendor] += 1
        
        self.stats["by_code"][primary_code] = self.stats["by_code"].get(primary_code, 0) + 1
        
        if len(all_codes) > 1:
            self.stats["multi_code_claims"] += 1
        
        if requires_review:
            self.stats["review_required"] += 1
    
    def classify_batch(
        self,
        vendor: str,
        df: pd.DataFrame,
        error_code_column: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Classify a batch of claims from a vendor
        
        Args:
            vendor: Vendor name
            df: DataFrame with claims
            error_code_column: Column name containing vendor error codes
            
        Returns:
            DataFrame with classification results
        """
        logger.info(f"Classifying batch for vendor {vendor}: {len(df)} claims")
        
        results = []
        for idx, row in df.iterrows():
            # Get vendor error codes if column specified
            error_codes = row.get(error_code_column) if error_code_column else None
            
            # Convert row to dict
            claim_data = row.to_dict()
            
            # Classify
            result = self.classify_claim(vendor, claim_data, error_codes)
            results.append(result.to_dict())
        
        # Convert to DataFrame
        results_df = pd.DataFrame(results)
        
        logger.info(f"Classified {len(results_df)} claims for {vendor}")
        logger.info(f"  - Multi-code claims: {self.stats['multi_code_claims']}")
        logger.info(f"  - Requires review: {self.stats['review_required']}")
        
        return results_df
    
    def get_statistics(self) -> Dict:
        """Get classification statistics"""
        return self.stats
    
    def print_statistics(self):
        """Print formatted statistics"""
        print("\n" + "="*80)
        print("CLASSIFICATION STATISTICS")
        print("="*80)
        print(f"Total Claims Processed: {self.stats['total_claims']}")
        print(f"Multi-Code Claims: {self.stats['multi_code_claims']}")
        print(f"Requires Human Review: {self.stats['review_required']}")
        
        print("\nBy Vendor:")
        for vendor, count in self.stats['by_vendor'].items():
            print(f"  {vendor}: {count}")
        
        print("\nTop 10 Dispute Codes:")
        sorted_codes = sorted(self.stats['by_code'].items(), key=lambda x: x[1], reverse=True)[:10]
        for code, count in sorted_codes:
            if count > 0:
                details = self.crosswalk.get_code_details(code)
                if details:
                    print(f"  {code} ({details['description']}): {count}")

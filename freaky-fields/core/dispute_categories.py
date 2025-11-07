"""
Dispute Category Definitions for PBM Claims Triage

Defines all ~20 dispute categories with priority rankings and business logic
descriptions. Priority 1 is highest (most critical), 99 is clean/no issue.

Based on: Technical & Business Logic Specs (copilot-instrcutions-summary.md)
Date: October 29, 2025
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


@dataclass
class CategoryMetadata:
    """Metadata for a dispute category"""
    priority: int  # Lower number = higher priority
    description: str
    business_rationale: str
    requires_human_review: bool = False
    typical_resolution_days: Optional[int] = None
    financial_impact: str = "MEDIUM"  # LOW, MEDIUM, HIGH


class DisputeCategory(Enum):
    """
    Standard dispute categories with priority ranking.
    
    Priority Order (1 = highest priority):
    1. Formulary Violation - Most critical, affects rebate eligibility
    2. 340B Dispute - Regulatory implications, duplicate discount risk
    3. Duplicate Claim - Prevents overpayment
    4. Invalid NDC - Data quality issue, blocks processing
    5. Provider Exclusion - Compliance requirement
    ... (expand to ~20 categories as needed)
    """
    
    # Priority 1: Formulary Issues (highest priority)
    FORMULARY_VIOLATION = CategoryMetadata(
        priority=1,
        description="Formulary Violation",
        business_rationale="Claim references non-formulary drug or lacks formulary authorization. "
                          "Critical for rebate eligibility determination.",
        requires_human_review=True,
        typical_resolution_days=7,
        financial_impact="HIGH"
    )
    
    # Priority 2: 340B Disputes
    CLAIM_340B = CategoryMetadata(
        priority=2,
        description="340B Dispute",
        business_rationale="Claim involves 340B drug pricing program. Manufacturers dispute to "
                          "avoid duplicate discounts. Requires 340B entity verification.",
        requires_human_review=True,
        typical_resolution_days=14,
        financial_impact="HIGH"
    )
    
    # Priority 3: Duplicate Claims
    DUPLICATE_CLAIM = CategoryMetadata(
        priority=3,
        description="Duplicate Claim",
        business_rationale="Claim has identical RX_NBR, NDC, and service date as another claim. "
                          "Prevents double-payment and overpayment.",
        requires_human_review=False,
        typical_resolution_days=3,
        financial_impact="MEDIUM"
    )
    
    # Priority 4: Invalid NDC
    INVALID_NDC = CategoryMetadata(
        priority=4,
        description="Invalid NDC",
        business_rationale="NDC code is invalid, missing, or not found in reference tables. "
                          "Blocks proper drug identification and rebate calculation.",
        requires_human_review=True,
        typical_resolution_days=5,
        financial_impact="MEDIUM"
    )
    
    # Priority 5: Provider Exclusion
    PROVIDER_EXCLUSION = CategoryMetadata(
        priority=5,
        description="Provider Exclusion",
        business_rationale="Provider NPI or Ref ID is on exclusion list. May indicate 340B "
                          "participation or other eligibility restrictions.",
        requires_human_review=True,
        typical_resolution_days=10,
        financial_impact="MEDIUM"
    )
    
    # Priority 6: Contract Violation
    CONTRACT_VIOLATION = CategoryMetadata(
        priority=6,
        description="Contract Violation",
        business_rationale="Claim violates specific contract terms or overrides. Requires "
                          "contract text review and legal validation.",
        requires_human_review=True,
        typical_resolution_days=21,
        financial_impact="HIGH"
    )
    
    # Priority 7: Pricing Error
    PRICING_ERROR = CategoryMetadata(
        priority=7,
        description="Pricing Error",
        business_rationale="Rebate amount calculation error or pricing discrepancy. May result "
                          "from incorrect rate application or data entry error.",
        requires_human_review=True,
        typical_resolution_days=7,
        financial_impact="MEDIUM"
    )
    
    # Priority 8: Benefit Design Issue
    BENEFIT_DESIGN = CategoryMetadata(
        priority=8,
        description="Benefit Design Issue",
        business_rationale="Claim does not align with benefit design or plan parameters. "
                          "Requires benefit structure validation.",
        requires_human_review=True,
        typical_resolution_days=14,
        financial_impact="MEDIUM"
    )
    
    # Priority 9: Medicaid Exclusion
    MEDICAID_EXCLUSION = CategoryMetadata(
        priority=9,
        description="Medicaid Exclusion",
        business_rationale="Claim involves Medicaid coverage. Manufacturers may exclude from "
                          "rebate based on Medicaid best price rules.",
        requires_human_review=True,
        typical_resolution_days=14,
        financial_impact="HIGH"
    )
    
    # Priority 10: Prior Authorization Missing
    PRIOR_AUTH_MISSING = CategoryMetadata(
        priority=10,
        description="Prior Authorization Missing",
        business_rationale="Claim requires prior authorization but PA is not documented. "
                          "May affect rebate eligibility or payment validation.",
        requires_human_review=True,
        typical_resolution_days=10,
        financial_impact="LOW"
    )
    
    # Priority 11: Specialty Drug Issue
    SPECIALTY_DRUG = CategoryMetadata(
        priority=11,
        description="Specialty Drug Issue",
        business_rationale="Claim involves specialty drug with unique handling requirements. "
                          "May require specialized validation or alternate channel verification.",
        requires_human_review=True,
        typical_resolution_days=14,
        financial_impact="HIGH"
    )
    
    # Priority 12: Reversal/Adjustment
    REVERSAL_ADJUSTMENT = CategoryMetadata(
        priority=12,
        description="Reversal/Adjustment",
        business_rationale="Claim represents a reversal or adjustment to previous claim. "
                          "Requires matching to original transaction.",
        requires_human_review=False,
        typical_resolution_days=5,
        financial_impact="LOW"
    )
    
    # Priority 13: Member Eligibility Issue
    MEMBER_ELIGIBILITY = CategoryMetadata(
        priority=13,
        description="Member Eligibility Issue",
        business_rationale="Member eligibility unclear or disputed at time of service. "
                          "Requires eligibility verification against plan records.",
        requires_human_review=True,
        typical_resolution_days=10,
        financial_impact="MEDIUM"
    )
    
    # Priority 14: Compound Drug
    COMPOUND_DRUG = CategoryMetadata(
        priority=14,
        description="Compound Drug",
        business_rationale="Claim involves compounded medication. May have special rebate "
                          "calculation rules or exclusions.",
        requires_human_review=True,
        typical_resolution_days=7,
        financial_impact="LOW"
    )
    
    # Priority 15: OTC/Non-Rebatable
    OTC_NON_REBATABLE = CategoryMetadata(
        priority=15,
        description="OTC/Non-Rebatable",
        business_rationale="Over-the-counter drug or otherwise non-rebatable product. "
                          "Should be excluded from rebate calculation.",
        requires_human_review=False,
        typical_resolution_days=3,
        financial_impact="LOW"
    )
    
    # Priority 16: Mail Order Issue
    MAIL_ORDER_ISSUE = CategoryMetadata(
        priority=16,
        description="Mail Order Issue",
        business_rationale="Mail order claim with specific handling requirements or discrepancies. "
                          "May involve specialty pharmacy verification.",
        requires_human_review=True,
        typical_resolution_days=7,
        financial_impact="LOW"
    )
    
    # Priority 17: Data Quality Issue
    DATA_QUALITY = CategoryMetadata(
        priority=17,
        description="Data Quality Issue",
        business_rationale="General data quality problem (missing fields, invalid formats, etc.). "
                          "Requires data correction before processing.",
        requires_human_review=True,
        typical_resolution_days=5,
        financial_impact="LOW"
    )
    
    # Priority 18: Timing/Period Issue
    TIMING_PERIOD_ISSUE = CategoryMetadata(
        priority=18,
        description="Timing/Period Issue",
        business_rationale="Claim service date or submission timing falls outside expected period. "
                          "May be late submission or period mismatch.",
        requires_human_review=True,
        typical_resolution_days=7,
        financial_impact="LOW"
    )
    
    # Priority 19: Unrecognized Error Code
    UNRECOGNIZED_ERROR = CategoryMetadata(
        priority=19,
        description="Unrecognized Error Code",
        business_rationale="Vendor error code not found in crosswalk tables. Requires human "
                          "classification and potential crosswalk update.",
        requires_human_review=True,
        typical_resolution_days=14,
        financial_impact="MEDIUM"
    )
    
    # Priority 20: Ambiguous/Multiple Categories
    AMBIGUOUS_MULTIPLE = CategoryMetadata(
        priority=20,
        description="Ambiguous/Multiple Categories",
        business_rationale="Claim matches multiple categories with same priority or has "
                          "conflicting categorization rules. Requires manual review.",
        requires_human_review=True,
        typical_resolution_days=10,
        financial_impact="MEDIUM"
    )
    
    # Priority 99: Clean (lowest priority/default)
    CLEAN_NO_ISSUE = CategoryMetadata(
        priority=99,
        description="Clean / No Issue",
        business_rationale="Claim passed all validation checks and is ready for standard "
                          "processing. No disputes or exceptions detected.",
        requires_human_review=False,
        typical_resolution_days=1,
        financial_impact="LOW"
    )
    
    @property
    def metadata(self) -> CategoryMetadata:
        """Get the metadata for this category"""
        return self.value
    
    @property
    def priority(self) -> int:
        """Get the priority ranking for this category"""
        return self.value.priority
    
    @property
    def description(self) -> str:
        """Get the human-readable description"""
        return self.value.description
    
    @property
    def requires_review(self) -> bool:
        """Check if this category requires human review"""
        return self.value.requires_human_review
    
    @classmethod
    def from_code(cls, code: str) -> Optional['DisputeCategory']:
        """
        Get category from string code (case-insensitive)
        
        Args:
            code: Category code (e.g., "FORMULARY_VIOLATION")
            
        Returns:
            DisputeCategory if found, None otherwise
        """
        try:
            return cls[code.upper()]
        except KeyError:
            return None
    
    @classmethod
    def get_highest_priority(cls, categories: list['DisputeCategory']) -> 'DisputeCategory':
        """
        Select the highest priority category from a list.
        
        Args:
            categories: List of dispute categories
            
        Returns:
            Category with lowest priority number (highest priority)
        """
        if not categories:
            return cls.CLEAN_NO_ISSUE
        
        return min(categories, key=lambda cat: cat.priority)
    
    @classmethod
    def get_all_categories(cls) -> list['DisputeCategory']:
        """Get list of all categories sorted by priority"""
        return sorted(list(cls), key=lambda cat: cat.priority)
    
    @classmethod
    def get_review_required_categories(cls) -> list['DisputeCategory']:
        """Get list of categories that require human review"""
        return [cat for cat in cls if cat.requires_review]


# Convenience mappings for common use cases
CATEGORY_BY_PRIORITY = {cat.priority: cat for cat in DisputeCategory}
HIGH_PRIORITY_CATEGORIES = [cat for cat in DisputeCategory if cat.priority <= 5]
AUTO_PROCESS_CATEGORIES = [cat for cat in DisputeCategory if not cat.requires_review]

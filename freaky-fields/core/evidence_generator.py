"""
Evidence Generator Module

Generates comprehensive audit trails for dispute classifications.

For each dispute, creates evidence documentation including:
- Data sources and references
- Business rules applied
- Crosswalk lookups performed
- Boolean flags triggered
- Supporting documentation
- Human review notes

Based on: Technical & Business Logic Specs
Date: October 29, 2025
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from core.dispute_categories import DisputeCategory

logger = logging.getLogger(__name__)


@dataclass
class EvidenceItem:
    """
    Single piece of evidence supporting a classification.
    
    Attributes:
        evidence_type: Type of evidence (rule, crosswalk, flag, data)
        description: Human-readable description
        source: Data source or rule name
        value: Specific value that triggered the evidence
        timestamp: When evidence was generated
    """
    evidence_type: str
    description: str
    source: str
    value: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for export."""
        return {
            "EVIDENCE_TYPE": self.evidence_type,
            "DESCRIPTION": self.description,
            "SOURCE": self.source,
            "VALUE": self.value or "",
            "TIMESTAMP": self.timestamp.isoformat() if self.timestamp else "",
        }


@dataclass
class EvidenceTrail:
    """
    Complete evidence trail for a claim classification.
    
    Attributes:
        claim_id: Unique claim identifier
        category: Dispute category assigned
        evidence_items: List of evidence supporting the classification
        data_references: References to source data (files, rows, columns)
        human_notes: Any human review notes
    """
    claim_id: str
    category: DisputeCategory
    evidence_items: List[EvidenceItem]
    data_references: Dict[str, str]
    human_notes: Optional[str] = None
    
    def add_evidence(
        self, 
        evidence_type: str, 
        description: str, 
        source: str, 
        value: Optional[str] = None
    ) -> None:
        """Add an evidence item to the trail."""
        item = EvidenceItem(
            evidence_type=evidence_type,
            description=description,
            source=source,
            value=value
        )
        self.evidence_items.append(item)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for export."""
        return {
            "CLAIM_ID": self.claim_id,
            "CATEGORY": self.category.name,
            "EVIDENCE_COUNT": len(self.evidence_items),
            "EVIDENCE_SUMMARY": self._summarize_evidence(),
            "DATA_REFERENCES": str(self.data_references),
            "HUMAN_NOTES": self.human_notes or "",
        }
    
    def _summarize_evidence(self) -> str:
        """Create summary of evidence items."""
        if not self.evidence_items:
            return "No evidence"
        
        summary_parts = []
        for item in self.evidence_items:
            summary_parts.append(f"{item.evidence_type}: {item.description}")
        
        return " | ".join(summary_parts)
    
    def to_markdown(self) -> str:
        """Generate markdown report of evidence trail."""
        lines = [
            f"# Evidence Trail: {self.claim_id}",
            f"**Category**: {self.category.name}",
            f"**Priority**: {self.category.metadata.priority}",
            f"**Description**: {self.category.metadata.description}",
            "",
            "## Evidence Items",
        ]
        
        for i, item in enumerate(self.evidence_items, 1):
            lines.append(f"### {i}. {item.evidence_type.upper()}")
            lines.append(f"- **Description**: {item.description}")
            lines.append(f"- **Source**: {item.source}")
            if item.value:
                lines.append(f"- **Value**: {item.value}")
            if item.timestamp:
                lines.append(f"- **Timestamp**: {item.timestamp.isoformat()}")
            lines.append("")
        
        lines.append("## Data References")
        for key, value in self.data_references.items():
            lines.append(f"- **{key}**: {value}")
        
        if self.human_notes:
            lines.append("")
            lines.append("## Human Review Notes")
            lines.append(self.human_notes)
        
        return "\n".join(lines)


class EvidenceGenerator:
    """
    Generates and manages evidence trails for dispute classifications.
    
    Creates comprehensive audit documentation showing:
    - Why a claim was classified into a specific category
    - What data was used
    - Which rules or crosswalks triggered
    - Who reviewed it (if applicable)
    """
    
    def __init__(self):
        """Initialize evidence generator."""
        self.trails: Dict[str, EvidenceTrail] = {}
        logger.info("Initialized EvidenceGenerator")
    
    def create_trail(
        self,
        claim_id: str,
        category: DisputeCategory,
        data_references: Dict[str, str]
    ) -> EvidenceTrail:
        """
        Create a new evidence trail for a claim.
        
        Args:
            claim_id: Unique claim identifier
            category: Assigned dispute category
            data_references: Dict of source data references
            
        Returns:
            New EvidenceTrail object
        """
        trail = EvidenceTrail(
            claim_id=claim_id,
            category=category,
            evidence_items=[],
            data_references=data_references
        )
        
        self.trails[claim_id] = trail
        return trail
    
    def add_rule_evidence(
        self,
        claim_id: str,
        rule_name: str,
        description: str,
        triggered_value: Optional[str] = None
    ) -> None:
        """
        Add evidence from a business rule.
        
        Args:
            claim_id: Claim identifier
            rule_name: Name of the rule that triggered
            description: Description of what the rule detected
            triggered_value: Specific value that triggered the rule
        """
        if claim_id not in self.trails:
            logger.warning(f"No trail found for claim {claim_id}")
            return
        
        self.trails[claim_id].add_evidence(
            evidence_type="RULE",
            description=description,
            source=rule_name,
            value=triggered_value
        )
    
    def add_crosswalk_evidence(
        self,
        claim_id: str,
        error_code: str,
        category: str,
        crosswalk_table: str
    ) -> None:
        """
        Add evidence from a crosswalk table lookup.
        
        Args:
            claim_id: Claim identifier
            error_code: Vendor error code that was looked up
            category: Category code from crosswalk
            crosswalk_table: Name of crosswalk table used
        """
        if claim_id not in self.trails:
            logger.warning(f"No trail found for claim {claim_id}")
            return
        
        self.trails[claim_id].add_evidence(
            evidence_type="CROSSWALK",
            description=f"Error code {error_code} mapped to category {category}",
            source=crosswalk_table,
            value=error_code
        )
    
    def add_flag_evidence(
        self,
        claim_id: str,
        flag_column: str,
        flag_value: str,
        category: str
    ) -> None:
        """
        Add evidence from a boolean flag.
        
        Args:
            claim_id: Claim identifier
            flag_column: Name of the flag column
            flag_value: Value of the flag (1, Y, True, etc.)
            category: Category indicated by the flag
        """
        if claim_id not in self.trails:
            logger.warning(f"No trail found for claim {claim_id}")
            return
        
        self.trails[claim_id].add_evidence(
            evidence_type="FLAG",
            description=f"Boolean flag {flag_column} = {flag_value} indicates {category}",
            source=flag_column,
            value=str(flag_value)
        )
    
    def add_data_evidence(
        self,
        claim_id: str,
        field_name: str,
        field_value: str,
        description: str
    ) -> None:
        """
        Add evidence from data field values.
        
        Args:
            claim_id: Claim identifier
            field_name: Name of the data field
            field_value: Value of the field
            description: Description of why this is relevant
        """
        if claim_id not in self.trails:
            logger.warning(f"No trail found for claim {claim_id}")
            return
        
        self.trails[claim_id].add_evidence(
            evidence_type="DATA",
            description=description,
            source=field_name,
            value=str(field_value)
        )
    
    def add_human_note(
        self,
        claim_id: str,
        note: str,
        reviewer: Optional[str] = None
    ) -> None:
        """
        Add human review notes to a trail.
        
        Args:
            claim_id: Claim identifier
            note: Review note text
            reviewer: Name of reviewer (optional)
        """
        if claim_id not in self.trails:
            logger.warning(f"No trail found for claim {claim_id}")
            return
        
        timestamp = datetime.now().isoformat()
        reviewer_prefix = f"[{reviewer}] " if reviewer else ""
        full_note = f"{reviewer_prefix}{timestamp}: {note}"
        
        existing_notes = self.trails[claim_id].human_notes
        if existing_notes is not None and existing_notes != "":
            self.trails[claim_id].human_notes = existing_notes + f"\n{full_note}"
        else:
            self.trails[claim_id].human_notes = full_note
    
    def get_trail(self, claim_id: str) -> Optional[EvidenceTrail]:
        """Get evidence trail for a claim."""
        return self.trails.get(claim_id)
    
    def export_trails_to_dataframe(self) -> pd.DataFrame:
        """
        Export all evidence trails to a DataFrame.
        
        Returns:
            DataFrame with one row per claim, including evidence summary
        """
        if not self.trails:
            return pd.DataFrame()
        
        trail_dicts = [trail.to_dict() for trail in self.trails.values()]
        return pd.DataFrame(trail_dicts)
    
    def export_detailed_evidence(self) -> pd.DataFrame:
        """
        Export detailed evidence items (one row per evidence item).
        
        Returns:
            DataFrame with one row per evidence item
        """
        all_items = []
        
        for claim_id, trail in self.trails.items():
            for item in trail.evidence_items:
                item_dict = item.to_dict()
                item_dict["CLAIM_ID"] = claim_id
                item_dict["CATEGORY"] = trail.category.name
                all_items.append(item_dict)
        
        return pd.DataFrame(all_items)
    
    def generate_report(self, claim_id: str) -> str:
        """
        Generate a markdown report for a specific claim.
        
        Args:
            claim_id: Claim identifier
            
        Returns:
            Markdown-formatted evidence report
        """
        trail = self.get_trail(claim_id)
        if not trail:
            return f"# No evidence trail found for claim {claim_id}"
        
        return trail.to_markdown()
    
    def generate_summary_report(self) -> str:
        """
        Generate a summary report of all evidence trails.
        
        Returns:
            Markdown-formatted summary report
        """
        lines = [
            "# Evidence Trail Summary Report",
            f"**Generated**: {datetime.now().isoformat()}",
            f"**Total Claims**: {len(self.trails)}",
            "",
            "## Category Distribution",
        ]
        
        # Count categories
        category_counts = {}
        for trail in self.trails.values():
            cat_name = trail.category.name
            category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
        
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- **{cat}**: {count} claims")
        
        lines.append("")
        lines.append("## Evidence Type Distribution")
        
        # Count evidence types
        evidence_type_counts = {}
        for trail in self.trails.values():
            for item in trail.evidence_items:
                etype = item.evidence_type
                evidence_type_counts[etype] = evidence_type_counts.get(etype, 0) + 1
        
        for etype, count in sorted(evidence_type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- **{etype}**: {count} items")
        
        return "\n".join(lines)
    
    def clear_trails(self) -> None:
        """Clear all evidence trails."""
        self.trails.clear()
        logger.info("Cleared all evidence trails")


# Helper function for quick evidence generation
def generate_evidence_for_classification(
    claim_id: str,
    category: DisputeCategory,
    matched_categories: List[DisputeCategory],
    data_row: pd.Series,
    crosswalk_matches: List[Dict],
    flag_matches: List[Dict]
) -> EvidenceTrail:
    """
    Generate complete evidence trail for a classification.
    
    Args:
        claim_id: Claim identifier
        category: Primary category assigned
        matched_categories: All categories that matched
        data_row: DataFrame row with claim data
        crosswalk_matches: List of crosswalk matches
        flag_matches: List of boolean flag matches
        
    Returns:
        Complete EvidenceTrail object
    """
    generator = EvidenceGenerator()
    
    # Create trail
    data_refs = {
        "VENDOR": data_row.get("VENDOR_SOURCE", "Unknown"),
        "FILE": data_row.get("FILE_NAME", "Unknown"),
        "LOAD_TIME": str(data_row.get("LOAD_TIMESTAMP", "Unknown")),
    }
    
    trail = generator.create_trail(claim_id, category, data_refs)
    
    # Add crosswalk evidence
    for match in crosswalk_matches:
        generator.add_crosswalk_evidence(
            claim_id,
            match["error_code"],
            match["category"],
            match["crosswalk_table"]
        )
    
    # Add flag evidence
    for match in flag_matches:
        generator.add_flag_evidence(
            claim_id,
            match["flag_column"],
            match["flag_value"],
            match["category"]
        )
    
    # Add priority resolution note if multiple categories matched
    if len(matched_categories) > 1:
        categories_str = ", ".join([c.name for c in matched_categories])
        generator.add_data_evidence(
            claim_id,
            "PRIORITY_RESOLUTION",
            category.name,
            f"Multiple categories matched ({categories_str}). Selected highest priority: {category.name}"
        )
    
    return trail

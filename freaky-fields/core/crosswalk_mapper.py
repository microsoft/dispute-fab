#!/usr/bin/env python3
"""
Crosswalk Mapper Module
Translates vendor-specific error codes to SeeHealth's internal dispute codes
using mappings from Pharma_Crosswalk.xlsx
"""

import pandas as pd
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CrosswalkMapper:
    """
    Maps vendor-specific error codes to SeeHealth's internal dispute codes
    using the Pharma_Crosswalk.xlsx file
    """
    
    def __init__(self, crosswalk_file_path: str = "data/reference/Pharma_Crosswalk.xlsx"):
        """
        Initialize the crosswalk mapper by loading vendor code mappings
        
        Args:
            crosswalk_file_path: Path to Pharma_Crosswalk.xlsx
        """
        self.crosswalk_file = Path(crosswalk_file_path)
        self.ouy_ikxsp_mapping: Dict[str, int] = {}
        self.qiibyq_mapping: Dict[str, int] = {}
        self.dispute_codes_config: Dict = {}
        
        # Load crosswalk mappings
        self._load_crosswalk_mappings()
        
        # Load dispute codes configuration for priority ranking
        self._load_dispute_codes_config()
        
    def _load_crosswalk_mappings(self):
        """Load vendor error code mappings from Pharma_Crosswalk.xlsx"""
        try:
            # Load Ouy Ikxsp sheet
            df_ouy = pd.read_excel(self.crosswalk_file, sheet_name="Ouy Ikxsp")
            logger.info(f"Loaded Ouy Ikxsp crosswalk: {len(df_ouy)} mappings")
            
            # Create mapping: Error Code → Dispute Code
            for _, row in df_ouy.iterrows():
                error_code = str(row['Error Code']).strip().upper()
                dispute_code = int(row['Dispute Code'])
                self.ouy_ikxsp_mapping[error_code] = dispute_code
                
            logger.info(f"Ouy Ikxsp mappings: {self.ouy_ikxsp_mapping}")
            
            # Load Qiibyq sheet
            df_qiibyq = pd.read_excel(self.crosswalk_file, sheet_name="Qiibyq")
            logger.info(f"Loaded Qiibyq crosswalk: {len(df_qiibyq)} mappings")
            
            # Create mapping: Error Code → Reason Code
            for _, row in df_qiibyq.iterrows():
                error_code = str(row['Error Code']).strip().upper()
                reason_code = int(row['Reason Code'])
                self.qiibyq_mapping[error_code] = reason_code
                
            logger.info(f"Qiibyq mappings: {len(self.qiibyq_mapping)} codes loaded")
            
        except Exception as e:
            logger.error(f"Error loading crosswalk file: {e}")
            raise
            
    def _load_dispute_codes_config(self):
        """Load SeeHealth dispute codes configuration with priority rankings"""
        config_path = Path("config/business-rules/dispute-codes.json")
        try:
            with open(config_path, 'r') as f:
                self.dispute_codes_config = json.load(f)
                
            logger.info(f"Loaded {len(self.dispute_codes_config['codes'])} dispute code definitions")
            
        except Exception as e:
            logger.error(f"Error loading dispute codes config: {e}")
            raise
            
    def translate_ouy_ikxsp_codes(self, error_codes: str) -> List[int]:
        """
        Translate Ouy Ikxsp vendor error codes to SeeHealth dispute codes
        
        Args:
            error_codes: Comma-separated error codes (e.g., "COB" or "XPX,XRX")
            
        Returns:
            List of SeeHealth internal dispute codes
            
        Examples:
            "COB" → [404]
            "XPX,XRX" → [301, 305]
            "DUP" → [401]
        """
        if pd.isna(error_codes) or not error_codes:
            return []
            
        # Split by comma and clean up
        codes = [code.strip().upper() for code in str(error_codes).split(',')]
        
        # Translate each code
        dispute_codes = []
        for code in codes:
            if code in self.ouy_ikxsp_mapping:
                dispute_codes.append(self.ouy_ikxsp_mapping[code])
                logger.debug(f"Translated {code} → {self.ouy_ikxsp_mapping[code]}")
            else:
                logger.warning(f"Unknown Ouy Ikxsp error code: {code}")
                
        return dispute_codes
        
    def translate_qiibyq_codes(self, error_codes: str) -> List[int]:
        """
        Translate Qiibyq vendor error codes to SeeHealth reason codes
        
        Args:
            error_codes: Comma-separated error codes (e.g., "D-CHN" or "M-DAY,M-PLN")
            
        Returns:
            List of SeeHealth internal reason codes
        """
        if pd.isna(error_codes) or not error_codes:
            return []
            
        # Split by comma and clean up
        codes = [code.strip().upper() for code in str(error_codes).split(',')]
        
        # Translate each code
        reason_codes = []
        for code in codes:
            if code in self.qiibyq_mapping:
                reason_codes.append(self.qiibyq_mapping[code])
                logger.debug(f"Translated {code} → {self.qiibyq_mapping[code]}")
            else:
                logger.warning(f"Unknown Qiibyq error code: {code}")
                
        return reason_codes
        
    def get_code_rank(self, dispute_code: int) -> int:
        """
        Get the priority rank for a given dispute code
        
        Args:
            dispute_code: SeeHealth internal dispute code
            
        Returns:
            Rank number (1 = highest priority, 23 = lowest priority)
        """
        for code_info in self.dispute_codes_config['codes']:
            if code_info['code'] == dispute_code:
                return code_info['rank']
                
        logger.warning(f"Unknown dispute code: {dispute_code}")
        return 999  # Unknown codes get lowest priority
        
    def get_primary_code_by_priority(self, codes: List[int]) -> Tuple[Optional[int], List[int]]:
        """
        Given multiple dispute codes, return the highest priority code (lowest rank)
        and all applicable codes sorted by priority
        
        Args:
            codes: List of SeeHealth internal dispute codes
            
        Returns:
            Tuple of (primary_code, all_codes_sorted_by_priority)
            
        Examples:
            [301, 401] → (301, [301, 401])  # 301 rank 1 beats 401 rank 9
            [404, 102, 305] → (305, [305, 102, 404])  # 305 rank 5 wins
        """
        if not codes:
            return (None, [])
            
        # Remove duplicates
        unique_codes = list(set(codes))
        
        # Sort by rank (lowest rank = highest priority)
        sorted_codes = sorted(unique_codes, key=lambda c: self.get_code_rank(c))
        
        primary_code = sorted_codes[0]
        
        logger.info(f"Multiple codes {unique_codes} → Primary: {primary_code} (Rank {self.get_code_rank(primary_code)})")
        
        return (primary_code, sorted_codes)
        
    def get_code_details(self, dispute_code: int) -> Optional[Dict]:
        """
        Get full details for a dispute code including description, category, rank, priority
        
        Args:
            dispute_code: SeeHealth internal dispute code
            
        Returns:
            Dictionary with code details or None if not found
        """
        for code_info in self.dispute_codes_config['codes']:
            if code_info['code'] == dispute_code:
                return code_info
                
        return None
        
    def generate_evidence(self, primary_code: int, all_codes: List[int], vendor_data: Dict) -> str:
        """
        Generate human-readable evidence for why a code was selected
        
        Args:
            primary_code: The selected primary dispute code
            all_codes: All applicable codes
            vendor_data: Original vendor claim data
            
        Returns:
            Evidence string explaining the classification
        """
        primary_details = self.get_code_details(primary_code)
        
        if not primary_details:
            return f"Unknown code {primary_code}"
            
        evidence_parts = []
        
        # Primary classification
        evidence_parts.append(f"PRIMARY DISPUTE CODE: {primary_code}")
        evidence_parts.append(f"Description: {primary_details['description']}")
        evidence_parts.append(f"Category: {primary_details['category']}")
        evidence_parts.append(f"Priority: {primary_details['priority']} (Rank {primary_details['rank']})")
        evidence_parts.append("")
        
        # Why this code was selected if multiple codes apply
        if len(all_codes) > 1:
            evidence_parts.append("RESOLUTION LOGIC:")
            evidence_parts.append(f"Multiple dispute codes applied: {all_codes}")
            evidence_parts.append(f"Selected Code {primary_code} because it has the highest priority (Rank {primary_details['rank']})")
            evidence_parts.append("")
            
            evidence_parts.append("OTHER APPLICABLE CODES:")
            for code in all_codes[1:]:
                details = self.get_code_details(code)
                if details:
                    evidence_parts.append(f"  • Code {code}: {details['description']} (Rank {details['rank']})")
            evidence_parts.append("")
        
        # Rules applied
        if 'rules' in primary_details:
            evidence_parts.append("RULES APPLIED:")
            for rule in primary_details['rules']:
                evidence_parts.append(f"  • {rule}")
            evidence_parts.append("")
        
        # Vendor data summary
        evidence_parts.append("CLAIM DATA:")
        for key, value in vendor_data.items():
            if pd.notna(value):
                evidence_parts.append(f"  • {key}: {value}")
        
        return "\n".join(evidence_parts)


# Example usage and testing
if __name__ == "__main__":
    print("="*80)
    print("CROSSWALK MAPPER TEST")
    print("="*80)
    
    # Initialize mapper
    mapper = CrosswalkMapper()
    
    # Test Ouy Ikxsp translations
    print("\n1. Testing Ouy Ikxsp vendor code translations:")
    print("-" * 80)
    
    test_codes = ["COB", "XPX,XRX", "DUP", "AQU", "HII", "TVO"]
    for code in test_codes:
        result = mapper.translate_ouy_ikxsp_codes(code)
        print(f"   {code:15} → {result}")
    
    # Test priority resolution
    print("\n2. Testing priority-based resolution:")
    print("-" * 80)
    
    test_scenarios = [
        [301, 401],  # Pharmacy exclusion vs duplicate
        [404, 102, 305],  # COB, days supply, pharmacy ID
        [201, 501],  # Formulary vs prior quarter
        [103, 204, 401],  # Units/day, invalid NDC, duplicate
    ]
    
    for codes in test_scenarios:
        primary, sorted_codes = mapper.get_primary_code_by_priority(codes)
        if primary:
            primary_details = mapper.get_code_details(primary)
            print(f"   Input: {codes}")
            if primary_details:
                print(f"   Primary: {primary} - {primary_details['description']} (Rank {primary_details['rank']})")
            print(f"   All codes (sorted): {sorted_codes}")
            print()
    
    # Test evidence generation
    print("\n3. Testing evidence generation:")
    print("-" * 80)
    
    primary, all_codes = mapper.get_primary_code_by_priority([301, 401, 103])
    vendor_data = {
        "Vendor": "Ouy Ikxsp",
        "NDC": "00002147180",
        "Product": "Mounjaro",
        "Quantity": 2,
        "Fill Date": "12/31/2024",
        "Error Codes": "XPX,DUP,AQU",
        "Pharmacy": "6257818"
    }
    
    if primary:
        evidence = mapper.generate_evidence(primary, all_codes, vendor_data)
    else:
        evidence = "No codes to generate evidence for"
    print(evidence)
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

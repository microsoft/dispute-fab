"""
Vendor Agent Module

Handles vendor-specific data normalization and format conversion. Each vendor
may have unique file formats, header rows, and column structures. The VendorAgent
standardizes all vendor data into a common schema for downstream processing.

Based on: Technical & Business Logic Specs
Date: October 29, 2025
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import pandas as pd

from config.vendor_configs import VendorConfig, STANDARD_SCHEMA_COLUMNS

logger = logging.getLogger(__name__)


class VendorAgent:
    """
    Handles vendor-specific data normalization and transformation.
    
    Each vendor may have:
    - Different header row positions
    - Unique column names
    - Vendor-specific error codes
    - Boolean flags for categories
    - Custom data formats
    
    The VendorAgent normalizes all of this into a standard schema.
    """
    
    def __init__(self, config: VendorConfig):
        """
        Initialize vendor agent with configuration.
        
        Args:
            config: VendorConfig with vendor-specific settings
        """
        self.config = config
        self.crosswalk_df: Optional[pd.DataFrame] = None
        self.processing_stats = {
            "files_processed": 0,
            "records_processed": 0,
            "errors": [],
        }
        
        logger.info(f"Initialized VendorAgent for {config.vendor_name}")
    
    def load_crosswalk(self, crosswalks_dir: Path) -> bool:
        """
        Load vendor-specific crosswalk table.
        
        Crosswalk tables map vendor error codes to internal dispute categories.
        
        Args:
            crosswalks_dir: Directory containing crosswalk files
            
        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.config.crosswalk_table:
            logger.info(f"No crosswalk table configured for {self.config.vendor_name}")
            return False
        
        crosswalk_path = crosswalks_dir / self.config.crosswalk_table
        
        if not crosswalk_path.exists():
            logger.warning(f"Crosswalk table not found: {crosswalk_path}")
            return False
        
        try:
            self.crosswalk_df = pd.read_excel(crosswalk_path, engine="openpyxl")
            logger.info(f"Loaded crosswalk table: {crosswalk_path} ({len(self.crosswalk_df)} rows)")
            return True
        except Exception as e:
            logger.error(f"Failed to load crosswalk table {crosswalk_path}: {e}")
            return False
    
    def load_file(self, file_path: Path) -> pd.DataFrame:
        """
        Load vendor file with vendor-specific settings.
        
        Args:
            file_path: Path to vendor file
            
        Returns:
            Raw DataFrame (not yet normalized)
            
        Raises:
            Exception if file cannot be loaded
        """
        logger.info(f"Loading file: {file_path}")
        
        try:
            # Determine file type and load accordingly
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                if self.config.sheet_name:
                    df = pd.read_excel(
                        file_path, 
                        engine="openpyxl",
                        sheet_name=self.config.sheet_name
                    )
                else:
                    df = pd.read_excel(file_path, engine="openpyxl")
            elif file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_path.suffix}")
            
            logger.info(f"Loaded {len(df)} rows from {file_path.name}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {e}")
            raise
    
    def normalize_data(self, raw_df: pd.DataFrame, source_filename: str = "") -> pd.DataFrame:
        """
        Convert vendor format to standard schema.
        
        Steps:
        1. Remove header rows and promote correct headers
        2. Apply column mappings (vendor names → standard names)
        3. Apply vendor-specific transformations
        4. Add metadata columns (vendor source, load time, etc.)
        5. Validate required columns exist
        
        Args:
            raw_df: Raw DataFrame from vendor file
            source_filename: Name of source file for tracking
            
        Returns:
            Normalized DataFrame with standard schema
            
        Raises:
            ValueError if required columns are missing
        """
        logger.info(f"Normalizing data for {self.config.vendor_name}")
        
        # Step 1: Handle header rows
        df = self._process_header_rows(raw_df)
        
        # Step 2: Apply column mappings
        df = self._apply_column_mappings(df)
        
        # Step 3: Apply vendor-specific transformations
        df = self._apply_transformations(df)
        
        # Step 4: Add metadata
        df = self._add_metadata(df, source_filename)
        
        # Step 5: Validate required columns
        self._validate_required_columns(df)
        
        # Update stats
        self.processing_stats["files_processed"] += 1
        self.processing_stats["records_processed"] += len(df)
        
        logger.info(f"Normalized {len(df)} records for {self.config.vendor_name}")
        
        return df
    
    def _process_header_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove header rows and promote correct header row.
        
        Many vendor files have metadata rows before the actual data headers.
        This function skips those rows and promotes the correct row as headers.
        """
        if self.config.header_row_index > 0:
            # Skip rows before the header
            df = df.iloc[self.config.header_row_index:].reset_index(drop=True)
            
            # Promote first row to column names
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)
            
            logger.debug(f"Skipped {self.config.header_row_index} header rows")
        
        # Remove bottom rows if needed
        if self.config.skip_rows_bottom > 0:
            df = df.iloc[:-self.config.skip_rows_bottom]
            logger.debug(f"Skipped {self.config.skip_rows_bottom} bottom rows")
        
        # Clean column names (remove spaces, special chars)
        df.columns = [str(col).strip() for col in df.columns]
        
        return df
    
    def _apply_column_mappings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rename vendor columns to standard schema names.
        
        Uses the column_mappings dict from config to rename columns.
        """
        if not self.config.column_mappings:
            return df
        
        # Only rename columns that exist
        mappings_to_apply = {
            vendor_col: standard_col 
            for vendor_col, standard_col in self.config.column_mappings.items()
            if vendor_col in df.columns
        }
        
        if mappings_to_apply:
            df = df.rename(columns=mappings_to_apply)
            logger.debug(f"Applied {len(mappings_to_apply)} column mappings")
        
        return df
    
    def _apply_transformations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply vendor-specific data transformations.
        
        This is where vendor-specific data cleaning happens:
        - Date format conversions
        - Currency formatting
        - Code standardization
        - etc.
        
        TODO: Implement vendor-specific transformation logic as needed.
        """
        # Placeholder for vendor-specific transformations
        # Each vendor may have unique transformation requirements
        
        # Example transformations (customize per vendor):
        # - Convert date formats
        # - Clean currency values
        # - Standardize boolean flags
        # - etc.
        
        return df
    
    def _add_metadata(self, df: pd.DataFrame, source_filename: str) -> pd.DataFrame:
        """
        Add metadata columns for tracking and audit.
        
        Adds:
        - VENDOR_SOURCE: Which vendor this data came from
        - FILE_NAME: Source filename
        - LOAD_TIMESTAMP: When data was processed
        """
        df["VENDOR_SOURCE"] = self.config.vendor_name
        df["FILE_NAME"] = source_filename
        df["LOAD_TIMESTAMP"] = datetime.now()
        
        return df
    
    def _validate_required_columns(self, df: pd.DataFrame) -> None:
        """
        Validate that all required columns are present.
        
        Raises:
            ValueError if required columns are missing
        """
        if not self.config.required_columns:
            return
        
        missing_cols = [
            col for col in self.config.required_columns 
            if col not in df.columns
        ]
        
        if missing_cols:
            error_msg = (
                f"Missing required columns for {self.config.vendor_name}: "
                f"{missing_cols}\n"
                f"Available columns: {list(df.columns)}"
            )
            logger.error(error_msg)
            self.processing_stats["errors"].append(error_msg)
            raise ValueError(error_msg)
    
    def get_boolean_flag_categories(self, row: pd.Series) -> List[str]:
        """
        Check boolean flags and return matching categories.
        
        Some vendors use boolean flag columns (1/0 or True/False) to indicate
        specific dispute categories directly. This is faster than crosswalk lookups.
        
        Args:
            row: DataFrame row
            
        Returns:
            List of category codes that match boolean flags
        """
        matched_categories = []
        
        for flag_column, category in self.config.boolean_flags.items():
            if flag_column in row:
                flag_value = row[flag_column]
                # Check if flag is "truthy" (1, True, "Y", etc.)
                if flag_value in [1, "1", True, "True", "Y", "y", "YES", "yes"]:
                    matched_categories.append(category.name)
        
        return matched_categories
    
    def process_file(
        self, 
        file_path: Path, 
        crosswalks_dir: Path
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Complete file processing pipeline.
        
        Steps:
        1. Load crosswalk table (if available)
        2. Load vendor file
        3. Normalize to standard schema
        4. Return normalized data + processing stats
        
        Args:
            file_path: Path to vendor file
            crosswalks_dir: Directory with crosswalk tables
            
        Returns:
            Tuple of (normalized_df, processing_stats)
        """
        # Load crosswalk if available
        self.load_crosswalk(crosswalks_dir)
        
        # Load and normalize file
        raw_df = self.load_file(file_path)
        normalized_df = self.normalize_data(raw_df, source_filename=file_path.name)
        
        stats = {
            "vendor": self.config.vendor_name,
            "file": file_path.name,
            "records_processed": len(normalized_df),
            "crosswalk_loaded": self.crosswalk_df is not None,
            "errors": self.processing_stats["errors"].copy(),
        }
        
        return normalized_df, stats


# Convenience function for quick vendor processing
def process_vendor_file(
    vendor_key: str,
    file_path: Path,
    crosswalks_dir: Path
) -> Tuple[pd.DataFrame, Dict]:
    """
    Quick helper to process a vendor file.
    
    Args:
        vendor_key: Vendor identifier (e.g., "cvs", "walgreens")
        file_path: Path to vendor file
        crosswalks_dir: Directory with crosswalk tables
        
    Returns:
        Tuple of (normalized_df, processing_stats)
    """
    from config.vendor_configs import get_vendor_config
    
    config = get_vendor_config(vendor_key)
    agent = VendorAgent(config)
    return agent.process_file(file_path, crosswalks_dir)

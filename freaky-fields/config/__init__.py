"""
Configuration package for vendor-specific settings.

This package contains configuration files for:
- Vendor data formats and mappings
- Crosswalk table definitions
- Boolean flag configurations
- Column schema definitions
"""

from .vendor_configs import (
    VendorConfig,
    VENDOR_CONFIGS,
    STANDARD_SCHEMA_COLUMNS,
    get_vendor_config,
    list_configured_vendors,
    find_vendor_by_filename,
)

__all__ = [
    "VendorConfig",
    "VENDOR_CONFIGS",
    "STANDARD_SCHEMA_COLUMNS",
    "get_vendor_config",
    "list_configured_vendors",
    "find_vendor_by_filename",
]

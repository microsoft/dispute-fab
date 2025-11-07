#!/usr/bin/env python3
"""
Process All 15 Vendors from Masked_Scrub_File_15.xlsx
Complete end-to-end classification with results dashboard
"""

import pandas as pd
from pathlib import Path
import sys
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

from core.enhanced_dispute_classifier import EnhancedDisputeClassifier
from core.column_mapper import ColumnMapper


def get_vendor_config():
    """
    Configuration for each vendor sheet
    Maps vendor name to error code column name (if applicable)
    """
    return {
        "GpkDke": {"error_column": None, "header_row": None},  # Needs investigation
        "Ouy Ikxsp": {"error_column": "Error Codes", "header_row": 7},
        "Hvsq Tkrbcgf": {"error_column": None, "header_row": None},
        "YAO": {"error_column": None, "header_row": None},
        "W&L": {"error_column": None, "header_row": None},
        "IOMMH": {"error_column": "Dispute Reason", "header_row": 0},  # Has descriptive reasons
        "GKO": {"error_column": None, "header_row": None},
        "MW": {"error_column": "Code", "header_row": 0},  # Has internal codes
        "Hvoqlgwu": {"error_column": "our codes", "header_row": 0},  # Has internal codes
        "naszpr": {"error_column": None, "header_row": None},
        "sspowy": {"error_column": None, "header_row": None},
        "ITZ": {"error_column": None, "header_row": None},
        "Uprygzwe": {"error_column": None, "header_row": None},
        "Azryup": {"error_column": None, "header_row": None},
        "Qiibyq": {"error_column": None, "header_row": None},  # Needs crosswalk
    }


def load_vendor_data(vendor_name: str, config: dict, use_ai_mapping: bool = True):
    """
    Load data for a specific vendor sheet with optional AI column mapping.
    
    Args:
        vendor_name: Name of vendor sheet
        config: Vendor configuration (deprecated, kept for backwards compatibility)
        use_ai_mapping: If True, use AI to detect headers and map columns
        
    Returns:
        Tuple of (DataFrame, column_mapping_dict) or (None, None) on error
    """
    file_path = Path("data/Masked_Scrub_File_15.xlsx")
    
    try:
        if use_ai_mapping:
            # Use AI column mapping for universal vendor support
            mapper = ColumnMapper(cache_dir="data/column_mappings")
            df, column_mapping = mapper.get_mapped_dataframe(
                str(file_path), 
                vendor_name, 
                vendor_name
            )
            
            # Clean up - remove rows that are all NaN
            df = df.dropna(how='all')
            
            return df, column_mapping
        else:
            # Legacy approach: manual configuration
            header_row = config.get("header_row", 0)
            df = pd.read_excel(file_path, sheet_name=vendor_name, header=header_row)
            
            # Clean up - remove rows that are all NaN
            df = df.dropna(how='all')
            
            print(f"  ✓ Loaded {len(df)} rows, {len(df.columns)} columns")
            
            return df, None
    except Exception as e:
        print(f"  ✗ Error loading: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def process_vendor(classifier, vendor_name: str, config: dict, max_rows: int | None = None, use_ai_mapping: bool = True):
    """Process claims for a single vendor"""
    print(f"\n{'='*80}")
    print(f"VENDOR: {vendor_name}")
    print(f"{'='*80}")
    
    # Load data with AI column mapping
    df, column_mapping = load_vendor_data(vendor_name, config, use_ai_mapping=use_ai_mapping)
    if df is None or len(df) == 0:
        print("  ⚠️  No data to process")
        return None
    
    # Limit rows if specified
    if max_rows is not None and len(df) > max_rows:
        print(f"  ⚠️  Limiting to first {max_rows} rows (total: {len(df)})")
        df = df.head(max_rows)
    else:
        print(f"  ✅ Processing ALL {len(df)} rows")
    
    # Show columns and mapping info
    if use_ai_mapping and column_mapping:
        print(f"  🤖 AI Column Mapping: {len(column_mapping)} fields mapped")
        # Determine error column from mapping
        error_col = None
        if "VENDOR_ERROR_CODE" in df.columns:
            error_col = "VENDOR_ERROR_CODE"
        elif "DISPUTE_REASON" in df.columns:
            error_col = "DISPUTE_REASON"
    else:
        error_col = config.get("error_column")
    
    print(f"  Error Code Column: {error_col if error_col else 'None (will use rule-based detection)'}")
    print(f"  Sample Columns: {df.columns.tolist()[:10]}...")
    
    # Classify
    try:
        results_df = classifier.classify_batch(
            vendor=vendor_name,
            df=df,
            error_code_column=error_col
        )
        
        return results_df
    except Exception as e:
        print(f"  ✗ Classification error: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_summary_report(all_results: dict):
    """Generate comprehensive summary report"""
    print("\n" + "="*80)
    print("COMPREHENSIVE SUMMARY REPORT")
    print("="*80)
    
    total_claims = sum(len(df) for df in all_results.values() if df is not None)
    vendors_processed = len([v for v in all_results.values() if v is not None])
    
    print(f"\n📊 Overall Statistics:")
    print(f"  Total Vendors Processed: {vendors_processed}/15")
    print(f"  Total Claims Classified: {total_claims:,}")
    
    # Combine all results
    all_claims = pd.concat([df for df in all_results.values() if df is not None], ignore_index=True)
    
    # Top dispute codes across all vendors
    print(f"\n🎯 Top 10 Dispute Codes (All Vendors):")
    code_counts = all_claims['PRIMARY_DISPUTE_CODE'].value_counts().head(10)
    for code, count in code_counts.items():
        desc = all_claims[all_claims['PRIMARY_DISPUTE_CODE'] == code]['DESCRIPTION'].iloc[0]
        pct = (count / len(all_claims)) * 100
        print(f"  {code:3d} - {desc:45s} {count:5,} ({pct:5.1f}%)")
    
    # By category
    print(f"\n📂 By Category:")
    cat_counts = all_claims['CATEGORY'].value_counts()
    for cat, count in cat_counts.items():
        pct = (count / len(all_claims)) * 100
        print(f"  {cat:25s} {count:5,} ({pct:5.1f}%)")
    
    # By vendor
    print(f"\n🏢 By Vendor:")
    vendor_counts = all_claims['VENDOR'].value_counts()
    for vendor, count in vendor_counts.items():
        pct = (count / len(all_claims)) * 100
        print(f"  {vendor:25s} {count:5,} ({pct:5.1f}%)")
    
    # Priority distribution
    print(f"\n⚠️  Priority Distribution:")
    priority_ranges = {
        "CRITICAL (Ranks 1-8)": all_claims[all_claims['PRIORITY_RANK'] <= 8],
        "HIGH (Ranks 9-12)": all_claims[(all_claims['PRIORITY_RANK'] >= 9) & (all_claims['PRIORITY_RANK'] <= 12)],
        "MEDIUM (Ranks 13-16)": all_claims[(all_claims['PRIORITY_RANK'] >= 13) & (all_claims['PRIORITY_RANK'] <= 16)],
        "LOWER (Ranks 17-21)": all_claims[(all_claims['PRIORITY_RANK'] >= 17) & (all_claims['PRIORITY_RANK'] <= 21)],
        "LOWEST (Ranks 22-23)": all_claims[all_claims['PRIORITY_RANK'] >= 22],
    }
    
    for priority, subset in priority_ranges.items():
        count = len(subset)
        pct = (count / len(all_claims)) * 100
        print(f"  {priority:30s} {count:5,} ({pct:5.1f}%)")
    
    # Human review required
    review_count = all_claims['REQUIRES_REVIEW'].sum()
    review_pct = (review_count / len(all_claims)) * 100
    print(f"\n👤 Requires Human Review: {review_count:,} ({review_pct:.1f}%)")
    
    # Confidence distribution
    print(f"\n📈 Confidence Distribution:")
    print(f"  Average Confidence: {all_claims['CONFIDENCE'].mean():.1%}")
    print(f"  High Confidence (>90%): {(all_claims['CONFIDENCE'] > 0.9).sum():,}")
    print(f"  Medium Confidence (70-90%): {((all_claims['CONFIDENCE'] >= 0.7) & (all_claims['CONFIDENCE'] <= 0.9)).sum():,}")
    print(f"  Low Confidence (<70%): {(all_claims['CONFIDENCE'] < 0.7).sum():,}")
    
    return all_claims


def main():
    print("="*80)
    print("PROCESSING ALL 15 VENDORS FROM MASKED_SCRUB_FILE_15.XLSX")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize classifier
    print("\n🔧 Initializing classifier...")
    classifier = EnhancedDisputeClassifier(
        crosswalk_file="data/reference/Pharma_Crosswalk.xlsx",
        dispute_codes_config="config/business-rules/dispute-codes.json"
    )
    
    # Get vendor configuration
    vendor_config = get_vendor_config()
    
    # Process each vendor
    all_results = {}
    
    for vendor_name, config in vendor_config.items():
        result = process_vendor(classifier, vendor_name, config, max_rows=None, use_ai_mapping=True)  # Process ALL claims with AI mapping
        all_results[vendor_name] = result
    
    # Generate summary report
    all_claims = generate_summary_report(all_results)
    
    # Print classifier statistics
    print("\n")
    classifier.print_statistics()
    
    # Save results
    print("\n" + "="*80)
    print("SAVING RESULTS")
    print("="*80)
    
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Save combined results
    combined_file = output_dir / "all_vendors_classification_results.csv"
    all_claims.to_csv(combined_file, index=False)
    print(f"✅ Combined results: {combined_file}")
    
    # Save individual vendor results
    for vendor_name, result_df in all_results.items():
        if result_df is not None:
            vendor_file = output_dir / f"{vendor_name.replace('&', 'and').replace(' ', '_')}_results.csv"
            result_df.to_csv(vendor_file, index=False)
            print(f"✅ {vendor_name}: {vendor_file}")
    
    # Save summary statistics
    summary_stats = {
        "timestamp": datetime.now().isoformat(),
        "total_vendors": len([v for v in all_results.values() if v is not None]),
        "total_claims": len(all_claims),
        "by_vendor": all_claims['VENDOR'].value_counts().to_dict(),
        "by_code": all_claims['PRIMARY_DISPUTE_CODE'].value_counts().to_dict(),
        "by_category": all_claims['CATEGORY'].value_counts().to_dict(),
        "requires_review": int(all_claims['REQUIRES_REVIEW'].sum()),
        "avg_confidence": float(all_claims['CONFIDENCE'].mean()),
    }
    
    import json
    stats_file = output_dir / "classification_summary.json"
    with open(stats_file, 'w') as f:
        json.dump(summary_stats, f, indent=2)
    print(f"✅ Summary statistics: {stats_file}")
    
    print("\n" + "="*80)
    print("PROCESSING COMPLETE")
    print("="*80)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n📁 All results saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    main()

export interface SheetData {
  sheetName: string;
  headers: string[];
  rows: Record<string, unknown>[];
}

export interface ColumnMapping {
  CLAIM_ID?: string;
  PRESCRIPTION_ID?: string;
  DRUG_NDC?: string;
  QUANTITY?: string;
  DAYS_SUPPLY?: string;
  PHARMACY_ID?: string;
  FILL_DATE?: string;
  REBATE_AMOUNT?: string;
  VENDOR_ERROR_CODE?: string;
  DISPUTE_REASON?: string;
}

export interface NormalizedClaim {
  CLAIM_ID?: unknown;
  PRESCRIPTION_ID?: unknown;
  DRUG_NDC?: unknown;
  QUANTITY?: unknown;
  DAYS_SUPPLY?: unknown;
  PHARMACY_ID?: unknown;
  FILL_DATE?: unknown;
  REBATE_AMOUNT?: unknown;
  VENDOR_ERROR_CODE?: unknown;
  DISPUTE_REASON?: unknown;
  // raw ref for debugging
  __raw?: Record<string, unknown>;
}

export interface ClassificationResult {
  claimId: string;
  categories: string[];
  primaryCategory: string;
  confidence: number;
  evidence: string[];
}

export interface SheetProcessingResult {
  sheetName: string;
  mapping: ColumnMapping;
  normalized: NormalizedClaim[];
  results: ClassificationResult[];
  mappingSource?: 'ai' | 'fallback' | 'client';
  aiError?: string | null;
}
export interface SheetData {
  sheetName: string;
  headers: string[];
  rows: Record<string, unknown>[];
}

export interface ColumnMapping {
  CLAIM_ID?: string;
  PRESCRIPTION_ID?: string;
  DRUG_NDC?: string;
  QUANTITY?: string;
  DAYS_SUPPLY?: string;
  PHARMACY_ID?: string;
  FILL_DATE?: string;
  REBATE_AMOUNT?: string;
  VENDOR_ERROR_CODE?: string;
  DISPUTE_REASON?: string;
}

export interface NormalizedClaim {
  CLAIM_ID?: unknown;
  PRESCRIPTION_ID?: unknown;
  DRUG_NDC?: unknown;
  QUANTITY?: unknown;
  DAYS_SUPPLY?: unknown;
  PHARMACY_ID?: unknown;
  FILL_DATE?: unknown;
  REBATE_AMOUNT?: unknown;
  VENDOR_ERROR_CODE?: unknown;
  DISPUTE_REASON?: unknown;
}

export interface ClassificationResult {
  claimId: string;
  categories: string[];
  primaryCategory: string;
  confidence: number;
  evidence: string[];
}

export interface SheetProcessingResult {
  sheetName: string;
  mapping: ColumnMapping;
  normalized: NormalizedClaim[];
  results: ClassificationResult[];
  mappingSource?: 'ai' | 'fallback' | 'client';
  aiError?: string | null;
}

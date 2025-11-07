/**
 * Type definitions for SeeHealth Claims Classification System
 */

export interface Claim {
  CLAIM_ID: string;
  VENDOR: string;
  PRIMARY_DISPUTE_CODE: number;
  DESCRIPTION: string;
  CATEGORY: string;
  PRIORITY_RANK: number;
  ALL_APPLICABLE_CODES: string; // JSON array as string
  EVIDENCE: string;
  CONFIDENCE: number; // 0-1 decimal
  REQUIRES_REVIEW: boolean | string; // May come as "True"/"False"
  REBATE_AMOUNT?: number | null;
  CLAIM_AMOUNT?: number | null;
}

export interface DisputeCode {
  code: number;
  description: string;
  category: string;
  rank: number;
}

export interface VendorSummary {
  name: string;
  totalClaims: number;
  avgConfidence: number;
  requiresReview: number;
  topCodes: { code: number; count: number }[];
}

export interface DashboardStats {
  totalClaims: number;
  totalVendors: number;
  avgConfidence: number;
  requiresReview: number;
  topCodes: { code: number; description: string; count: number; percentage: number }[];
  byCategory: { category: string; count: number; percentage: number }[];
  byPriority: { priority: string; count: number; percentage: number }[];
  byVendor: VendorSummary[];
}

export interface ComparisonMetrics {
  before: {
    totalClaims: number;
    code104Count: number;
    code104Percentage: number;
    validClaimIds: number;
    validClaimIdsPercentage: number;
    realClassifications: number;
    realClassificationsPercentage: number;
  };
  after: {
    totalClaims: number;
    code104Count: number;
    code104Percentage: number;
    validClaimIds: number;
    validClaimIdsPercentage: number;
    realClassifications: number;
    realClassificationsPercentage: number;
  };
}

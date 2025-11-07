/**
 * Data loading utilities for CSV files
 */

import Papa from 'papaparse';
import type { Claim } from './types';

const RESULTS_CSV_PATH = '/outputs/all_vendors_classification_results.csv';

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function extractNumericFromEvidence(evidence: unknown, labels: string[]): number | null {
  if (!evidence) {
    return null;
  }
  const text = String(evidence);
  for (const label of labels) {
    const pattern = new RegExp(
      `${escapeRegExp(label)}(?:\\s*\\([^)]*\\))?\\s*[:=]\\s*(-?[0-9,]+(?:\\.[0-9]+)?)`,
      'i'
    );
    const match = pattern.exec(text);
    if (match) {
      const numeric = parseFloat(match[1].replace(/,/g, ''));
      if (!Number.isNaN(numeric)) {
        return numeric;
      }
    }
  }
  return null;
}

/**
 * Load and parse the claims classification results CSV
 */
export async function loadClaimsData(): Promise<Claim[]> {
  try {
    const response = await fetch(RESULTS_CSV_PATH);
    if (!response.ok) {
      throw new Error(`Failed to load claims data: ${response.statusText}`);
    }
    
    const csvText = await response.text();
    
    return new Promise((resolve, reject) => {
      Papa.parse<Claim>(csvText, {
        header: true,
        dynamicTyping: true,
        skipEmptyLines: true,
        complete: (results) => {
          // Convert string booleans to actual booleans
          const claims = results.data.map((claim) => ({
            ...claim,
            REQUIRES_REVIEW: 
              typeof claim.REQUIRES_REVIEW === 'string'
                ? claim.REQUIRES_REVIEW.toLowerCase() === 'true'
                : Boolean(claim.REQUIRES_REVIEW),
            CONFIDENCE: Number(claim.CONFIDENCE) || 0,
            PRIMARY_DISPUTE_CODE: Number(claim.PRIMARY_DISPUTE_CODE) || 0,
            PRIORITY_RANK: Number(claim.PRIORITY_RANK) || 0,
            REBATE_AMOUNT: extractNumericFromEvidence(claim.EVIDENCE, [
              'Requested Rebate Amt',
              'Rebate Amount',
              'Rebate Amt',
              'Rebate Requested',
            ]),
            CLAIM_AMOUNT: extractNumericFromEvidence(claim.EVIDENCE, [
              'Gross Sales',
              'Claim Amount',
              'Claim Total',
              'Claim Amt',
            ]),
          }));
          resolve(claims);
        },
        error: (error: unknown) => {
          reject(error);
        },
      });
    });
  } catch (error: unknown) {
    console.error('Error loading claims data:', error);
    throw error instanceof Error ? error : new Error('Unknown data load error');
  }
}

/**
 * Calculate dashboard statistics from claims data
 */
export function calculateStats(claims: Claim[]) {
  const total = claims.length;
  const requiresReview = claims.filter(c => c.REQUIRES_REVIEW).length;
  const avgConfidence = claims.reduce((sum, c) => sum + c.CONFIDENCE, 0) / total;
  
  // Top codes
  const codeCounts = new Map<number, { count: number; description: string; category: string }>();
  claims.forEach(claim => {
    const existing = codeCounts.get(claim.PRIMARY_DISPUTE_CODE);
    if (existing) {
      existing.count++;
    } else {
      codeCounts.set(claim.PRIMARY_DISPUTE_CODE, {
        count: 1,
        description: claim.DESCRIPTION,
        category: claim.CATEGORY,
      });
    }
  });
  
  const topCodes = Array.from(codeCounts.entries())
    .map(([code, data]) => ({
      code,
      description: data.description,
      count: data.count,
      percentage: (data.count / total) * 100,
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);
  
  // By category
  const categoryCounts = new Map<string, number>();
  claims.forEach(claim => {
    const count = categoryCounts.get(claim.CATEGORY) || 0;
    categoryCounts.set(claim.CATEGORY, count + 1);
  });
  
  const byCategory = Array.from(categoryCounts.entries())
    .map(([category, count]) => ({
      category,
      count,
      percentage: (count / total) * 100,
    }))
    .sort((a, b) => b.count - a.count);
  
  // By priority
  const priorityRanges = [
    { label: 'CRITICAL (1-8)', min: 1, max: 8 },
    { label: 'HIGH (9-12)', min: 9, max: 12 },
    { label: 'MEDIUM (13-16)', min: 13, max: 16 },
    { label: 'LOWER (17-21)', min: 17, max: 21 },
    { label: 'LOWEST (22-23)', min: 22, max: 23 },
  ];
  
  const byPriority = priorityRanges.map(range => {
    const count = claims.filter(
      c => c.PRIORITY_RANK >= range.min && c.PRIORITY_RANK <= range.max
    ).length;
    return {
      priority: range.label,
      count,
      percentage: (count / total) * 100,
    };
  });
  
  // By vendor
  const vendorCounts = new Map<string, Claim[]>();
  claims.forEach(claim => {
    const existing = vendorCounts.get(claim.VENDOR) || [];
    existing.push(claim);
    vendorCounts.set(claim.VENDOR, existing);
  });
  
  const byVendor = Array.from(vendorCounts.entries())
    .map(([name, vendorClaims]) => {
      const totalClaims = vendorClaims.length;
      const avgConfidence = vendorClaims.reduce((sum, c) => sum + c.CONFIDENCE, 0) / totalClaims;
      const requiresReview = vendorClaims.filter(c => c.REQUIRES_REVIEW).length;
      
      // Top 3 codes for this vendor
      const vendorCodeCounts = new Map<number, number>();
      vendorClaims.forEach(claim => {
        const count = vendorCodeCounts.get(claim.PRIMARY_DISPUTE_CODE) || 0;
        vendorCodeCounts.set(claim.PRIMARY_DISPUTE_CODE, count + 1);
      });
      
      const topCodes = Array.from(vendorCodeCounts.entries())
        .map(([code, count]) => ({ code, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 3);
      
      return {
        name,
        totalClaims,
        avgConfidence,
        requiresReview,
        topCodes,
      };
    })
    .sort((a, b) => b.totalClaims - a.totalClaims);
  
  const totalVendors = byVendor.length;
  
  return {
    totalClaims: total,
    totalVendors,
    avgConfidence,
    requiresReview,
    topCodes,
    byCategory,
    byPriority,
    byVendor,
  };
}

/**
 * Get comparison metrics (hardcoded from analysis)
 */
export function getComparisonMetrics() {
  return {
    before: {
      totalClaims: 7785,
      code104Count: 5356,
      code104Percentage: 68.8,
      validClaimIds: 741,
      validClaimIdsPercentage: 9.5,
      realClassifications: 2429,
      realClassificationsPercentage: 31.2,
    },
    after: {
      totalClaims: 7739,
      code104Count: 1183,
      code104Percentage: 15.3,
      validClaimIds: 5479,
      validClaimIdsPercentage: 70.8,
      realClassifications: 6556,
      realClassificationsPercentage: 84.7,
    },
  };
}

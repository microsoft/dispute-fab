import type { NormalizedClaim, ClassificationResult } from './types';

export interface Rule {
  id: string;
  test: (c: NormalizedClaim) => boolean;
  category: string;
  confidence: number;
  reason: string;
}

export const RULES: Rule[] = [
  {
    id: 'LONG_DAYS_SUPPLY',
    test: c => c.DAYS_SUPPLY !== undefined && Number(c.DAYS_SUPPLY) > 90,
    category: 'DURATION_REVIEW',
    confidence: 0.82,
    reason: 'Days supply exceeds typical thresholds.'
  },
  {
    id: 'HIGH_REBATE',
    test: c => c.REBATE_AMOUNT !== undefined && Number(c.REBATE_AMOUNT) > 500,
    category: 'FINANCIAL_ANOMALY',
    confidence: 0.86,
    reason: 'Rebate amount unusually high compared to historical range.'
  },
  {
    id: 'MISSING_NDC',
    test: c => !c.DRUG_NDC || c.DRUG_NDC.toString().trim().length === 0,
    category: 'DATA_COMPLETENESS',
    confidence: 0.74,
    reason: 'Drug NDC missing; requires data remediation.'
  },
  {
    id: 'LOW_QUANTITY_HIGH_DAYS',
    test: c => c.QUANTITY !== undefined && c.DAYS_SUPPLY !== undefined && Number(c.QUANTITY) < 5 && Number(c.DAYS_SUPPLY) > 30,
    category: 'UTILIZATION_PATTERN',
    confidence: 0.78,
    reason: 'Low quantity with long days supply suggests possible mismatch.'
  }
];

export function classifyClaim(claim: NormalizedClaim): ClassificationResult {
  const matched = RULES.filter(r => {
    try { return r.test(claim); } catch { return false; }
  });
  if (!matched.length) {
    return {
      claimId: (claim.CLAIM_ID ?? 'UNKNOWN').toString(),
      categories: ['NO_FLAG'],
      primaryCategory: 'NO_FLAG',
      confidence: 0.55,
      evidence: ['No rule matched; baseline pass.']
    };
  }
  matched.sort((a,b)=> b.confidence - a.confidence);
  const primary = matched[0];
  return {
    claimId: (claim.CLAIM_ID ?? 'UNKNOWN').toString(),
    categories: matched.map(m => m.category),
    primaryCategory: primary.category,
    confidence: primary.confidence,
    evidence: matched.map(m => `Rule ${m.id} (${m.category}): ${m.reason}`)
  };
}

// Return the full matched rule objects for a claim (ordered by confidence desc)
export function getMatchedRules(claim: NormalizedClaim): Rule[] {
  const matched = RULES.filter(r => r.test(claim));
  return matched.sort((a,b) => b.confidence - a.confidence);
}

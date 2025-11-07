import type { SheetData, ColumnMapping } from './types';

export const STANDARD_FIELDS = [
  'CLAIM_ID',
  'PRESCRIPTION_ID',
  'DRUG_NDC',
  'QUANTITY',
  'DAYS_SUPPLY',
  'PHARMACY_ID',
  'FILL_DATE',
  'REBATE_AMOUNT',
  'VENDOR_ERROR_CODE',
  'DISPUTE_REASON'
];

interface MappingContext {
  columns: string[];
  sample: Record<string, unknown>[];
}

function selectClaimId(columns: string[], sample: Record<string, unknown>[]): string | null {
  // Broader patterns: claim id, invoice id, transaction id, script claim id variants.
  const claimCandidates = columns.filter(c => /claim.*(id|number|no)|invoice.*(id|number)|transaction.*(id|number)|rx.*(claim|id)|prescription.*(claim|id)/i.test(c));
  if (!claimCandidates.length) return null;

  const valuesPerColumn: Record<string, string[]> = {};
  claimCandidates.forEach(c => {
    valuesPerColumn[c] = sample
      .map(r => (r[c] ?? '').toString().trim())
      .filter(v => v.length > 0);
  });

  const scored = claimCandidates.map(c => {
    const vals = valuesPerColumn[c];
    const uniq = new Set(vals);
    // treat long numeric or mixed ids as potentially better
    const numericLengths = vals
      .map(v => (/^[0-9A-Za-z]+$/.test(v) ? v.length : 0))
      .filter(n => n > 0);
    const avgLen = numericLengths.length
      ? numericLengths.reduce((a, b) => a + b, 0) / numericLengths.length
      : 0;
    return { col: c, uniquenessRatio: uniq.size / Math.max(vals.length, 1), avgLen };
  });

  scored.sort((a, b) => (b.avgLen !== a.avgLen ? b.avgLen - a.avgLen : b.uniquenessRatio - a.uniquenessRatio));
  const top = scored[0];
  // Loosen threshold slightly for varied vendor data.
  if (top.avgLen >= 10 && top.uniquenessRatio > 0.8) return top.col;
  return null;
}

function heuristicMap(ctx: MappingContext): ColumnMapping {
  const mapping: ColumnMapping = {};
  const { columns, sample } = ctx;

  const claimId = selectClaimId(columns, sample);
  if (claimId) mapping.CLAIM_ID = claimId;

  const pick = (field: keyof ColumnMapping, pattern: RegExp) => {
    if (mapping[field]) return; // already mapped
    const found = columns.find(c => pattern.test(c));
    if (found) mapping[field] = found;
  };

  pick('PRESCRIPTION_ID', /rx.*(number|id)|prescription.*(number|id)|script.*id/i);
  pick('DRUG_NDC', /ndc|national.*drug.*code|drug.*ndc|drug.*code|product.*code/i);
  pick('QUANTITY', /^(qty|quantity)$/i);
  pick('DAYS_SUPPLY', /days.*supply/i);
  pick('PHARMACY_ID', /pharmacy.*(id|ncpdp)|ncpdp|pharm.*id/i);
  pick('FILL_DATE', /fill.*date|dispense.*date|date.*filled|service.*date/i);
  pick('REBATE_AMOUNT', /rebate|discount|adj.*amount|credit|remit.*amount/i);
  pick('VENDOR_ERROR_CODE', /error.*code|dispute.*code|reject.*code|denial.*code/i);
  pick('DISPUTE_REASON', /reason|description|reject.*text|denial|resolution.*desc/i);

  return mapping;
}

export async function generateColumnMapping(sheet: SheetData): Promise<ColumnMapping> {
  const ctx: MappingContext = { columns: sheet.headers, sample: sheet.rows.slice(0, 100) };
  const mapping = heuristicMap(ctx);
  // Dev visibility: log mapping (can be removed later)
  if (typeof window !== 'undefined') {
    console.debug('[ColumnMapper] sheet', sheet.sheetName, 'mapping', mapping);
  }
  return mapping;
}

import * as XLSX from 'xlsx';
import type { SheetData, SheetProcessingResult, NormalizedClaim } from './types';
import { generateColumnMapping } from './ColumnMapper';
import { classifyClaim } from './Classification';

// Clean single implementation (removed duplicate legacy + Evidence hook)
// Heuristic header extraction to avoid __EMPTY / __EMPTY_X artifacts when first row isn't the true header.
// Strategy:
// 1. Use sheet_to_json with header:1 to get raw rows (arrays).
// 2. Find first candidate row with >=3 non-empty cells OR > 30% non-empty cells.
// 3. Drop columns with blank header values; ignore trailing empty columns.
// 4. Build objects for subsequent rows keyed by original (un-normalized) header strings.
// 5. Fallback to legacy behavior if heuristic fails.
type RawMatrixRow = (string | number | boolean | null)[];

function extractStructuredRows(sheet: XLSX.WorkSheet, sheetName: string): { headers: string[]; rows: Record<string, unknown>[] } {
  const matrix: RawMatrixRow[] = XLSX.utils.sheet_to_json<RawMatrixRow>(sheet, { header: 1, defval: '' });
  if (!matrix.length) return { headers: [], rows: [] };

  const isHeaderCandidate = (row: RawMatrixRow): boolean => {
    const nonEmpty = row.filter(c => String(c).trim().length > 0);
    if (nonEmpty.length >= 3) return true;
    return nonEmpty.length / (row.length || 1) >= 0.3 && nonEmpty.length >= 2;
  };

  let headerRowIndex = -1;
  for (let i = 0; i < matrix.length; i++) {
    if (isHeaderCandidate(matrix[i])) { headerRowIndex = i; break; }
  }
  if (headerRowIndex === -1) {
    // Fallback: use legacy sheet_to_json object form
    const legacy = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, { defval: '' });
    const headers = Object.keys(legacy[0] || {});
    console.debug('[Pipeline] Fallback legacy header extraction for sheet', sheetName, headers);
    return { headers, rows: legacy };
  }

  const rawHeader = matrix[headerRowIndex].map(h => String(h).trim());
  // Remove empty header columns in-place; collect indices to keep.
  const keepIndices: number[] = [];
  rawHeader.forEach((h, idx) => { if (h.length > 0) keepIndices.push(idx); });
  const headers = keepIndices.map(i => rawHeader[i]);

  const dataRows = matrix.slice(headerRowIndex + 1);
  const rows: Record<string, unknown>[] = dataRows.map((rArr) => {
    const obj: Record<string, unknown> = {};
    keepIndices.forEach((colIdx, i) => {
      const key = headers[i];
      obj[key] = rArr[colIdx] ?? '';
    });
    return obj;
  }).filter(r => Object.values(r).some(v => String(v).trim().length > 0)); // drop fully empty rows

  console.debug('[Pipeline] Extracted headers for sheet', sheetName, headers);
  console.debug('[Pipeline] Row sample', sheetName, rows[0]);
  return { headers, rows };
}

export async function parseExcel(file: File): Promise<SheetData[]> {
  const arrayBuf = await file.arrayBuffer();
  const wb = XLSX.read(arrayBuf, { type: 'array' });
  return wb.SheetNames.map(sheetName => {
    const sheet = wb.Sheets[sheetName];
    const { headers, rows } = extractStructuredRows(sheet, sheetName);
    return { sheetName, headers, rows };
  });
}

export async function processSheet(sheet: SheetData): Promise<SheetProcessingResult> {
  const mapping = await generateColumnMapping(sheet);
  const normalized: NormalizedClaim[] = sheet.rows.map(r => {
    const n: NormalizedClaim = { __raw: r };
  Object.entries(mapping).forEach(([std, orig]) => { if (orig) (n as Record<string, unknown>)[std] = r[orig]; });
    return n;
  });
  const results = normalized.map(c => classifyClaim(c));
  return { sheetName: sheet.sheetName, mapping, normalized, results };
}

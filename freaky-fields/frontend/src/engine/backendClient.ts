// Backend ingestion client
// Uses FastAPI endpoints to perform column mapping + classification

export interface BackendIngestSheet {
  sheetName: string;
  mapping: Record<string,string>;
  originalColumns: string[];
  mappedColumns: string[];
  rowCount: number;
  sampleMappedRows: Record<string,unknown>[];
  sampleClassification: Record<string,unknown>[];
  // Added in demo-v2 for source attribution & diagnostics
  mappingSource?: 'ai' | 'fallback' | 'client';
  aiError?: string | null;
}

export interface BackendIngestResponse {
  vendor: string;
  sheets: BackendIngestSheet[];
  success: boolean;
  error?: string;
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export async function ingestWorkbookBackend(file: File, vendor: string, sampleSize = 25): Promise<BackendIngestResponse> {
  const form = new FormData();
  form.append('vendor', vendor);
  form.append('file', file);
  form.append('sample_size', String(sampleSize)); // pass -1 to request full dataset
  const res = await fetch(`${API_BASE}/api/ingest`, { method: 'POST', body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Backend ingest failed: ${res.status} ${text}`);
  }
  return res.json();
}

// ---------------- Claim Chat ----------------
export interface ClaimChatPayload {
  question: string;
  CLAIM_ID: string;
  VENDOR: string;
  PRIMARY_DISPUTE_CODE: number;
  DESCRIPTION: string;
  CATEGORY: string;
  PRIORITY_RANK: number;
  ALL_APPLICABLE_CODES: string;
  EVIDENCE: string;
  CONFIDENCE: number;
  REQUIRES_REVIEW: boolean;
}

export interface ClaimChatResponse {
  claim_id: string;
  answer: string;
  success: boolean;
  model?: string;
  error?: string;
  direct_answer?: string;
  rationale?: string;
  next_action?: string;
  risks?: string;
  raw?: string;
  finish_reason?: string | null;
  completion_id?: string | null;
  diagnostics?: Record<string, unknown> | null;
}

export async function claimChat(payload: ClaimChatPayload): Promise<ClaimChatResponse> {
  const res = await fetch(`${API_BASE}/api/claim-chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Chat failed: ${res.status} ${text}`);
  }
  return res.json();
}

// ---------------- Classification Story ----------------
export interface ClassificationStoryPayload {
  CLAIM_ID: string;
  VENDOR: string;
  PRIMARY_DISPUTE_CODE: number;
  PRIMARY_DESCRIPTION: string;
  CATEGORY: string;
  PRIORITY_RANK: number;
  ALL_APPLICABLE_CODES: string;
  EVIDENCE: string;
  CONFIDENCE: number;
  REQUIRES_REVIEW: boolean;
  VENDOR_ERROR_CODES?: string | null;
  RULE_FLAGS?: string | null;
  ADDITIONAL_CONTEXT?: string | null;
}

export interface ClassificationStoryResponse {
  claim_id: string;
  story: string;
  success: boolean;
  model?: string | null;
  finish_reason?: string | null;
  raw?: string | null;
  error?: string;
}

export async function classificationStory(payload: ClassificationStoryPayload): Promise<ClassificationStoryResponse> {
  const res = await fetch(`${API_BASE}/api/classification-story`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Classification story failed: ${res.status} ${text}`);
  }
  return res.json();
}

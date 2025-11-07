import type { Claim } from '../types';

// Raw values from environment
const RAW_AI_SUMMARY_ENDPOINT = import.meta.env.VITE_AI_SUMMARY_ENDPOINT as string | undefined;
const API_BASE = import.meta.env.VITE_API_BASE as string | undefined;

// Build a fully qualified endpoint:
// - If RAW_AI_SUMMARY_ENDPOINT is absolute (http/https), use as-is.
// - If relative (starts with '/'), prepend API_BASE (or window.location.origin fallback).
// - If missing leading slash, treat as relative path segment.
function resolveEndpoint(): string | undefined {
  if (!RAW_AI_SUMMARY_ENDPOINT) return undefined;

  // Strip wrapping quotes if present (due to .env generation style)
  const trimmed = RAW_AI_SUMMARY_ENDPOINT.trim().replace(/^['"](.*)['"]$/, '$1');
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed; // already absolute
  }

  const base = (API_BASE && API_BASE.trim()) || window.location.origin;
  // Normalize slashes: remove trailing slash from base, ensure leading slash on path
  const normalizedBase = base.replace(/\/$/, '');
  const path = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  return `${normalizedBase}${path}`;
}

const AI_SUMMARY_ENDPOINT = resolveEndpoint();

const parseCodes = (codes: Claim['ALL_APPLICABLE_CODES']): string[] => {
  if (!codes) {
    return [];
  }

  if (Array.isArray(codes)) {
    return codes.map(item => String(item).trim()).filter(Boolean);
  }

  const trimmed = String(codes).trim();
  if (!trimmed) {
    return [];
  }

  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) {
      return parsed.map(item => String(item).trim()).filter(Boolean);
    }
  } catch {
    // Ignore JSON parse fallbacks and continue to delimiter-based parsing.
  }

  return trimmed
    .split(/[,|]/)
    .map(item => item.trim())
    .filter(Boolean);
};

const normalizeRequiresReview = (value: Claim['REQUIRES_REVIEW']): boolean => {
  if (typeof value === 'boolean') {
    return value;
  }

  if (typeof value === 'string') {
    return value.toLowerCase() === 'true' || value === '1';
  }

  return Boolean(value);
};

export async function requestClaimSummary(claim: Claim): Promise<string> {
  if (!AI_SUMMARY_ENDPOINT) {
    throw new Error('AI summary endpoint is not configured. Set VITE_AI_SUMMARY_ENDPOINT before requesting summaries.');
  }

  const payload = {
    CLAIM_ID: claim.CLAIM_ID,
    VENDOR: claim.VENDOR,
    PRIMARY_DISPUTE_CODE: claim.PRIMARY_DISPUTE_CODE,
    DESCRIPTION: claim.DESCRIPTION,
    CATEGORY: claim.CATEGORY,
    PRIORITY_RANK: claim.PRIORITY_RANK,
    CONFIDENCE: claim.CONFIDENCE,
    REQUIRES_REVIEW: normalizeRequiresReview(claim.REQUIRES_REVIEW),
    EVIDENCE: claim.EVIDENCE || '',
    ALL_APPLICABLE_CODES: parseCodes(claim.ALL_APPLICABLE_CODES).join(', '),
  };

  const response = await fetch(AI_SUMMARY_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const errorBody = await response.json();
      detail = errorBody?.error || errorBody?.message;
    } catch {
      // Response body is not JSON; ignore and fallback to status text.
    }

    const message = detail ? `AI summary request failed: ${detail}` : `AI summary request failed with status ${response.status}`;
    throw new Error(message);
  }

  const data = await response.json();
  const summary: unknown = data?.summary ?? data?.result ?? data?.message;

  if (typeof summary !== 'string' || summary.trim().length === 0) {
    throw new Error('AI summary response did not include summary text.');
  }

  return summary.trim();
}

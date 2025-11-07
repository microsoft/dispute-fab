import { Fragment, useEffect, useState, useMemo, useRef } from 'react';
import { 
  Box, 
  Heading, 
  Text, 
  Grid, 
  Card, 
  Flex,
  Input,
  Button,
  Badge,
  Table,
  VStack,
  HStack,
  Spinner,
  CloseButton,
  useBreakpointValue,
} from '@chakra-ui/react';
import { loadClaimsData, calculateStats, getComparisonMetrics } from '../dataLoader';
import type { Claim } from '../types';
import { requestClaimSummary } from '../services/aiSummaryService';
import { claimChat, classificationStory as fetchClassificationStory } from '../engine/backendClient';

type SummaryBlock =
  | { type: 'heading'; title: string }
  | { type: 'paragraph'; text: string }
  | { type: 'list'; items: string[] };

const trimQuotes = (value: string) => value.replace(/^["'“”]+|["'“”]+$/g, '').trim();

const parseAiSummary = (summary: string): SummaryBlock[] => {
  const lines = summary
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean);

  const blocks: SummaryBlock[] = [];
  let currentList: string[] = [];

  const flushList = () => {
    if (currentList.length === 0) return;
    blocks.push({ type: 'list', items: currentList });
    currentList = [];
  };

  lines.forEach(line => {
    if (/^[-*]\s+/.test(line)) {
      const cleaned = trimQuotes(line.replace(/^[-*]\s+/, ''));
      if (cleaned) {
        currentList.push(cleaned);
      }
      return;
    }

    if (/^\d+\.\s+/.test(line)) {
      const cleaned = trimQuotes(line.replace(/^\d+\.\s+/, ''));
      if (cleaned) {
        currentList.push(cleaned);
      }
      return;
    }

    flushList();

    const headingMatch = line.match(/^\*\*(.+?)\*\*:?\s*(.*)$/);
    if (headingMatch) {
      const heading = trimQuotes(headingMatch[1]);
      if (heading) {
        blocks.push({ type: 'heading', title: heading });
      }
      const remainder = trimQuotes(headingMatch[2] || '');
      if (remainder) {
        blocks.push({ type: 'paragraph', text: remainder });
      }
      return;
    }

    const cleaned = trimQuotes(line);
    if (cleaned) {
      blocks.push({ type: 'paragraph', text: cleaned });
    }
  });

  flushList();
  return blocks;
};

const renderStructuredBlocks = (blocks: SummaryBlock[], keyPrefix: string) => {
  return blocks.map((block, idx) => {
    if (block.type === 'heading') {
      const showSeparator = idx !== 0;
      return (
        <Fragment key={`${keyPrefix}-heading-${idx}`}>
          {showSeparator && <Box borderTop="1px solid" borderColor="gray.200" pt={2} />}
          <Text
            fontSize="xs"
            fontWeight="semibold"
            color="gray.600"
            textTransform="uppercase"
            letterSpacing="0.08em"
          >
            {block.title}
          </Text>
        </Fragment>
      );
    }

    if (block.type === 'paragraph') {
      return (
        <Text
          key={`${keyPrefix}-paragraph-${idx}`}
          fontSize="sm"
          color="gray.700"
          lineHeight="1.6"
        >
          {block.text}
        </Text>
      );
    }

    return (
      <Box as="ul" key={`${keyPrefix}-list-${idx}`} pl={4} display="grid" gap={1}>
        {block.items.map((item, bulletIdx) => (
          <Box
            as="li"
            key={`${keyPrefix}-list-${idx}-item-${bulletIdx}`}
            fontSize="sm"
            color="gray.700"
            lineHeight="1.5"
          >
            {item}
          </Box>
        ))}
      </Box>
    );
  });
};

const getPriorityBadgeStyles = (rank: number) => {
  if (rank <= 8) {
    return { bg: 'red.50', color: 'red.700', borderColor: 'red.200' };
  }
  if (rank <= 12) {
    return { bg: 'orange.50', color: 'orange.700', borderColor: 'orange.200' };
  }
  if (rank <= 16) {
    return { bg: 'yellow.50', color: 'yellow.700', borderColor: 'yellow.300' };
  }
  return { bg: 'gray.100', color: 'gray.700', borderColor: 'gray.300' };
};

const getConfidenceChipStyles = (confidence: number) => {
  if (confidence >= 0.9) {
    return { bg: 'green.50', color: 'green.700', borderColor: 'green.200' };
  }
  if (confidence >= 0.7) {
    return { bg: 'orange.50', color: 'orange.700', borderColor: 'orange.200' };
  }
  return { bg: 'red.50', color: 'red.700', borderColor: 'red.200' };
};

const getCodeBadgeStyles = (code: number) => {
  if (code === 104) {
    return { bg: 'red.50', color: 'red.700', borderColor: 'red.200' };
  }
  return { bg: 'blue.50', color: 'blue.700', borderColor: 'blue.200' };
};

const normalizeText = (value: unknown) => String(value ?? '').toLowerCase();

const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

const formatCurrency = (value: number | null | undefined) => {
  if (!isFiniteNumber(value)) {
    return '—';
  }
  const formatted = Math.abs(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return value < 0 ? `-$${formatted}` : `$${formatted}`;
};

const parseRangeValue = (raw: string): number | null => {
  const trimmed = raw.trim();
  if (trimmed === '') {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
};

const CODE_DESCRIPTIONS: Record<number, string> = {
  301: 'Excluded 340B Pharmacy',
  302: 'Government Pharmacy',
  303: 'Hospital Pharmacy',
  304: 'Long Term Care and Nursing Home Pharmacies',
  305: 'Pharmacy ID is Invalid',
  306: 'Pharmacy in Excluded List',
  307: 'Pharmacy in Excluded State',
  308: 'Pharmacy Service Type is Invalid',
  401: 'Horizontal Duplicate',
  402: 'Vertical Duplicate',
  403: 'Internal Duplicate (DUP)',
  404: 'Coordination of Benefits',
  101: 'Aberrant Quantity',
  102: 'Days Supply is Invalid',
  103: 'Units per Day Exceeds Limit',
  104: 'RX ID is invalid',
  201: 'Formulary Non-Compliance',
  202: 'Plan ID is Invalid',
  203: 'Product Date Range',
  204: 'Product ID or NDC is Invalid',
  205: 'Rebate Rate is Invalid',
  501: 'Claims from Prior Quarters',
  502: 'Prior Exclusion Credit',
};

export default function Dashboard() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Chat state
  const [chatQuestion, setChatQuestion] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<Array<{
    q: string;
    a: string;
    direct?: string;
    rationale?: string;
    next?: string;
    risks?: string;
    model?: string | null;
    finishReason?: string | null;
    completionId?: string | null;
    diagnostics?: Record<string, unknown> | null;
  }>>([]);
  const [chatError, setChatError] = useState<string | null>(null);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);
  const [classificationStoryText, setClassificationStoryText] = useState<string | null>(null);
  const [classificationStoryModel, setClassificationStoryModel] = useState<string | null>(null);
  const [classificationStoryFinish, setClassificationStoryFinish] = useState<string | null>(null);
  const [classificationStoryLoading, setClassificationStoryLoading] = useState(false);
  const [classificationStoryError, setClassificationStoryError] = useState<string | null>(null);
  const classificationStoryCache = useRef<Map<string, { story: string; model?: string | null; finish?: string | null }>>(
    new Map()
  );
  const [classificationStoryExpanded, setClassificationStoryExpanded] = useState(false);
  const [summaryExpanded, setSummaryExpanded] = useState(true);

  const handleClearChat = () => {
    setChatHistory([]);
    setChatError(null);
    setChatQuestion('');
  };

  const handleClaimChat = async () => {
    if (!selectedClaim || !chatQuestion.trim()) return;
    setChatLoading(true);
    setChatError(null);
    try {
      const payload = {
        question: chatQuestion.trim(),
        CLAIM_ID: String(selectedClaim.CLAIM_ID),
        VENDOR: String(selectedClaim.VENDOR || 'UNKNOWN'),
        PRIMARY_DISPUTE_CODE: Number(selectedClaim.PRIMARY_DISPUTE_CODE || 0),
        DESCRIPTION: String(selectedClaim.DESCRIPTION || ''),
        CATEGORY: String(selectedClaim.CATEGORY || 'UNSPECIFIED'),
        PRIORITY_RANK: Number(selectedClaim.PRIORITY_RANK || 0),
        ALL_APPLICABLE_CODES: String(selectedClaim.ALL_APPLICABLE_CODES || ''),
        EVIDENCE: String(selectedClaim.EVIDENCE || ''),
        CONFIDENCE: Number(selectedClaim.CONFIDENCE || 0),
        REQUIRES_REVIEW: Boolean(selectedClaim.REQUIRES_REVIEW || false)
      };
      const resp = await claimChat(payload as unknown as {
        question: string; CLAIM_ID: string; VENDOR: string; PRIMARY_DISPUTE_CODE: number; DESCRIPTION: string; CATEGORY: string; PRIORITY_RANK: number; ALL_APPLICABLE_CODES: string; EVIDENCE: string; CONFIDENCE: number; REQUIRES_REVIEW: boolean;
      });
      setChatHistory(h => [
        ...h,
        {
          q: chatQuestion.trim(),
          a: resp.answer,
          direct: resp.direct_answer,
          rationale: resp.rationale,
          next: resp.next_action,
          risks: resp.risks,
          model: resp.model ?? null,
          finishReason: resp.finish_reason ?? null,
          completionId: resp.completion_id ?? null,
          diagnostics: resp.diagnostics ?? null,
        },
      ]);
      setChatQuestion('');
    } catch (e: unknown) {
      setChatError(e instanceof Error ? e.message : 'Chat request failed');
    } finally {
      setChatLoading(false);
    }
  };

  const getSortLabel = (field: 'rebate' | 'amount', label: string) =>
    sortField === field ? `${label} (${sortDirection === 'asc' ? '↑' : '↓'})` : label;

  const handleSortChange = (field: 'rebate' | 'amount') => {
    if (sortField === field) {
      setSortDirection(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const handleSortReset = () => {
    setSortField('none');
    setSortDirection('desc');
  };
  const [search, setSearch] = useState('');
  const [vendorFilter, setVendorFilter] = useState('');
  const [reviewFilter, setReviewFilter] = useState<'all' | 'review' | 'no-review'>('all');
  const [codeFilter, setCodeFilter] = useState('');
  const [rebateMin, setRebateMin] = useState('');
  const [rebateMax, setRebateMax] = useState('');
  const [amountMin, setAmountMin] = useState('');
  const [amountMax, setAmountMax] = useState('');
  const [sortField, setSortField] = useState<'none' | 'rebate' | 'amount'>('none');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(100);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  
  // Load data on mount
  useEffect(() => {
    loadClaimsData()
      .then(data => {
        setClaims(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    setAiSummary(null);
    setAiError(null);
    setAiLoading(false);
    setAiPanelOpen(false);
    setClassificationStoryText(null);
    setClassificationStoryModel(null);
    setClassificationStoryFinish(null);
    setClassificationStoryError(null);
    setClassificationStoryLoading(false);
    setClassificationStoryExpanded(false);
    setSummaryExpanded(true);
  }, [selectedClaim?.CLAIM_ID]);

  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [chatHistory, aiPanelOpen]);

  useEffect(() => {
    if (!selectedClaim) {
      setClassificationStoryText(null);
      setClassificationStoryModel(null);
      setClassificationStoryFinish(null);
      setClassificationStoryError(null);
      setClassificationStoryLoading(false);
      setClassificationStoryExpanded(false);
      return;
    }

    const claimKey = String(selectedClaim.CLAIM_ID);
    const cached = classificationStoryCache.current.get(claimKey);
    if (cached) {
      setClassificationStoryText(cached.story);
      setClassificationStoryModel(cached.model ?? null);
      setClassificationStoryFinish(cached.finish ?? null);
      setClassificationStoryLoading(false);
      return;
    }

    let cancelled = false;
    setClassificationStoryLoading(true);
    setClassificationStoryError(null);

    const rawRequiresReview = selectedClaim.REQUIRES_REVIEW;
    const requiresReview = typeof rawRequiresReview === 'string'
      ? rawRequiresReview.toLowerCase() === 'true'
      : Boolean(rawRequiresReview);

    const payload = {
      CLAIM_ID: String(selectedClaim.CLAIM_ID),
      VENDOR: String(selectedClaim.VENDOR || 'UNKNOWN'),
      PRIMARY_DISPUTE_CODE: Number(selectedClaim.PRIMARY_DISPUTE_CODE || 0),
      PRIMARY_DESCRIPTION: String(selectedClaim.DESCRIPTION || ''),
      CATEGORY: String(selectedClaim.CATEGORY || 'UNSPECIFIED'),
      PRIORITY_RANK: Number(selectedClaim.PRIORITY_RANK || 0),
      ALL_APPLICABLE_CODES: String(selectedClaim.ALL_APPLICABLE_CODES || ''),
      EVIDENCE: String(selectedClaim.EVIDENCE || ''),
      CONFIDENCE: Number(selectedClaim.CONFIDENCE || 0),
      REQUIRES_REVIEW: requiresReview,
    };

    fetchClassificationStory(payload)
      .then(resp => {
        if (cancelled) return;
        setClassificationStoryText(resp.story);
        setClassificationStoryModel(resp.model ?? null);
        setClassificationStoryFinish(resp.finish_reason ?? null);
        classificationStoryCache.current.set(claimKey, {
          story: resp.story,
          model: resp.model ?? null,
          finish: resp.finish_reason ?? null,
        });
      })
      .catch(err => {
        if (cancelled) return;
        setClassificationStoryError(err instanceof Error ? err.message : 'Failed to generate classification story');
      })
      .finally(() => {
        if (!cancelled) {
          setClassificationStoryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedClaim]);
  
  // Calculate stats
  const stats = useMemo(() => {
    if (claims.length === 0) return null;
    return calculateStats(claims);
  }, [claims]);
  
  const comparison = getComparisonMetrics();
  const classificationStoryBlocks = useMemo(
    () => (classificationStoryText ? parseAiSummary(classificationStoryText) : []),
    [classificationStoryText]
  );
  const classificationStoryPreviewText = useMemo(() => {
    if (!classificationStoryText) return null;
    const trimmed = classificationStoryText.trim();
    if (trimmed.length <= 320) {
      return trimmed;
    }
    return `${trimmed.slice(0, 320).trim()}…`;
  }, [classificationStoryText]);
  const showClassificationExpandHint = useMemo(() => {
    if (!classificationStoryText) return false;
    if (classificationStoryBlocks.length > 3) return true;
    const trimmed = classificationStoryText.trim();
    const preview = classificationStoryPreviewText?.trim() ?? '';
    return preview.length > 0 && preview.length < trimmed.length;
  }, [classificationStoryBlocks, classificationStoryPreviewText, classificationStoryText]);
  const summaryBlocks = useMemo(() => (aiSummary ? parseAiSummary(aiSummary) : []), [aiSummary]);
  const aiPanelWidthConfig = useMemo(
    () => ({ base: '100%', md: '360px', lg: '420px', xl: '480px' } as const),
    []
  );
  const aiPanelWidthValue = useBreakpointValue({ base: 0, md: 360, lg: 420, xl: 480 }) ?? 0;

  useEffect(() => {
    if (aiSummary) {
      setSummaryExpanded(true);
    }
  }, [aiSummary]);
  const detailRightOffset = aiPanelOpen && aiPanelWidthValue > 0 ? `${aiPanelWidthValue}px` : '0px';

  const handleSummarizeClaim = async () => {
    if (!selectedClaim) {
      return;
    }

    setAiPanelOpen(true);
    setAiLoading(true);
    setAiError(null);

    try {
      const summary = await requestClaimSummary(selectedClaim);
      setAiSummary(summary);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to generate AI summary.';
      setAiError(message);
    } finally {
      setAiLoading(false);
    }
  };
  
  // Filter claims
  const filteredClaims = useMemo(() => {
    const normalizedSearch = normalizeText(search);
    const hasSearch = normalizedSearch.length > 0;
    const vendorTarget = normalizeText(vendorFilter);
    const codeTarget = codeFilter.trim();
    const minRebateValue = parseRangeValue(rebateMin);
    const maxRebateValue = parseRangeValue(rebateMax);
    const minAmountValue = parseRangeValue(amountMin);
    const maxAmountValue = parseRangeValue(amountMax);

    const filtered = claims.filter(claim => {
      const matchesSearch = !hasSearch ||
        normalizeText(claim.CLAIM_ID).includes(normalizedSearch) ||
        normalizeText(claim.VENDOR).includes(normalizedSearch) ||
        normalizeText(claim.DESCRIPTION).includes(normalizedSearch) ||
        normalizeText(claim.EVIDENCE).includes(normalizedSearch);

      if (!matchesSearch) return false;

      const matchesVendor = vendorFilter === '' || normalizeText(claim.VENDOR) === vendorTarget;
      if (!matchesVendor) return false;

      const matchesReview =
        reviewFilter === 'all' ||
        (reviewFilter === 'review' && claim.REQUIRES_REVIEW) ||
        (reviewFilter === 'no-review' && !claim.REQUIRES_REVIEW);
      if (!matchesReview) return false;

      const matchesCode = codeTarget === '' || String(claim.PRIMARY_DISPUTE_CODE) === codeTarget;
      if (!matchesCode) return false;

      const rebateValue = claim.REBATE_AMOUNT;
      if (minRebateValue !== null || maxRebateValue !== null) {
        if (!isFiniteNumber(rebateValue)) {
          return false;
        }
        if (minRebateValue !== null && rebateValue < minRebateValue) {
          return false;
        }
        if (maxRebateValue !== null && rebateValue > maxRebateValue) {
          return false;
        }
      }

      const amountValue = claim.CLAIM_AMOUNT;
      if (minAmountValue !== null || maxAmountValue !== null) {
        if (!isFiniteNumber(amountValue)) {
          return false;
        }
        if (minAmountValue !== null && amountValue < minAmountValue) {
          return false;
        }
        if (maxAmountValue !== null && amountValue > maxAmountValue) {
          return false;
        }
      }

      return true;
    });

    if (sortField === 'none') {
      return filtered;
    }

    const directionMultiplier = sortDirection === 'asc' ? 1 : -1;
    const sentinel = sortDirection === 'asc' ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
    const getSortValue = (claim: Claim) => {
      const raw = sortField === 'rebate' ? claim.REBATE_AMOUNT : claim.CLAIM_AMOUNT;
      return isFiniteNumber(raw) ? raw : sentinel;
    };

    return [...filtered].sort((a, b) => {
      const aVal = getSortValue(a);
      const bVal = getSortValue(b);
      if (aVal === bVal) {
        return String(a.CLAIM_ID).localeCompare(String(b.CLAIM_ID));
      }
      return aVal > bVal ? directionMultiplier : -directionMultiplier;
    });
  }, [
    claims,
    search,
    vendorFilter,
    reviewFilter,
    codeFilter,
    rebateMin,
    rebateMax,
    amountMin,
    amountMax,
    sortField,
    sortDirection,
  ]);
  
  // Get unique vendors
  const vendors = useMemo(() => {
    return Array.from(new Set(claims.map(c => c.VENDOR))).sort();
  }, [claims]);
  const codes = useMemo(() => {
    const unique = new Set<number>();
    claims.forEach(claim => {
      const code = claim.PRIMARY_DISPUTE_CODE;
      if (Number.isFinite(code)) {
        unique.add(code);
      }
    });
    return Array.from(unique).sort((a, b) => a - b);
  }, [claims]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [search, vendorFilter, reviewFilter, codeFilter, rebateMin, rebateMax, amountMin, amountMax, sortField, sortDirection]);

  // Pagination
  const totalPages = Math.ceil(filteredClaims.length / itemsPerPage);
  const paginatedClaims = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return filteredClaims.slice(startIndex, endIndex);
  }, [filteredClaims, currentPage, itemsPerPage]);
  
  if (loading) {
    return (
      <Flex justify="center" align="center" h="400px">
        <VStack>
          <Spinner size="xl" color="blue.500" />
          <Text>Loading claims data...</Text>
        </VStack>
      </Flex>
    );
  }
  
  if (error) {
    return (
      <Box bg="red.100" borderColor="red.500" borderWidth={1} p={4} borderRadius="md">
        <VStack align="start">
          <Text fontWeight="bold" color="red.700">Error loading data:</Text>
          <Text>{error}</Text>
          <Text fontSize="sm">Make sure the CSV file is available at /outputs/all_vendors_classification_results.csv</Text>
        </VStack>
      </Box>
    );
  }
  
  return (
    <VStack gap={8} align="stretch" pb={8}>
      <Heading size="xl">SeeHealth Claims Classification Dashboard</Heading>
      
      {/* Summary Stats */}
      {stats && (
        <>
          <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)", lg: "repeat(4, 1fr)" }} gap={5}>
            <Card.Root bg="white" borderWidth="1px" borderColor="gray.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">Total Claims</Text>
                  <Heading size="3xl" color="gray.800" fontWeight="bold">{stats.totalClaims.toLocaleString()}</Heading>
                </VStack>
              </Card.Body>
            </Card.Root>
            
            <Card.Root bg="white" borderWidth="1px" borderColor="orange.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">Requires Review</Text>
                  <Heading size="3xl" color="orange.600" fontWeight="bold">
                    {stats.requiresReview.toLocaleString()}
                  </Heading>
                  <Text fontSize="sm" color="gray.600" fontWeight="medium">
                    {((stats.requiresReview / stats.totalClaims) * 100).toFixed(1)}%
                  </Text>
                </VStack>
              </Card.Body>
            </Card.Root>
            
            <Card.Root bg="white" borderWidth="1px" borderColor="green.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">Avg Confidence</Text>
                  <Heading size="3xl" color="green.600" fontWeight="bold">
                    {(stats.avgConfidence * 100).toFixed(1)}%
                  </Heading>
                </VStack>
              </Card.Body>
            </Card.Root>
            
            <Card.Root bg="white" borderWidth="1px" borderColor="blue.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">Total Vendors</Text>
                  <Heading size="3xl" color="blue.600" fontWeight="bold">{stats.totalVendors}</Heading>
                </VStack>
              </Card.Body>
            </Card.Root>
          </Grid>

          {/* Additional Insights */}
          <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" }} gap={5}>
            <Card.Root bg="white" borderWidth="1px" borderColor="red.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">High Priority Claims</Text>
                  <Heading size="3xl" color="red.600" fontWeight="bold">
                    {claims.filter(c => c.PRIORITY_RANK <= 12).length.toLocaleString()}
                  </Heading>
                  <Text fontSize="sm" color="gray.600" fontWeight="medium">
                    {((claims.filter(c => c.PRIORITY_RANK <= 12).length / stats.totalClaims) * 100).toFixed(1)}% of total
                  </Text>
                </VStack>
              </Card.Body>
            </Card.Root>

            <Card.Root bg="white" borderWidth="1px" borderColor="purple.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">Top Dispute Code</Text>
                  <Heading size="3xl" color="purple.600" fontWeight="bold">
                    {stats.topCodes[0]?.code || '—'}
                  </Heading>
                  <Text fontSize="xs" color="gray.600" truncate>
                    {stats.topCodes[0]?.description || 'N/A'}
                  </Text>
                  <Text fontSize="sm" color="gray.600" fontWeight="medium">
                    {stats.topCodes[0]?.count.toLocaleString() || 0} claims ({stats.topCodes[0]?.percentage.toFixed(1) || 0}%)
                  </Text>
                </VStack>
              </Card.Body>
            </Card.Root>

            <Card.Root bg="white" borderWidth="1px" borderColor="teal.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">Avg Claim Amount</Text>
                  <Heading size="3xl" color="teal.600" fontWeight="bold">
                    {formatCurrency(
                      claims.reduce((sum, c) => sum + (isFiniteNumber(c.CLAIM_AMOUNT) ? c.CLAIM_AMOUNT : 0), 0) / 
                      claims.filter(c => isFiniteNumber(c.CLAIM_AMOUNT)).length
                    )}
                  </Heading>
                  <Text fontSize="sm" color="gray.600" fontWeight="medium">
                    {claims.filter(c => isFiniteNumber(c.CLAIM_AMOUNT)).length.toLocaleString()} claims with amounts
                  </Text>
                </VStack>
              </Card.Body>
            </Card.Root>

            <Card.Root bg="white" borderWidth="1px" borderColor="cyan.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">Total Financial Impact</Text>
                  <Heading size="3xl" color="cyan.600" fontWeight="bold">
                    {formatCurrency(
                      claims.reduce((sum, c) => sum + (isFiniteNumber(c.REBATE_AMOUNT) ? c.REBATE_AMOUNT : 0), 0)
                    )}
                  </Heading>
                  <Text fontSize="sm" color="gray.600" fontWeight="medium">
                    Total rebate amount disputed
                  </Text>
                </VStack>
              </Card.Body>
            </Card.Root>

            <Card.Root bg="white" borderWidth="1px" borderColor="yellow.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">Low Confidence Rate</Text>
                  <Heading size="3xl" color="yellow.600" fontWeight="bold">
                    {claims.filter(c => c.CONFIDENCE < 0.7).length.toLocaleString()}
                  </Heading>
                  <Text fontSize="sm" color="gray.600" fontWeight="medium">
                    {((claims.filter(c => c.CONFIDENCE < 0.7).length / stats.totalClaims) * 100).toFixed(1)}% below 70%
                  </Text>
                </VStack>
              </Card.Body>
            </Card.Root>

            <Card.Root bg="white" borderWidth="1px" borderColor="green.200" boxShadow="sm">
              <Card.Body p={6}>
                <VStack align="start" gap={2}>
                  <Text fontSize="xs" fontWeight="semibold" color="gray.500" textTransform="uppercase" letterSpacing="wide">Auto-Approved</Text>
                  <Heading size="3xl" color="green.600" fontWeight="bold">
                    {(stats.totalClaims - stats.requiresReview).toLocaleString()}
                  </Heading>
                  <Text fontSize="sm" color="gray.600" fontWeight="medium">
                    {(((stats.totalClaims - stats.requiresReview) / stats.totalClaims) * 100).toFixed(1)}% no review needed
                  </Text>
                </VStack>
              </Card.Body>
            </Card.Root>
          </Grid>
        </>
      )}
      
      {/* Before/After Comparison */}
      <Card.Root bg="gradient.to-r" gradientFrom="white" gradientTo="purple.50" borderWidth="1px" borderColor="blue.100" boxShadow="md">
        <Card.Header pb={3}>
          <Heading size="lg" color="gray.800">AI Column Mapping Impact</Heading>
        </Card.Header>
        <Card.Body pt={3}>
          <Grid templateColumns={{ base: "1fr", md: "repeat(3, 1fr)" }} gap={6}>
            <Box bg="white" p={5} borderRadius="xl" borderWidth="1px" borderColor="gray.200" boxShadow="base">
              <Text fontSize="xs" fontWeight="semibold" color="gray.500" mb={3} textTransform="uppercase" letterSpacing="wide">Real Classifications</Text>
              <Flex align="center" gap={3} mb={3}>
                <Box>
                  <Text fontSize="xs" color="gray.500">Before</Text>
                  <Text fontSize="2xl" fontWeight="bold" color="red.600">{comparison.before.realClassificationsPercentage}%</Text>
                </Box>
                <Text fontSize="2xl" color="gray.400">→</Text>
                <Box>
                  <Text fontSize="xs" color="gray.500">After</Text>
                  <Text fontSize="2xl" fontWeight="bold" color="green.600">{comparison.after.realClassificationsPercentage}%</Text>
                </Box>
              </Flex>
              <Box
                as="span"
                px={3}
                py={1}
                borderRadius="full"
                fontWeight="semibold"
                fontSize="xs"
                bg="green.50"
                color="green.700"
                borderWidth="1px"
                borderColor="green.200"
              >
                +{(comparison.after.realClassificationsPercentage - comparison.before.realClassificationsPercentage).toFixed(1)}%
              </Box>
            </Box>

            <Box bg="white" p={5} borderRadius="xl" borderWidth="1px" borderColor="gray.200" boxShadow="base">
              <Text fontSize="xs" fontWeight="semibold" color="gray.500" mb={3} textTransform="uppercase" letterSpacing="wide">Valid CLAIM_IDs</Text>
              <Flex align="center" gap={3} mb={3}>
                <Box>
                  <Text fontSize="xs" color="gray.500">Before</Text>
                  <Text fontSize="2xl" fontWeight="bold" color="red.600">{comparison.before.validClaimIdsPercentage}%</Text>
                </Box>
                <Text fontSize="2xl" color="gray.400">→</Text>
                <Box>
                  <Text fontSize="xs" color="gray.500">After</Text>
                  <Text fontSize="2xl" fontWeight="bold" color="green.600">{comparison.after.validClaimIdsPercentage}%</Text>
                </Box>
              </Flex>
              <Box
                as="span"
                px={3}
                py={1}
                borderRadius="full"
                fontWeight="semibold"
                fontSize="xs"
                bg="green.50"
                color="green.700"
                borderWidth="1px"
                borderColor="green.200"
              >
                +{(comparison.after.validClaimIdsPercentage - comparison.before.validClaimIdsPercentage).toFixed(1)}%
              </Box>
            </Box>

            <Box bg="white" p={5} borderRadius="xl" borderWidth="1px" borderColor="gray.200" boxShadow="base">
              <Text fontSize="xs" fontWeight="semibold" color="gray.500" mb={3} textTransform="uppercase" letterSpacing="wide">Code 104 (Fallback)</Text>
              <Flex align="center" gap={3} mb={3}>
                <Box>
                  <Text fontSize="xs" color="gray.500">Before</Text>
                  <Text fontSize="2xl" fontWeight="bold" color="red.600">{comparison.before.code104Percentage}%</Text>
                </Box>
                <Text fontSize="2xl" color="gray.400">→</Text>
                <Box>
                  <Text fontSize="xs" color="gray.500">After</Text>
                  <Text fontSize="2xl" fontWeight="bold" color="green.600">{comparison.after.code104Percentage}%</Text>
                </Box>
              </Flex>
              <Box
                as="span"
                px={3}
                py={1}
                borderRadius="full"
                fontWeight="semibold"
                fontSize="xs"
                bg="blue.50"
                color="blue.700"
                borderWidth="1px"
                borderColor="blue.200"
              >
                -{(comparison.before.code104Percentage - comparison.after.code104Percentage).toFixed(1)}%
              </Box>
            </Box>
          </Grid>
        </Card.Body>
      </Card.Root>
      
      {/* Filters and Search */}
      <Card.Root bg="white" borderWidth="1px" borderColor="gray.200" boxShadow="sm">
        <Card.Header pb={3} borderBottom="1px" borderColor="gray.200">
          <Flex justify="space-between" align="center">
            <Heading size="lg" color="gray.800">Claims Browser</Heading>
            <Box
              as="span"
              px={3}
              py={1}
              borderRadius="full"
              fontSize="sm"
              fontWeight="semibold"
              bg="blue.50"
              color="blue.700"
              borderWidth="1px"
              borderColor="blue.200"
            >
              {filteredClaims.length.toLocaleString()} claims
            </Box>
          </Flex>
        </Card.Header>
        <Card.Body pt={5}>
          <VStack align="stretch" gap={4} mb={5}>
            <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' }} gap={3}>
              <Input
                placeholder="Search claims..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                size="md"
                borderColor="gray.300"
                _focus={{ borderColor: 'blue.400', boxShadow: '0 0 0 1px var(--chakra-colors-blue-400)' }}
              />

              <select
                value={vendorFilter}
                onChange={(e) => setVendorFilter(e.target.value)}
                style={{
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E0',
                  fontSize: '14px',
                  backgroundColor: 'white',
                  cursor: 'pointer',
                }}
              >
                <option value="">All Vendors</option>
                {vendors.map(vendor => (
                  <option key={vendor} value={vendor}>{vendor}</option>
                ))}
              </select>

              <select
                value={reviewFilter}
                onChange={(e) => setReviewFilter(e.target.value as 'all' | 'review' | 'no-review')}
                style={{
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E0',
                  fontSize: '14px',
                  backgroundColor: 'white',
                  cursor: 'pointer',
                }}
              >
                <option value="all">All Claims</option>
                <option value="review">Requires Review</option>
                <option value="no-review">No Review Needed</option>
              </select>

              <select
                value={codeFilter}
                onChange={(e) => setCodeFilter(e.target.value)}
                style={{
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E0',
                  fontSize: '14px',
                  backgroundColor: 'white',
                  cursor: 'pointer',
                }}
              >
                <option value="">All Codes</option>
                {codes.map(code => (
                  <option key={code} value={code}>
                    {code} - {CODE_DESCRIPTIONS[code] || 'Unknown'}
                  </option>
                ))}
              </select>
            </Grid>

            <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' }} gap={3}>
              <Input
                type="number"
                placeholder="Min Rebate"
                value={rebateMin}
                onChange={(e) => setRebateMin(e.target.value)}
                borderColor="gray.300"
                _focus={{ borderColor: 'purple.400', boxShadow: '0 0 0 1px var(--chakra-colors-purple-400)' }}
                inputMode="decimal"
              />
              <Input
                type="number"
                placeholder="Max Rebate"
                value={rebateMax}
                onChange={(e) => setRebateMax(e.target.value)}
                borderColor="gray.300"
                _focus={{ borderColor: 'purple.400', boxShadow: '0 0 0 1px var(--chakra-colors-purple-400)' }}
                inputMode="decimal"
              />
              <Input
                type="number"
                placeholder="Min Amount"
                value={amountMin}
                onChange={(e) => setAmountMin(e.target.value)}
                borderColor="gray.300"
                _focus={{ borderColor: 'purple.400', boxShadow: '0 0 0 1px var(--chakra-colors-purple-400)' }}
                inputMode="decimal"
              />
              <Input
                type="number"
                placeholder="Max Amount"
                value={amountMax}
                onChange={(e) => setAmountMax(e.target.value)}
                borderColor="gray.300"
                _focus={{ borderColor: 'purple.400', boxShadow: '0 0 0 1px var(--chakra-colors-purple-400)' }}
                inputMode="decimal"
              />
            </Grid>

            <Flex align={{ base: 'stretch', md: 'center' }} justify="space-between" gap={3} flexWrap="wrap">
              <HStack gap={2} flexWrap="wrap">
                <Button
                  size="sm"
                  variant={sortField === 'rebate' ? 'solid' : 'outline'}
                  colorScheme={sortField === 'rebate' ? 'purple' : 'gray'}
                  onClick={() => handleSortChange('rebate')}
                >
                  {getSortLabel('rebate', 'Sort Rebate')}
                </Button>
                <Button
                  size="sm"
                  variant={sortField === 'amount' ? 'solid' : 'outline'}
                  colorScheme={sortField === 'amount' ? 'purple' : 'gray'}
                  onClick={() => handleSortChange('amount')}
                >
                  {getSortLabel('amount', 'Sort Amount')}
                </Button>
                {sortField !== 'none' && (
                  <Button size="sm" variant="ghost" colorScheme="gray" onClick={handleSortReset}>
                    Clear Sort
                  </Button>
                )}
              </HStack>
              <Button
                onClick={() => {
                  setSearch('');
                  setVendorFilter('');
                  setReviewFilter('all');
                  setCodeFilter('');
                  setRebateMin('');
                  setRebateMax('');
                  setAmountMin('');
                  setAmountMax('');
                  handleSortReset();
                }}
                variant="outline"
                size="sm"
                borderRadius="full"
                borderColor="gray.300"
                color="gray.700"
                bg="white"
                _hover={{ bg: 'gray.100', borderColor: 'gray.400' }}
                _active={{ bg: 'gray.200' }}
              >
                Clear Filters
              </Button>
            </Flex>
          </VStack>

          {/* Claims Table */}
          <Box overflowX="auto" borderRadius="lg" borderWidth="1px" borderColor="gray.200">
            <Box maxH="600px" overflowY="auto">
              <Table.Root
                size="md"
                variant="line"
                key={`table-${filteredClaims.length}-${vendorFilter}-${codeFilter}-${reviewFilter}-${sortField}-${sortDirection}`}
              >
                <Table.Header position="sticky" top={0} bg="gray.50" zIndex={1} borderBottom="2px" borderColor="gray.300">
                  <Table.Row>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600">Claim ID</Table.ColumnHeader>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600">Vendor</Table.ColumnHeader>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600">Code</Table.ColumnHeader>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600">Description</Table.ColumnHeader>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600">Priority</Table.ColumnHeader>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600">Confidence</Table.ColumnHeader>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600" textAlign="right">
                      {getSortLabel('rebate', 'Rebate')}
                    </Table.ColumnHeader>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600" textAlign="right">
                      {getSortLabel('amount', 'Amount')}
                    </Table.ColumnHeader>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600">Review</Table.ColumnHeader>
                    <Table.ColumnHeader fontWeight="bold" fontSize="xs" textTransform="uppercase" color="gray.600">Actions</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
              <Table.Body>
                {paginatedClaims.map((claim, idx) => {
                  const codeStyles = getCodeBadgeStyles(claim.PRIMARY_DISPUTE_CODE);
                  const priorityStyles = getPriorityBadgeStyles(claim.PRIORITY_RANK);
                  const confidenceStyles = getConfidenceChipStyles(claim.CONFIDENCE);

                  return (
                    <Table.Row 
                      key={`${idx}-${claim.VENDOR}-${claim.CLAIM_ID}-${claim.PRIMARY_DISPUTE_CODE}`}
                      bg={claim.REQUIRES_REVIEW ? 'orange.50' : 'white'}
                      _hover={{ bg: claim.REQUIRES_REVIEW ? 'orange.100' : 'gray.100' }}
                      cursor="pointer"
                      transition="background 0.2s"
                      onClick={() => setSelectedClaim(claim)}
                    >
                      <Table.Cell fontWeight="semibold" fontSize="sm" color="gray.700">{claim.CLAIM_ID}</Table.Cell>
                      <Table.Cell fontSize="sm" color="gray.600">{claim.VENDOR}</Table.Cell>
                      <Table.Cell>
                        <Badge
                          px={3}
                          py={1}
                          borderRadius="full"
                          fontSize="xs"
                          bg={codeStyles.bg}
                          color={codeStyles.color}
                          borderWidth="1px"
                          borderColor={codeStyles.borderColor}
                        >
                          {claim.PRIMARY_DISPUTE_CODE}
                        </Badge>
                      </Table.Cell>
                      <Table.Cell maxW="320px" truncate fontSize="sm" color="gray.700">{claim.DESCRIPTION}</Table.Cell>
                      <Table.Cell>
                        <Badge
                          px={3}
                          py={1}
                          borderRadius="full"
                          fontSize="xs"
                          bg={priorityStyles.bg}
                          color={priorityStyles.color}
                          borderWidth="1px"
                          borderColor={priorityStyles.borderColor}
                        >
                          Rank {claim.PRIORITY_RANK}
                        </Badge>
                      </Table.Cell>
                      <Table.Cell>
                        <Box
                          as="span"
                          px={3}
                          py={1}
                          borderRadius="full"
                          fontWeight="semibold"
                          fontSize="xs"
                          bg={confidenceStyles.bg}
                          color={confidenceStyles.color}
                          borderWidth="1px"
                          borderColor={confidenceStyles.borderColor}
                          display="inline-flex"
                          alignItems="center"
                          justifyContent="center"
                          minW="48px"
                        >
                          {(claim.CONFIDENCE * 100).toFixed(0)}%
                        </Box>
                      </Table.Cell>
                      <Table.Cell textAlign="right">
                        <Text fontSize="sm" color="gray.700">{formatCurrency(claim.REBATE_AMOUNT)}</Text>
                      </Table.Cell>
                      <Table.Cell textAlign="right">
                        <Text fontSize="sm" color="gray.700">{formatCurrency(claim.CLAIM_AMOUNT)}</Text>
                      </Table.Cell>
                      <Table.Cell>
                        {claim.REQUIRES_REVIEW ? (
                          <Box
                            as="span"
                            px={3}
                            py={1}
                            borderRadius="full"
                            fontSize="xs"
                            fontWeight="semibold"
                            bg="orange.100"
                            color="orange.700"
                            borderWidth="1px"
                            borderColor="orange.200"
                          >
                            Review
                          </Box>
                        ) : (
                          <Text fontSize="xs" color="gray.500">Clear</Text>
                        )}
                      </Table.Cell>
                      <Table.Cell>
                        <Button 
                          size="sm"
                          variant="outline"
                          borderRadius="full"
                          fontSize="xs"
                          bg="white"
                          borderColor="gray.300"
                          color="gray.700"
                          _hover={{ bg: 'gray.100', borderColor: 'gray.400' }}
                          _active={{ bg: 'gray.200' }}
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedClaim(claim);
                          }}
                        >
                          Details
                        </Button>
                      </Table.Cell>
                    </Table.Row>
                  );
                })}
              </Table.Body>
              </Table.Root>
            </Box>
          </Box>
          
          {/* Pagination Controls */}
          <Flex mt={4} justify="space-between" align="center" flexWrap="wrap" gap={3}>
            <Text fontSize="sm" color="gray.600">
              Showing {((currentPage - 1) * itemsPerPage) + 1} - {Math.min(currentPage * itemsPerPage, filteredClaims.length)} of {filteredClaims.length.toLocaleString()} claims
            </Text>
            
            <Flex gap={2} align="center" flexWrap="wrap">
              <Text fontSize="sm" color="gray.600">Per page:</Text>
              <Button 
                size="sm" 
                variant={itemsPerPage === 50 ? 'solid' : 'outline'} 
                onClick={() => setItemsPerPage(50)}
              >
                50
              </Button>
              <Button 
                size="sm" 
                variant={itemsPerPage === 100 ? 'solid' : 'outline'} 
                onClick={() => setItemsPerPage(100)}
              >
                100
              </Button>
              <Button 
                size="sm" 
                variant={itemsPerPage === 200 ? 'solid' : 'outline'} 
                onClick={() => setItemsPerPage(200)}
              >
                200
              </Button>
            </Flex>
            
            <Flex gap={2} align="center">
              <Button 
                size="sm" 
                onClick={() => setCurrentPage(1)} 
                disabled={currentPage === 1}
              >
                First
              </Button>
              <Button 
                size="sm" 
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))} 
                disabled={currentPage === 1}
              >
                Previous
              </Button>
              <Text fontSize="sm" color="gray.700" px={2}>
                Page {currentPage} of {totalPages}
              </Text>
              <Button 
                size="sm" 
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} 
                disabled={currentPage === totalPages}
              >
                Next
              </Button>
              <Button 
                size="sm" 
                onClick={() => setCurrentPage(totalPages)} 
                disabled={currentPage === totalPages}
              >
                Last
              </Button>
            </Flex>
          </Flex>
        </Card.Body>
      </Card.Root>
      
      {/* Claim Detail Side Panel */}
      {selectedClaim && (
        <>
          <Box
            position="fixed"
            inset={0}
            bg="rgba(0, 0, 0, 0.65)"
            zIndex={1000}
            onClick={() => setSelectedClaim(null)}
          />

          <Box
            position="fixed"
            top={0}
            bottom={0}
            right={detailRightOffset}
            width={{ base: '100%', md: '640px', xl: '720px' }}
            bg="white"
            boxShadow="dark-lg"
            zIndex={1001}
            overflowY="auto"
            px={{ base: 5, md: 8 }}
            py={6}
            transition="right 0.3s ease-in-out"
          >
            <VStack align="stretch" gap={6} minH="100%">
              <Flex justify="space-between" align="center" borderBottom="1px" borderColor="gray.200" pb={4}>
                <Heading size="lg">Claim Details</Heading>
                <HStack gap={3}>
                  <Button
                    onClick={handleSummarizeClaim}
                    colorScheme="blue"
                    borderRadius="full"
                    variant="solid"
                    disabled={aiLoading || !selectedClaim}
                  >
                    {aiLoading ? 'Working with AI...' : 'Summon AI Agent'}
                  </Button>
                  <CloseButton size="lg" onClick={() => setSelectedClaim(null)} />
                </HStack>
              </Flex>

              <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)' }} gap={5} alignItems="flex-start">
                <Box>
                  <Text fontSize="sm" color="gray.600">Claim ID</Text>
                  <Text fontWeight="bold" fontSize="lg" color="gray.800">{selectedClaim.CLAIM_ID}</Text>
                </Box>

                <Box>
                  <Text fontSize="sm" color="gray.600">Vendor</Text>
                  <Text fontWeight="bold" fontSize="lg" color="gray.800">{selectedClaim.VENDOR}</Text>
                </Box>

                <Box>
                  <Text fontSize="sm" color="gray.600">Primary Dispute Code</Text>
                  <HStack align="start" gap={2} mt={1}>
                    <Badge
                      px={3}
                      py={1}
                      borderRadius="full"
                      fontSize="sm"
                      bg="blue.50"
                      color="blue.700"
                      borderWidth="1px"
                      borderColor="blue.200"
                    >
                      {selectedClaim.PRIMARY_DISPUTE_CODE}
                    </Badge>
                    <Text color="gray.700" fontSize="sm" flex={1}>{selectedClaim.DESCRIPTION}</Text>
                  </HStack>
                </Box>

                <Box>
                  <Text fontSize="sm" color="gray.600">Category</Text>
                  <Badge
                    px={3}
                    py={1}
                    borderRadius="full"
                    fontSize="xs"
                    bg="purple.50"
                    color="purple.700"
                    borderWidth="1px"
                    borderColor="purple.200"
                    mt={1}
                  >
                    {selectedClaim.CATEGORY}
                  </Badge>
                </Box>

                <Box>
                  <Text fontSize="sm" color="gray.600">Priority Rank</Text>
                  {(() => {
                    const styles = getPriorityBadgeStyles(selectedClaim.PRIORITY_RANK);
                    return (
                      <Badge
                        px={3}
                        py={1}
                        borderRadius="full"
                        fontSize="xs"
                        bg={styles.bg}
                        color={styles.color}
                        borderWidth="1px"
                        borderColor={styles.borderColor}
                        mt={1}
                      >
                        Rank {selectedClaim.PRIORITY_RANK}
                      </Badge>
                    );
                  })()}
                </Box>

                <Box>
                  <Text fontSize="sm" color="gray.600">Confidence</Text>
                  <Text
                    fontSize="lg"
                    fontWeight="bold"
                    color={
                      selectedClaim.CONFIDENCE > 0.9 ? 'green.600' :
                      selectedClaim.CONFIDENCE > 0.7 ? 'orange.600' : 'red.600'
                    }
                    mt={1}
                  >
                    {(selectedClaim.CONFIDENCE * 100).toFixed(1)}%
                  </Text>
                </Box>
              </Grid>

              <Box>
                <Text fontSize="sm" color="gray.600" mb={2}>All Applicable Codes</Text>
                <Flex gap={2} flexWrap="wrap">
                  {(() => {
                    const codes = selectedClaim.ALL_APPLICABLE_CODES;
                    if (!codes) return <Text fontSize="sm">None</Text>;
                    const codeArray = typeof codes === 'string' ? codes.split(',') : Array.isArray(codes) ? codes : [String(codes)];
                    return codeArray.map((code, idx) => (
                      <Badge
                        key={idx}
                        px={3}
                        py={1}
                        borderRadius="full"
                        fontSize="xs"
                        bg="gray.100"
                        color="gray.700"
                        borderWidth="1px"
                        borderColor="gray.200"
                      >
                        {String(code).trim()}
                      </Badge>
                    ));
                  })()}
                </Flex>
              </Box>

              <Box>
                <Flex justify="space-between" align="center" mb={2}>
                  <Text fontSize="sm" fontWeight="semibold" color="gray.700">Evidence Trail</Text>
                  <Badge
                    px={2}
                    py={0.5}
                    borderRadius="full"
                    fontSize="2xs"
                    bg="blue.50"
                    color="blue.700"
                    borderWidth="1px"
                    borderColor="blue.200"
                  >
                    Audit Log
                  </Badge>
                </Flex>
                <Box
                  p={5}
                  bg="white"
                  borderRadius="lg"
                  border="2px"
                  borderColor="gray.200"
                  boxShadow="sm"
                  maxH="400px"
                  overflowY="auto"
                  css={{
                    '&::-webkit-scrollbar': {
                      width: '8px',
                    },
                    '&::-webkit-scrollbar-track': {
                      background: '#f1f1f1',
                      borderRadius: '10px',
                    },
                    '&::-webkit-scrollbar-thumb': {
                      background: '#cbd5e0',
                      borderRadius: '10px',
                    },
                    '&::-webkit-scrollbar-thumb:hover': {
                      background: '#a0aec0',
                    },
                  }}
                >
                  <VStack align="stretch" gap={3}>
                    {selectedClaim.EVIDENCE ? (
                      selectedClaim.EVIDENCE.split('\n\n').map((section, idx) => {
                        const lines = section.split('\n');
                        const header = lines[0];
                        const isHeader = header.includes(':') && header.toUpperCase() === header;
                        
                        return (
                          <Box key={idx}>
                            {isHeader ? (
                              <>
                                <Text
                                  fontSize="xs"
                                  fontWeight="bold"
                                  color="blue.700"
                                  textTransform="uppercase"
                                  letterSpacing="wide"
                                  mb={2}
                                  pb={1}
                                  borderBottom="1px"
                                  borderColor="blue.200"
                                >
                                  {header.replace(':', '')}
                                </Text>
                                <VStack align="stretch" gap={1} pl={3}>
                                  {lines.slice(1).map((line, lineIdx) => {
                                    const isBullet = line.trim().startsWith('•') || line.trim().startsWith('-');
                                    return isBullet ? (
                                      <Flex key={lineIdx} gap={2} fontSize="sm" color="gray.700" lineHeight="1.6">
                                        <Text color="blue.500" fontWeight="bold">•</Text>
                                        <Text flex={1}>{line.trim().replace(/^[•-]\s*/, '')}</Text>
                                      </Flex>
                                    ) : (
                                      <Text
                                        key={lineIdx}
                                        fontSize="sm"
                                        color="gray.700"
                                        lineHeight="1.6"
                                      >
                                        {line}
                                      </Text>
                                    );
                                  })}
                                </VStack>
                              </>
                            ) : (
                              <Text
                                fontSize="sm"
                                color="gray.700"
                                lineHeight="1.6"
                                whiteSpace="pre-wrap"
                              >
                                {section}
                              </Text>
                            )}
                          </Box>
                        );
                      })
                    ) : (
                      <Flex
                        align="center"
                        justify="center"
                        py={8}
                        color="gray.400"
                        flexDirection="column"
                        gap={2}
                      >
                        <Text fontSize="2xl">📋</Text>
                        <Text fontSize="sm" fontWeight="medium">No evidence provided</Text>
                      </Flex>
                    )}
                  </VStack>
                </Box>
              </Box>

              {selectedClaim.REQUIRES_REVIEW && (
                <Box bg="orange.100" borderColor="orange.500" borderWidth={1} p={4} borderRadius="md">
                  <VStack align="start" gap={1}>
                    <Text fontWeight="bold" color="orange.700">⚠️ Requires Human Review</Text>
                    <Text fontSize="sm">
                      This claim has been flagged for manual review based on confidence score,
                      multiple applicable codes, or business rule complexity.
                    </Text>
                  </VStack>
                </Box>
              )}
            </VStack>
          </Box>

          <Box
            position="fixed"
            top={0}
            bottom={0}
            right={0}
            width={aiPanelWidthConfig}
            bg="white"
            boxShadow="2xl"
            zIndex={1002}
            transform={aiPanelOpen ? 'translateX(0)' : 'translateX(100%)'}
            transition="transform 0.3s ease-in-out"
            display="flex"
            flexDirection="column"
          >
            <Flex align="center" justify="space-between" px={6} py={4} borderBottom="1px" borderColor="gray.200">
              <VStack align="start" gap={0}>
                <Text fontSize="xs" color="gray.500" textTransform="uppercase" letterSpacing="0.08em" fontWeight="semibold">
                  AI Foundry Triage Agent
                </Text>
                <Text fontSize="sm" color="gray.600">
                  Generate a concise summary and guidance for finance reviewers.
                </Text>
              </VStack>
              <CloseButton size="md" onClick={() => setAiPanelOpen(false)} />
            </Flex>

            <Box flex={1} px={6} py={5} overflowY="auto" display="grid" gap={4}>
              <Button
                onClick={handleSummarizeClaim}
                disabled={aiLoading || !selectedClaim}
                borderRadius="full"
                colorScheme="blue"
                justifySelf="stretch"
              >
                {aiLoading ? 'Working with AI...' : aiSummary ? 'Regenerate Summary' : 'Summarize Claim'}
              </Button>

              {aiLoading && (
                <HStack
                  gap={3}
                  align="center"
                  bg="gray.50"
                  borderRadius="md"
                  borderWidth="1px"
                  borderColor="gray.200"
                  p={4}
                >
                  <Spinner size="sm" color="blue.500" />
                  <Text fontSize="sm" color="gray.600">
                    Querying the AI Foundry agent...
                  </Text>
                </HStack>
              )}

              {aiError && (
                <Box
                  borderRadius="md"
                  borderWidth="1px"
                  borderColor="red.200"
                  bg="red.50"
                  p={4}
                >
                  <Text fontSize="sm" color="red.700">{aiError}</Text>
                </Box>
              )}

              {selectedClaim && (
                <Box
                  borderRadius="md"
                  borderWidth="1px"
                  borderColor="purple.100"
                  bg="white"
                  px={4}
                  py={4}
                  boxShadow="xs"
                  display="grid"
                  gap={3}
                >
                  <Flex align="center" justify="space-between" gap={2} flexWrap="wrap">
                    <Text fontSize="xs" fontWeight="semibold" color="purple.700" textTransform="uppercase" letterSpacing="0.08em">
                      Classification Story
                    </Text>
                    <HStack gap={2} align="center">
                      {classificationStoryModel && (
                        <Badge colorScheme={classificationStoryModel.toLowerCase().includes('gpt-5') ? 'pink' : 'purple'}>
                          {classificationStoryModel}
                        </Badge>
                      )}
                      {classificationStoryFinish && (
                        <Badge variant="outline" colorScheme="gray">{classificationStoryFinish}</Badge>
                      )}
                      <Button
                        size="xs"
                        variant="ghost"
                        colorScheme="purple"
                        onClick={() => {
                          if (!classificationStoryText || classificationStoryLoading) {
                            return;
                          }
                          setClassificationStoryExpanded(prev => !prev);
                        }}
                      >
                        {classificationStoryExpanded ? 'Collapse' : 'Expand'}
                      </Button>
                    </HStack>
                  </Flex>

                  {classificationStoryLoading && (
                    <HStack gap={3} align="center" borderRadius="md" borderWidth="1px" borderColor="purple.100" bg="purple.50" p={3}>
                      <Spinner size="xs" color="purple.500" />
                      <Text fontSize="xs" color="purple.700">Asking the classifier to narrate the decision...</Text>
                    </HStack>
                  )}

                  {classificationStoryError && !classificationStoryLoading && (
                    <Box borderRadius="md" borderWidth="1px" borderColor="red.200" bg="red.50" p={3}>
                      <Text fontSize="xs" color="red.700">{classificationStoryError}</Text>
                    </Box>
                  )}

                  {classificationStoryText && !classificationStoryLoading && !classificationStoryError && (
                    <>
                      {!classificationStoryExpanded && (
                        <Box display="grid" gap={2}>
                          {classificationStoryBlocks.length > 0 ? (
                            renderStructuredBlocks(classificationStoryBlocks.slice(0, 3), 'classification-story-preview')
                          ) : (
                            <Text fontSize="sm" color="gray.700" lineHeight="1.6">
                              {classificationStoryPreviewText || ''}
                            </Text>
                          )}
                          {showClassificationExpandHint && (
                            <Text fontSize="xs" color="gray.500">
                              Expand to read the full rationale and evidence references.
                            </Text>
                          )}
                        </Box>
                      )}
                      {classificationStoryExpanded && (
                        <Box display="grid" gap={2} mt={2}>
                          {classificationStoryBlocks.length > 0 ? (
                            renderStructuredBlocks(classificationStoryBlocks, 'classification-story-full')
                          ) : (
                            <Text fontSize="sm" color="gray.700" lineHeight="1.6" whiteSpace="pre-wrap">
                              {classificationStoryText}
                            </Text>
                          )}
                        </Box>
                      )}
                    </>
                  )}

                  {!classificationStoryText && !classificationStoryLoading && !classificationStoryError && (
                    <Text fontSize="xs" color="gray.500">
                      Select a claim to generate a narrated explanation of how the classifier arrived at the primary dispute code.
                    </Text>
                  )}
                </Box>
              )}

              {aiSummary && !aiLoading && (
                <Box
                  borderRadius="md"
                  borderWidth="1px"
                  borderColor="gray.200"
                  bg="gray.50"
                  px={4}
                  py={4}
                  boxShadow="xs"
                  display="grid"
                  gap={3}
                >
                  <Flex align="center" justify="space-between" gap={2} flexWrap="wrap">
                    <Text fontSize="xs" fontWeight="semibold" color="gray.600" textTransform="uppercase" letterSpacing="0.08em">
                      Executive Summary
                    </Text>
                    <Button
                      size="xs"
                      variant="ghost"
                      colorScheme="gray"
                      onClick={() => setSummaryExpanded(prev => !prev)}
                    >
                      {summaryExpanded ? 'Collapse' : 'Expand'}
                    </Button>
                  </Flex>

                  {summaryExpanded && (
                    <Box display="grid" gap={3} mt={2}>
                      {summaryBlocks.length > 0 ? (
                        renderStructuredBlocks(summaryBlocks, 'summary-block')
                      ) : (
                        <Text fontSize="sm" color="gray.700" lineHeight="1.6">
                          {aiSummary}
                        </Text>
                      )}
                    </Box>
                  )}

                  {!summaryExpanded && (
                    <Text fontSize="xs" color="gray.500">
                      Summary collapsed. Expand to review the AI guidance.
                    </Text>
                  )}
                </Box>
              )}

              {!aiSummary && !aiLoading && !aiError && (
                <Text fontSize="xs" color="gray.500">
                  Configure VITE_AI_SUMMARY_ENDPOINT to point at your AI Foundry agent API.
                </Text>
              )}

              {/* Analyst Chat Section */}
              {selectedClaim && (
                <Box
                  borderRadius="md"
                  borderWidth="1px"
                  borderColor="gray.200"
                  bg="white"
                  p={4}
                  boxShadow="xs"
                  display="grid"
                  gap={3}
                >
                  <Flex align="center" justify="space-between">
                    <Text fontSize="xs" fontWeight="semibold" color="gray.600" textTransform="uppercase" letterSpacing="0.08em">
                      Analyst Chat
                    </Text>
                    {chatHistory.length > 0 && (
                      <Button size="xs" variant="ghost" colorScheme="gray" onClick={handleClearChat}>
                        Clear chat
                      </Button>
                    )}
                  </Flex>
                  <Text fontSize="sm" color="gray.600">
                    Ask targeted questions about this claim. The AI will cite evidence fragments and flag uncertain areas.
                  </Text>
                  <HStack gap={2} align="start">
                    <Input
                      size="sm"
                      placeholder="e.g. What is the recommended next action?"
                      value={chatQuestion}
                      onChange={e => setChatQuestion(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') handleClaimChat(); }}
                    />
                    <Button
                      size="sm"
                      colorScheme="purple"
                      borderRadius="full"
                      disabled={!chatQuestion.trim() || chatLoading}
                      onClick={handleClaimChat}
                    >
                      {chatLoading ? <Spinner size="xs" mr={2} /> : null}Ask
                    </Button>
                  </HStack>
                  {chatError && (
                    <Box border="1px" borderColor="red.200" bg="red.50" p={2} borderRadius="md">
                      <Text fontSize="xs" color="red.600">{chatError}</Text>
                    </Box>
                  )}
                  <Box
                    ref={chatContainerRef}
                    maxH="240px"
                    overflowY="auto"
                    display="grid"
                    gap={3}
                    borderTop="1px"
                    borderColor="gray.100"
                    pt={2}
                  >
                    {chatHistory.length === 0 && (
                      <Text fontSize="xs" color="gray.500">No chat yet. Enter a question above.</Text>
                    )}
                    {chatHistory.map((m, idx) => (
                      <Box key={idx} border="1px" borderColor="gray.200" bg="gray.50" p={3} borderRadius="md" display="grid" gap={1}>
                        <Flex align="center" justify="space-between">
                          <Text fontSize="xs" fontWeight="bold" color="purple.700">Q: {m.q}</Text>
                          {m.model && <Badge colorScheme={m.model.toLowerCase().includes('gpt-5') ? 'pink' : 'purple'}>{m.model}</Badge>}
                        </Flex>
                        {m.direct && (
                          <Text fontSize="xs" color="gray.800"><strong>Answer:</strong> {m.direct}</Text>
                        )}
                        {m.rationale && (
                          <Text fontSize="xs" color="gray.700"><strong>Rationale:</strong> {m.rationale}</Text>
                        )}
                        {m.next && (
                          <Text fontSize="xs" color="gray.700"><strong>Next Action:</strong> {m.next}</Text>
                        )}
                        {m.risks && (
                          <Text fontSize="xs" color="red.700"><strong>Risks/Red Flags:</strong> {m.risks}</Text>
                        )}
                        {!m.direct && !m.rationale && !m.next && !m.risks && (
                          <Text fontSize="xs" color={m.a === '<no response>' ? 'red.600' : 'gray.700'} whiteSpace="pre-wrap">
                            {m.a === '<no response>' ? 'No model output. Verify deployment name, token parameter, or set AI_CHAT_DEBUG=1 for diagnostics.' : m.a}
                          </Text>
                        )}
                      </Box>
                    ))}
                  </Box>
                  {/* Quick suggestion prompts */}
                  <HStack gap={2} flexWrap="wrap">
                    {['Key risks?', 'Next best action?', 'Confidence rationale?', 'Evidence gaps?'].map(s => (
                      <Button key={s} size="xs" variant="outline" onClick={() => setChatQuestion(s)}>{s}</Button>
                    ))}
                  </HStack>
                </Box>
              )}
            </Box>
          </Box>
        </>
      )}
    </VStack>
  );
}

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Heading, Text, Spinner, Flex, Badge, Input, Button } from '@chakra-ui/react';
import type { ClaimChatPayload, ClaimChatResponse } from '../engine/backendClient';
import { claimChat } from '../engine/backendClient';

interface ClassificationRow {
  [key: string]: unknown;
}

interface IngestedSheet {
  results?: ClassificationRow[];
  normalized?: ClassificationRow[];
}

export default function ClaimDetail() {
  const { claimId } = useParams();
  const [loadingClaim, setLoadingClaim] = useState(true);
  const [claimContext, setClaimContext] = useState<ClaimChatPayload | null>(null);
  const [question, setQuestion] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<Array<{ q: string; a: string }>>([]);
  const [error, setError] = useState<string | null>(null);

  // Attempt to reconstruct claim details from global ingestion session
  useEffect(() => {
    setLoadingClaim(true);
    try {
  const rawGlobal = (window as unknown as { __DEMO_V2_INGESTED__?: unknown }).__DEMO_V2_INGESTED__;
  const globalSheets: IngestedSheet[] | undefined = Array.isArray(rawGlobal) ? (rawGlobal as IngestedSheet[]) : undefined;
      let found: ClassificationRow | null = null;
      if (Array.isArray(globalSheets)) {
        for (const sheet of globalSheets) {
          const rows: ClassificationRow[] = sheet?.results || []; // backend ingestion path
          for (const r of rows) {
            const cid = r['CLAIM_ID'] || r['claimId'];
            if (cid && String(cid) === String(claimId)) {
              found = r; break;
            }
          }
          if (found) break;
        }
      }
      if (!found && globalSheets) {
        // Fallback: search mapped normalized rows for metadata
        for (const sheet of globalSheets) {
          const norm: ClassificationRow[] = sheet?.normalized || [];
          for (const r of norm) {
            if (r['CLAIM_ID'] && String(r['CLAIM_ID']) === String(claimId)) {
              found = r; break;
            }
          }
          if (found) break;
        }
      }
      if (!found) {
        setError('Claim context not found in current ingestion session. Upload workbook first.');
        setClaimContext(null);
      } else {
        // Build chat payload with safe fallbacks
        const payload: ClaimChatPayload = {
          question: '',
          CLAIM_ID: String(found['CLAIM_ID'] || found['claimId'] || claimId),
            VENDOR: String(found['VENDOR'] || 'UNKNOWN'),
          PRIMARY_DISPUTE_CODE: Number(found['PRIMARY_DISPUTE_CODE'] || 0),
          DESCRIPTION: String(found['DESCRIPTION'] || found['DISPUTE_REASON'] || 'No description available'),
          CATEGORY: String(found['CATEGORY'] || found['primaryCategory'] || 'UNSPECIFIED'),
          PRIORITY_RANK: Number(found['PRIORITY_RANK'] || 0),
          ALL_APPLICABLE_CODES: String(found['ALL_APPLICABLE_CODES'] || found['categories'] || ''),
          EVIDENCE: String(found['EVIDENCE'] || found['evidence'] || ''),
          CONFIDENCE: Number(found['CONFIDENCE'] || found['confidence'] || 0),
          REQUIRES_REVIEW: Boolean(found['REQUIRES_REVIEW'] || found['requiresReview'] || false)
        };
        setClaimContext(payload);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to build claim context');
    } finally {
      setLoadingClaim(false);
    }
  }, [claimId]);

  const ask = useCallback(async () => {
    if (!claimContext || !question.trim()) return;
    setChatLoading(true); setError(null);
    try {
      const resp: ClaimChatResponse = await claimChat({ ...claimContext, question });
      setChatHistory(h => [...h, { q: question.trim(), a: resp.answer }]);
      setQuestion('');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Chat failed');
    } finally {
      setChatLoading(false);
    }
  }, [claimContext, question]);

  return (
    <Box>
      <Heading size="lg" mb={4}>Claim Detail</Heading>
      {loadingClaim && <Spinner size="sm" />}
      {error && (
        <Box mb={4} p={3} border="1px solid" borderColor="red.300" bg="red.50" borderRadius="md">
          <Text fontSize="sm" color="red.600">{error}</Text>
        </Box>
      )}
      {!loadingClaim && claimContext && (
        <Box mb={6} p={4} bg="white" borderRadius="lg" boxShadow="sm">
          <Flex align="center" gap={3} mb={2}>
            <Heading size="sm">Claim ID: {claimContext.CLAIM_ID}</Heading>
            {claimContext.REQUIRES_REVIEW && <Badge colorScheme="orange">Needs Review</Badge>}
            {claimContext.CONFIDENCE < 0.7 && <Badge colorScheme="yellow">Low Confidence</Badge>}
          </Flex>
          <Text fontSize="xs" color="gray.600" mb={2}>Primary Code: {claimContext.PRIMARY_DISPUTE_CODE} | Category: {claimContext.CATEGORY} | Priority Rank: {claimContext.PRIORITY_RANK}</Text>
          <Text fontSize="xs" color="gray.600" mb={2}>All Codes: {claimContext.ALL_APPLICABLE_CODES || '(none)'} </Text>
          <Text fontSize="xs" color="gray.600" mb={2}>Evidence Fragments: {claimContext.EVIDENCE || '(none provided)'} </Text>
        </Box>
      )}

      {claimContext && (
        <Box p={4} bg="white" borderRadius="lg" boxShadow="sm">
          <Heading size="sm" mb={3}>Analyst Chat</Heading>
          <Text fontSize="xs" color="gray.600" mb={3}>Ask targeted questions about this claim. The model will cite evidence fragments and flag missing data.</Text>
          <Flex gap={2} mb={3}>
            <Input size="sm" placeholder="e.g. What is the most likely resolution path?" value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') ask(); }} />
            <Button size="sm" colorScheme="blue" onClick={ask} disabled={!question.trim() || chatLoading}>
              {chatLoading && <Spinner size="xs" mr={2} />}Ask
            </Button>
          </Flex>
          <Box>
            {chatHistory.length === 0 && <Text fontSize="xs" color="gray.500">No chat yet. Enter a question above.</Text>}
            {chatHistory.map((m, i) => (
              <Box key={i} mb={3} p={3} border="1px solid" borderColor="gray.200" borderRadius="md" bg="gray.50">
                <Text fontSize="xs" fontWeight="bold" mb={1}>Q: {m.q}</Text>
                <Text fontSize="xs" whiteSpace="pre-wrap">{m.a}</Text>
              </Box>
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}

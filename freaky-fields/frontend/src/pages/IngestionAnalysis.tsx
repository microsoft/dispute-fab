import { useEffect, useMemo, useState } from 'react';
import { Box, Heading, Text, Badge, Flex } from '@chakra-ui/react';
import type { SheetProcessingResult, ClassificationResult } from '../engine/types';

declare global { interface Window { __DEMO_V2_INGESTED__?: SheetProcessingResult[] } }

export default function IngestionAnalysis() {
  const [error, setError] = useState<string | null>(null);
  const [processed, setProcessed] = useState<SheetProcessingResult[]>([]);

  // Load previously ingested session placed on window by Upload page
  useEffect(() => {
    try {
      const data = (window.__DEMO_V2_INGESTED__ || []) as SheetProcessingResult[];
      setProcessed(Array.isArray(data) ? data.filter(s => s && typeof s === 'object') : []);
    } catch (_err) {
      setError('Failed to read ingested session data');
      setProcessed([]);
    }
  }, []);

  const sampleTransforms = useMemo(() => {
    try {
      return processed.map(sheet => {
        if (!sheet || !Array.isArray(sheet.normalized)) {
            return { sheet: sheet?.sheetName || 'UNKNOWN', raw: {}, normalized: {}, classification: undefined };
        }
        const firstNorm = sheet.normalized[0];
        const firstRes: ClassificationResult | undefined = sheet.results?.[0];
        const rawVal = (firstNorm && typeof firstNorm === 'object' && '__raw' in firstNorm)
          ? (firstNorm as Record<string, unknown>)['__raw'] || {}
          : {};
        return {
          sheet: sheet.sheetName,
          raw: rawVal as Record<string, unknown>,
          normalized: firstNorm,
          classification: firstRes
        };
      });
    } catch (err) {
      setError((err as Error)?.message || 'Failed building sample transforms');
      return [];
    }
  }, [processed]);

  return (
    <Box>
      <Heading size="lg" mb={4}>Ingestion Analysis</Heading>
      <Text fontSize="sm" color="gray.600" mb={6}>Visualizing how vendor-specific column headers map to our standard schema, and a sample claim's transformation pipeline (Raw ➜ Normalized ➜ Classified).</Text>

      {error && (
        <Box mb={4} p={3} border="1px solid" borderColor="red.300" bg="red.50" borderRadius="md">
          <Text fontSize="sm" color="red.600" fontWeight="semibold">Error: {error}</Text>
        </Box>
      )}

      {!error && processed.length === 0 && (
        <Text fontSize="sm" color="gray.500">No ingestion session found. Upload a workbook via <Badge colorScheme="blue">Update Claim Data</Badge> page first.</Text>
      )}

      {processed.map((sheet, idx) => (
        <Box key={sheet?.sheetName || idx} mb={10} p={5} bg="white" borderRadius="lg" boxShadow="sm">
          <Flex justify="space-between" align="center" mb={3}>
            <Flex align="center" gap={2}>
              <Heading size="sm">Sheet: {sheet?.sheetName || 'UNKNOWN'}</Heading>
              {sheet.mappingSource === 'ai' && (<Badge colorScheme="green">AI</Badge>)}
              {sheet.mappingSource === 'fallback' && (
                <Badge colorScheme="yellow" variant="subtle" title={sheet.aiError || 'AI mapping empty; fallback heuristics applied'}>Fallback</Badge>
              )}
              {sheet.mappingSource === 'client' && (
                <Badge colorScheme="blue" variant="outline" title="Client-side heuristic mapping (no backend AI)">Client</Badge>
              )}
            </Flex>
            <Badge colorScheme="purple">{Array.isArray(sheet.results) ? sheet.results.length : 0} claims</Badge>
          </Flex>
          <Flex align="center" gap={2} mb={2}>
            <Text fontSize="xs" color="gray.600" fontWeight="medium">Header Mapping Diff</Text>
            {sheet.mappingSource === 'ai' && (<Badge colorScheme="green">AI</Badge>)}
            {sheet.mappingSource === 'fallback' && (<Badge colorScheme="yellow" variant="subtle">Fallback</Badge>)}
            {sheet.mappingSource === 'client' && (<Badge colorScheme="blue" variant="outline">Client</Badge>)}
          </Flex>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:'12px' }} aria-label={`Header mapping for ${sheet?.sheetName || 'UNKNOWN'}`}>
            <thead style={{ background:'#f5f5f5' }}>
              <tr><th style={{ textAlign:'left', padding:'4px' }}>Standard Field</th><th style={{ textAlign:'left', padding:'4px' }}>Vendor Header</th></tr>
            </thead>
            <tbody>
              {Object.entries(sheet.mapping || {}).map(([std, vendor]) => (
                <tr key={std} style={{ cursor:'default' }}>
                  <td style={{ padding:'4px', borderBottom:'1px solid #eee' }}>{std}</td>
                  <td style={{ padding:'4px', borderBottom:'1px solid #eee' }}>{vendor || <span style={{ color:'#999' }}>(not mapped)</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Box>
      ))}

      {sampleTransforms.length > 0 && (
        <Box mt={4} p={5} bg="white" borderRadius="lg" boxShadow="sm">
          <Heading size="sm" mb={3}>Sample Claim Transformation</Heading>
          {sampleTransforms.map(t => (
            <Box key={t.sheet} mb={6}>
              <Text fontSize="sm" fontWeight="semibold" mb={1}>Sheet: {t.sheet}</Text>
              <Box display="grid" gap={3}>
                <TransformBlock title="Raw Row" obj={t.raw} />
                <TransformBlock title="Normalized Claim" obj={t.normalized} />
                <TransformBlock title="Classification Result" obj={t.classification} />
              </Box>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}

function TransformBlock({ title, obj }: { title: string; obj: unknown }) {
  return (
    <Box border="1px solid" borderColor="gray.200" borderRadius="md" p={3} bg="gray.50">
      <Text fontSize="xs" fontWeight="bold" color="gray.600" mb={1}>{title}</Text>
      <Box as="pre" fontSize="xs" whiteSpace="pre-wrap" overflowX="auto">{JSON.stringify(obj, null, 2)}</Box>
    </Box>
  );
}

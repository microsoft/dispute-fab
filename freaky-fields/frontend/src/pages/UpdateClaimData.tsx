import { useState, useCallback, useRef } from 'react';
import { Box, Heading, Text, Flex, Spinner, Button, Badge } from '@chakra-ui/react';
import { parseExcel, processSheet } from '../engine/Pipeline';
import type { SheetProcessingResult, SheetData, ClassificationResult } from '../engine/types';
import { generateColumnMapping } from '../engine/ColumnMapper';
import { ingestWorkbookBackend } from '../engine/backendClient';
import { useNavigate } from 'react-router-dom';

// NOTE: We have not yet introduced a unified ClaimsContext in demo-v2; reuse Processing-style local state via window for now.
// This lightweight global lets existing pages (e.g. AllClaims) optionally read processed data later.
declare global {
  interface Window { __DEMO_V2_INGESTED__?: SheetProcessingResult[] }
}

export default function UpdateClaimData() {
  const [dragActive, setDragActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheets, setSheets] = useState<SheetProcessingResult[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [mappingPreviews, setMappingPreviews] = useState<Record<string, Record<string,string>>>({});
  const [fullDataset, setFullDataset] = useState(false);
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(async (fileList: FileList | null) => {
    console.log('handleFiles called', fileList);
    if (!fileList?.length) return;
    const file = fileList[0];
    console.log('Processing file:', file.name);
    setBusy(true); setError(null); setSheets([]); setLogs([]); setMappingPreviews({});
    try {
      setLogs(l => [...l, `File selected: ${file.name}`]);

  const useBackend = true; // feature flag / env var later
      if (useBackend) {
        setLogs(l => [...l, '▶ Using backend ingestion']);
        try {
          const backend = await ingestWorkbookBackend(file, 'VENDOR', fullDataset ? -1 : 25);
          if (!backend.success) throw new Error(backend.error || 'Backend failure');
          const processed: SheetProcessingResult[] = [];
          backend.sheets.forEach(s => {
            // build reversed mapping for preview (vendor header -> standard)
            const rev: Record<string,string> = {};
            Object.entries(s.mapping).forEach(([std, vendor]) => { if (vendor) rev[String(vendor)] = std; });
            setMappingPreviews(mp => ({ ...mp, [s.sheetName]: rev }));
            // adapt classification
            const norm = s.sampleMappedRows.map(r => ({ __raw: r, ...r }));
            const results: ClassificationResult[] = s.sampleClassification.map(r => ({
              claimId: String(r['CLAIM_ID'] || 'UNKNOWN'),
              categories: String(r['ALL_APPLICABLE_CODES'] || '').split(',').map(c => c.trim()).filter(Boolean),
              primaryCategory: String(r['PRIMARY_DISPUTE_CODE'] || r['PRIMARY_CATEGORY'] || ''),
              confidence: Number(r['CONFIDENCE'] || 0),
              evidence: String(r['EVIDENCE'] || '').split('|').map(e => e.trim()).filter(Boolean)
            }));
            processed.push({
              sheetName: s.sheetName,
              mapping: s.mapping as Record<string,string>,
              normalized: norm,
              results,
              mappingSource: s.mappingSource as ('ai'|'fallback') | undefined,
              aiError: s.aiError || null
            });
            setLogs(l => [...l, `  ✓ Sheet ${s.sheetName}: ${s.rowCount} rows (sample ${norm.length}) mapped`]);
          });
            setSheets(processed);
            window.__DEMO_V2_INGESTED__ = processed;
            setLogs(l => [...l, '✓ Backend ingestion complete']);
            setBusy(false);
            return; // skip client-side pipeline
        } catch (be) {
          setLogs(l => [...l, `⚠ Backend ingest error, falling back: ${(be as Error).message}`]);
        }
      }

      const parsedSheets: SheetData[] = await parseExcel(file);
      setLogs(l => [...l, `Parsed ${parsedSheets.length} sheets (client pipeline)`]);
      // Preview mappings
      for (const sheet of parsedSheets) {
        if (!sheet.headers.length) continue;
        const mapping = await generateColumnMapping(sheet);
        // reverse mapping for display: originalHeader -> mappedField(s)
        const rev: Record<string,string> = {};
  Object.entries(mapping).forEach(([std, orig]) => { if (orig) rev[String(orig)] = std; });
        setMappingPreviews(mp => ({ ...mp, [sheet.sheetName]: rev }));
        console.debug('[UpdateClaimData] mapping for sheet', sheet.sheetName, mapping);
      }
      // Full processing
      const processed: SheetProcessingResult[] = [];
      for (const sheet of parsedSheets) {
        if (!sheet.headers.length) continue;
        setLogs(l => [...l, `▶ Processing sheet: ${sheet.sheetName}`]);
        const res = await processSheet(sheet);
        setLogs(l => [...l, `  ✓ Classified ${res.results.length} rows`]);
        if (res.normalized[0]) {
          console.debug('[UpdateClaimData] sample normalized row', sheet.sheetName, res.normalized[0]);
          console.debug('[UpdateClaimData] sample classification', sheet.sheetName, res.results[0]);
        }
        // Attach client-only mappingSource indicator if not already present
        processed.push({ ...res, mappingSource: res.mappingSource || 'client' });
        setSheets([...processed]);
      }
      window.__DEMO_V2_INGESTED__ = processed;
      setLogs(l => [...l, '✓ Ingestion complete']);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to ingest file');
      setLogs(l => [...l, '✗ Ingestion error']);
    } finally {
      setBusy(false);
    }
  }, [fullDataset]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation(); setDragActive(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);
  const onDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); setDragActive(true); }, []);
  const onDragLeave = useCallback((e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); setDragActive(false); }, []);

  const totalClaims = sheets.reduce((a,s)=> a + s.results.length, 0);
  const flagged = sheets.reduce((a,s)=> a + s.results.filter((r: ClassificationResult)=> r.primaryCategory !== 'NO_FLAG').length, 0);

  return (
    <Box>
      <Heading size="lg" mb={4}>Update Claim Data (Workbook Ingestion)</Heading>
      <Text fontSize="sm" color="gray.600" mb={6}>Drag & drop the masked 15-sheet Excel workbook to re-run mapping + classification in-browser. Results feed into the Claims Browser.</Text>
      <Flex align="center" gap={2} mb={4}>
        <Button size="xs" variant={fullDataset ? 'solid' : 'outline'} colorScheme="purple" onClick={() => setFullDataset(v => !v)}>
          {fullDataset ? 'Full Dataset: ON' : 'Full Dataset: OFF'}
        </Button>
        <Text fontSize="xs" color="gray.600">Toggle to send all rows (-1 sample size)</Text>
      </Flex>
      <Box
        border="2px dashed"
        borderColor={dragActive ? 'blue.400' : 'gray.300'}
        borderRadius="lg"
        p={10}
        textAlign="center"
        bg={dragActive ? 'blue.50' : 'white'}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
      >
        <Text fontSize="md" mb={3}>Drop workbook here or select manually</Text>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          style={{ display: 'none' }}
          onChange={(e) => {
            console.log('File input onChange', e.target.files);
            handleFiles(e.target.files);
            // Reset value to allow selecting the same file again
            if (e.target) {
              e.target.value = '';
            }
          }}
        />
        <Button size="sm" onClick={() => {
          console.log('Choose File button clicked, fileInputRef:', fileInputRef.current);
          const input = fileInputRef.current;
          if (input) {
            // Reset value before clicking to ensure onChange fires in Edge
            input.value = '';
            input.click();
          }
        }} disabled={busy}>Choose File</Button>
        {busy && <Flex mt={4} justify="center" align="center" gap={2}><Spinner size="sm" /><Text>Processing…</Text></Flex>}
        {error && <Text mt={4} color="red.500" fontSize="sm">{error}</Text>}
      </Box>

      {sheets.length > 0 && (
        <Box mt={10} p={5} bg="white" borderRadius="lg" boxShadow="sm">
          <Heading size="md" mb={3}>Session Summary</Heading>
          <Flex gap={4} mb={4} wrap="wrap">
            <Stat label="Sheets" value={sheets.length} />
            <Stat label="Total Claims" value={totalClaims} />
            <Stat label="Flagged" value={flagged} />
            <Stat label="No Flag" value={totalClaims - flagged} />
          </Flex>
          <Button size="sm" colorScheme="blue" onClick={() => navigate('/claims')}>View in Claims Browser</Button>
          <Button size="sm" ml={3} variant="outline" onClick={() => navigate('/analysis')}>Open Ingestion Analysis</Button>
        </Box>
      )}

      {Object.keys(mappingPreviews).length > 0 && (
        <Box mt={12}>
          <Heading size="sm" mb={3}>Header Mapping Preview (first pass)</Heading>
          {Object.entries(mappingPreviews).map(([sheetName, rev]) => (
            <Box key={sheetName} mb={6} p={4} bg="white" borderRadius="md" boxShadow="sm">
              <Flex justify="space-between" align="center" mb={2}>
                <Text fontWeight="semibold">Sheet: {sheetName}</Text>
                <Badge colorScheme="purple">{Object.keys(rev).length} mapped</Badge>
              </Flex>
              <Box as="table" fontSize="xs" width="100%" style={{ borderCollapse:'collapse' }}>
                <Box as="thead" bg="gray.100"><Box as="tr"><Box as="th" p={2} textAlign="left">Original Header</Box><Box as="th" p={2} textAlign="left">Standard Field</Box></Box></Box>
                <Box as="tbody">
                  {Object.entries(rev).map(([orig,std]) => (
                    <Box as="tr" key={orig} _hover={{ bg:'gray.50' }}>
                      <Box as="td" p={2}>{orig}</Box>
                      <Box as="td" p={2}>{std}</Box>
                    </Box>
                  ))}
                </Box>
              </Box>
            </Box>
          ))}
        </Box>
      )}

      {!!logs.length && (
        <Box mt={12} p={4} bg="white" borderRadius="md" boxShadow="sm">
          <Heading size="sm" mb={2}>Processing Log</Heading>
            <Box as="pre" fontSize="xs" maxHeight="220px" overflowY="auto" p={2} bg="gray.50" borderRadius="md" border="1px solid" borderColor="gray.200">{logs.join('\n')}</Box>
        </Box>
      )}
    </Box>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Flex direction="column" p={3} bg="gray.50" borderRadius="md" border="1px solid" borderColor="gray.200" minW="110px">
      <Text fontSize="xs" color="gray.500" textTransform="uppercase" mb={1}>{label}</Text>
      <Text fontSize="md" fontWeight="semibold">{value}</Text>
    </Flex>
  );
}

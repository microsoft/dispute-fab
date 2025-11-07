import io
import pandas as pd
from fastapi.testclient import TestClient
import api_server

class StubMapper:
    def map_columns(self, vendor, df):
        # Map first column to CLAIM_ID, second to DRUG_NDC if exists
        cols = list(df.columns)
        mapping = {}
        if cols:
            mapping['CLAIM_ID'] = cols[0]
        if len(cols) > 1:
            mapping['DRUG_NDC'] = cols[1]
        return mapping
    def apply_mapping(self, df, mapping):
        rename = {v: k for k, v in mapping.items()}
        return df.rename(columns=rename)
    def clear_cache(self, vendor=None):
        pass

class StubClassifier:
    def classify_batch(self, vendor, df):
        # Return DataFrame with required columns for ingestion adaptation
        rows = []
        for _, r in df.iterrows():
            rows.append({
                'CLAIM_ID': r.get('CLAIM_ID', 'X'),
                'PRIMARY_DISPUTE_CODE': 101,
                'DESCRIPTION': 'Stub Description',
                'CATEGORY': 'Stub Category',
                'PRIORITY_RANK': 5,
                'ALL_APPLICABLE_CODES': '101,102',
                'EVIDENCE': 'PRIMARY DISPUTE CODE: 101 | Reason: stub',
                'CONFIDENCE': 0.9,
                'REQUIRES_REVIEW': False
            })
        return pd.DataFrame(rows)

# Monkeypatch globals
api_server._MAPPER = StubMapper()
api_server._CLASSIFIER = StubClassifier()

client = TestClient(api_server.app)


def make_excel_bytes():
    df = pd.DataFrame({
        'Line Number': ['A123', 'B456', 'C789'],
        'ProductCode': ['00011122233', '00011122244', '00011122255'],
        'ExtraCol': [1,2,3]
    })
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    bio.seek(0)
    return bio.read()


def test_ingest_stub():
    excel_bytes = make_excel_bytes()
    files = {'file': ('test.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    resp = client.post('/api/ingest', data={'vendor': 'TESTVENDOR', 'sample_size': '10'}, files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data['success'] is True
    assert data['vendor'] == 'TESTVENDOR'
    assert len(data['sheets']) == 1
    sheet = data['sheets'][0]
    assert 'CLAIM_ID' in sheet['mapping']
    assert sheet['rowCount'] == 3
    assert len(sheet['sampleClassification']) > 0
    assert sheet['mappingSource'] == 'ai'
    assert sheet.get('aiError') in (None, '')
    # classification sample has expected field
    assert sheet['sampleClassification'][0]['PRIMARY_DISPUTE_CODE'] == 101


def test_classify_batch_stub():
    claims = [
        {'CLAIM_ID': 'X1', 'DRUG_NDC': '00011122233'},
        {'CLAIM_ID': 'X2', 'DRUG_NDC': '00011122244'}
    ]
    resp = client.post('/api/classify-batch', json={'vendor': 'TESTVENDOR', 'claims': claims})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload['vendor'] == 'TESTVENDOR'
    assert payload['count'] == 2
    assert len(payload['results']) == 2
    assert payload['results'][0]['PRIMARY_DISPUTE_CODE'] == 101

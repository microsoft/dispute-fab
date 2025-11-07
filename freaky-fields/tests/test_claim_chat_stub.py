import sys, os
sys.path.append(os.path.dirname(__file__) + '/../')  # ensure root added for direct module import
import api_server
from fastapi.testclient import TestClient


class StubChat:
    def __call__(self, messages, deployment=None):  # mimic run_claim_chat signature
        # Return deterministic answer for tests
        return "Stub answer: PRIORITY suggests prompt review."


def test_claim_chat_endpoint_stub():
    # Monkeypatch chat runner
    api_server.run_claim_chat = StubChat()  # type: ignore
    client = TestClient(api_server.app)
    payload = {
        "question": "What is the recommended action?",
        "CLAIM_ID": "C12345",
        "VENDOR": "VENDORX",
        "PRIMARY_DISPUTE_CODE": 101,
        "DESCRIPTION": "Test description",
        "CATEGORY": "PRICING",
        "PRIORITY_RANK": 7,
        "ALL_APPLICABLE_CODES": "101,102",
        "EVIDENCE": "PRIMARY DISPUTE CODE: 101 | Reason: underpayment",
        "CONFIDENCE": 0.82,
        "REQUIRES_REVIEW": False
    }
    resp = client.post("/api/claim-chat", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["claim_id"] == "C12345"
    assert data["success"] is True
    assert "Stub answer" in data["answer"]
    # Structured fields should hydrate (direct_answer may fallback to first sentences)
    assert "direct_answer" in data
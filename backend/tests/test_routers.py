"""
Router Integration Tests
=========================
Tests all 5 API routers using FastAPI's TestClient with:
  - app.dependency_overrides to inject mocked DB and auth dependencies
  - Realistic Indian business data fixtures
  - No real DB, no real JWT, no real external APIs needed

Test coverage:
  auth     — sync, me, profile update, account delete, validation
  analysis — full bundle, metrics, anomalies with filter, customers, history
  reports  — generate (mocked LLM), list, get by id, send WhatsApp validation
  whatsapp — webhook verify, HMAC rejection, opt-in, invalid phone/language
  ca       — dashboard, list/create/get/update/deactivate clients, access control
  system   — health check, root, docs
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Environment is set up in conftest.py before any imports
# ---------------------------------------------------------------------------
from main import app
from auth import AuthenticatedUser
from db.neon_client import get_db_session


# ---------------------------------------------------------------------------
# Constants — shared across all tests
# ---------------------------------------------------------------------------

USER_ID   = str(uuid.uuid4())
EMAIL     = "akshit@sharma-traders.com"
CLIENT_ID = str(uuid.uuid4())
UPLOAD_ID = str(uuid.uuid4())
ANALYSIS_ID = str(uuid.uuid4())
REPORT_ID   = str(uuid.uuid4())

MOCK_USER_ROW = SimpleNamespace(
    id=USER_ID,
    email=EMAIL,
    name="Akshit Sharma",
    phone="+919876543210",
    user_type="ca_firm",
    language_preference="hi",
    whatsapp_opted_in=True,
    subscription_status="trial",
    avatar_url="https://lh3.googleusercontent.com/a/photo",
    created_at="2026-01-01T00:00:00",
)

MOCK_METRICS = {
    "current_revenue": 145000,
    "previous_revenue": 120000,
    "change_amount": 25000,
    "change_pct": 20.83,
    "trend": "up",
    "top_products": [
        {"rank": 1, "name": "Parle-G Biscuit", "revenue": 45000, "trend": "up"},
        {"rank": 2, "name": "Surf Excel", "revenue": 38000, "trend": "flat"},
    ],
    "dead_stock": [{"product": "Tata Salt", "days_since_sale": 22}],
    "dead_stock_count": 1,
}

MOCK_ANOMALIES = {
    "total": 3,
    "high_count": 1,
    "medium_count": 2,
    "low_count": 0,
    "anomalies": [
        {
            "type": "slow_moving_stock",
            "severity": "HIGH",
            "confidence": 0.95,
            "title": "Tata Salt is not selling",
            "explanation": "Tata Salt has not sold in 22 days.",
            "action": "Run a 5% discount this week.",
        },
        {
            "type": "customer_churn_risk",
            "severity": "MEDIUM",
            "confidence": 0.80,
            "title": "Patel Kirana at risk",
            "explanation": "No orders in 25 days.",
            "action": "Call and offer loyalty discount.",
        },
    ],
}

MOCK_CUSTOMERS = {
    "total": 47,
    "segments": {"Champion": 5, "Loyal": 12, "At Risk": 8, "New": 6, "Average": 16},
    "top_customers": [
        {"name": "Sharma Traders", "segment": "Champion", "rfm_score": "555"},
        {"name": "Patel Kirana", "segment": "At Risk", "rfm_score": "244"},
    ],
}

MOCK_ANALYSIS_ROW = SimpleNamespace(
    id=ANALYSIS_ID,
    period_start="2026-01-05",
    period_end="2026-03-14",
    metrics=MOCK_METRICS,
    anomalies=MOCK_ANOMALIES,
    customers=MOCK_CUSTOMERS,
    seasonality_context={"events": ["Holi 2026"], "notes": "Festival season"},
    created_at="2026-03-15T08:00:00",
)

MOCK_CA_CLIENT = SimpleNamespace(
    id=CLIENT_ID,
    client_name="Sharma Trading Co.",
    client_phone="+919876543210",
    client_email="sharma@trading.com",
    white_label_name="Sharma Reports",
    white_label_logo_url=None,
    language_preference="hi",
    whatsapp_opted_in=True,
    active=True,
    upload_count=5,
    last_upload_at="2026-03-15T08:00:00",
    latest_health_score=82,
    created_at="2026-01-10T00:00:00",
)


# ---------------------------------------------------------------------------
# Dependency override helpers
# ---------------------------------------------------------------------------

def _make_db_override(fetchone_values=None, fetchall_value=None, scalar_value=0):
    """
    Create a FastAPI dependency override for get_db_session.
    fetchone_values: list of return values for successive fetchone() calls.
    """
    async def override():
        session = AsyncMock()
        result = MagicMock()

        if fetchone_values is not None:
            result.fetchone.side_effect = fetchone_values
        else:
            result.fetchone.return_value = None

        result.fetchall.return_value = fetchall_value or []
        result.scalar.return_value = scalar_value
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        yield session

    return override


def _mock_auth(user_type="ca_firm"):
    """Create a mock AuthenticatedUser dependency override."""
    user = AuthenticatedUser(user_id=USER_ID, email=EMAIL, name="Akshit Sharma")

    async def override():
        return user

    return override


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def default_db_override():
    """
    Always inject a working (but empty) DB session so tests don't need
    a real database. FastAPI resolves dependencies before body validation,
    so even 422-returning tests need the DB dependency satisfied.
    Individual tests override this by setting app.dependency_overrides[get_db_session]
    again with specific return values.
    """
    app.dependency_overrides[get_db_session] = _make_db_override()
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth Router Tests
# ---------------------------------------------------------------------------

class TestAuthRouter:

    def test_sync_user_creates_or_updates(self):
        """/auth/sync upserts user and returns profile."""
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[MOCK_USER_ROW]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/sync", json={
            "google_id": "google-uid-123456",
            "email": EMAIL,
            "name": "Akshit Sharma",
            "avatar_url": "https://lh3.googleusercontent.com/a/photo",
            "user_type": "ca_firm",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["email"] == EMAIL
        assert data["user_type"] == "ca_firm"

    def test_sync_invalid_user_type_rejected(self):
        """user_type='admin' is rejected with 422."""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/sync", json={
            "google_id": "uid",
            "email": "test@test.com",
            "name": "Test",
            "user_type": "admin",
        })
        assert resp.status_code == 422

    def test_sync_invalid_email_rejected(self):
        """Non-email in email field returns 422."""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/auth/sync", json={
            "google_id": "uid",
            "email": "not-an-email",
            "name": "Test",
        })
        assert resp.status_code == 422

    def test_get_me_requires_auth(self):
        """/auth/me without JWT returns 401 or 403 (unauthenticated)."""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)  # HTTPBearer returns 403; JWT check returns 401

    def test_get_me_returns_profile(self):
        """/auth/me returns profile for authenticated user."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[MOCK_USER_ROW]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        assert resp.json()["email"] == EMAIL

    def test_update_profile_language(self):
        """/auth/profile updates language_preference."""
        from auth import get_current_user
        updated = SimpleNamespace(**{k: getattr(MOCK_USER_ROW, k) for k in vars(MOCK_USER_ROW)})
        updated.language_preference = "en"
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[updated]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.put(
            "/api/v1/auth/profile",
            json={"language_preference": "en"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200

    def test_update_profile_invalid_language(self):
        """language_preference='french' returns 422."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.put(
            "/api/v1/auth/profile",
            json={"language_preference": "french"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 422

    def test_update_profile_empty_body(self):
        """Empty update body returns 400."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.put(
            "/api/v1/auth/profile",
            json={},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 400

    def test_delete_account_returns_204(self):
        """DELETE /auth/account returns 204 on success."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[SimpleNamespace(id=USER_ID)]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/v1/auth/account", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 204

    def test_delete_nonexistent_account_returns_404(self):
        """DELETE /auth/account for unknown user returns 404."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[None]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/v1/auth/account", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Analysis Router Tests
# ---------------------------------------------------------------------------

class TestAnalysisRouter:

    def test_full_analysis_bundle(self):
        """GET /analysis/{upload_id} returns all 4 analysis sections."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[MOCK_ANALYSIS_ROW]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analysis/{UPLOAD_ID}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["upload_id"] == UPLOAD_ID
        assert "metrics" in data
        assert "anomalies" in data
        assert "customers" in data
        assert "seasonality_context" in data

    def test_metrics_endpoint(self):
        """GET /analysis/{upload_id}/metrics returns revenue + products."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[MOCK_ANALYSIS_ROW]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analysis/{UPLOAD_ID}/metrics", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["revenue"]["current"] == 145000
        assert data["revenue"]["trend"] == "up"
        assert data["dead_stock_count"] == 1

    def test_anomalies_endpoint(self):
        """GET /analysis/{upload_id}/anomalies returns sorted alerts."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[MOCK_ANALYSIS_ROW]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analysis/{UPLOAD_ID}/anomalies", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["high_count"] == 1
        assert data["medium_count"] == 2
        assert len(data["anomalies"]) == 2

    def test_anomalies_filter_by_severity(self):
        """?severity=HIGH filters to only HIGH anomalies."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[MOCK_ANALYSIS_ROW]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            f"/api/v1/analysis/{UPLOAD_ID}/anomalies?severity=HIGH",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        assert all(a["severity"] == "HIGH" for a in resp.json()["anomalies"])

    def test_anomalies_invalid_severity_returns_400(self):
        """?severity=CRITICAL returns 400."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            f"/api/v1/analysis/{UPLOAD_ID}/anomalies?severity=CRITICAL",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 400

    def test_customers_endpoint(self):
        """GET /analysis/{upload_id}/customers returns RFM data."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[MOCK_ANALYSIS_ROW]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analysis/{UPLOAD_ID}/customers", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_customers"] == 47
        assert "Champion" in data["segments"]

    def test_analysis_not_found_returns_404(self):
        """Unknown upload_id returns 404."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[None]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/v1/analysis/{uuid.uuid4()}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 404

    def test_analysis_history(self):
        """GET /analysis/history/list returns paginated list."""
        from auth import get_current_user
        history_row = SimpleNamespace(
            id=ANALYSIS_ID, upload_id=UPLOAD_ID,
            file_name="jan_sales.xml", file_type="tally_xml",
            data_health_score=85, period_start="2026-01-01",
            period_end="2026-01-31", current_revenue=145000,
            trend="up", anomaly_count=3,
            created_at="2026-03-15T08:00:00",
        )
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchall_value=[history_row], scalar_value=1
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/analysis/history/list", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["file_name"] == "jan_sales.xml"


# ---------------------------------------------------------------------------
# Reports Router Tests
# ---------------------------------------------------------------------------

class TestReportsRouter:

    REPORT_ROW = SimpleNamespace(
        id=REPORT_ID, analysis_id=ANALYSIS_ID,
        report_type="weekly", language="hi",
        content_hindi="📊 साप्ताहिक रिपोर्ट\n\nइस हफ्ते बिक्री ₹1,45,000 रही। 🎉",
        content_english=None,
        whatsapp_sent=False, whatsapp_sent_at=None,
        created_at="2026-03-15T09:00:00",
        period_start="2026-03-08", period_end="2026-03-14",
    )

    def test_generate_report(self):
        """POST /reports/generate returns report with LLM content."""
        from auth import get_current_user
        from services.reporter.llm_narrator import NarratorResult

        analysis_row = SimpleNamespace(
            id=ANALYSIS_ID, period_start="2026-03-08", period_end="2026-03-14",
            metrics=MOCK_METRICS, anomalies=MOCK_ANOMALIES,
            customers=MOCK_CUSTOMERS,
            seasonality_context={"events": []},
            user_id=USER_ID,
        )
        report_insert_row = SimpleNamespace(id=REPORT_ID, created_at="2026-03-15T09:00:00")

        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[analysis_row, report_insert_row]
        )

        mock_result = NarratorResult(
            content="📊 साप्ताहिक रिपोर्ट\n\nइस हफ्ते बिक्री ₹1,45,000 रही।",
            language="hi", word_count=12, used_fallback=False, generation_time_ms=850,
        )

        with patch("routers.reports.generate_report", return_value=mock_result):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/api/v1/reports/generate",
                json={
                    "analysis_id": ANALYSIS_ID,
                    "language": "hi",
                    "report_type": "weekly",
                    "owner_name": "Sharma Traders",
                },
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["language"] == "hi"
        assert "content" in data
        assert data["used_fallback"] is False

    def test_generate_report_invalid_language(self):
        """language='marathi' returns 400."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/reports/generate",
            json={"analysis_id": ANALYSIS_ID, "language": "marathi"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 400

    def test_generate_report_invalid_type(self):
        """report_type='quarterly' returns 400."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/reports/generate",
            json={"analysis_id": ANALYSIS_ID, "language": "en", "report_type": "quarterly"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 400

    def test_list_reports(self):
        """GET /reports returns paginated list."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchall_value=[self.REPORT_ROW], scalar_value=1
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/reports", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["report_type"] == "weekly"

    def test_get_report_by_id(self):
        """GET /reports/{id} returns full content."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[self.REPORT_ROW]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/v1/reports/{REPORT_ID}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "₹" in data["content"]

    def test_get_report_not_found(self):
        """Unknown report_id returns 404."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[None]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/v1/reports/{uuid.uuid4()}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 404

    def test_send_whatsapp_invalid_phone_format(self):
        """phone without + country code returns 400."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"/api/v1/reports/{REPORT_ID}/send",
            json={"phone_number": "9876543210"},  # Missing +91
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 400

    def test_send_whatsapp_valid_phone(self):
        """Valid E.164 phone sends report (WhatsApp API mocked)."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[self.REPORT_ROW, SimpleNamespace(id=REPORT_ID)]
        )
        with patch("routers.reports._send_whatsapp_message", return_value="wamid.test123"):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                f"/api/v1/reports/{REPORT_ID}/send",
                json={"phone_number": "+919876543210"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"


# ---------------------------------------------------------------------------
# WhatsApp Router Tests
# ---------------------------------------------------------------------------

class TestWhatsAppRouter:

    def test_webhook_verify_correct_token(self):
        """GET /whatsapp/webhook echoes challenge with correct token."""
        with patch("routers.whatsapp.settings") as s:
            s.WHATSAPP_VERIFY_TOKEN = "my-verify-token"
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/v1/whatsapp/webhook", params={
                "hub.mode": "subscribe",
                "hub.verify_token": "my-verify-token",
                "hub.challenge": "challenge-abc123",
            })
        assert resp.status_code == 200
        assert resp.text == "challenge-abc123"

    def test_webhook_verify_wrong_token_returns_403(self):
        """Wrong verify_token returns 403."""
        with patch("routers.whatsapp.settings") as s:
            s.WHATSAPP_VERIFY_TOKEN = "correct-token"
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/v1/whatsapp/webhook", params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "abc",
            })
        assert resp.status_code == 403

    def test_webhook_verify_unconfigured_returns_503(self):
        """Empty WHATSAPP_VERIFY_TOKEN returns 503."""
        with patch("routers.whatsapp.settings") as s:
            s.WHATSAPP_VERIFY_TOKEN = ""
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/v1/whatsapp/webhook", params={
                "hub.mode": "subscribe",
                "hub.verify_token": "anything",
                "hub.challenge": "abc",
            })
        assert resp.status_code == 503

    def test_incoming_webhook_no_signature_rejected(self):
        """POST without X-Hub-Signature-256 returns 403 when token configured."""
        with patch("routers.whatsapp.settings") as s:
            s.WHATSAPP_ACCESS_TOKEN = "real-app-secret"
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/api/v1/whatsapp/webhook",
                json={"object": "whatsapp_business_account", "entry": []},
                # No X-Hub-Signature-256 header
            )
        assert resp.status_code == 403

    def test_incoming_webhook_empty_entries_ok(self):
        """POST with no HMAC config and empty entries returns 200."""
        app.dependency_overrides[get_db_session] = _make_db_override()
        with patch("routers.whatsapp.settings") as s:
            s.WHATSAPP_ACCESS_TOKEN = ""  # HMAC disabled
            s.WHATSAPP_VERIFY_TOKEN = ""
            s.WHATSAPP_PHONE_NUMBER_ID = ""
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/api/v1/whatsapp/webhook",
                json={"object": "whatsapp_business_account", "entry": []},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_optin_valid(self):
        """POST /whatsapp/optin with valid E.164 phone opts user in."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/whatsapp/optin",
            json={"phone_number": "+919876543210", "language": "hi"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "opted_in"

    def test_optin_invalid_phone(self):
        """Phone without + returns 400."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/whatsapp/optin",
            json={"phone_number": "9876543210", "language": "hi"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 400

    def test_optin_invalid_language(self):
        """language='gujarati' returns 400."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/whatsapp/optin",
            json={"phone_number": "+919876543210", "language": "gujarati"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# CA Router Tests
# ---------------------------------------------------------------------------

class TestCARouter:

    def _ca_setup(self, extra_fetchone=None):
        """DB override with CA user_type check as first result."""
        values = [SimpleNamespace(user_type="ca_firm")]
        if extra_fetchone:
            values.extend(extra_fetchone)
        return _make_db_override(fetchone_values=values)

    def test_dashboard_returns_portfolio_stats(self):
        """GET /ca/dashboard returns aggregate client stats."""
        from auth import get_current_user
        stats = SimpleNamespace(
            total_clients=12, active_clients=10, total_uploads=47,
            clients_at_risk=2, portfolio_health_score=78,
        )
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[SimpleNamespace(user_type="ca_firm"), stats],
            fetchall_value=[],
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/ca/dashboard", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_clients"] == 12
        assert data["active_clients"] == 10
        assert "clients_with_high_alerts" in data

    def test_list_clients(self):
        """GET /ca/clients returns client list."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[SimpleNamespace(user_type="ca_firm")],
            fetchall_value=[MOCK_CA_CLIENT],
            scalar_value=1,
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/ca/clients", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_create_client(self):
        """POST /ca/clients creates new client."""
        from auth import get_current_user
        new_client = SimpleNamespace(
            id=CLIENT_ID, client_name="Gupta Kirana", client_phone="+919123456789",
            client_email="gupta@kirana.com", white_label_name=None,
            language_preference="hi", whatsapp_opted_in=False,
            active=True, created_at="2026-03-20T00:00:00",
        )
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[SimpleNamespace(user_type="ca_firm"), new_client]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/ca/clients",
            json={
                "client_name": "Gupta Kirana",
                "client_phone": "+919123456789",
                "client_email": "gupta@kirana.com",
                "language_preference": "hi",
            },
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 201
        assert resp.json()["client_name"] == "Gupta Kirana"

    def test_create_client_name_too_short(self):
        """Single-char name returns 422 (validation) after auth passes."""
        from auth import get_current_user
        # Need CA user check to pass so we reach body validation
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[SimpleNamespace(user_type="ca_firm")]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/ca/clients",
            json={"client_name": "X"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 422

    def test_get_client_detail(self):
        """GET /ca/clients/{id} returns client detail."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[SimpleNamespace(user_type="ca_firm"), MOCK_CA_CLIENT]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/v1/ca/clients/{CLIENT_ID}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        assert resp.json()["client_name"] == "Sharma Trading Co."

    def test_get_nonexistent_client_returns_404(self):
        """Unknown client_id returns 404."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[SimpleNamespace(user_type="ca_firm"), None]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/v1/ca/clients/{uuid.uuid4()}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 404

    def test_deactivate_client(self):
        """DELETE /ca/clients/{id} soft-deletes client."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[
                SimpleNamespace(user_type="ca_firm"),
                SimpleNamespace(id=CLIENT_ID, client_name="Sharma Trading Co."),
            ]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete(f"/api/v1/ca/clients/{CLIENT_ID}", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deactivated"

    def test_smb_owner_blocked_from_ca_dashboard(self):
        """SMB owner (user_type != ca_firm) gets 403."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[SimpleNamespace(user_type="smb_owner")]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/ca/dashboard", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 403

    def test_update_client_empty_body_returns_400(self):
        """PUT /ca/clients/{id} with empty body returns 400."""
        from auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_auth()
        app.dependency_overrides[get_db_session] = _make_db_override(
            fetchone_values=[SimpleNamespace(user_type="ca_firm")]
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.put(
            f"/api/v1/ca/clients/{CLIENT_ID}",
            json={},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# System Endpoints Tests
# ---------------------------------------------------------------------------

class TestSystemEndpoints:

    def test_health_check(self):
        """GET /health returns {status: ok}."""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root(self):
        """GET / returns product info."""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["product"] == "Munim"

    def test_docs_available(self):
        """GET /docs returns swagger UI (development mode)."""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/docs")
        assert resp.status_code in (200, 307, 404)  # 404 in production mode

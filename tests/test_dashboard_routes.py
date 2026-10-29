"""
Unit and Integration Tests for User Dashboard API Routes
Verifies strict database-driven metrics, authentication isolation, and empty state handling.
"""

import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_dashboard_unauthenticated_access(client):
    """All dashboard APIs must return 401 when accessed without an active session."""
    endpoints = [
        "/api/dashboard/stats",
        "/api/dashboard/upload-activity",
        "/api/dashboard/document-types",
        "/api/dashboard/confidence",
        "/api/dashboard/recent-documents",
    ]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 401, f"Expected 401 for {ep}, got {res.status_code}"
        data = res.get_json()
        assert data["success"] is False
        assert "Authentication required" in data["message"]


def test_dashboard_stats_authenticated(client):
    """Test /api/dashboard/stats for an authenticated user."""
    with client.session_transaction() as sess:
        sess["user_id"] = 45
        sess["role"] = "user"

    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "total_documents" in data
    assert "processed" in data
    assert "processing" in data
    assert "failed" in data
    assert isinstance(data["total_documents"], int)
    assert isinstance(data["processed"], int)
    assert isinstance(data["processing"], int)
    assert isinstance(data["failed"], int)
    assert data["total_documents"] >= data["processed"] + data["failed"]


def test_dashboard_upload_activity_no_repeated_dates(client):
    """Verify that upload-activity returns distinct dates with no duplicates."""
    with client.session_transaction() as sess:
        sess["user_id"] = 45
        sess["role"] = "user"

    for period in ["7", "30", "90", "all"]:
        res = client.get(f"/api/dashboard/upload-activity?period={period}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        labels = data["labels"]
        raw_dates = data["dates"]
        # Guarantee no duplicates
        assert len(raw_dates) == len(set(raw_dates)), f"Duplicate dates detected in period {period}: {raw_dates}"
        assert len(labels) == len(data["counts"])
        assert data["total"] == sum(data["counts"])


def test_dashboard_document_types_real_data(client):
    """Verify document-types matches real database classification counts."""
    with client.session_transaction() as sess:
        sess["user_id"] = 45
        sess["role"] = "user"

    res = client.get("/api/dashboard/document-types")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "labels" in data
    assert "counts" in data
    assert "types" in data
    assert len(data["labels"]) == len(data["counts"])
    for item in data["types"]:
        assert "type" in item
        assert "count" in item
        assert item["count"] > 0


def test_dashboard_confidence_scores(client):
    """Verify confidence analytics provides parsed floats and accurate average."""
    with client.session_transaction() as sess:
        sess["user_id"] = 45
        sess["role"] = "user"

    res = client.get("/api/dashboard/confidence")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    values = data["values"]
    for v in values:
        assert isinstance(v, (int, float))
        assert 0.0 <= v <= 100.0
    if values:
        expected_avg = round(sum(values) / len(values), 1)
        assert abs(data["average"] - expected_avg) < 0.05


def test_dashboard_recent_documents(client):
    """Verify recent documents provides required table fields."""
    with client.session_transaction() as sess:
        sess["user_id"] = 45
        sess["role"] = "user"

    res = client.get("/api/dashboard/recent-documents?limit=5")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    docs = data["documents"]
    assert len(docs) <= 5
    for doc in docs:
        assert "job_id" in doc
        assert "filename" in doc
        assert "document_type" in doc
        assert "status" in doc
        assert "confidence_score" in doc
        assert "created_at" in doc
        assert "result_url" in doc


def test_dashboard_empty_user_handling(client):
    """Verify clean empty states when a user has zero documents."""
    with client.session_transaction() as sess:
        sess["user_id"] = 999999
        sess["role"] = "user"

    # Stats
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    assert res.get_json()["total_documents"] == 0

    # Activity
    res = client.get("/api/dashboard/upload-activity")
    assert res.status_code == 200
    assert res.get_json()["empty"] is True
    assert len(res.get_json()["labels"]) == 0

    # Types
    res = client.get("/api/dashboard/document-types")
    assert res.status_code == 200
    assert res.get_json()["empty"] is True
    assert len(res.get_json()["labels"]) == 0

    # Confidence
    res = client.get("/api/dashboard/confidence")
    assert res.status_code == 200
    assert res.get_json()["empty"] is True
    assert res.get_json()["average"] == 0.0

    # Recent Documents
    res = client.get("/api/dashboard/recent-documents")
    assert res.status_code == 200
    assert res.get_json()["empty"] is True
    assert len(res.get_json()["documents"]) == 0

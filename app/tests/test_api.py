"""
API integration tests.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Cloud Club AI - Resume Parser POC"
    assert "endpoints" in data


def test_health_check():
    """Test health check."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"


def test_parse_resume_no_file():
    """Test parse endpoint with no file."""
    response = client.post("/api/v1/parse/resume")
    assert response.status_code == 422  # Validation error


def test_parse_resume_invalid_format():
    """Test parse endpoint with invalid file format."""
    response = client.post(
        "/api/v1/parse/resume",
        files={"file": ("test.txt", b"invalid content", "text/plain")}
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cost_estimate():
    """Test cost estimation endpoint."""
    response = client.get("/api/v1/cost/estimate?file_size_kb=20&num_resumes=10")
    assert response.status_code == 200
    data = response.json()
    assert "cost_per_resume_usd" in data
    assert "total_cost_usd" in data
    assert data["num_resumes"] == 10

"""
Pytest configuration and fixtures.
"""

import pytest
from pathlib import Path

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "sample_resumes"


@pytest.fixture
def sample_resume_path():
    """Path to sample resume."""
    return TEST_DATA_DIR / "jesus_resume.pdf"


@pytest.fixture
def sample_resume_bytes(sample_resume_path):
    """Load sample resume bytes."""
    if not sample_resume_path.exists():
        pytest.skip(f"Sample resume not found: {sample_resume_path}")
    
    with open(sample_resume_path, "rb") as f:
        return f.read()


@pytest.fixture
def poorly_formatted_resume_path():
    """Path to poorly formatted resume (stress test)."""
    return TEST_DATA_DIR / "poorly_formatted.pdf"


@pytest.fixture
def consulting_resume_path():
    """Path to consulting resume (vendor vs company test)."""
    return TEST_DATA_DIR / "consulting_resume.pdf"

"""
Tests for resume parser.

Tests cover key requirements:
1. Client product extraction (for lead generation)
2. Vendor vs company separation
3. SFDC years calculation (entire resume, not per-page)
4. Overall career summarization (not per-page)
5. Handles any resume format
"""

import pytest
from app.core.extraction.resume_parser import ResumeParser
from app.schemas.candidate import CandidateProfile


@pytest.fixture
def parser():
    """Parser fixture."""
    return ResumeParser()


@pytest.mark.asyncio
async def test_parse_well_formatted_resume(parser, sample_resume_bytes):
    """
    Test parsing well-formatted resume.
    
    This should parse with >95% accuracy.
    """
    profile = await parser.parse(sample_resume_bytes, "jesus_resume.pdf")
    
    # Basic assertions
    assert isinstance(profile, CandidateProfile)
    assert profile.full_name
    assert len(profile.emails) > 0
    assert profile.sha256
    
   
    assert profile.sfdc_years is not None
    assert profile.sfdc_years > 0
    assert profile.sfdc_earliest_year is not None
    
  
    assert profile.candidate_overall_summary
    assert len(profile.candidate_overall_summary) > 50
    
    # Experiences
    assert len(profile.experiences) > 0
    

    total_clients = sum(len(exp.client_projects) for exp in profile.experiences)
    
    # Log results for verification
    print(f"\n✅ Parsed: {profile.full_name}")
    print(f"📧 Emails: {profile.emails}")
    print(f"📍 Location: {profile.candidate_location}")
    print(f"📅 SFDC Years: {profile.sfdc_years} (started {profile.sfdc_earliest_year})")
    print(f"💼 Experiences: {len(profile.experiences)}")
    print(f"🏢 Clients Extracted: {total_clients}")
    print(f"📝 Summary: {profile.candidate_overall_summary[:100]}...")
    
    # Print client products (for lead generation verification)
    for exp in profile.experiences:
        if exp.client_projects:
            print(f"\n{exp.company_name or exp.vendor_consulting_firm}:")
            for client in exp.client_projects:
                print(f"  - {client.project_end_client_name}: {client.products}")


@pytest.mark.asyncio
async def test_vendor_vs_company_logic(parser, consulting_resume_path):
    """
    Test vendor vs company separation.
    
    Consulting roles should have:
    - vendor_consulting_firm populated
    - company_name = NULL
    - client_projects array with end clients
    """
    if not consulting_resume_path.exists():
        pytest.skip("Consulting resume not available")
    
    with open(consulting_resume_path, "rb") as f:
        file_bytes = f.read()
    
    profile = await parser.parse(file_bytes, "consulting_resume.pdf")
    
    # Find consulting experience
    consulting_exp = next(
        (exp for exp in profile.experiences if exp.vendor_consulting_firm),
        None
    )
    
    if consulting_exp:
        # Assertions for consulting role
        assert consulting_exp.vendor_consulting_firm is not None
        assert consulting_exp.company_name is None
        assert len(consulting_exp.client_projects) > 0
        
        # Check client products (for lead generation)
        for client in consulting_exp.client_projects:
            assert client.project_end_client_name
            # Products might be empty if not specified in resume
            
        print(f"\n✅ Vendor Logic Correct:")
        print(f"Firm: {consulting_exp.vendor_consulting_firm}")
        print(f"Clients: {[c.project_end_client_name for c in consulting_exp.client_projects]}")


@pytest.mark.asyncio
async def test_client_product_extraction(parser, sample_resume_bytes):
    """
    
    
    Example: If resume says "At American Express, worked on Sales Cloud and CPQ"
    Should extract:
    {
      "project_end_client_name": "American Express",
      "products": ["Sales Cloud", "CPQ"]
    }
    """
    profile = await parser.parse(sample_resume_bytes, "jesus_resume.pdf")
    
    # Check if any experience has client projects
    has_client_projects = any(
        len(exp.client_projects) > 0
        for exp in profile.experiences
    )
    
    if has_client_projects:
        for exp in profile.experiences:
            for client in exp.client_projects:
                # Each client should have a name
                assert client.project_end_client_name
                
                # Products array (might be empty if not specified)
                assert isinstance(client.products, list)
                
                print(f"\n✅ Client: {client.project_end_client_name}")
                print(f"   Products: {client.products}")
                print(f"   Industry: {client.project_client_industry}")


@pytest.mark.asyncio
async def test_poorly_formatted_resume(parser, poorly_formatted_resume_path):
    """
    Test with poorly formatted resume (where Document AI struggles).
    
    GPT-4o should still extract core fields with >85% accuracy.
    """
    if not poorly_formatted_resume_path.exists():
        pytest.skip("Poorly formatted resume not available")
    
    with open(poorly_formatted_resume_path, "rb") as f:
        file_bytes = f.read()
    
    profile = await parser.parse(file_bytes, "poorly_formatted.pdf")
    
    # Should still extract core fields
    assert profile.full_name
    assert len(profile.experiences) > 0
    
    # Summary should cover entire resume (not per-page)
    assert profile.candidate_overall_summary
    
    # SFDC years should be calculated correctly (not per-page)
    if profile.sfdc_earliest_year:
        assert profile.sfdc_years is not None
        assert profile.sfdc_years > 0
    
    print(f"\n✅ Poorly Formatted Resume Parsed:")
    print(f"Candidate: {profile.full_name}")
    print(f"Summary: {profile.candidate_overall_summary[:100]}...")


def test_location_normalization():
    """Test location format normalization."""
    from app.core.extraction.rules import normalize_location
    
    # US format
    assert normalize_location("Austin, TX 78701") == "Austin, TX"
    assert normalize_location("San Francisco, CA 94102") == "San Francisco, CA"
    
    # International format
    assert normalize_location("Buenos Aires, Argentina") == "Buenos Aires, Argentina"
    assert normalize_location("London, UK") == "London, UK"
    
    # Remove street addresses
    assert "123 Main St" not in normalize_location("123 Main St, Austin, TX 78701")


def test_product_normalization():
    """Test Salesforce product normalization."""
    from app.core.extraction.rules import normalize_product
    
    # Sales Cloud variants
    assert normalize_product("sales cloud") == "Sales Cloud"
    assert normalize_product("SFDC Sales") == "Sales Cloud"
    assert normalize_product("CRM Core") == "Sales Cloud"
    
    # CPQ variants
    assert normalize_product("cpq") == "CPQ"
    assert normalize_product("Apttus CPQ") == "CPQ"
    assert normalize_product("Revenue Cloud") == "CPQ"
    
    # Experience Cloud variants
    assert normalize_product("Communities") == "Experience Cloud"
    assert normalize_product("Community Cloud") == "Experience Cloud"


def test_sfdc_years_calculation():
    
    from app.core.extraction.rules import calculate_sfdc_years
    
    # Should calculate across entire resume
    assert calculate_sfdc_years("2018") == 7  # 2025 - 2018
    assert calculate_sfdc_years("2020") == 5  # 2025 - 2020
    assert calculate_sfdc_years("2015") == 10  # 2025 - 2015
    
    # Edge cases
    assert calculate_sfdc_years(None) == 0
    assert calculate_sfdc_years("invalid") == 0


@pytest.mark.asyncio
async def test_cost_estimate(parser):
    """Test cost estimation."""
    # Average resume: ~5000 characters
    cost = parser.calculate_cost_estimate(5000)
    
    # Should be around $0.025
    assert 0.02 <= cost <= 0.03
    
    print(f"\n✅ Cost Estimate: ${cost:.4f} per resume")

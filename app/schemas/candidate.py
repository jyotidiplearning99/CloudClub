"""
Pydantic schemas for candidate profiles.


- Extract ALL companies (vendors, employers, clients)
- Client products for lead generation
- Vendor vs company separation
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class SocialLinks(BaseModel):
    """Professional links."""
    linkedin: Optional[str] = Field(None, description="LinkedIn profile URL")
    trailblazer: Optional[str] = Field(None, description="Salesforce Trailblazer profile URL")
    github: Optional[str] = Field(None, description="GitHub profile URL")


class ClientProject(BaseModel):
    """
    Client project under consulting engagement.
   
    Example: "At American Express, worked on Sales Cloud and CPQ"
    This creates Leads in Salesforce tagged with products.
    """
    project_end_client_name: str = Field(
        ...,
        description="End client company name (e.g., 'American Express', 'Charles Tyrwhitt')"
    )
    project_client_industry: Optional[str] = Field(
        None,
        description="Client industry (e.g., 'Financial Services', 'Retail')"
    )
    project_start_date: Optional[str] = Field(
        None,
        description="Project start date (YYYY-MM). Only if explicitly stated AND different from job dates."
    )
    project_end_date: Optional[str] = Field(
        None,
        description="Project end date (YYYY-MM or 'Present'). Only if explicitly stated AND different from job dates."
    )
    products: List[str] = Field(
        default_factory=list,
        description="Salesforce/Commerce products used AT THIS CLIENT. For Lead tagging."
    )


class Experience(BaseModel):
    """
    Work experience entry.
    
   
    - If consulting role: set vendor_consulting_firm, leave company_name NULL
    - If direct employment: set company_name, leave vendor_consulting_firm NULL
    """
    company_name: Optional[str] = Field(
        None,
        description="Direct employer company name. NULL if consulting role."
    )
    vendor_consulting_firm: Optional[str] = Field(
        None,
        description="Consulting firm name (e.g., 'Deloitte', 'Soitron'). NULL if direct employment."
    )
    job_title: Optional[str] = Field(
        None,
        description="Job title (e.g., 'Senior Salesforce Developer')"
    )
    job_start_date: Optional[str] = Field(
        None,
        description="Job start date (YYYY-MM format). NULL if not stated."
    )
    job_end_date: Optional[str] = Field(
        None,
        description="Job end date (YYYY-MM or 'Present'). NULL if not stated."
    )
    products: List[str] = Field(
        default_factory=list,
        description="Salesforce products used in this role"
    )
    skills: List[str] = Field(
        default_factory=list,
        description="Technical skills"
    )
    client_projects: List[ClientProject] = Field(
        default_factory=list,
        description="End clients if consulting role. CRITICAL for lead generation."
    )


class CompaniesSummary(BaseModel):
    """
    Summary of all companies extracted from resume.
    

    - vendors: Consulting firms (potential subcontracting clients)
    - employers: Direct employers (potential staffing clients)
    - clients: End clients (leads to sell to other consultancies)
    """
    vendors: List[str] = Field(
        default_factory=list,
        description="Consulting/vendor firms (Wunderman Thompson, Soitron, etc.)"
    )
    employers: List[str] = Field(
        default_factory=list,
        description="Direct employers (OSF Digital, Machinas, etc.)"
    )
    clients: List[str] = Field(
        default_factory=list,
        description="End clients from consulting projects (Charles Tyrwhitt, etc.)"
    )


class CandidateProfile(BaseModel):
    """
    Complete candidate profile from resume.
    

    - SFDC years calculated across ENTIRE resume (not per-page)
    - Summary of ENTIRE career (not per-page)
    - Client extraction with products (for lead generation)
    - Companies summary (ALL companies are potential clients)
    """
    
    # Basic Information
    full_name: str = Field(..., description="Full name (title-cased)")
    emails: List[EmailStr] = Field(default_factory=list, description="Email addresses")
    phones: List[str] = Field(default_factory=list, description="Phone numbers")
    links: Optional[SocialLinks] = Field(None, description="Professional links")
    
    # Location
    candidate_location: Optional[str] = Field(
        None,
        description="Location in 'City, ST' (US) or 'City, Country' format"
    )
    
    # Experience Timeline
    it_earliest_year: Optional[str] = Field(
        None,
        description="First year in IT (YYYY format)"
    )
    sfdc_earliest_year: Optional[str] = Field(
        None,
        description="First year with Salesforce/Commerce Cloud (YYYY format)"
    )
    sfdc_years: Optional[int] = Field(
        None,
        description="Years in Salesforce. MUST calculate across ENTIRE resume: 2025 - sfdc_earliest_year"
    )
    
    # Summary
    candidate_overall_summary: Optional[str] = Field(
        None,
        description="2-3 sentences about ENTIRE career. NOT per-page. No candidate name."
    )
    
    # Current Role
    most_recent_job_title: Optional[str] = Field(
        None,
        description="Most recent job title"
    )
    
    # Skills
    other_skills: List[str] = Field(
        default_factory=list,
        description="Non-Salesforce skills"
    )
    certifications: List[str] = Field(
        default_factory=list,
        description="Salesforce certifications"
    )
    
    # Work Experience
    experiences: List[Experience] = Field(
        default_factory=list,
        description="Work experiences with client projects"
    )
    
    
    companies_summary: Optional[CompaniesSummary] = Field(
        None,
        description="Summary of all companies by relationship type"
    )
    
    # Metadata
    sha256: Optional[str] = Field(None, description="Resume hash for deduplication")
    raw_text_ref: Optional[str] = Field(None, description="Storage reference")
    parsed_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Parse timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Jesus Rodriguez",
                "emails": ["jesus@example.com"],
                "candidate_location": "Buenos Aires, Argentina",
                "sfdc_earliest_year": "2018",
                "sfdc_years": 7,
                "companies_summary": {
                    "vendors": ["Arcadia"],
                    "employers": ["Tech Corp"],
                    "clients": ["Cloud Club", "Finales"]
                }
            }
        }

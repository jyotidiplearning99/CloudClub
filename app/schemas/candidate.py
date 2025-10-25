"""
Pydantic schemas with STRICT skill categorization.
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict
from datetime import datetime
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SocialLinks(BaseModel):
    """Professional links."""
    linkedin: Optional[str] = Field(None)
    trailblazer: Optional[str] = Field(None)
    github: Optional[str] = Field(None)
    personal_web: Optional[str] = Field(None)


class ClientProject(BaseModel):
    """End client project."""
    project_end_client_name: str = Field(...)
    via_vendor: Optional[str] = Field(None)
    project_client_industry: Optional[str] = Field(None)
    project_start_date: Optional[str] = Field(None)
    project_end_date: Optional[str] = Field(None)
    products: List[str] = Field(default_factory=list)


class Experience(BaseModel):
    """Work experience with STRICT skills."""
    
    company_name: Optional[str] = Field(None)
    vendor_consulting_firm: Optional[str] = Field(None)
    company_industry: Optional[str] = Field(None)
    job_title: Optional[str] = Field(None)
    job_start_date: Optional[str] = Field(None)
    job_end_date: Optional[str] = Field(None)
    products: List[str] = Field(default_factory=list)
    
    # STRICT: Dict only with 7 categories
    skills: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "admin_and_automation": [],
            "dev_coding": [],
            "architecture_design": [],
            "data_management": [],
            "deployment_devops": [],
            "integration": [],
            "marketing_automation": []
        }
    )
    
    client_projects: List[ClientProject] = Field(default_factory=list)
    
    @validator('skills', pre=True)
    def enforce_categories(cls, v):
        """Enforce all 7 categories."""
        required = [
            "admin_and_automation", "dev_coding", "architecture_design",
            "data_management", "deployment_devops", "integration",
            "marketing_automation"
        ]
        
        if isinstance(v, list):
            logger.warning("skills_list_converted_to_dict")
            return {cat: [] for cat in required}
        
        if not isinstance(v, dict):
            return {cat: [] for cat in required}
        
        for cat in required:
            if cat not in v:
                v[cat] = []
        
        valid_keys = set(required)
        for key in list(v.keys()):
            if key not in valid_keys:
                logger.warning(f"unknown_category_removed: {key}")
                del v[key]
        
        return v


class CompaniesSummary(BaseModel):
    """Two-category summary."""
    vendors: List[str] = Field(default_factory=list)
    clients: List[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    """Complete profile."""
    
    full_name: str = Field(...)
    emails: List[EmailStr] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    links: Optional[SocialLinks] = Field(None)
    
    candidate_location: Optional[str] = Field(None)
    
    it_earliest_year: Optional[str] = Field(None)
    sfdc_earliest_year: Optional[str] = Field(None)
    sfdc_years: Optional[int] = Field(None)
    
    candidate_overall_summary: Optional[str] = Field(None)
    most_recent_job_title: Optional[str] = Field(None)
    
    other_skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    
    experiences: List[Experience] = Field(default_factory=list)
    companies_summary: Optional[CompaniesSummary] = Field(None)
    
    sha256: Optional[str] = Field(None)
    raw_text_ref: Optional[str] = Field(None)
    parsed_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

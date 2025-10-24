"""
Job description schemas for matching.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class JobRequirement(BaseModel):
    """Job requirement from job description."""
    
    title: str
    company: Optional[str] = None
    industry: Optional[str] = None
    
    
    must: List[str] = Field(
        default_factory=list,
        description="Required skills/products"
    )
    preferred: List[str] = Field(
        default_factory=list,
        description="Preferred skills/products"
    )
    bonus: List[str] = Field(
        default_factory=list,
        description="Nice-to-have skills/products"
    )
    
    # Engagement Details
    engagement_type: Optional[str] = None  # contract, full-time, support
    duration_weeks: Optional[int] = None
    hours_per_week: Optional[int] = None
    location: Optional[str] = None  # remote, onsite, hybrid
    timezone: Optional[str] = None
    
    # Budget
    currency: str = "USD"
    hourly_min: Optional[float] = None
    hourly_max: Optional[float] = None

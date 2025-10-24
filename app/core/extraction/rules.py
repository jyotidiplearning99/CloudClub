"""
Normalization rules for resume data.


- Title case all proper nouns
- Normalize Salesforce product names
- Format locations correctly
- Calculate SFDC years properly
"""

from datetime import datetime
from typing import Dict, List


PRODUCT_ALIASES = {
    # Sales Cloud variants
    "sales cloud": "Sales Cloud",
    "sfdc sales": "Sales Cloud",
    "crm core": "Sales Cloud",
    "salesforce crm": "Sales Cloud",
    "sales force cloud": "Sales Cloud",
    
    # Service Cloud variants
    "service cloud": "Service Cloud",
    "sfdc service": "Service Cloud",
    
    # CPQ variants
    "cpq": "CPQ",
    "revenue cloud": "CPQ",
    "apttus cpq": "CPQ",
    "salesforce cpq": "CPQ",
    "steelbrick": "CPQ",
    
    # Experience Cloud variants
    "experience cloud": "Experience Cloud",
    "communities": "Experience Cloud",
    "community cloud": "Experience Cloud",
    
    # Marketing Cloud variants
    "marketing cloud": "Marketing Cloud",
    "sfmc": "Marketing Cloud",
    "exacttarget": "Marketing Cloud",
    "pardot": "Marketing Cloud Account Engagement",
    "marketing cloud account engagement": "Marketing Cloud Account Engagement",
    
    # Financial Services Cloud
    "financial services cloud": "Financial Services Cloud",
    "fsc": "Financial Services Cloud",
    
    # Health Cloud
    "health cloud": "Health Cloud",
    
    # Data Cloud
    "data cloud": "Data Cloud",
    
    # Tableau CRM / Einstein Analytics
    "tableau crm": "Tableau CRM",
    "einstein analytics": "Tableau CRM",
    
    # Industries Cloud
    "industries cloud": "Industries Cloud",
    
    # Field Service
    "field service": "Field Service",
    "field service lightning": "Field Service",
    
    # Commerce Cloud
    "commerce cloud": "Commerce Cloud",
    "demandware": "Commerce Cloud",
}


def normalize_product(product: str) -> str:
    """
    Normalize Salesforce product name to canonical form.
    
    Args:
        product: Product name from resume
        
    Returns:
        Canonical product name
    """
    if not product:
        return product
    
    product_lower = product.lower().strip()
    normalized = PRODUCT_ALIASES.get(product_lower, product.title())
    
    return normalized


def normalize_location(location: str) -> str:
    """
    
    - US: "City, ST"
    - International: "City, Country"
    
    Remove ZIP codes, street addresses, full state names.
    
    Args:
        location: Raw location string
        
    Returns:
        Normalized location
    """
    if not location:
        return location
    
    import re
    
    # Title case
    location = location.title()
    
    # Remove ZIP codes
    location = re.sub(r'\d{5}(-\d{4})?', '', location)
    
    # Remove street addresses
    location = re.sub(
        r'\d+\s+[\w\s]+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way)',
        '',
        location,
        flags=re.IGNORECASE
    )
    
    # Extract city, state/country
    parts = [p.strip() for p in location.split(',') if p.strip()]
    
    if len(parts) >= 2:
        # Take first two parts (city, state/country)
        return f"{parts[0]}, {parts[1]}"
    
    return location.strip()


def calculate_sfdc_years(sfdc_earliest_year: str | None) -> int:
    """
    Calculate years in Salesforce.
    
    CRITICAL: Must calculate across ENTIRE resume, not per-page.
    This fixes Document AI's bug where it calculated per-page.
    
    Args:
        sfdc_earliest_year: First year working with Salesforce (YYYY format)
        
    Returns:
        Number of years (0 if invalid)
    """
    if not sfdc_earliest_year:
        return 0
    
    try:
        year = int(sfdc_earliest_year)
        current_year = 2025  # Update annually
        years = max(0, current_year - year)
        return years
    except (ValueError, TypeError):
        return 0


def apply_normalization_rules(data: Dict) -> Dict:
    """
    Apply all normalization rules to parsed resume data.
    
    Rules:
    1. Title case all proper nouns
    2. Normalize location format
    3. Calculate SFDC years correctly (across entire resume)
    4. Normalize product names
    5. Deduplicate skills
    
    Args:
        data: Raw parsed data from GPT
        
    Returns:
        Normalized data
    """
    # Title case name
    if data.get("full_name"):
        data["full_name"] = data["full_name"].title()
    
    # Normalize location
    if data.get("candidate_location"):
        data["candidate_location"] = normalize_location(data["candidate_location"])
    
    # Calculate SFDC years (FIX: across entire resume, not per-page)
    if data.get("sfdc_earliest_year"):
        data["sfdc_years"] = calculate_sfdc_years(data["sfdc_earliest_year"])
    
    # Normalize experiences
    for exp in data.get("experiences", []):
        # Title case
        if exp.get("job_title"):
            exp["job_title"] = exp["job_title"].title()
        if exp.get("company_name"):
            exp["company_name"] = exp["company_name"].title()
        if exp.get("vendor_consulting_firm"):
            exp["vendor_consulting_firm"] = exp["vendor_consulting_firm"].title()
        
        # Normalize products
        exp["products"] = [normalize_product(p) for p in exp.get("products", [])]
        
        # Normalize skills (title case)
        exp["skills"] = [s.title() for s in exp.get("skills", [])]
        
   
        for project in exp.get("client_projects", []):
            if project.get("project_end_client_name"):
                project["project_end_client_name"] = project["project_end_client_name"].title()
            if project.get("project_client_industry"):
                project["project_client_industry"] = project["project_client_industry"].title()
            
            # Normalize products at client level (for Lead tagging)
            project["products"] = [normalize_product(p) for p in project.get("products", [])]
    
    # Deduplicate and normalize other_skills
    if data.get("other_skills"):
        skills = [s.title() for s in data["other_skills"]]
        data["other_skills"] = list(set(skills))  # Deduplicate
    
    # Normalize certifications
    if data.get("certifications"):
        data["certifications"] = [c.title() for c in data["certifications"]]
    
    # Title case most recent job
    if data.get("most_recent_job_title"):
        data["most_recent_job_title"] = data["most_recent_job_title"].title()
    
    data = compute_companies_summary(data)
    
    return data
def compute_companies_summary(data: dict) -> dict:
    """
    Compute companies_summary from experiences.
    
    Categorizes all companies into:
    - vendors: Consulting firms (vendor_consulting_firm)
    - employers: Direct employers (company_name)
    - clients: End clients (from client_projects)
    
    Args:
        data: Normalized resume data
        
    Returns:
        Data with companies_summary added
    """
    vendors = []
    employers = []
    clients = []
    
    for exp in data.get("experiences", []):
        # Vendors (consulting firms)
        if exp.get("vendor_consulting_firm"):
            vendor = exp["vendor_consulting_firm"]
            if vendor and vendor not in vendors:
                vendors.append(vendor)
        
        # Employers (direct employment)
        if exp.get("company_name"):
            employer = exp["company_name"]
            if employer and employer not in employers:
                employers.append(employer)
        
        # Clients (end clients from consulting projects)
        for project in exp.get("client_projects", []):
            client = project.get("project_end_client_name")
            if client and client not in clients:
                clients.append(client)
    
    data["companies_summary"] = {
        "vendors": sorted(vendors),
        "employers": sorted(employers),
        "clients": sorted(clients)
    }
    
    return data

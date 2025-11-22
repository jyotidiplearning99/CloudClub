"""
POST-PARSE rules with FORCED industry population and timezone extraction.
"""

from typing import Dict, List, Optional
import re
import pytz
from datetime import datetime
from collections import defaultdict
from app.utils.logger import get_logger
from app.constants import (
    SALESFORCE_PRODUCTS_CANONICAL,
    PRODUCT_ALIASES,
    KNOWN_VENDOR_NAMES,
    VENDOR_INDICATORS
)

logger = get_logger(__name__)


# Timezone mapping (US + International)
INTERNATIONAL_TIMEZONES = {
    # US States
    'al': 'America/Chicago', 'alabama': 'America/Chicago',
    'ca': 'America/Los_Angeles', 'california': 'America/Los_Angeles',
    'ny': 'America/New_York', 'new york': 'America/New_York',
    'tx': 'America/Chicago', 'texas': 'America/Chicago',
    'fl': 'America/New_York', 'florida': 'America/New_York',
    'il': 'America/Chicago', 'illinois': 'America/Chicago',
    'pa': 'America/New_York', 'pennsylvania': 'America/New_York',
    'oh': 'America/New_York', 'ohio': 'America/New_York',
    'ga': 'America/New_York', 'georgia': 'America/New_York',
    'nc': 'America/New_York', 'north carolina': 'America/New_York',
    'mi': 'America/New_York', 'michigan': 'America/New_York',
    'wa': 'America/Los_Angeles', 'washington': 'America/Los_Angeles',
    'az': 'America/Phoenix', 'arizona': 'America/Phoenix',
    'ma': 'America/New_York', 'massachusetts': 'America/New_York',
    'co': 'America/Denver', 'colorado': 'America/Denver',
    'mn': 'America/Chicago', 'minnesota': 'America/Chicago',
    
    # International
    'london': 'Europe/London', 'uk': 'Europe/London',
    'paris': 'Europe/Paris', 'france': 'Europe/Paris',
    'mumbai': 'Asia/Kolkata', 'india': 'Asia/Kolkata',
    'bangalore': 'Asia/Kolkata', 'bengaluru': 'Asia/Kolkata',
    'sydney': 'Australia/Sydney', 'australia': 'Australia/Sydney',
}


def extract_timezone_from_location(location: str) -> Optional[Dict[str, str]]:
    """Extract timezone info from location string."""
    if not location or not isinstance(location, str):
        return None
    
    try:
        parts = [p.strip() for p in location.split(',')]
        if len(parts) < 2:
            return None
        
        city = parts[0].lower()
        state_or_country = parts[1].lower().strip()
        
        if city in INTERNATIONAL_TIMEZONES:
            tz_name = INTERNATIONAL_TIMEZONES[city]
        elif state_or_country in INTERNATIONAL_TIMEZONES:
            tz_name = INTERNATIONAL_TIMEZONES[state_or_country]
        else:
            logger.warning("timezone_not_found", location=location)
            return None
        
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        utc_offset = now.strftime('%z')
        utc_offset_formatted = f"{utc_offset[:3]}:{utc_offset[3:]}"
        
        result = {
            "timezone": tz_name,
            "utc_offset": utc_offset_formatted,
            "current_time": now.strftime('%Y-%m-%d %H:%M')
        }
        
        logger.info("timezone_extracted", location=location, result=result)
        return result
        
    except Exception as e:
        logger.error("timezone_extraction_error", error=str(e))
        return None


def derive_company_industry(company_name: str) -> str:
    """Derive industry from company name. NEVER returns None or "?"."""
    if not company_name or not isinstance(company_name, str):
        return "Unknown"
    
    if isinstance(company_name, dict):
        logger.error("company_name_is_dict", value=company_name)
        return "Unknown"
    
    name_lower = company_name.lower().strip()
    
    # Exact company mapping
    company_map = {
        # Insurance
        'american family insurance': 'Insurance',
        'state farm': 'Insurance',
        'allstate': 'Insurance',
        'geico': 'Insurance',
        'progressive': 'Insurance',
        
        # Retail
        'best buy': 'Retail/E-commerce',
        'walmart': 'Retail/E-commerce',
        'target': 'Retail/E-commerce',
        'yeti': 'Retail/E-commerce',
        'yeti coolers': 'Retail/E-commerce',
        'direct supply': 'Retail/Healthcare Supplies',
        
        # Banking/Financial
        't. rowe price': 'Banking/Financial Services',
        't rowe price': 'Banking/Financial Services',
        'deutsche bank': 'Banking/Financial Services',
        'jpmorgan': 'Banking/Financial Services',
        'bank of america': 'Banking/Financial Services',
        'huntington bank': 'Banking/Financial Services',
        
        # Healthcare
        'k health': 'Healthcare',
        'kaiser': 'Healthcare',
        'anthem': 'Healthcare',
        
        # Technology/Cybersecurity
        'zscaler': 'Technology/Cybersecurity',
        'smart solutions': 'Technology/Software',
        
        # Automotive
        'ford': 'Automotive/Manufacturing',
        'ford motor company': 'Automotive/Manufacturing',
        'michelin': 'Automotive/Manufacturing',
        
        # Media
        'sony': 'Media/Entertainment',
        'sony interactive': 'Media/Entertainment',
        
        # Non-Profit
        'ypo': 'Non-Profit/NGO',
        'neighborhood reinvestment': 'Non-Profit/NGO',
        
        # Government
        'city of toronto': 'Government/Public Sector',
        
        # Real Estate
        'lead homes': 'Real Estate',
        
        # Recruiting/HR
        'qc careers': 'Technology/Recruiting',
    }
    
    for company, industry in company_map.items():
        if company in name_lower:
            logger.info("industry_derived_exact", company=company_name, industry=industry)
            return industry
    
    # Keyword matching
    keyword_map = {
        'insurance': 'Insurance',
        'bank': 'Banking/Financial Services',
        'financial': 'Banking/Financial Services',
        'health': 'Healthcare',
        'healthcare': 'Healthcare',
        'retail': 'Retail/E-commerce',
        'solutions': 'Technology/Software',
        'tech': 'Technology/Software',
        'motor': 'Automotive/Manufacturing',
        'automotive': 'Automotive/Manufacturing',
        'entertainment': 'Media/Entertainment',
        'city of': 'Government/Public Sector',
        'government': 'Government/Public Sector',
        'careers': 'Technology/Recruiting',
        'homes': 'Real Estate',
    }
    
    for keyword, industry in keyword_map.items():
        if keyword in name_lower:
            logger.info("industry_derived_keyword", company=company_name, industry=industry, keyword=keyword)
            return industry
    
    logger.warning("industry_unknown", company=company_name)
    return "Unknown"


def is_vendor_name(company_name: str) -> bool:
    """Vendor detection using imported KNOWN_VENDOR_NAMES."""
    if not company_name or not isinstance(company_name, str):
        return False
    
    name_lower = company_name.lower().strip()
    
    if name_lower in KNOWN_VENDOR_NAMES:
        return True
    
    for vendor in KNOWN_VENDOR_NAMES:
        if vendor in name_lower or name_lower in vendor:
            return True
    
    for indicator in VENDOR_INDICATORS:
        if indicator in name_lower:
            return True
    
    return False


def normalize_company_name(name: str) -> str:
    """Normalize company names."""
    if not name or not isinstance(name, str):
        return "Unknown Company"
    
    normalizations = {
        "american family insurance": "American Family Insurance",
        "smart solutions": "Smart Solutions",
        "direct supply": "Direct Supply",
        "teksystems": "TEKsystems",
        "v-soft consulting": "V-Soft Consulting",
        "zensar technologies": "Zensar Technologies",
        "quinnox": "Quinnox",
        "fortech": "Fortech",
        "relevantz": "Relevantz",
        "cloudnerd": "CloudNerd",
        "genisis technology solutions": "Genisis Technology Solutions",
        "t. rowe price": "T. Rowe Price",
        "ford motor company": "Ford Motor Company",
        "yeti coolers": "Yeti Coolers",
        "k health": "K Health",
        "sony interactive entertainment": "Sony Interactive Entertainment",
        "neighborhood reinvestment corporation": "Neighborhood Reinvestment Corporation",
        "michelin": "Michelin",
        "ypo, inc": "YPO, Inc",
        "zscaler": "Zscaler",
        "huntington bank": "Huntington Bank",
        "slolam": "Slolam",
        "gears crm": "Gears CRM",
        "cloudware connections": "Cloudware Connections",
        "eezentek": "Eezentek",
        "city of toronto": "City of Toronto",
        "qc careers": "QC Careers",
        "lead homes": "Lead Homes",
    }
    
    name_lower = name.lower().strip()
    if name_lower in normalizations:
        return normalizations[name_lower]
    
    return name.title().strip()


def normalize_product(product: str) -> str | None:
    """Normalize product using imported PRODUCT_ALIASES."""
    if not product or not isinstance(product, str):
        return None
    
    product_lower = product.lower().strip()
    product_lower = re.sub(r'^salesforce\s+', '', product_lower)
    
    if product_lower in PRODUCT_ALIASES:
        canonical = PRODUCT_ALIASES[product_lower]
        if canonical in SALESFORCE_PRODUCTS_CANONICAL:
            logger.info("product_normalized", original=product, canonical=canonical)
            return canonical
    
    # Exclude tools
    tool_keywords = [
        'copado', 'flosum', 'gearset', 'mulesoft', 'hubspot', 'docusign',
        'qualtrics', 'zoominfo', 'outreach', 'informatica', 'workato'
    ]
    if any(tool in product_lower for tool in tool_keywords):
        logger.info("product_excluded_tool", product=product)
        return None
    
    logger.warning("product_not_recognized", product=product)
    return None


def calculate_it_total_years(it_earliest_year: str) -> int:
    """Calculate IT years."""
    if not it_earliest_year:
        return 0
    try:
        year = int(str(it_earliest_year)[:4])
        current_year = datetime.utcnow().year
        return max(0, min(50, current_year - year))
    except:
        return 0


def calculate_sfdc_years(earliest_year: str) -> int:
    """Calculate SFDC years."""
    if not earliest_year:
        return 0
    try:
        year = int(str(earliest_year)[:4])
        current_year = datetime.utcnow().year
        return max(0, min(50, current_year - year))
    except:
        return 0


def set_company_is_sfdc_client(exp: dict) -> dict:
    """Set TRUE ONLY if Salesforce confirmed."""
    job_title = exp.get("job_title", "")
    if not isinstance(job_title, str):
        job_title = ""
    
    products = exp.get("products", [])
    title_lower = job_title.lower()
    
    if "salesforce" in title_lower or "sfdc" in title_lower:
        exp["company_is_sfdc_client"] = "TRUE"
        return exp
    
    if products and len(products) > 0:
        exp["company_is_sfdc_client"] = "TRUE"
        return exp
    
    exp["company_is_sfdc_client"] = "FALSE"
    return exp


def reclassify_vendors_to_correct_field(data: dict) -> dict:
    """Move vendors from company_name to vendor_consulting_firm."""
    for exp in data.get("experiences", []):
        company_name = exp.get("company_name")
        
        if company_name and is_vendor_name(company_name):
            normalized = normalize_company_name(company_name)
            exp["vendor_consulting_firm"] = normalized
            exp["company_name"] = None
            logger.info("vendor_moved", vendor=normalized)
    
    return data


def populate_company_industries(data: dict) -> dict:
    """FORCE populate company_industry for ALL experiences and projects."""
    for exp in data.get("experiences", []):
        company = exp.get("company_name")
        if company:
            current_industry = exp.get("company_industry")
            if not current_industry or current_industry in ["?", "Unknown", None]:
                industry = derive_company_industry(company)
                exp["company_industry"] = industry
                logger.info("company_industry_force_populated", company=company, industry=industry)
        
        for proj in exp.get("client_projects", []):
            client = proj.get("project_end_client_name")
            if client:
                current_industry = proj.get("project_client_industry")
                if not current_industry or current_industry in ["?", "Unknown", None]:
                    industry = derive_company_industry(client)
                    proj["project_client_industry"] = industry
                    logger.info("project_industry_force_populated", client=client, industry=industry)
    
    return data


def backfill_project_via_vendor(data: dict) -> dict:
    """Backfill via_vendor for client projects."""
    for exp in data.get("experiences", []):
        vendor = exp.get("vendor_consulting_firm")
        if vendor:
            for proj in exp.get("client_projects", []):
                if not proj.get("via_vendor"):
                    proj["via_vendor"] = vendor
    return data


def classify_and_filter(data: dict) -> dict:
    """Classify and filter products and projects."""
    for exp in data.get("experiences", []):
        # Filter products
        original_products = exp.get("products", [])
        filtered_products = []
        for p in original_products:
            canonical = normalize_product(p)
            if canonical and canonical not in filtered_products:
                filtered_products.append(canonical)
        exp["products"] = filtered_products
        
        # Filter client projects
        valid_projects = []
        for project in exp.get("client_projects", []):
            client_name = project.get("project_end_client_name", "")
            
            if not isinstance(client_name, str):
                continue
            
            if any(vendor in client_name.lower() for vendor in KNOWN_VENDOR_NAMES):
                continue
            
            if "coe" in client_name.lower():
                continue
            
            project["project_end_client_name"] = normalize_company_name(client_name)
            
            # Filter project products
            project_products = []
            for p in project.get("products", []):
                canonical = normalize_product(p)
                if canonical and canonical not in project_products:
                    project_products.append(canonical)
            project["products"] = project_products
            
            valid_projects.append(project)
        
        exp["client_projects"] = valid_projects
    
    return data


def compute_companies_summary(data: dict) -> dict:
    """Compute companies summary."""
    vendors = set()
    clients = set()
    
    for exp in data.get("experiences", []):
        if exp.get("vendor_consulting_firm"):
            vendor_name = normalize_company_name(exp["vendor_consulting_firm"])
            vendors.add(vendor_name)
        
        if exp.get("company_name"):
            company_name = normalize_company_name(exp["company_name"])
            if is_vendor_name(company_name):
                vendors.add(company_name)
            else:
                clients.add(company_name)
        
        for project in exp.get("client_projects", []):
            if project.get("project_end_client_name"):
                clients.add(normalize_company_name(project["project_end_client_name"]))
            if project.get("via_vendor"):
                vendors.add(normalize_company_name(project["via_vendor"]))
    
    clients -= vendors
    
    data["companies_summary"] = {
        "vendors": sorted(list(vendors)),
        "clients": sorted(list(clients))
    }
    
    logger.info("companies_summary_computed", vendors=len(vendors), clients=len(clients))
    
    return data


def compute_industry_summary(data: dict) -> dict:
    """Aggregate all industries."""
    industries = set()
    for exp in data.get("experiences", []):
        industry = exp.get("company_industry")
        if industry and isinstance(industry, str) and industry not in ["Unknown", "?"]:
            industries.add(industry)
        for proj in exp.get("client_projects", []):
            proj_industry = proj.get("project_client_industry")
            if proj_industry and isinstance(proj_industry, str) and proj_industry not in ["Unknown", "?"]:
                industries.add(proj_industry)
    
    data["industry_summary"] = sorted(list(industries))
    logger.info("industry_summary_computed", industries=data["industry_summary"])
    return data


def compute_industry_experience(data: dict) -> dict:
    """Calculate years and clients per industry."""
    industry_data = defaultdict(lambda: {"years": 0, "clients": set()})
    current_year = datetime.utcnow().year
    
    for exp in data.get("experiences", []):
        industry = exp.get("company_industry")
        if industry and isinstance(industry, str) and industry not in ["Unknown", "?"]:
            start = exp.get("job_start_date")
            end = exp.get("job_end_date")
            if start:
                try:
                    start_year = int(str(start)[:4])
                    if end and end != "Present":
                        end_year = int(str(end)[:4])
                    else:
                        end_year = current_year
                    years = end_year - start_year
                    industry_data[industry]["years"] += years
                except:
                    pass
            
            client = exp.get("company_name")
            if client and isinstance(client, str):
                industry_data[industry]["clients"].add(client)
        
        for proj in exp.get("client_projects", []):
            proj_industry = proj.get("project_client_industry")
            if proj_industry and isinstance(proj_industry, str) and proj_industry not in ["Unknown", "?"]:
                client = proj.get("project_end_client_name")
                if client and isinstance(client, str):
                    industry_data[proj_industry]["clients"].add(client)
    
    result = {}
    for industry, stats in industry_data.items():
        result[industry] = {
            "years": stats["years"],
            "clients": len(stats["clients"])
        }
    
    data["industry_experience"] = result
    logger.info("industry_experience_computed", metrics=result)
    return data


def compute_product_experience(data: dict) -> dict:
    """Calculate years and clients per product."""
    product_data = defaultdict(lambda: {"years": 0, "clients": set()})
    current_year = datetime.utcnow().year
    
    for exp in data.get("experiences", []):
        products = exp.get("products", [])
        if products:
            start = exp.get("job_start_date")
            end = exp.get("job_end_date")
            years = 0
            if start:
                try:
                    start_year = int(str(start)[:4])
                    if end and end != "Present":
                        end_year = int(str(end)[:4])
                    else:
                        end_year = current_year
                    years = end_year - start_year
                except:
                    pass
            
            client = exp.get("company_name")
            
            for product in products:
                if isinstance(product, str):
                    if years > 0:
                        product_data[product]["years"] += years
                    if client and isinstance(client, str):
                        product_data[product]["clients"].add(client)
        
        for proj in exp.get("client_projects", []):
            proj_products = proj.get("products", [])
            client = proj.get("project_end_client_name")
            if proj_products and client and isinstance(client, str):
                for product in proj_products:
                    if isinstance(product, str):
                        product_data[product]["clients"].add(client)
    
    result = {}
    for product, stats in product_data.items():
        result[product] = {
            "years": stats["years"],
            "clients": len(stats["clients"])
        }
    
    data["product_experience"] = result
    logger.info("product_experience_computed", metrics=result)
    return data


def sanitize_location(location: str) -> str | None:
    """Sanitize location."""
    if not location or not isinstance(location, str):
        return None
    
    location_lower = location.lower().strip()
    
    invalid_phrases = [
        'extract from', 'resume', 'header', 'city, state', 'if present', 'n/a'
    ]
    if any(phrase in location_lower for phrase in invalid_phrases):
        return None
    
    tech_terms = ['amazon', 'twilio', 'salesforce', 'cloud']
    if any(term in location_lower for term in tech_terms):
        return None
    
    return location


def expand_certifications(certifications: List[str]) -> List[str]:
    """Expand certifications."""
    expanded = []
    for cert in certifications:
        if not isinstance(cert, str):
            continue
        cert_lower = cert.lower()
        if "platform developer ii" in cert_lower and "salesforce" not in cert_lower:
            expanded.append("Salesforce Certified Platform Developer II")
        else:
            expanded.append(cert)
    return expanded


def split_certifications_and_awards(certifications: List[str]) -> tuple:
    """Split certifications."""
    sfdc_certs = []
    non_sfdc_certs = []
    awards = []
    
    awards_keywords = ["mvp", "speaker", "ambassador"]
    
    for cert in certifications:
        if not isinstance(cert, str):
            continue
        cert_lower = cert.lower()
        
        if any(kw in cert_lower for kw in awards_keywords):
            awards.append(cert)
        elif "salesforce certified" in cert_lower:
            sfdc_certs.append(cert)
        else:
            non_sfdc_certs.append(cert)
    
    return sfdc_certs, non_sfdc_certs, awards


def apply_normalization_rules(data: Dict) -> Dict:
    """Apply all normalization rules. CRITICAL: Timezone extraction ENABLED."""
    
    # Sanitize location
    if data.get("candidate_location"):
        data["candidate_location"] = sanitize_location(data["candidate_location"])
    
    # CRITICAL: Extract timezone from location
    if data.get("candidate_location"):
        timezone_info = extract_timezone_from_location(data["candidate_location"])
        if timezone_info:
            data["timezone_info"] = timezone_info
            logger.info("timezone_extracted", info=timezone_info)
    
    # Expand certifications
    if data.get("certifications"):
        data["certifications"] = expand_certifications(data["certifications"])
    
    # Split certifications
    if data.get("certifications"):
        sfdc, non_sfdc, awards = split_certifications_and_awards(data["certifications"])
        data["sfdc_certifications"] = sfdc
        if not data.get("non_sfdc_certifications"):
            data["non_sfdc_certifications"] = non_sfdc
        if awards:
            data["awards_community"] = awards
        data["certifications"] = sfdc
    
    # Calculate years
    if data.get("it_earliest_year"):
        data["it_total_years_experience"] = calculate_it_total_years(data["it_earliest_year"])
    
    if data.get("sfdc_earliest_year"):
        data["sfdc_years"] = calculate_sfdc_years(data["sfdc_earliest_year"])
    
    # Process experiences
    for exp in data.get("experiences", []):
        exp = set_company_is_sfdc_client(exp)
    
    # Apply transformations
    data = classify_and_filter(data)
    data = reclassify_vendors_to_correct_field(data)
    data = populate_company_industries(data)
    data = backfill_project_via_vendor(data)
    
    # Compute summaries
    data = compute_industry_summary(data)
    data = compute_industry_experience(data)
    data = compute_product_experience(data)
    data = compute_companies_summary(data)
    
    return data

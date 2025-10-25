"""
POST-PARSE rules with ALL Excel field calculations.
"""

from typing import Dict, List
import re
from datetime import datetime
from app.utils.logger import get_logger

logger = get_logger(__name__)


KNOWN_VENDOR_NAMES = {
    "accenture", "deloitte", "capgemini", "cognizant", "infosys", "wipro", 
    "tcs", "tata consultancy", "hcl", "tech mahindra",
    "ntt data", "ntt data, inc", "nttdata",
    "ewave", "ewave do brazil", "ewave do brazil informática",
    "dvlpr", "dvlpr-br", "dvlpr br",
    "osf digital", "osf global", "osf global services", "cloudnerd", "cloud nerd", 
    "genisis", "genisis technology", "genisis technology solutions", "relevantz", 
    "guerratech", "guerra tech",
    "teksystems", "tek systems", "v-soft", "vsoft", "v-soft consulting",
    "zensar", "zensar technologies", "quinnox", "fortech",
    "kcsit", "machinas", "machinas ecommerce", "soitron", "wunderman", 
    "wunderman thompson", "wunderman thompson commerce", "globant",
    "sysmap", "sysmap solutions",
    "consulting", "consultancy", "staffing", "solutions inc",
    "technology solutions", "tech solutions", "informática"
}

VENDOR_INDICATORS = [
    "consulting", "consultancy", "staffing", "solutions", "services",
    "technologies", "technology", "tech", "global services"
]

SALESFORCE_PRODUCTS_CANONICAL = {
    "Sales Cloud", "Service Cloud", "Experience Cloud", "Marketing Cloud",
    "Commerce Cloud", "CPQ",
    "Financial Services Cloud", "Health Cloud", "Communications Cloud",
    "Energy Cloud", "Media Cloud", "Automotive Cloud", 
    "Education Cloud", "Nonprofit Cloud", "Manufacturing Cloud",
    "Consumer Goods Cloud", "Public Sector Cloud",
    "Data Cloud", "Tableau CRM", "Revenue Cloud",
    "Field Service", "Industries Cloud", 
    "Marketing Cloud Account Engagement"
}

PRODUCT_ALIASES = {
    "sales cloud": "Sales Cloud",
    "service cloud": "Service Cloud",
    "cpq": "CPQ",
    "salesforce cpq": "CPQ",
    "marketing cloud": "Marketing Cloud",
    "sfmc": "Marketing Cloud",
    "experience cloud": "Experience Cloud",
    "communities": "Experience Cloud",
    "community": "Experience Cloud",
    "community cloud": "Experience Cloud",
    "commerce cloud": "Commerce Cloud",
    "b2b commerce": "Commerce Cloud",
    "b2c commerce": "Commerce Cloud",
    "lightning b2b commerce": "Commerce Cloud",
    "financial services cloud": "Financial Services Cloud",
    "fsc": "Financial Services Cloud",
    "health cloud": "Health Cloud",
    "communications cloud": "Communications Cloud",
    "communication cloud": "Communications Cloud",
    "energy cloud": "Energy Cloud",
    "media cloud": "Media Cloud",
    "automotive cloud": "Automotive Cloud",
    "education cloud": "Education Cloud",
    "nonprofit cloud": "Nonprofit Cloud",
    "manufacturing cloud": "Manufacturing Cloud",
    "consumer goods cloud": "Consumer Goods Cloud",
    "public sector cloud": "Public Sector Cloud",
    "data cloud": "Data Cloud",
    "revenue cloud": "Revenue Cloud",
    "tableau crm": "Tableau CRM",
    "wave analytics": "Tableau CRM",
    "einstein analytics": "Tableau CRM",
    "field service": "Field Service",
    "field service lightning": "Field Service",
    "industries cloud": "Industries Cloud",
    "vlocity": "Industries Cloud",
    "pardot": "Marketing Cloud Account Engagement",
    "marketing cloud account engagement": "Marketing Cloud Account Engagement"
}


def is_vendor_name(company_name: str) -> bool:
    """Enhanced vendor detection."""
    if not company_name:
        return False
    
    name_lower = company_name.lower().strip()
    
    if name_lower in KNOWN_VENDOR_NAMES:
        logger.info("vendor_detected_exact_match", company=company_name)
        return True
    
    for vendor in KNOWN_VENDOR_NAMES:
        if vendor in name_lower or name_lower in vendor:
            logger.info("vendor_detected_partial_match", company=company_name, matched_vendor=vendor)
            return True
    
    for indicator in VENDOR_INDICATORS:
        if indicator in name_lower:
            logger.info("vendor_detected_keyword", company=company_name, keyword=indicator)
            return True
    
    return False


def normalize_company_name(name: str) -> str:
    """Normalize company names."""
    if not name:
        return name
    
    normalizations = {
        "teksystems": "TEKsystems",
        "tek systems": "TEKsystems",
        "v-soft consulting": "V-Soft Consulting",
        "vsoft": "V-Soft Consulting",
        "osf digital": "OSF Digital",
        "osf global": "OSF Global Services",
        "osf global services": "OSF Global Services",
        "zensar technologies": "Zensar Technologies",
        "cloudnerd": "CloudNerd",
        "cloud nerd": "CloudNerd",
        "cognizant": "Cognizant",
        "genisis": "Genisis Technology Solutions",
        "genisis technology solutions": "Genisis Technology Solutions",
        "globant": "Globant",
        "sysmap solutions": "SysMap Solutions",
        "wunderman thompson commerce": "Wunderman Thompson Commerce",
        "t.rowe price": "T. Rowe Price",
        "t rowe price": "T. Rowe Price",
        "ford motors": "Ford Motor Company",
        "ford motor company": "Ford Motor Company",
        "ypo, inc": "YPO, Inc",
        "te connectivity": "TE Connectivity",
        "coca-cola": "Coca-Cola Enterprises",
        "coca-cola enterprises": "Coca-Cola Enterprises"
    }
    
    name_lower = name.lower().strip()
    if name_lower in normalizations:
        return normalizations[name_lower]
    
    name = re.sub(r'\s*\([^)]+\)\s*$', '', name)
    
    return name.title().strip()


def normalize_product(product: str) -> str | None:
    """Normalize product."""
    if not product:
        return None
    
    product_lower = product.lower().strip()
    product_lower = re.sub(r'^salesforce\s+', '', product_lower)
    
    if product_lower in PRODUCT_ALIASES:
        canonical = PRODUCT_ALIASES[product_lower]
        return canonical if canonical in SALESFORCE_PRODUCTS_CANONICAL else None
    
    tool_keywords = [
        "copado", "flosum", "gearset", "mulesoft", "aws", "azure", 
        "dataloader", "informatica", "jitterbit", "genesys", "marketo",
        "adobe", "sap", "oracle", "advantage crm", "dynamics",
        "own backup", "ownbackup", "ant migration"
    ]
    if any(tool in product_lower for tool in tool_keywords):
        return None
    
    return None


def calculate_it_total_years(it_earliest_year: str) -> int:
    """Calculate total IT years from earliest IT year."""
    if not it_earliest_year:
        return 0
    try:
        year = int(str(it_earliest_year)[:4])
        current_year = datetime.utcnow().year
        years = current_year - year
        return max(0, min(50, years))
    except:
        return 0


def set_company_is_sfdc_client(exp: dict) -> dict:
    """Set TRUE if Salesforce usage confirmed."""
    indicators = [
        bool(exp.get("products")),
        "salesforce" in exp.get("job_title", "").lower(),
        "sfdc" in exp.get("job_title", "").lower(),
    ]
    exp["company_is_sfdc_client"] = "TRUE" if any(indicators) else "FALSE"
    return exp


def derive_sfdc_role_level(job_title: str) -> str:
    """Infer seniority from job title."""
    if not job_title:
        return None
    
    title_lower = job_title.lower()
    
    if any(x in title_lower for x in ["architect", "principal", "distinguished"]):
        return "Architect"
    elif any(x in title_lower for x in ["director", "vp", "head of"]):
        return "Director"
    elif any(x in title_lower for x in ["manager", "lead", "team lead"]):
        return "Manager/Lead"
    elif any(x in title_lower for x in ["senior", "sr.", "staff"]):
        return "Senior"
    elif any(x in title_lower for x in ["junior", "jr.", "associate", "entry"]):
        return "Junior"
    else:
        return "Mid-Level"


def generate_sfdc_role_description(exp: dict) -> str:
    """Generate role description without client name."""
    job_title = exp.get("job_title", "")
    products = exp.get("products", [])
    company_industry = exp.get("company_industry", "")
    
    if not job_title:
        return None
    
    industry_desc = f"an {company_industry} organization" if company_industry else "an enterprise client"
    
    if products:
        products_str = ", ".join(products[:3])
        return f"{job_title} implementing {products_str} solutions for {industry_desc}."
    else:
        return f"{job_title} providing Salesforce consulting services for {industry_desc}."


def derive_company_industry(company_name: str) -> str:
    """Derive industry from company name."""
    if not company_name:
        return None
    
    name_lower = company_name.lower().strip()
    
    industries = {
        "bank": "Banking/Financial Services",
        "deutsche bank": "Banking/Financial Services",
        "questrade": "Financial Services/Investment",
        "exxonmobil": "Energy/Oil & Gas",
        "eletrobras": "Energy/Utilities",
        "claro": "Telecommunications",
        "telecommunication": "Telecommunications",
        "toyota": "Automotive/Manufacturing",
        "hapag": "Shipping/Logistics",
        "lloyd": "Shipping/Logistics",
        "in all media": "Media/Entertainment",
        "grupo rbs": "Media/Broadcasting",
        "euroconsumers": "Consumer Advocacy/Non-Profit",
        "idb": "International Development/NGO",
        "bid": "International Development/NGO",
        "inter-american": "International Development/NGO",
        "atile": "Branding/Marketing Services",
        "carabiner": "Business Consulting",
    }
    
    for keyword, industry in industries.items():
        if keyword in name_lower:
            return industry
    
    return None


def reclassify_vendors_to_correct_field(data: dict) -> dict:
    """Move vendor companies from company_name to vendor_consulting_firm."""
    for exp in data.get("experiences", []):
        company_name = exp.get("company_name")
        
        if company_name and is_vendor_name(company_name):
            normalized = normalize_company_name(company_name)
            exp["vendor_consulting_firm"] = normalized
            exp["company_name"] = None
            logger.info("vendor_moved_to_correct_field", vendor=normalized)
    
    return data


def populate_company_industries(data: dict) -> dict:
    """Populate company_industry for all experiences."""
    for exp in data.get("experiences", []):
        company = exp.get("company_name")
        if company and not exp.get("company_industry"):
            exp["company_industry"] = derive_company_industry(company)
    
    return data


def backfill_project_via_vendor(data: dict) -> dict:
    """Backfill via_vendor from parent experience."""
    for exp in data.get("experiences", []):
        vendor = exp.get("vendor_consulting_firm")
        if vendor:
            for proj in exp.get("client_projects", []):
                if not proj.get("via_vendor"):
                    proj["via_vendor"] = vendor
                    logger.info("via_vendor_backfilled", vendor=vendor)
    return data


def derive_project_industries(data: dict) -> dict:
    """Derive industries for project clients."""
    for exp in data.get("experiences", []):
        for proj in exp.get("client_projects", []):
            client = proj.get("project_end_client_name")
            if client:
                industry = derive_company_industry(client)
                if industry:
                    proj["project_client_industry"] = industry
    return data


def classify_and_filter(data: dict) -> dict:
    """Enhanced: Classify companies, filter vendors."""
    
    if "_filtered_vendors" not in data:
        data["_filtered_vendors"] = []
    
    filtered_vendors_this_call = set()
    
    for exp in data.get("experiences", []):
        original_products = exp.get("products", [])
        filtered_products = []
        for p in original_products:
            canonical = normalize_product(p)
            if canonical and canonical not in filtered_products:
                filtered_products.append(canonical)
        exp["products"] = filtered_products
        
        valid_projects = []
        for project in exp.get("client_projects", []):
            client_name = project.get("project_end_client_name", "")
            client_lower = client_name.lower()
            
            if any(vendor in client_lower for vendor in KNOWN_VENDOR_NAMES):
                normalized_vendor = normalize_company_name(client_name)
                filtered_vendors_this_call.add(normalized_vendor)
                logger.warning("vendor_filtered_from_client_projects", 
                              vendor=client_name,
                              experience_company=exp.get("company_name") or exp.get("vendor_consulting_firm"))
                continue
            
            if "coe" in client_lower:
                logger.warning("internal_project_filtered", project=client_name)
                continue
            
            project["project_end_client_name"] = normalize_company_name(client_name)
            
            if project.get("via_vendor"):
                project["via_vendor"] = normalize_company_name(project["via_vendor"])
            
            project_products = []
            for p in project.get("products", []):
                canonical = normalize_product(p)
                if canonical and canonical not in project_products:
                    project_products.append(canonical)
            project["products"] = project_products
            
            valid_projects.append(project)
        
        exp["client_projects"] = valid_projects
    
    data["_filtered_vendors"].extend(list(filtered_vendors_this_call))
    
    logger.info("classify_and_filter_completed", 
               filtered_vendors_count=len(filtered_vendors_this_call),
               filtered_vendors=list(filtered_vendors_this_call),
               total_accumulated=len(data["_filtered_vendors"]))
    
    return data


def compute_companies_summary(data: dict) -> dict:
    """Enhanced: Include ALL accumulated filtered vendors."""
    vendors = set()
    clients = set()
    
    if "_filtered_vendors" in data:
        unique_filtered = set(data["_filtered_vendors"])
        for vendor in unique_filtered:
            vendors.add(vendor)
        logger.info("filtered_vendors_added_to_summary", 
                   count=len(unique_filtered),
                   vendors=sorted(list(unique_filtered)))
        del data["_filtered_vendors"]
    
    for exp in data.get("experiences", []):
        if exp.get("vendor_consulting_firm"):
            vendor_name = normalize_company_name(exp["vendor_consulting_firm"])
            vendors.add(vendor_name)
        
        if exp.get("company_name"):
            company_name = normalize_company_name(exp["company_name"])
            company_lower = company_name.lower()
            
            if any(vendor in company_lower for vendor in KNOWN_VENDOR_NAMES):
                vendors.add(company_name)
                logger.info("company_reclassified_as_vendor", company=company_name)
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
    
    logger.info("companies_summary_computed", 
               vendors=len(vendors), 
               clients=len(clients),
               vendor_names=sorted(list(vendors)),
               client_names=sorted(list(clients)))
    
    return data


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


def expand_certifications(certifications: List[str]) -> List[str]:
    """Expand certification patterns."""
    expanded = []
    
    for cert in certifications:
        cert_lower = cert.lower()
        
        if "architect certifications" in cert_lower and "integration" in cert_lower and ("iam" in cert_lower or "identity" in cert_lower):
            expanded.append("Salesforce Certified Integration Architect")
            expanded.append("Salesforce Certified Identity and Access Management Architect")
            logger.info("cert_expanded", original=cert)
        elif "platform developer ii" in cert_lower and "salesforce" not in cert_lower:
            expanded.append("Salesforce Certified Platform Developer II")
        else:
            expanded.append(cert)
    
    return expanded


def sanitize_location(location: str) -> str | None:
    """Remove placeholder locations."""
    if not location:
        return None
    
    if re.fullmatch(r'\s*(city|town)\s*,\s*(country|nation)\s*', location, re.I):
        logger.warning("location_placeholder_removed", location=location)
        return None
    
    return location


def fill_most_recent_job_title(data: dict) -> dict:
    """Fill most_recent_job_title from first experience."""
    if not data.get("most_recent_job_title") and data.get("experiences"):
        first = next((e for e in data["experiences"] if isinstance(e, dict) and e.get("job_title")), None)
        if first:
            data["most_recent_job_title"] = first["job_title"]
    
    return data


def split_certifications_and_awards(certifications: List[str]) -> tuple:
    """Split certifications."""
    sfdc_certs = []
    non_sfdc_certs = []
    awards = []
    
    awards_keywords = ["mvp", "speaker", "ambassador", "dreamforce", "tdx", "trailhead"]
    
    for cert in certifications:
        cert_lower = cert.lower()
        
        if any(kw in cert_lower for kw in awards_keywords):
            awards.append(cert)
        elif "salesforce certified" in cert_lower:
            sfdc_certs.append(cert)
        else:
            non_sfdc_certs.append(cert)
    
    return sfdc_certs, non_sfdc_certs, awards


def aggregate_and_validate_skills(data: dict) -> dict:
    """Aggregate skills."""
    aggregated = {
        "admin_and_automation": set(),
        "dev_coding": set(),
        "architecture_design": set(),
        "data_management": set(),
        "deployment_devops": set(),
        "integration": set(),
        "marketing_automation": set()
    }
    
    for exp in data.get("experiences", []):
        if not isinstance(exp, dict):
            continue
        
        skills = exp.get("skills", {})
        
        if not isinstance(skills, dict):
            logger.error("skills_not_dict", company=exp.get("company_name"))
            continue
        
        for category, skill_list in skills.items():
            if category in aggregated and isinstance(skill_list, list):
                for skill in skill_list:
                    if isinstance(skill, str) and skill.strip():
                        aggregated[category].add(skill.strip())
    
    total = sum(len(s) for s in aggregated.values())
    
    logger.info(
        "skills_aggregated",
        admin=len(aggregated["admin_and_automation"]),
        dev=len(aggregated["dev_coding"]),
        arch=len(aggregated["architecture_design"]),
        data=len(aggregated["data_management"]),
        devops=len(aggregated["deployment_devops"]),
        integration=len(aggregated["integration"]),
        marketing=len(aggregated["marketing_automation"]),
        total=total
    )
    
    if total == 0:
        logger.error("CRITICAL_NO_SKILLS")
    if total < 10:
        logger.warning("FEW_SKILLS", count=total)
    
    return data


def validate_companies_extraction(data: dict) -> dict:
    """Validate companies."""
    direct = set()
    vendors = set()
    clients = set()
    
    for exp in data.get("experiences", []):
        if not isinstance(exp, dict):
            continue
        
        if exp.get("company_name"):
            direct.add(exp["company_name"])
        if exp.get("vendor_consulting_firm"):
            vendors.add(exp["vendor_consulting_firm"])
        
        for proj in exp.get("client_projects", []):
            if isinstance(proj, dict):
                if proj.get("project_end_client_name"):
                    clients.add(proj["project_end_client_name"])
                if proj.get("via_vendor"):
                    vendors.add(proj["via_vendor"])
    
    total = len(direct) + len(vendors) + len(clients)
    
    logger.info(
        "companies_validation",
        direct=len(direct),
        vendors=len(vendors),
        clients=len(clients),
        total=total
    )
    
    if total == 0:
        logger.error("CRITICAL_NO_COMPANIES")
    if total < 3:
        logger.warning("FEW_COMPANIES", count=total)
    
    return data


def apply_normalization_rules(data: Dict) -> Dict:
    """Apply all normalization rules including NEW fields."""
    
    # Sanitize location
    if data.get("candidate_location"):
        data["candidate_location"] = sanitize_location(data["candidate_location"])
    
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
    
    # Calculate IT years
    if data.get("it_earliest_year"):
        data["it_total_years_experience"] = calculate_it_total_years(data["it_earliest_year"])
        logger.info("it_years_calculated", years=data["it_total_years_experience"])
    
    # Calculate SFDC years
    if data.get("sfdc_earliest_year"):
        data["sfdc_years"] = calculate_sfdc_years(data["sfdc_earliest_year"])
    
    # Fill job title
    data = fill_most_recent_job_title(data)
    
    # Process experiences
    for exp in data.get("experiences", []):
        exp = set_company_is_sfdc_client(exp)
        
        if exp.get("job_title"):
            exp["sfdc_role_level"] = derive_sfdc_role_level(exp["job_title"])
        
        if not exp.get("sfdc_role_description"):
            exp["sfdc_role_description"] = generate_sfdc_role_description(exp)
    
    # NEW: Add these 4 critical functions
    data = classify_and_filter(data)
    data = reclassify_vendors_to_correct_field(data)  # NEW
    data = populate_company_industries(data)  # NEW
    data = backfill_project_via_vendor(data)  # NEW
    data = derive_project_industries(data)  # NEW
    data = compute_companies_summary(data)
    data = aggregate_and_validate_skills(data)
    data = validate_companies_extraction(data)
    
    return data

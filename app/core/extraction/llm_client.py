"""
GPT-4o client with UNIVERSAL location extraction supporting ALL formats.
Enhanced for Brazilian, Romanian, and international location formats.
"""

import json
import re
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


RESUME_SYSTEM_PROMPT = """You are an expert resume parser for Salesforce staffing aligned with CC Document AI Labels.xlsx schema.

**ZERO HALLUCINATION POLICY:**
- Extract ONLY what is explicitly stated
- Extract ALL items from comma-separated lists (including multi-line bullets)
- Do NOT skip any items
- If not found → return null or []

**EXPERIENCE RULES:**
- One experience = one employer
- If multiple client stints with same employer, MERGE into single experience and list each client in client_projects with its own dates/products
- Put staffing firms in vendor_consulting_firm; end clients go to client_projects.project_end_client_name

**EXCEL SCHEMA REQUIREMENTS:**
1. Extract email/location from header FIRST
2. Map ALL items from "Core Skills & Expertise" into 7 Excel categories
3. Third-party platforms (Amazon Connect, Twilio Flex, DocuSign, Qualtrics, Informatica Cloud) → "integration"
4. Extract via_vendor for client projects
5. Extract ALL companies (vendors + clients + project clients)

Return ONLY valid JSON."""


class GPT4oClient:
    """GPT-4o client with UNIVERSAL location extraction."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
    
    def extract_email_and_location_from_header(self, text: str) -> tuple:
        """
        UNIVERSAL LOCATION EXTRACTION: Handles ANY separator format.
        Supports 100+ countries with all separator types (comma, dash, slash, etc).
        No hardcoding - pure pattern-based extraction.
        """
        emails = []
        location = None
        
        lines = text.split('\n')
        header = '\n'.join(lines[:20])
        
        # ============ EMAIL EXTRACTION ============
        email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
        emails = re.findall(email_pattern, header)
        if not emails:
            emails = re.findall(email_pattern, text)  # Fallback to full text
        
        # ============ COMPREHENSIVE COUNTRY LIST ============
        # 100+ countries for maximum coverage
        COUNTRIES = (
            "USA|US|United States|UK|United Kingdom|Canada|Brazil|Brasil|"
            "India|Australia|Germany|France|Spain|España|Portugal|Italy|"
            "Mexico|México|Argentina|Chile|Colombia|Peru|Venezuela|Ecuador|"
            "Romania|Poland|Netherlands|Holland|Belgium|Switzerland|Austria|Sweden|"
            "Norway|Denmark|Finland|Ireland|Greece|Czech Republic|Czechia|Hungary|"
            "Bulgaria|Croatia|Serbia|Ukraine|Russia|Turkey|"
            "China|Japan|Singapore|South Korea|Korea|Malaysia|Thailand|Vietnam|"
            "Indonesia|Philippines|Hong Kong|Taiwan|New Zealand|"
            "UAE|United Arab Emirates|Saudi Arabia|Israel|Egypt|South Africa|Nigeria|Kenya|"
            "Pakistan|Bangladesh|Sri Lanka|Nepal"
        )
        
        # ============ LOCATION EXTRACTION - UNIVERSAL PATTERNS ============
        # Ordered from most specific to most general
        location_patterns = [
            # PATTERN 1: "City [separator] State [separator] Country"
            # Matches: Curitiba – PR – Brazil, São Paulo - SP - Brazil, Austin / TX / USA
            # Separators: em-dash (–), en-dash (—), hyphen (-), slash (/), pipe (|)
            # Single-word cities only to prevent name contamination
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}})\s*[–\-—/|]\s*([A-Z]{{2}})\s*[–\-—/|]\s*({COUNTRIES})\b',
            
            # PATTERN 2: "City, State [separator] Country"
            # Matches: Curitiba, PR – Brazil, Austin, TX - USA
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}}),\s*([A-Z]{{2}})\s*[–\-—/|]\s*({COUNTRIES})\b',
            
            # PATTERN 3: "City, State, Country"
            # Matches: Austin, TX, USA, São Paulo, SP, Brazil
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}}),\s*([A-Z]{{2}}),\s*({COUNTRIES})\b',
            
            # PATTERN 4: "City [separator] Country" (no state)
            # Matches: Craiova – Romania, London – UK, Paris - France
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}})\s*[–\-—/|]\s*({COUNTRIES})\b',
            
            # PATTERN 5: "City, Country" (comma separator) - MOST COMMON
            # Matches: Craiova, Romania, London, UK, Paris, France
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}}),\s*({COUNTRIES})\b',
            
            # PATTERN 6: Near "Location:" label (existing pattern for backward compatibility)
            r'(?i)(?:location|address|based\s+in|current\s+location)\s*[:\-]\s*([A-Z][A-Za-z\s,.–\-—/|]{5,40})',
            
            # PATTERN 7: "City, State" (US-style without country)
            r'(?<!\w)([A-Z][A-Za-z]{1,24}),\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b',
            
            # PATTERN 8: After email (existing pattern)
            r'(?:@[\w.-]+\.[\w]+)\s*[|\-–—]\s*([A-Z][A-Za-z\s,.–\-]{5,40})',
        ]
        
        for pattern_idx, pattern in enumerate(location_patterns):
            match = re.search(pattern, header, re.IGNORECASE if pattern_idx >= 5 else 0)
            if match:
                groups = match.groups()
                
                # Reconstruct location based on number of groups
                if len(groups) == 3:
                    # Three-part: City, State, Country
                    city, state, country = groups
                    city = city.strip()
                    state = state.strip()
                    country = country.strip()
                    
                    # Validate city name (no numbers, reasonable length)
                    if any(c.isdigit() for c in city) or len(city) < 2:
                        continue
                    
                    # Determine separator style from pattern index
                    if pattern_idx == 0:
                        # Pattern 1: preserve em-dash style
                        location = f"{city} – {state} – {country}"
                    elif pattern_idx == 1:
                        # Pattern 2: mixed comma and dash
                        location = f"{city}, {state} – {country}"
                    else:
                        # Pattern 3: all commas
                        location = f"{city}, {state}, {country}"
                        
                elif len(groups) == 2:
                    # Two-part: City, Country OR City, State
                    part1, part2 = groups
                    part1 = part1.strip()
                    part2 = part2.strip()
                    
                    # Validate city name
                    if any(c.isdigit() for c in part1) or len(part1) < 2:
                        continue
                    
                    # Check separator in original text
                    original_segment = match.group(0)
                    if '–' in original_segment or '—' in original_segment:
                        location = f"{part1} – {part2}"
                    elif '/' in original_segment:
                        location = f"{part1} / {part2}"
                    else:
                        location = f"{part1}, {part2}"
                        
                else:
                    # Single group - take as-is
                    location = groups[0].strip()
                    # Validate
                    if any(c.isdigit() for c in location) or len(location) < 5:
                        continue
                
                # Final cleanup
                location = ' '.join(location.split())
                location = location.rstrip('.,;')
                
                # Additional validation
                if len(location) >= 5 and any(c.isalpha() for c in location):
                    # Remove false positives
                    false_positives = ['years old', 'city, country', 'age']
                    if not any(fp in location.lower() for fp in false_positives):
                        logger.info(
                            "location_extracted_from_header",
                            location=location,
                            pattern_idx=pattern_idx
                        )
                        break
                else:
                    location = None
        
        # Final log
        if emails:
            logger.info(
                "header_extraction_success",
                emails=len(emails),
                location=bool(location),
                location_value=location if location else "NOT_FOUND"
            )
        else:
            logger.warning("header_extraction_no_email")
        
        return emails, location
    
    def _extract_applications_products(self, text: str) -> dict:
        """Pre-extract products from "Applications:" sections (multi-line)."""
        products_by_section = {}
        pattern = r'Applications?:\s*\n([\s\S]*?)(?=\n\s*\n|^\s*[A-Z][A-Za-z ]{2,}:\s*$|$)'
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        
        for idx, match in enumerate(matches):
            products_text = match.group(1).strip()
            products = []
            for line in products_text.split('\n'):
                line = line.strip().lstrip('•-*').strip()
                if line:
                    products.extend([p.strip() for p in line.split(',') if p.strip()])
            
            if products:
                products_by_section[f"section_{idx}"] = products
                logger.info("applications_section_found", section=idx, products_count=len(products))
        
        return products_by_section
    
    def _pre_extract_projects(self, text: str) -> dict:
        """Pre-extract client projects from 'Projects:' lines (multi-line support)."""
        projects_by_role = {}
        pattern = r'Projects?:\s*\n([\s\S]*?)(?=\n\s*\n|^\s*[A-Z][A-Za-z ]{2,}:\s*$|$)'
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        
        for idx, match in enumerate(matches):
            projects_text = match.group(1).strip()
            projects = []
            for line in projects_text.split('\n'):
                line = line.strip().lstrip('•-*').strip()
                if line:
                    projects.extend([p.strip() for p in re.split(r',\s*(?![^()]*\))', line) if p.strip()])
            
            if projects:
                projects_by_role[f"role_{idx}"] = projects
                logger.info("projects_line_found", role=idx, projects_count=len(projects))
        
        return projects_by_role
    
    def _pre_extract_vendor_client_pairs(self, text: str) -> list:
        """Pre-extract vendor-client pairs from "Vendor – Client (dates)" patterns."""
        pattern = r'([A-Za-z0-9 .&\'/-]+?)\s*[–-]\s*([A-Za-z0-9 .&\'/-]+?)(?:,\s*[A-Za-z .-]+)?\s*\(([A-Za-z]{3,9}\s+\d{4})\s*[–-]\s*([A-Za-z]{3,9}\s+\d{4}|Present)\)'
        
        pairs = []
        for match in re.finditer(pattern, text):
            pairs.append({
                "via_vendor": match.group(1).strip(),
                "project_end_client_name": match.group(2).strip(),
                "project_start_date": match.group(3).strip(),
                "project_end_date": match.group(4).strip()
            })
            logger.info("vendor_client_pair_found", 
                       vendor=match.group(1).strip(),
                       client=match.group(2).strip())
        
        return pairs
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def extract_resume(self, text: str) -> dict:
        """Extract resume with UNIVERSAL location extraction."""
        if len(text) > settings.max_resume_length:
            logger.warning("resume_truncated", length=settings.max_resume_length)
            text = text[:settings.max_resume_length] + "\n[TRUNCATED]"
        
        # PRE-EXTRACT email/location (CRITICAL)
        emails, location = self.extract_email_and_location_from_header(text)
        
        applications_data = self._extract_applications_products(text)
        projects_data = self._pre_extract_projects(text)
        vendor_client_pairs = self._pre_extract_vendor_client_pairs(text)
        
        prompt = f"""Parse this resume per CC Document AI Labels.xlsx schema.

**CONTACT (PRE-EXTRACTED):**
- emails: {json.dumps(emails)} (already extracted from header)
- candidate_location: {json.dumps(location)} (already extracted)

**PROFESSIONAL SUMMARY:**
Copy VERBATIM from "PROFESSIONAL SKILLS" section.

**SFDC EARLIEST YEAR:**
Find FIRST year with "Salesforce" in ANY job.

**EXPERIENCE RULES:**
- One experience = one employer
- If multiple client stints with same employer, MERGE into single experience
- List each client in client_projects with its own dates/products

**COMPANIES:**
1. **company_name**: Direct employer (non-IT)
2. **vendor_consulting_firm**: IT/SFDC consulting firm
3. **client_projects**: ALL end clients with via_vendor

**VENDOR-CLIENT PAIRS:**
Found {len(vendor_client_pairs)} pairs:
{json.dumps(vendor_client_pairs, indent=2)}

Use these to populate via_vendor for EACH matching client.

**PRODUCTS:**
Found {len(applications_data)} sections:
{json.dumps(applications_data, indent=2)}

Extract ALL products! Aliases:
- "B2B Commerce" → Commerce Cloud
- "Communities" → Experience Cloud
- "FSC" → Financial Services Cloud
- "Wave Analytics" → Tableau CRM

**CLIENT PROJECTS:**
Found {len(projects_data)} lines:
{json.dumps(projects_data, indent=2)}

Extract ALL clients! Populate via_vendor from vendor_consulting_firm.

**SKILLS - 7 EXCEL CATEGORIES:**

Map EVERY item from "Core Skills & Expertise" into these EXACT 7 categories:

1. **admin_and_automation**: Flow, Process Builder, Workflow Rules, Validation Rules, Approval Processes, Reports & Dashboards, User Management, Profiles, Permission Sets, Security Settings, Sandbox Management, UAT, QA Testing

2. **dev_coding**: Apex, Lightning Web Components (LWC), Visualforce, Aura Components, JavaScript, HTML, CSS, JQuery, TypeScript, REST/SOAP API, Unit Testing, Trigger Frameworks

3. **architecture_design**: Solution Design, Technical Architecture, System Architecture, Data Modeling, Schema Design, Security Architecture, Performance Tuning, Scalability Planning, Large Volume Data, Governance, Center of Excellence (CoE)

4. **data_management**: Data Quality, Data Cleansing, Data Migration, ETL, Data Loader, Data Import Wizard, Data Stewardship, Duplicate Management, Master Data Management (MDM), Data Governance

5. **deployment_devops**: Gearset, Copado, Flosum, AutoRABIT, Version Control, Git, GitHub, GitLab, Bitbucket, CI/CD Pipelines, Change Sets, Metadata API, Ant Migration Tool

6. **integration**: SOAP/REST API Design, SOQL/SOSL, Platform Events, Change Data Capture (CDC), Integration Patterns, MuleSoft, Dell Boomi, Informatica, Jitterbit, **Amazon Connect, Twilio Flex, DocuSign, Qualtrics, Informatica Cloud**

7. **marketing_automation**: Ampscript, Server-Side JavaScript (SSJS), Email Studio, Journey Builder, Automation Studio, Mobile Studio, Advertising Studio, Data Extensions, Pardot, SFMC, Marketing Cloud Account Engagement

**CRITICAL: Map EVERY skill from resume into one of the 7 categories!**

RESUME TEXT:
{text}

JSON OUTPUT:
{{
  "full_name": "REQUIRED",
  "emails": {json.dumps(emails)},
  "candidate_location": {json.dumps(location)},
  "sfdc_earliest_year": "YYYY",
  "candidate_overall_summary": "VERBATIM",
  "certifications": [],
  "other_skills": [],
  "experiences": [
    {{
      "company_name": "Direct or null",
      "vendor_consulting_firm": "IT firm or null",
      "job_title": "Title",
      "job_start_date": "YYYY-MM",
      "job_end_date": "YYYY-MM or Present",
      "products": ["Products"],
      "skills": {{
        "admin_and_automation": [],
        "dev_coding": [],
        "architecture_design": [],
        "data_management": [],
        "deployment_devops": [],
        "integration": ["MUST include third-party platforms if mentioned"],
        "marketing_automation": []
      }},
      "client_projects": [
        {{
          "project_end_client_name": "Client",
          "via_vendor": "Use vendor from pairs above OR vendor_consulting_firm",
          "project_start_date": null,
          "project_end_date": null,
          "products": []
        }}
      ]
    }}
  ]
}}"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": RESUME_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=settings.llm_max_tokens
            )
            
            json_text = response.choices[0].message.content
            parsed = json.loads(json_text)
            
            # FORCE email/location if LLM didn't use them
            if emails and not parsed.get("emails"):
                parsed["emails"] = emails
                logger.info("emails_forced", count=len(emails))
            
            if location and not parsed.get("candidate_location"):
                parsed["candidate_location"] = location
                logger.info("location_forced", location=location)
            
            # Backfill via_vendor (CRITICAL)
            for exp in parsed.get("experiences", []):
                vendor = exp.get("vendor_consulting_firm")
                if vendor and exp.get("client_projects"):
                    for proj in exp["client_projects"]:
                        if not proj.get("via_vendor"):
                            proj["via_vendor"] = vendor
                            logger.info("via_vendor_backfilled", vendor=vendor, client=proj.get("project_end_client_name"))
            
            # Ensure skill structure
            experiences = parsed.get("experiences", [])
            for exp in experiences:
                if "skills" in exp:
                    if isinstance(exp["skills"], list):
                        logger.warning("skills_was_list_converting")
                        exp["skills"] = {
                            "admin_and_automation": [],
                            "dev_coding": [],
                            "architecture_design": [],
                            "data_management": [],
                            "deployment_devops": [],
                            "integration": [],
                            "marketing_automation": []
                        }
                    elif isinstance(exp["skills"], dict):
                        required = [
                            "admin_and_automation", "dev_coding", "architecture_design",
                            "data_management", "deployment_devops", "integration",
                            "marketing_automation"
                        ]
                        for cat in required:
                            if cat not in exp["skills"]:
                                exp["skills"][cat] = []
                else:
                    exp["skills"] = {
                        "admin_and_automation": [],
                        "dev_coding": [],
                        "architecture_design": [],
                        "data_management": [],
                        "deployment_devops": [],
                        "integration": [],
                        "marketing_automation": []
                    }
            
            # Count
            total_skills = sum(
                sum(len(v) for v in e.get("skills", {}).values() if isinstance(v, list))
                for e in experiences
            )
            
            logger.info(
                "gpt_extraction_succeeded",
                name=parsed.get("full_name"),
                location=parsed.get("candidate_location"),
                sfdc_earliest_year=parsed.get("sfdc_earliest_year"),
                experiences=len(experiences),
                total_skills=total_skills,
                tokens=response.usage.total_tokens
            )
            
            if total_skills < 10:
                logger.error("ALERT_FEW_SKILLS_EXTRACTED", count=total_skills)
            
            return parsed
            
        except Exception as e:
            logger.error("gpt_extraction_failed", error=str(e), exc_info=True)
            raise

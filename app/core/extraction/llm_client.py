# app/core/extraction/llm_client.py - FINAL WORKING VERSION

"""
GPT-4o client with COMPLETE field extraction matching Excel schema.
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
- Extract ALL items from comma-separated lists
- Do NOT skip any items
- If not found → return null or []

**CRITICAL: EXTRACT ALL MANDATORY FIELDS**
You MUST extract these fields for EVERY resume:
1. education (ALL post-secondary degrees)
2. languages_spoken (ALL languages)
3. leadership_skills (ALL leadership phrases)
4. it_earliest_year (REQUIRED - earliest IT job start)
5. sfdc_earliest_year (REQUIRED - earliest SFDC job start)

Return ONLY valid JSON."""


class GPT4oClient:
    """GPT-4o client with COMPLETE extraction."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
    
    def extract_email_and_location_from_header(self, text: str) -> tuple:
        """UNIVERSAL LOCATION EXTRACTION."""
        emails = []
        location = None
        
        lines = text.split('\n')
        header = '\n'.join(lines[:20])
        
        # EMAIL EXTRACTION
        email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
        emails = re.findall(email_pattern, header)
        if not emails:
            emails = re.findall(email_pattern, text)
        
        # COMPREHENSIVE COUNTRY LIST
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
        
        # LOCATION EXTRACTION PATTERNS
        location_patterns = [
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}})\s*[–\-—/|]\s*([A-Z]{{2}})\s*[–\-—/|]\s*({COUNTRIES})\b',
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}}),\s*([A-Z]{{2}})\s*[–\-—/|]\s*({COUNTRIES})\b',
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}}),\s*([A-Z]{{2}}),\s*({COUNTRIES})\b',
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}})\s*[–\-—/|]\s*({COUNTRIES})\b',
            rf'(?<!\w)([A-Z][A-Za-z]{{1,24}}),\s*({COUNTRIES})\b',
            r'(?i)(?:location|address|based\s+in|current\s+location)\s*[:\-]\s*([A-Z][A-Za-z\s,.–\-—/|]{5,40})',
            r'(?<!\w)([A-Z][A-Za-z]{1,24}),\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b',
            r'(?:@[\w.-]+\.[\w]+)\s*[|\-–—]\s*([A-Z][A-Za-z\s,.–\-]{5,40})',
        ]
        
        for pattern_idx, pattern in enumerate(location_patterns):
            match = re.search(pattern, header, re.IGNORECASE if pattern_idx >= 5 else 0)
            if match:
                groups = match.groups()
                
                if len(groups) == 3:
                    city, state, country = groups
                    city = city.strip()
                    state = state.strip()
                    country = country.strip()
                    
                    if any(c.isdigit() for c in city) or len(city) < 2:
                        continue
                    
                    if pattern_idx == 0:
                        location = f"{city} – {state} – {country}"
                    elif pattern_idx == 1:
                        location = f"{city}, {state} – {country}"
                    else:
                        location = f"{city}, {state}, {country}"
                        
                elif len(groups) == 2:
                    part1, part2 = groups
                    part1 = part1.strip()
                    part2 = part2.strip()
                    
                    if any(c.isdigit() for c in part1) or len(part1) < 2:
                        continue
                    
                    original_segment = match.group(0)
                    if '–' in original_segment or '—' in original_segment:
                        location = f"{part1} – {part2}"
                    elif '/' in original_segment:
                        location = f"{part1} / {part2}"
                    else:
                        location = f"{part1}, {part2}"
                        
                else:
                    location = groups[0].strip()
                    if any(c.isdigit() for c in location) or len(location) < 5:
                        continue
                
                location = ' '.join(location.split())
                location = location.rstrip('.,;')
                
                if len(location) >= 5 and any(c.isalpha() for c in location):
                    false_positives = ['years old', 'city, country', 'age']
                    if not any(fp in location.lower() for fp in false_positives):
                        logger.info("location_extracted_from_header", location=location, pattern_idx=pattern_idx)
                        break
                else:
                    location = None
        
        if emails:
            logger.info("header_extraction_success", emails=len(emails), location=bool(location), location_value=location if location else "NOT_FOUND")
        else:
            logger.warning("header_extraction_no_email")
        
        return emails, location
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def extract_resume(self, text: str) -> dict:
        """Extract resume with ALL Excel fields."""
        if len(text) > settings.max_resume_length:
            logger.warning("resume_truncated", length=settings.max_resume_length)
            text = text[:settings.max_resume_length] + "\n[TRUNCATED]"
        
        emails, location = self.extract_email_and_location_from_header(text)
        
        # ============ CRITICAL: COMPLETE EXTRACTION PROMPT ============
        prompt = f"""Parse this resume per CC Document AI Labels.xlsx schema.

**CONTACT (PRE-EXTRACTED):**
- emails: {json.dumps(emails)}
- candidate_location: {json.dumps(location)}

**MANDATORY EXTRACTIONS (DO NOT SKIP):**

1. **education** (CRITICAL - MUST EXTRACT):
Extract ALL post-secondary degrees (Bachelor's and above):
{{
  "degree": "B.A. Graduation in International Relationship",
  "institution_name": "University Tuiuti",
  "is_degree_completed": "Completed",
  "graduation_year": "2001"
}}

Look for "Education", "Academic Background", "Qualifications" sections.

2. **languages_spoken** (MUST EXTRACT ALL):
Extract ONLY language names (e.g., "English", "Portuguese"):
- Remove proficiency: "English (Fluent)" → "English"
- Look for: "Languages:", "Fluent in:", "Idiomas:"

3. **leadership_skills** (MUST EXTRACT ALL):
Extract ALL phrases showing:
- "Led team of X"
- "Mentored X developers"
- "Managed budget"
- "Guiding the team"

4. **it_earliest_year** (REQUIRED):
Find EARLIEST start date across ALL IT jobs.
Return YYYY format.

5. **sfdc_earliest_year** (REQUIRED):
Find EARLIEST start date where "Salesforce" or "SFDC" mentioned.
Return YYYY format.

6. **CRITICAL: candidate_overall_summary RULES:**
- EXACTLY 2-3 sentences
- THIRD PERSON ONLY: "This candidate has..." NOT "I have..."
- NO personal pronouns: Remove "I", "my", "me"
- NO client/company names
- Synthesize: SFDC start year + recent title + products + certs
- Example: "This candidate is a highly certified Salesforce professional with 12 years of experience specializing in Sales Cloud, Service Cloud, and CPQ. They hold 25 Salesforce certifications including multiple architect credentials."

**═══════════════════════════════════════════════════════════════**
**CRITICAL: CLIENT PROJECTS EXTRACTION FROM COMMA-SEPARATED LISTS**
**═══════════════════════════════════════════════════════════════**

When you see text like:
"Projects: Euroconsumers (Portugal), KCSIT (Portugal), Cognizant (England), Hapag-Lloyd (England), Deutsche Bank (Germany)"

You MUST extract EVERY item as a SEPARATE client project:

{{
  "client_projects": [
    {{
      "project_end_client_name": "Euroconsumers",
      "project_scope_summary": "Led Salesforce implementation"
    }},
    {{
      "project_end_client_name": "KCSIT",
      "project_scope_summary": "Led Salesforce implementation"
    }},
    {{
      "project_end_client_name": "Cognizant",
      "project_scope_summary": "Led Salesforce implementation"
    }},
    {{
      "project_end_client_name": "Hapag-Lloyd",
      "project_scope_summary": "Led Salesforce implementation"
    }},
    {{
      "project_end_client_name": "Deutsche Bank",
      "project_scope_summary": "Led Salesforce implementation"
    }}
  ]
}}

**DO NOT skip any items in comma-separated lists!**

**═══════════════════════════════════════════════════════════════**
**CRITICAL: COMPREHENSIVE SKILLS EXTRACTION FROM JOB DESCRIPTIONS**
**═══════════════════════════════════════════════════════════════**

For EACH work experience, you MUST:

1. **READ EVERY SENTENCE** in the "Main activities:" section
2. **READ EVERY ITEM** in the "Applications:" section  
3. **EXTRACT EVERY SKILL MENTIONED** using the parsing rules below

**HOW TO PARSE NARRATIVE TEXT INTO SKILLS:**

Read each sentence and extract based on these patterns:

**ADMINISTRATIVE ACTIONS → admin_and_automation:**
- "Created validation rules" → ["Validation Rules"]
- "Built approval processes" → ["Approval Processes"]
- "Configured profiles and permission sets" → ["Profiles", "Permission Sets"]
- "Developed reports and dashboards" → ["Reports", "Dashboards"]
- "Implemented workflow rules" → ["Workflow Rules"]
- "Created queues and public groups" → ["Queues", "Public Groups"]
- "Designed email templates" → ["Email Templates"]
- "Configured custom settings" → ["Custom Settings"]
- "Set up record types" → ["Record Types"]
- "Built page layouts" → ["Page Layouts"]
- "Configured sharing settings" → ["Sharing Settings"]
- "Managed user access" → ["User Management"]
- "Created flows" → ["Flow"]
- "Built process builder" → ["Process Builder"]

**DEVELOPMENT ACTIONS → dev_coding:**
- "Developed Apex classes" → ["Apex", "Apex Classes"]
- "Created Apex triggers" → ["Apex Triggers"]
- "Built Lightning Web Components" → ["LWC", "Lightning Web Components"]
- "Developed Visualforce pages" → ["Visualforce"]
- "Created Aura components" → ["Aura Components"]
- "Wrote test classes" → ["Test Classes", "Unit Testing"]
- "Developed controllers" → ["Controllers"]
- "Implemented batch Apex" → ["Batch Apex"]
- "Used SOQL queries" → ["SOQL"]
- "Wrote JavaScript" → ["JavaScript"]
- "Developed REST API" → ["REST API"]
- "Implemented SOAP API" → ["SOAP API"]
- "Created Apex REST services" → ["REST API", "Apex"]
- "Developed platform events" → ["Platform Events"]
- "Used SOSL" → ["SOSL"]
- "Wrote scheduled Apex" → ["Scheduled Apex"]
- "Implemented queueable Apex" → ["Queueable Apex"]

**ARCHITECTURE ACTIONS → architecture_design:**
- "Led solution design" → ["Solution Design"]
- "Defined technical architecture" → ["Technical Architecture"]
- "Implemented security models" → ["Security Models"]
- "Conducted code reviews" → ["Code Reviews"]
- "Established best practices" → ["Best Practices"]
- "Designed scalable solutions" → ["Scalability"]
- "Implemented governance" → ["Governance"]
- "Built Center of Excellence" → ["CoE"]
- "Created design patterns" → ["Design Patterns"]
- "Managed technical debt" → ["Technical Debt Management"]
- "Performed architecture reviews" → ["Solution Reviews", "Architecture Reviews"]
- "Designed data models" → ["Data Modeling"]
- "Implemented security architecture" → ["Security Architecture"]
- "Optimized performance" → ["Performance Tuning"]
- "Established enterprise architecture" → ["Enterprise Architecture"]
- "Implemented sharing rules" → ["Sharing Rules"]

**DATA ACTIONS → data_management:**
- "Created custom objects" → ["Custom Objects"]
- "Established master-detail relationships" → ["Master-Detail Relationships"]
- "Built lookup relationships" → ["Lookup Relationships"]
- "Designed junction objects" → ["Junction Objects"]
- "Performed data migration" → ["Data Migration"]
- "Used Data Loader" → ["Data Loader"]
- "Implemented data quality" → ["Data Quality"]
- "Designed data models" → ["Data Modeling"]
- "Created external objects" → ["External Objects"]
- "Used Schema Builder" → ["Schema Builder"]
- "Performed ETL" → ["ETL"]
- "Implemented data cleansing" → ["Data Cleansing"]
- "Managed data stewardship" → ["Data Stewardship"]
- "Implemented MDM" → ["MDM"]
- "Used big objects" → ["Big Objects"]

**DEVOPS ACTIONS → deployment_devops:**
- "Implemented CI/CD" → ["CI/CD"]
- "Used Copado" → ["Copado"]
- "Configured Flosum" → ["Flosum"]
- "Set up Git" → ["Git"]
- "Used Gearset" → ["Gearset"]
- "Created change sets" → ["Change Sets"]
- "Used Metadata API" → ["Metadata API"]
- "Configured ANT migration" → ["ANT Migration Tool"]
- "Managed releases" → ["Release Management"]
- "Used Salesforce CLI" → ["Salesforce CLI", "SFDX"]
- "Managed sandboxes" → ["Sandboxes"]
- "Used GitHub" → ["GitHub"]
- "Implemented version control" → ["Version Control"]
- "Used Salesforce DX" → ["SFDX"]
- "Configured Own Backup" → ["Own Backup"]
- "Managed packages" → ["Package Development"]

**INTEGRATION ACTIONS → integration:**
- "Integrated with MuleSoft" → ["MuleSoft"]
- "Built REST integrations" → ["REST API"]
- "Implemented SOAP services" → ["SOAP API"]
- "Used Platform Events" → ["Platform Events"]
- "Integrated with SAP" → ["SAP Integration"]
- "Connected to Oracle" → ["Oracle Integration"]
- "Used Informatica" → ["Informatica"]
- "Implemented Jitterbit" → ["Jitterbit"]
- "Created webhooks" → ["Webhooks"]
- "Developed outbound messages" → ["Outbound Messages"]
- "Configured CDC" → ["Change Data Capture"]
- "Used middleware" → ["Middleware"]
- "Implemented API gateway" → ["API Gateway"]
- "Configured remote site settings" → ["Remote Site Settings"]
- "Set up named credentials" → ["Named Credentials"]
- "Created connected apps" → ["Connected Apps"]

**MARKETING ACTIONS → marketing_automation:**
- "Developed Ampscript" → ["Ampscript"]
- "Used Journey Builder" → ["Journey Builder"]
- "Configured Email Studio" → ["Email Studio"]
- "Implemented Pardot" → ["Pardot"]
- "Used Marketing Cloud" → ["SFMC"]
- "Developed SSJS" → ["SSJS"]
- "Used Content Builder" → ["Content Builder"]
- "Configured Automation Studio" → ["Automation Studio"]
- "Implemented Einstein recommendations" → ["Einstein Recommendations"]

**SKILL CATEGORIES WITH FULL KEYWORD LISTS:**

1. **admin_and_automation**: 
Flow, Process Builder, Workflow Rules, Validation Rules, Reports, Dashboards, 
User Management, Profiles, Permission Sets, Approval Processes, Queues, Public Groups,
Email Templates, Custom Settings, Sharing Settings, Roles, Permission Set Groups,
Dynamic Forms, Record Types, Page Layouts, Field-Level Security, Object Security

2. **dev_coding**: 
Apex, LWC (Lightning Web Components), Aura Components, Visualforce, JavaScript,
HTML, CSS, REST API, SOAP API, SOQL, SOSL, Unit Testing, Test Classes,
Apex Triggers, Controllers, Batch Apex, Scheduled Apex, Queueable Apex,
Platform Events, Custom Metadata, Lightning Design System, Apex Classes

3. **architecture_design**: 
Solution Design, Technical Architecture, Data Modeling, Security Architecture,
Performance Tuning, Scalability, Governance, CoE (Center of Excellence),
Enterprise Architecture, Security Models, Sharing Rules, Code Reviews,
Best Practices, Design Patterns, Technical Debt Management, Solution Reviews,
Architecture Reviews

4. **data_management**: 
Data Quality, Data Cleansing, Data Migration, ETL, Data Loader, Data Stewardship,
MDM (Master Data Management), Data Modeling, Custom Objects, Master-Detail Relationships,
Lookup Relationships, Junction Objects, External Objects, Big Objects,
Data Import Wizard, Schema Builder

5. **deployment_devops**: 
Gearset, Copado, Flosum, Git, GitHub, Bitbucket, CI/CD Pipelines, Change Sets,
Metadata API, ANT Migration Tool, Release Management, Version Control,
SFDX (Salesforce DX), Salesforce CLI, Own Backup, Package Development,
Sandboxes, Environment Management

6. **integration**: 
REST API, SOAP API, SOQL, SOSL, Platform Events, Change Data Capture (CDC),
MuleSoft, Informatica, Jitterbit, External Web Services, SAP Integration,
Oracle Integration, Middleware, API Gateway, Webhooks, Outbound Messages,
Remote Site Settings, Named Credentials, Connected Apps

7. **marketing_automation**: 
Ampscript, SSJS (Server-Side JavaScript), Email Studio, Journey Builder,
Pardot, SFMC (Marketing Cloud), Marketing Cloud Account Engagement,
Content Builder, Automation Studio, Einstein Recommendations

**EXTRACTION REQUIREMENTS:**
- For architect roles: MINIMUM 15 skills total across all categories
- For other roles: MINIMUM 8 skills total
- Parse EVERY sentence in "Main activities" section
- Extract EVERY tool from "Applications" section
- Do NOT skip any mentioned technologies

**EXAMPLE EXTRACTION (ExxonMobil System Architect):**

From text: "Developed Apex classes with REST calls to connect to external web services... Created custom objects and established relationships using lookup, master-detail, and junction objects to support complex data models... Led the creation and implementation of the CI/CD process, configuring Flosum and Copado... Worked extensively on Salesforce security models, including Apex-based sharing rules... Developed Salesforce features such as Approval Processes, Queues, Public Groups, Email Templates, and Communities. Configured security at the profile, object, field, and record levels... Integrated with MuleSoft and SAP"

Extract:
{{
  "skills": {{
    "admin_and_automation": [
      "Approval Processes", "Queues", "Public Groups", "Email Templates",
      "Profiles", "Permission Sets", "Field-Level Security", "Sharing Settings",
      "Object Security"
    ],
    "dev_coding": [
      "Apex", "Apex Classes", "REST API", "SOQL", "Test Classes", "Apex Triggers",
      "Controllers", "Unit Testing"
    ],
    "architecture_design": [
      "Security Models", "Sharing Rules", "Security Architecture", "Solution Design",
      "Enterprise Architecture", "Best Practices", "Technical Architecture"
    ],
    "data_management": [
      "Custom Objects", "Master-Detail Relationships", "Lookup Relationships",
      "Junction Objects", "Data Modeling", "Data Migration"
    ],
    "deployment_devops": [
      "CI/CD", "Flosum", "Copado", "Release Management", "Own Backup",
      "Version Control"
    ],
    "integration": [
      "REST API", "MuleSoft", "SAP Integration", "External Web Services",
      "SOAP API"
    ],
    "marketing_automation": []
  }}
}}

RESUME TEXT:
{text}

JSON OUTPUT (ALL FIELDS REQUIRED):
{{
  "full_name": "REQUIRED",
  "emails": {json.dumps(emails)},
  "candidate_location": {json.dumps(location)},
  "resume_header_title": null,
  "it_earliest_year": "YYYY (REQUIRED)",
  "sfdc_earliest_year": "YYYY (REQUIRED)",
  "candidate_overall_summary": "THIRD PERSON, 2-3 sentences",
  "education": [
    {{
      "degree": "EXTRACT ALL",
      "institution_name": "EXTRACT ALL",
      "is_degree_completed": "Completed",
      "graduation_year": "YYYY"
    }}
  ],
  "certifications": ["Salesforce certs only"],
  "non_sfdc_certifications": ["AWS, PMP, etc"],
  "languages_spoken": ["English", "Portuguese", "EXTRACT ALL"],
  "leadership_skills": ["EXTRACT ALL phrases"],
  "other_skills": [],
  "experiences": [
    {{
      "company_name": "Direct client or null",
      "vendor_consulting_firm": "IT firm or null",
      "job_title": "Title",
      "job_start_date": "YYYY-MM",
      "job_end_date": "YYYY-MM or Present",
      "products": ["Products"],
      "sfdc_appexchange_products": ["Apttus CPQ", "PROS CPQ", etc],
      "skills": {{
        "admin_and_automation": ["EXTRACT FROM MAIN ACTIVITIES - READ EVERY SENTENCE"],
        "dev_coding": ["EXTRACT FROM MAIN ACTIVITIES - READ EVERY SENTENCE"],
        "architecture_design": ["EXTRACT FROM MAIN ACTIVITIES - READ EVERY SENTENCE"],
        "data_management": ["EXTRACT FROM MAIN ACTIVITIES - READ EVERY SENTENCE"],
        "deployment_devops": ["EXTRACT FROM MAIN ACTIVITIES - READ EVERY SENTENCE"],
        "integration": ["EXTRACT FROM MAIN ACTIVITIES - READ EVERY SENTENCE"],
        "marketing_automation": ["If applicable"]
      }},
      "client_projects": [
        {{
          "project_end_client_name": "Client",
          "via_vendor": "Vendor if applicable",
          "project_scope_summary": "FULL description with role/responsibilities",
          "products": [],
          "project_sfdc_appexchange_products": ["If any"]
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
            
            # Check for truncation
            if json_text.endswith('...') or not json_text.strip().endswith('}'):
                logger.error("gpt_response_truncated", partial_json=json_text[-200:])
                raise ValueError("GPT response was truncated due to token limit")
            
            parsed = json.loads(json_text)
            
            # Force email/location
            if emails and not parsed.get("emails"):
                parsed["emails"] = emails
            if location and not parsed.get("candidate_location"):
                parsed["candidate_location"] = location
            
            # CRITICAL: Derive it_earliest_year if null
            if not parsed.get("it_earliest_year"):
                min_year = None
                for exp in parsed.get("experiences", []):
                    start_date = exp.get("job_start_date")
                    if start_date:
                        year = int(str(start_date)[:4])
                        if min_year is None or year < min_year:
                            min_year = year
                
                if min_year:
                    parsed["it_earliest_year"] = str(min_year)
                    logger.warning("it_earliest_year_derived", year=min_year)
            
            # CRITICAL: Derive sfdc_earliest_year if null
            if not parsed.get("sfdc_earliest_year"):
                min_year = None
                for exp in parsed.get("experiences", []):
                    start_date = exp.get("job_start_date")
                    if start_date:
                        is_sfdc_job = (
                            "salesforce" in exp.get("job_title", "").lower() or
                            "sfdc" in exp.get("job_title", "").lower() or
                            bool(exp.get("products"))
                        )
                        if is_sfdc_job:
                            year = int(str(start_date)[:4])
                            if min_year is None or year < min_year:
                                min_year = year
                
                if min_year:
                    parsed["sfdc_earliest_year"] = str(min_year)
                    logger.warning("sfdc_earliest_year_derived", year=min_year)
            
            # Backfill via_vendor for ALL projects
            for exp in parsed.get("experiences", []):
                vendor = exp.get("vendor_consulting_firm")
                if vendor and exp.get("client_projects"):
                    for proj in exp["client_projects"]:
                        if not proj.get("via_vendor"):
                            proj["via_vendor"] = vendor
                            logger.info("via_vendor_backfilled", vendor=vendor)
            
            # Ensure skill structure FOR EVERY EXPERIENCE
            experiences = parsed.get("experiences", [])
            for exp_idx, exp in enumerate(experiences):
                if "skills" not in exp or not isinstance(exp["skills"], dict):
                    exp["skills"] = {
                        "admin_and_automation": [],
                        "dev_coding": [],
                        "architecture_design": [],
                        "data_management": [],
                        "deployment_devops": [],
                        "integration": [],
                        "marketing_automation": []
                    }
                else:
                    required = [
                        "admin_and_automation", "dev_coding", "architecture_design",
                        "data_management", "deployment_devops", "integration",
                        "marketing_automation"
                    ]
                    for cat in required:
                        if cat not in exp["skills"]:
                            exp["skills"][cat] = []
                
                # VALIDATE: Log if skills are insufficient
                total_skills = sum(len(v) for v in exp["skills"].values() if isinstance(v, list))
                job_title = exp.get("job_title", "").lower()
                min_expected = 15 if "architect" in job_title else 8
                
                if total_skills < min_expected:
                    logger.error(
                        "INCOMPLETE_SKILLS_EXTRACTION",
                        experience_index=exp_idx,
                        company=exp.get("company_name") or exp.get("vendor_consulting_firm"),
                        title=exp.get("job_title"),
                        extracted_skills=total_skills,
                        expected=min_expected
                    )
            
            logger.info(
                "gpt_extraction_succeeded",
                name=parsed.get("full_name"),
                it_earliest_year=parsed.get("it_earliest_year"),
                sfdc_earliest_year=parsed.get("sfdc_earliest_year"),
                education=len(parsed.get("education", [])),
                languages=len(parsed.get("languages_spoken", [])),
                leadership=len(parsed.get("leadership_skills", [])),
                experiences=len(experiences)
            )
            
            return parsed
            
        except Exception as e:
            logger.error("gpt_extraction_failed", error=str(e), exc_info=True)
            raise

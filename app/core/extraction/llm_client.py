"""
GPT-4o CLIENT - COMPREHENSIVE FIX
Fixes: DOCX name extraction, skills categorization, industry extraction
"""

import json
import re
from typing import Optional, Dict, List, Tuple
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


# COMPREHENSIVE exclusion list for name extraction
EXCLUDE_FROM_NAME = {
    # Skills/Tech terms
    'skills', 'expertise', 'core', 'technical', 'proficient', 'technologies',
    'certifications', 'tools', 'platforms', 'frameworks', 'languages',
    'specialization', 'competencies', 'qualifications',
    
    # Salesforce-specific
    'lightning', 'web', 'components', 'lwc', 'apex', 'visualforce',
    'salesforce', 'sfdc', 'cloud', 'service', 'sales', 'marketing',
    'commerce', 'experience', 'cpq', 'einstein', 'tableau',
    
    # Job titles/roles
    'specialist', 'certified', 'architect', 'developer', 'administrator',
    'consultant', 'manager', 'analyst', 'engineer', 'lead', 'senior',
    'expert', 'professional', 'coordinator', 'associate',
    
    # Resume sections
    'resume', 'curriculum', 'cv', 'summary', 'profile', 'objective',
    'experience', 'education', 'background'
}


RESUME_SYSTEM_PROMPT = """You are an expert resume parser for Salesforce staffing.

**ZERO HALLUCINATION POLICY:**
- Extract ONLY explicitly stated information
- DO NOT infer products from context
- DO NOT add products unless explicitly named

**SALESFORCE JOB RULE:**
A job is Salesforce-related ONLY if:
- Job title contains "Salesforce" or "SFDC", OR
- Products explicitly listed

Return ONLY valid JSON."""


class GPT4oClient:
    """GPT-4o client with all critical fixes."""
    
    def __init__(self):
        try:
            api_key = settings.openai_api_key
            if not api_key or not isinstance(api_key, str):
                raise ValueError("OpenAI API key must be a non-empty string")
            
            self.client = AsyncOpenAI(api_key=api_key)
            self.model = getattr(settings, 'llm_model', 'gpt-4o')
            self.max_tokens = getattr(settings, 'llm_max_tokens', 16000)
            self.max_resume_length = getattr(settings, 'max_resume_length', 50000)
            
            logger.info("gpt4o_client_initialized", model=self.model)
        except Exception as e:
            logger.error("gpt4o_client_initialization_failed", error=str(e))
            raise
    
    def extract_name_from_header(self, text: str) -> Optional[str]:
        """
        Extract candidate name with ULTRA-STRICT filtering for DOCX files.
        
        CRITICAL FIX: Prevent extracting "Lightning Web", "Core Skills", etc.
        """
        lines = text.split('\n')
        
        # Strategy 1: Look for name in first 3 lines ONLY
        for i, line in enumerate(lines[:3]):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Skip lines with contact info
            if '@' in line or re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', line):
                continue
            
            # Skip if line is too long (likely a sentence)
            if len(line) > 50:
                continue
            
            line_lower = line.lower()
            
            # CRITICAL: Skip if contains ANY excluded keywords
            if any(kw in line_lower for kw in EXCLUDE_FROM_NAME):
                logger.info("name_extraction_skipped_keyword", line=line[:50], line_number=i+1)
                continue
            
            # Skip if contains punctuation (bullets, colons, etc.)
            if any(char in line for char in ['•', ':', '|', '–', '—', '*', '►', '■', '-', '/', '\\']):
                logger.info("name_extraction_skipped_punctuation", line=line[:50])
                continue
            
            # Skip if contains "and" or "&"
            if ' and ' in line_lower or ' & ' in line:
                logger.info("name_extraction_skipped_conjunction", line=line[:50])
                continue
            
            # Skip if any word is all caps (likely headers)
            words = line.split()
            if any(w.isupper() and len(w) > 2 for w in words):
                logger.info("name_extraction_skipped_all_caps", line=line[:50])
                continue
            
            # Name should be 2-4 words
            if not (2 <= len(words) <= 4):
                continue
            
            # Each word must start with capital letter
            if not all(w[0].isupper() for w in words if len(w) > 1):
                continue
            
            # Words should be reasonable length (2-15 chars)
            if not all(2 <= len(w) <= 15 for w in words):
                continue
            
            # FINAL CHECK: No word should be in exclusion list
            if any(w.lower() in EXCLUDE_FROM_NAME for w in words):
                logger.warning("name_extraction_skipped_word_in_exclusion", line=line[:50])
                continue
            
            # VALID NAME FOUND
            logger.info("name_extracted_header", name=line, line_number=i+1)
            return line
        
        # Strategy 2: Pattern matching for "Firstname Lastname"
        for i, line in enumerate(lines[:5]):
            # Skip if contains excluded keywords
            if any(kw in line.lower() for kw in EXCLUDE_FROM_NAME):
                continue
            
            match = re.search(r'\b([A-Z][a-z]{1,14})\s+([A-Z][a-z]{1,14})\b', line)
            if match:
                name = match.group(0)
                name_lower = name.lower()
                
                # Validate not in exclusion list
                if not any(term in name_lower for term in EXCLUDE_FROM_NAME):
                    logger.info("name_extracted_pattern", name=name, line_number=i+1)
                    return name
        
        logger.warning("name_extraction_failed_no_match")
        return None
    
    def extract_email_and_location_from_header(self, text: str) -> Tuple[List[str], Optional[str]]:
        """Extract email and location with strict validation."""
        emails = []
        location = None
        
        try:
            lines = text.split('\n')
            
            # Extract emails from first 20 lines
            email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
            header = '\n'.join(lines[:20])
            emails = re.findall(email_pattern, header)
            if not emails:
                emails = re.findall(email_pattern, text)
            
            # Extract location from first 10 lines
            header_lines = lines[:10]
            
            # Patterns for location
            location_patterns = [
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{2,})(?:\s+(\d{5}))?\b',  # US format
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'  # International
            ]
            
            for i, line in enumerate(header_lines):
                line_lower = line.lower()
                
                # Skip skills sections
                if any(kw in line_lower for kw in ['skills', 'expertise', 'technical', 'tools']):
                    continue
                
                # Skip bullets
                if line.strip().startswith(('•', '-', '*', '►')):
                    continue
                
                # Try patterns
                for pattern in location_patterns:
                    for match in re.finditer(pattern, line):
                        city = match.group(1)
                        region = match.group(2)
                        
                        # Validation
                        if any(term in city.lower() for term in EXCLUDE_FROM_NAME):
                            continue
                        
                        if any(char.isdigit() for char in city):
                            continue
                        
                        if i > 5:
                            continue
                        
                        zipcode = match.group(3) if match.lastindex >= 3 else None
                        if zipcode:
                            location = f"{city}, {region} {zipcode}"
                        else:
                            location = f"{city}, {region}"
                        
                        logger.info("location_extracted", location=location, line_number=i+1)
                        break
                    
                    if location:
                        break
                
                if location:
                    break
            
            logger.info("header_extraction_complete", emails=len(emails), location=bool(location))
        except Exception as e:
            logger.error("header_extraction_failed", error=str(e))
        
        return emails, location
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError))
    )
    async def extract_resume(
        self, 
        text: str, 
        filename: Optional[str] = None
    ) -> dict:
        """Extract resume with ALL fixes."""
        try:
            if not text or not isinstance(text, str):
                raise ValueError("Resume text must be a non-empty string")
            
            if filename:
                logger.info("processing_resume", filename=filename)
            
            if len(text) > self.max_resume_length:
                logger.warning("resume_truncated", length=self.max_resume_length)
                text = text[:self.max_resume_length] + "\n[TRUNCATED]"
            
            # Pre-extract name, email, location
            name_from_header = self.extract_name_from_header(text)
            emails, location = self.extract_email_and_location_from_header(text)
            
            # Build comprehensive prompt
            prompt = f"""Parse this resume per schema.

**═══════════════════════════════════════════════════════════════**
**CRITICAL: NAME - AVOID SKILLS/TECH TERMS**
**═══════════════════════════════════════════════════════════════**

Pre-extracted name: {json.dumps(name_from_header)}

The candidate's name is at the VERY TOP (first 1-3 lines), often in larger font.

DO NOT extract:
- "Lightning Web Components" → NOT a name
- "Core Skills Technical Expertise" → NOT a name
- Any job titles or skills

**═══════════════════════════════════════════════════════════════**
**CRITICAL: INDUSTRY EXTRACTION - REQUIRED FOR EVERY COMPANY**
**═══════════════════════════════════════════════════════════════**

For EVERY company (employer, vendor, or client), extract industry:

**EXPLICIT mentions:**
- "American Family Insurance" → "Insurance"
- "healthcare provider" → "Healthcare"
- "financial services firm" → "Banking/Financial Services"

**CONTEXT clues:**
- "policy management" → "Insurance"
- "patient records" → "Healthcare"
- "banking operations" → "Banking/Financial Services"

**COMPANY NAME clues:**
- "Smart Solutions" → Look for industry in job description
- "Direct Supply" → Look for industry in job description

**MANDATORY:**
- company_industry: REQUIRED for ALL company_name entries
- project_client_industry: REQUIRED for ALL project_end_client_name entries

If no clues: Return "Unknown" (NOT null, NOT "?")

**═══════════════════════════════════════════════════════════════**
**CRITICAL: SKILLS EXTRACTION - READ EVERY BULLET**
**═══════════════════════════════════════════════════════════════**

For EACH work experience, extract skills into categories:

1. **admin_and_automation:**
   - Process Builder, Flow, Workflow Rules
   - Validation Rules, Formula Fields
   - Reports, Dashboards
   - Security (Profiles, Permission Sets, Sharing Rules)
   
   Examples from bullets:
   - "Automated approval processes" → ["Approval Processes"]
   - "Built custom reports" → ["Reports"]
   - "Configured validation rules" → ["Validation Rules"]

2. **dev_coding:**
   - Apex, Triggers, Batch Classes
   - LWC, Aura Components, Visualforce
   - SOQL, SOSL, DML
   - JavaScript, HTML, CSS
   
   Examples:
   - "Developed Apex triggers" → ["Apex", "Triggers"]
   - "Built LWC components" → ["LWC"]
   - "Wrote SOQL queries" → ["SOQL"]

3. **architecture_design:**
   - Solution Design, Technical Architecture
   - Data Modeling
   - Scalability, Performance Optimization

4. **data_management:**
   - Data Migration, Data Loader
   - ETL, Data Quality
   - Deduplication

5. **deployment_devops:**
   - CI/CD (Copado, Gearset, Flosum)
   - Git, GitHub, Bitbucket
   - Change Sets, Metadata API

6. **integration:**
   - REST API, SOAP API
   - MuleSoft, Dell Boomi, Informatica
   - Middleware, Webhooks
   
   Examples:
   - "Integrated HubSpot via REST API" → ["REST API", "HubSpot"]
   - "Implemented DocuSign integration" → ["DocuSign"]

7. **marketing_automation:**
   - Marketing Cloud
   - Pardot
   - Email Studio, Journey Builder

**RULE: READ EVERY SENTENCE AND BULLET**
Each experience should have 10-30 skills total across categories.

**═══════════════════════════════════════════════════════════════**
**CRITICAL: ZERO HALLUCINATION - PRODUCTS**
**═══════════════════════════════════════════════════════════════**

ONLY extract Salesforce products if EXPLICITLY NAMED:

✅ "Implemented Sales Cloud" → ["Sales Cloud"]
✅ "Configured CPQ pricing" → ["CPQ"]

❌ "Senior Consultant at insurance company" → [] (NO PRODUCTS)
❌ "Managed policy systems" → [] (NO PRODUCTS)
❌ "Built customer portal" → [] (NO Experience Cloud unless explicitly named)

**NON-SALESFORCE JOBS:**
If job title does NOT contain "Salesforce" or "SFDC":
- company_is_sfdc_client: "FALSE"
- products: [] (empty)

Examples:
- "Senior Consultant at Smart Solutions" → company_is_sfdc_client: "FALSE", products: []
- "IT Analyst at Direct Supply" → company_is_sfdc_client: "FALSE", products: []

**═══════════════════════════════════════════════════════════════**
**CRITICAL: SFDC START YEAR - TITLE ONLY**
**═══════════════════════════════════════════════════════════════**

**IT START YEAR (it_earliest_year):**
Earliest year of ANY IT/software job → "YYYY"

**SALESFORCE START YEAR (sfdc_earliest_year):**
Earliest year where job TITLE contains "Salesforce" or "SFDC" → "YYYY"

✅ "Salesforce Developer (2017-2019)" → sfdc_earliest_year = "2017"
❌ "Senior Consultant using Salesforce tools (2010-2017)" → Does NOT count (no "Salesforce" in title)

**═══════════════════════════════════════════════════════════════**
**JOB SUMMARY**
**═══════════════════════════════════════════════════════════════**

For each experience, generate 2-3 sentence summary:
- Company type/industry
- Role focus
- Products used
- Key outcomes

Example: "Worked as a Salesforce Developer at this mid-sized insurance company for 2 years. Implemented Sales and Service Cloud to streamline claims processing and allow customers to track claim status."

**═══════════════════════════════════════════════════════════════**
**CANDIDATE SUMMARY**
**═══════════════════════════════════════════════════════════════**

Write 2-3 sentences in THIRD PERSON, NO identifying information:
- Start year in Salesforce
- Core products/clouds
- Industry specialties
- Total certifications

Example: "Seasoned Salesforce Developer with 12 years of experience and 10 SFDC certifications. Carved out a niche in financial services, working with large banking and insurance clients on Financial Services Cloud. Specializes in integrations with MuleSoft and Informatica."

DO NOT include:
- Candidate's name
- Company names
- Location/regions
- Personal pronouns (I, my, etc.)

**═══════════════════════════════════════════════════════════════**
**CONTACT INFO**
**═══════════════════════════════════════════════════════════════**

Pre-extracted:
- Emails: {json.dumps(emails)}
- Location: {json.dumps(location)}

If location not found, return null (NOT instruction text).

**═══════════════════════════════════════════════════════════════**

RESUME TEXT:
{text}

JSON OUTPUT:
{{
  "full_name": {json.dumps(name_from_header) if name_from_header else '"EXTRACT FROM RESUME TOP"'},
  "emails": {json.dumps(emails)},
  "candidate_location": {json.dumps(location) if location else 'null'},
  "it_earliest_year": "YYYY",
  "sfdc_earliest_year": "YYYY or null if no Salesforce jobs",
  "candidate_overall_summary": "Third person, 2-3 sentences, NO names/companies/locations",
  "education": [],
  "certifications": [],
  "experiences": [
    {{
      "company_name": "Direct employer OR null",
      "vendor_consulting_firm": "Vendor name OR null",
      "company_industry": "REQUIRED - NEVER null or ?",
      "job_title": "REQUIRED",
      "job_start_date": "YYYY-MM",
      "job_end_date": "YYYY-MM or Present",
      "job_summary": "2-3 sentence summary",
      "products": ["ONLY if explicitly named"],
      "company_is_sfdc_client": "TRUE or FALSE",
      "skills": {{
        "admin_and_automation": ["skill1", "skill2"],
        "dev_coding": [],
        "architecture_design": [],
        "data_management": [],
        "deployment_devops": [],
        "integration": [],
        "marketing_automation": []
      }},
      "client_projects": [
        {{
          "project_end_client_name": "Client name",
          "via_vendor": "Vendor if applicable",
          "project_client_industry": "REQUIRED - NEVER null or ?",
          "products": ["ONLY if explicitly named"]
        }}
      ]
    }}
  ]
}}"""
            
            logger.info("sending_gpt_request", model=self.model, text_length=len(text))
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": RESUME_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=self.max_tokens
            )
            
            json_text = response.choices[0].message.content
            
            if not json_text or not json_text.strip():
                raise ValueError("GPT returned empty response")
            
            if json_text.endswith('...') or not json_text.strip().endswith('}'):
                logger.error("gpt_response_truncated")
                raise ValueError("GPT response was truncated")
            
            parsed = json.loads(json_text)
            
            # Force pre-extracted values
            if name_from_header and (not parsed.get("full_name") or parsed.get("full_name") in ["REQUIRED", "EXTRACT FROM RESUME TOP"]):
                parsed["full_name"] = name_from_header
                logger.warning("full_name_forced_from_header", name=name_from_header)
            
            if emails and not parsed.get("emails"):
                parsed["emails"] = emails
            
            if location and not parsed.get("candidate_location"):
                parsed["candidate_location"] = location
            
            # Sanitize location
            location_val = parsed.get("candidate_location")
            if location_val and isinstance(location_val, str):
                location_lower = location_val.lower()
                if any(phrase in location_lower for phrase in [
                    'extract from', 'resume', 'header', 'contact', 'city, state', 'if present', 'n/a'
                ]):
                    parsed["candidate_location"] = None
                    logger.warning("location_sanitized", original=location_val)
            
            # Derive IT year if missing
            if not parsed.get("it_earliest_year"):
                min_year = None
                for exp in parsed.get("experiences", []):
                    start_date = exp.get("job_start_date")
                    if start_date:
                        try:
                            year = int(str(start_date)[:4])
                            if min_year is None or year < min_year:
                                min_year = year
                        except:
                            pass
                
                if min_year:
                    parsed["it_earliest_year"] = str(min_year)
                    logger.warning("it_earliest_year_derived", year=min_year)
            
            if not parsed.get("sfdc_earliest_year"):
                min_year = None
                sfdc_jobs = []
                
                for exp in parsed.get("experiences", []):
                    job_title = exp.get("job_title", "")
                    job_summary = exp.get("job_summary", "")  # ✅ FIX: Extract job_summary
                    start_date = exp.get("job_start_date")
                    
                    if not start_date:
                        continue
                    
                    # Check BOTH title AND description for Salesforce mentions
                    title_lower = job_title.lower() if job_title else ""
                    summary_lower = job_summary.lower() if job_summary else ""
                    
                    
                    is_sfdc_job = (
                        "salesforce" in title_lower or 
                        "sfdc" in title_lower or
                        "salesforce" in summary_lower or
                        "sfdc" in summary_lower
                    )
                    
                    if is_sfdc_job: 
                        try:
                            year = int(str(start_date)[:4])
                            sfdc_jobs.append({
                                "title": job_title,
                                "year": year,
                                "has_sfdc_in_title": "salesforce" in title_lower or "sfdc" in title_lower,
                                "has_sfdc_in_description": "salesforce" in summary_lower or "sfdc" in summary_lower
                            })
                            
                            if min_year is None or year < min_year:
                                min_year = year
                        except:
                            continue
                
                if min_year:
                    parsed["sfdc_earliest_year"] = str(min_year)
                    logger.warning("sfdc_earliest_year_derived", year=min_year, jobs=sfdc_jobs)
                else:
                    logger.error("NO_SALESFORCE_JOBS_FOUND")
                    parsed["sfdc_earliest_year"] = None
            
            # Ensure skill structure for ALL experiences
            for exp in parsed.get("experiences", []):
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
            
            logger.info(
                "gpt_extraction_succeeded",
                name=parsed.get("full_name"),
                location=parsed.get("candidate_location"),
                emails=len(parsed.get("emails", [])),
                it_year=parsed.get("it_earliest_year"),
                sfdc_year=parsed.get("sfdc_earliest_year"),
                experiences=len(parsed.get("experiences", [])),
                filename=filename
            )
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error("json_decode_failed", error=str(e))
            raise TypeError(f"Failed to parse GPT response as JSON: {e}")
        except ValueError as e:
            logger.error("value_error_in_extraction", error=str(e))
            raise TypeError(f"Validation error: {e}")
        except Exception as e:
            logger.error("gpt_extraction_failed", error=str(e))
            raise TypeError(f"Extraction failed: {e}")

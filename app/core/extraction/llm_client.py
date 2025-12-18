"""
GPT-4o CLIENT - COMPREHENSIVE FIX with 14 skill categories
"""

import json
import re
from typing import Optional, Dict, List, Tuple
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import get_settings
from app.utils.logger import get_logger
from app.constants import SALESFORCE_PRODUCTS_CANONICAL, PRODUCT_ALIASES, SKILLS_CATEGORIES

settings = get_settings()
logger = get_logger(__name__)


EXCLUDE_FROM_NAME = {
    'professional', 'summary', 'skills', 'expertise', 'core', 'technical',
    'certifications', 'experience', 'education', 'resume', 'cv', 'certified',
    'architect', 'developer', 'consultant', 'lightning', 'web', 'components',
    'salesforce', 'sfdc'
}


RESUME_SYSTEM_PROMPT = """You are an expert resume parser for Salesforce staffing.

**ZERO HALLUCINATION:**
- Extract ONLY explicitly stated information
- DO NOT infer products

Return ONLY valid JSON."""


class GPT4oClient:
    """GPT-4o client with 14 skill categories."""
    
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
        """Extract name from first 5 lines."""
        lines = text.split('\n')
        
        for i, line in enumerate(lines[:3]):
            line = line.strip()
            
            if not line or '@' in line or re.search(r'\d{3}[-.\s]?\d{3}', line):
                continue
            
            line_lower = line.lower()
            
            if any(kw in line_lower for kw in EXCLUDE_FROM_NAME):
                logger.info("name_skipped", line=line[:50])
                continue
            
            if any(char in line for char in ['•', ':', '|', '–', '—', '-', '/']):
                continue
            
            words = line.split()
            if 2 <= len(words) <= 4:
                if all(w[0].isupper() for w in words if len(w) > 1):
                    if all(2 <= len(w) <= 15 for w in words):
                        if not any(w.lower() in EXCLUDE_FROM_NAME for w in words):
                            logger.info("name_extracted", name=line, line_number=i+1)
                            return line
        
        for i, line in enumerate(lines[:5]):
            if any(kw in line.lower() for kw in EXCLUDE_FROM_NAME):
                continue
            
            match = re.search(r'\b([A-Z][a-z]{2,14})\s+([A-Z][a-z]{2,14})\b', line)
            if match:
                name = match.group(0)
                if not any(term in name.lower() for term in EXCLUDE_FROM_NAME):
                    logger.info("name_extracted_pattern", name=name)
                    return name
        
        logger.warning("name_extraction_failed")
        return None
    
    def extract_email_and_location_from_header(self, text: str) -> Tuple[List[str], Optional[str]]:
        """Extract email and location."""
        emails = []
        location = None
        
        try:
            lines = text.split('\n')
            
            email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
            header = '\n'.join(lines[:20])
            emails = re.findall(email_pattern, header)
            if not emails:
                emails = re.findall(email_pattern, text)
            
            header_lines = lines[:10]
            location_patterns = [
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{2,})(?:\s+(\d{5}))?\b',
                r'\b([A-Z][a-z]+),\s*([A-Z][a-z]+)\b'
            ]
            
            for i, line in enumerate(header_lines):
                line_lower = line.lower()
                
                if any(kw in line_lower for kw in ['skills', 'expertise', 'technical']):
                    continue
                
                if line.strip().startswith(('•', '-', '*')):
                    continue
                
                for pattern in location_patterns:
                    for match in re.finditer(pattern, line):
                        city = match.group(1)
                        region = match.group(2)
                        
                        if any(term in city.lower() for term in EXCLUDE_FROM_NAME):
                            continue
                        
                        if i > 5:
                            continue
                        
                        zipcode = match.group(3) if match.lastindex >= 3 else None
                        if zipcode:
                            location = f"{city}, {region} {zipcode}"
                        else:
                            location = f"{city}, {region}"
                        
                        logger.info("location_extracted", location=location)
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
        """Extract resume with ALL 14 skill categories."""
        try:
            if not text or not isinstance(text, str):
                raise ValueError("Resume text must be a non-empty string")
            
            if filename:
                logger.info("processing_resume", filename=filename)
            
            if len(text) > self.max_resume_length:
                text = text[:self.max_resume_length] + "\n[TRUNCATED]"
            
            name_from_header = self.extract_name_from_header(text)
            emails, location = self.extract_email_and_location_from_header(text)
            
            products_list = ", ".join(sorted(SALESFORCE_PRODUCTS_CANONICAL))
            
            prompt = f"""Parse this resume per schema.

**CRITICAL: COMPANY CLASSIFICATION - NO SALESFORCE ISV CATEGORY**

For each work experience, classify companies as EITHER:

1. **vendor_consulting_firm**: IT consulting firms, staffing firms, OR Salesforce ISVs
   - Examples: Accenture, Deloitte, Slolam, Gears CRM, Cloudware Connections, Eezentek
   - Indicators: "consulting", "staffing", "solutions", "technologies" in name
   - **IMPORTANT: ALL ISVs go here (NO separate "Salesforce ISV" category)**

2. **company_name**: Direct employers who are NOT consulting firms
   - Examples: Zscaler, Huntington Bank, Target
   - Only use if company is an end client/direct employer

**CRITICAL: EXTRACT CLIENT PROJECTS UNDER VENDORS**

When a vendor has multiple client engagements listed, extract each as a client project.

**CRITICAL: SFDC START YEAR - CHECK TITLE AND DESCRIPTION**

Find EARLIEST year where EITHER:
1. Job title contains "Salesforce" or "SFDC", OR
2. Job description mentions "Salesforce" or "SFDC"

**PRODUCTS (ONLY IF EXPLICITLY NAMED):**
Valid products: {products_list}

**SKILLS CATEGORIES (14 categories):**
- admin_and_automation: Flow Builder, Process Builder, Reports, Dashboards, Data Loader, etc.
- dev_coding: Apex, LWC, Visualforce, JavaScript, Python, Java, etc.
- architecture_design: Solution Design, Data Modeling, Integration Patterns, etc.
- data_management: Data Migration, ETL, Data Quality, etc.
- deployment_devops: Copado, Gearset, CI/CD, Git, etc.
- integration: MuleSoft, REST API, Platform Events, etc.
- data_reporting: CRM Analytics, Tableau, Einstein Discovery, SQL, etc.
- ecosystem_tools: DocuSign, Conga, ZoomInfo, Veeva, etc.
- security_compliance: Salesforce Shield, MFA, Encryption, SSO, etc.
- delivery_methodology: Agile, Scrum, Jira, Sprint Planning, etc.
- business_analysis: Requirements Gathering, User Stories, Process Mapping, etc.
- project_program_management: Budget Management, Risk Management, etc.
- qa_testing: Test Automation, Regression Testing, UAT, etc.
- marketing_automation: SFMC, AMPScript, Journey Builder, Pardot, etc.

**CONTACT:**
Emails: {json.dumps(emails)}
Location: {json.dumps(location)}

**RESUME:**
{text}

**JSON OUTPUT:**
{{
  "full_name": {json.dumps(name_from_header) if name_from_header else '"EXTRACT"'},
  "emails": {json.dumps(emails)},
  "candidate_location": {json.dumps(location) if location else 'null'},
  "it_earliest_year": "YYYY",
  "sfdc_earliest_year": "YYYY",
  "candidate_overall_summary": "Third person, NO names/companies",
  "education": [],
  "certifications": [],
  "experiences": [
    {{
      "company_name": "Direct employer name OR null",
      "vendor_consulting_firm": "Vendor/ISV name OR null",
      "company_industry": "Derive from context",
      "job_title": "EXACTLY as written",
      "job_start_date": "YYYY-MM or YYYY",
      "job_end_date": "YYYY-MM or Present (NEVER ?)",
      "job_summary": "2-3 sentences",
      "products": ["ONLY if explicitly named"],
      "skills": {{
        "admin_and_automation": [],
        "dev_coding": [],
        "architecture_design": [],
        "data_management": [],
        "deployment_devops": [],
        "integration": [],
        "data_reporting": [],
        "ecosystem_tools": [],
        "security_compliance": [],
        "delivery_methodology": [],
        "business_analysis": [],
        "project_program_management": [],
        "qa_testing": [],
        "marketing_automation": []
      }},
      "client_projects": [
        {{
          "project_end_client_name": "Client name",
          "via_vendor": "Vendor if applicable",
          "project_client_industry": "Derive from context",
          "project_start_date": "YYYY-MM",
          "project_end_date": "YYYY-MM or Present",
          "products": ["ONLY if explicitly named"],
          "project_scope_summary": "Brief description"
        }}
      ]
    }}
  ]
}}"""
            
            logger.info("sending_gpt_request", model=self.model)
            
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
            
            parsed = json.loads(json_text)
            
            # Force pre-extracted values
            if name_from_header and (not parsed.get("full_name") or parsed.get("full_name") in ["REQUIRED", "EXTRACT"]):
                parsed["full_name"] = name_from_header
                logger.warning("full_name_forced", name=name_from_header)
            
            if emails and not parsed.get("emails"):
                parsed["emails"] = emails
            
            if location and not parsed.get("candidate_location"):
                parsed["candidate_location"] = location
            
            # Sanitize location
            location_val = parsed.get("candidate_location")
            if location_val and isinstance(location_val, str):
                if any(phrase in location_val.lower() for phrase in [
                    'extract', 'resume', 'city, state', 'if present', 'n/a'
                ]):
                    parsed["candidate_location"] = None
            
            # Derive IT year
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
            
            # Derive SFDC year - CHECK BOTH TITLE AND DESCRIPTION
            if not parsed.get("sfdc_earliest_year"):
                min_year = None
                sfdc_jobs = []
                
                for exp in parsed.get("experiences", []):
                    job_title = exp.get("job_title", "")
                    job_summary = exp.get("job_summary", "")
                    start_date = exp.get("job_start_date")
                    
                    if not start_date:
                        continue
                    
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
                            pass
                
                if min_year:
                    parsed["sfdc_earliest_year"] = str(min_year)
                    logger.warning("sfdc_earliest_year_derived", year=min_year, jobs=sfdc_jobs)
                else:
                    logger.error("NO_SALESFORCE_EXPERIENCE_FOUND")
                    parsed["sfdc_earliest_year"] = None
            
            # Ensure skill structure (ALL 14 CATEGORIES)
            for exp in parsed.get("experiences", []):
                if "skills" not in exp or not isinstance(exp["skills"], dict):
                    exp["skills"] = {
                        "admin_and_automation": [],
                        "dev_coding": [],
                        "architecture_design": [],
                        "data_management": [],
                        "deployment_devops": [],
                        "integration": [],
                        "data_reporting": [],
                        "ecosystem_tools": [],
                        "security_compliance": [],
                        "delivery_methodology": [],
                        "business_analysis": [],
                        "project_program_management": [],
                        "qa_testing": [],
                        "marketing_automation": []
                    }
            
            logger.info(
                "gpt_extraction_succeeded",
                name=parsed.get("full_name"),
                location=parsed.get("candidate_location"),
                experiences=len(parsed.get("experiences", [])),
                filename=filename
            )
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error("json_decode_failed", error=str(e))
            raise TypeError(f"Failed to parse GPT response as JSON: {e}")
        except Exception as e:
            logger.error("gpt_extraction_failed", error=str(e))
            raise TypeError(f"Extraction failed: {e}")

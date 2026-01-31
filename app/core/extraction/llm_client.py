"""
GPT-4o CLIENT - FINAL PRODUCTION VERSION
Complete with comprehensive prompts AND all enforcement methods
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
Extract ONLY explicitly stated information. DO NOT infer products or compute years.
Return ONLY valid JSON."""

CRM_TRIGGERS = ["saql", "crma", "tcrm", "tableau crm", "einstein analytics", "wave analytics", "crm analytics"]

SUMMARY_REPAIR_SYS = """Rewrite job summaries using ONLY the provided facts.
- Do NOT add company names
- Do NOT add metrics unless provided  
- Write 35-60 words in What-How-Why format
- Anonymize company to [size] + [industry]
Return plain text only."""


class GPT4oClient:
    """GPT-4o client - FINAL PRODUCTION."""
    
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
    
    def extract_phones(self, text: str) -> List[str]:
        """FIX 1: Extract phones - capture full match."""
        phone_re = re.compile(r'(?:\+?\d{1,3}[\s.-]*)?\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}')
        raw = [m.group(0) for m in phone_re.finditer(text)]
        norm = []
        for p in raw:
            p2 = re.sub(r'[^\d+]', '', p)
            if p2 and p2 not in norm:
                norm.append(p2)
        logger.info("phones_extracted", count=len(norm))
        return norm
    
    def extract_linkedin_url(self, text: str) -> Optional[str]:
        """FIX 2: Extract LinkedIn - only if URL present."""
        m = re.search(r'(https?://)?(www\.)?linkedin\.com/in/[A-Za-z0-9\-_/%]+', text, re.I)
        if not m:
            if re.search(r'\blinkedin\b', text, re.I):
                return "LinkedIn (URL not provided)"
            return None
        url = m.group(0)
        return url if url.startswith("http") else f"https://{url.lstrip('/')}"
    
    def derive_sfdc_year_from_profile(self, text: str, current_year: int = 2026) -> Optional[str]:
        """FIX 3: Derive SFDC year from profile - Python math."""
        t = text.lower()
        patterns = [
            r'(?:over\s*)?(\d{1,2})\s*\+?\s*years?.{0,30}\bsalesforce\b',
            r'\bsalesforce\b.{0,30}(?:over\s*)?(\d{1,2})\s*\+?\s*years?'
        ]
        for p in patterns:
            m = re.search(p, t)
            if m:
                yrs = int(m.group(1))
                if 1 <= yrs <= 30:
                    derived = current_year - yrs
                    logger.info("sfdc_year_from_profile", years=yrs, derived=derived)
                    return str(derived)
        return None
    
    def derive_industry_from_name(self, name: str) -> str:
        """Quick industry derivation from company name."""
        if not name or not isinstance(name, str):
            return "Unknown"
        
        name_lower = name.lower()
        
        industry_keywords = {
            'hotel': 'Hospitality',
            'seasons': 'Hospitality',
            'bank': 'Banking/Financial Services',
            'financial': 'Banking/Financial Services',
            'insurance': 'Insurance',
            'fleet': 'Fleet Management',
            'university': 'Education',
            'college': 'Education',
            'telus': 'Telecommunications',
            'rogers': 'Telecommunications',
        }
        
        for keyword, industry in industry_keywords.items():
            if keyword in name_lower:
                return industry
        
        return "Unknown"
    
    def extract_clients_from_text(self, text: str, vendor: str) -> List[dict]:
        """Extract client companies from project descriptions using regex."""
        clients = []
        
        # Patterns to match "project for [Company Name]"
        patterns = [
            r'project for ([A-Z][A-Za-z\s&\.\-]+(?:Hotels?|Bank|Insurance|Corporation|Inc|LLC|Ltd|Management|University|Communications|Financial|Fleet|Investments?))',
            r'working (?:with|for) ([A-Z][A-Za-z\s&\.\-]+(?:Hotels?|Bank|Insurance|Corporation|Inc|LLC|Ltd))',
            r'([A-Z][A-Za-z\s&\.\-]+(?:Hotels?|Bank|University)) (?:implementation|project)',
            r'(?:client|engagement):\s*([A-Z][A-Za-z\s&\.\-]+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                client_name = match.group(1).strip()
                
                # Skip if it's a vendor name
                vendor_keywords = ['slalom', 'deloitte', 'accenture', 'cognizant', 'consulting']
                if any(kw in client_name.lower() for kw in vendor_keywords):
                    continue
                
                # Clean up the name
                client_name = re.sub(r'\s+', ' ', client_name).strip()
                
                clients.append({
                    "project_end_client_name": client_name,
                    "project_client_industry": self.derive_industry_from_name(client_name),
                    "via_vendor": vendor,
                    "products": []
                })
                logger.info("client_extracted_via_regex", client=client_name, vendor=vendor)
                break  # Only take first match per pattern
        
        return clients
    
    def redact_company_names(self, summary: str, exp: dict) -> str:
        """FIX 5: Redact company names - deterministic."""
        if not summary:
            return summary
        for key in ("company_name", "vendor_consulting_firm"):
            name = (exp.get(key) or "").strip()
            if name:
                summary = re.sub(re.escape(name), "the company", summary, flags=re.I)
        for proj in exp.get("client_projects", []):
            client = proj.get("project_end_client_name", "").strip()
            if client:
                summary = re.sub(re.escape(client), "the client", summary, flags=re.I)
        return summary
    
    def ensure_crm_analytics(self, exp: dict):
        """FIX 6: Force CRM Analytics if triggers present."""
        blob = " ".join([
            exp.get("job_summary", ""),
            " ".join(exp.get("skills", {}).get("data_reporting", []) or []),
        ]).lower()
        
        if any(k in blob for k in CRM_TRIGGERS):
            prods = exp.get("products") or []
            if "CRM Analytics" not in prods:
                prods.append("CRM Analytics")
                logger.info("crm_analytics_injected", title=exp.get("job_title"))
            exp["products"] = prods
    
    async def repair_job_summary(self, exp: dict) -> str:
        """FIX 4: Repair job summary if <35 words."""
        facts = {
            "job_title": exp.get("job_title"),
            "dates": f'{exp.get("job_start_date")} to {exp.get("job_end_date")}',
            "industry": exp.get("company_industry"),
            "products": exp.get("products") or [],
            "skills": exp.get("skills") or {},
            "original_summary": exp.get("job_summary") or ""
        }
        
        try:
            start = exp.get("job_start_date", "")
            end = exp.get("job_end_date", "")
            if start:
                start_year = int(str(start)[:4])
                if end == "Present":
                    end_year = 2026
                elif end:
                    end_year = int(str(end)[:4])
                else:
                    end_year = start_year
                duration_years = end_year - start_year
                facts["duration"] = f"{duration_years} years" if duration_years != 1 else "1 year"
        except:
            facts["duration"] = "time period"
        
        user = f"""Facts JSON:
{json.dumps(facts, ensure_ascii=False)}

Write 40-60 words using What-How-Why structure:
1. Context: "[Role] for [industry] company for [duration]..."
2. How: Products and tools from facts
3. Why: Outcome or scope from facts (do not invent)

Anonymize all company names to industry descriptors.
"""
        
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SUMMARY_REPAIR_SYS},
                    {"role": "user", "content": user}
                ],
                temperature=0.0,
                max_tokens=400
            )
            repaired = (resp.choices[0].message.content or "").strip()
            logger.info("job_summary_repaired", 
                       original_len=len(facts["original_summary"].split()), 
                       repaired_len=len(repaired.split()))
            return repaired
        except Exception as e:
            logger.error("repair_failed", error=str(e))
            return exp.get("job_summary", "")
    
    def extract_name_from_header(self, text: str) -> Optional[str]:
        """Extract name from first 5 lines."""
        lines = text.split('\n')
        
        for i, line in enumerate(lines[:3]):
            line = line.strip()
            
            if not line or '@' in line or re.search(r'\d{3}[-.\s]?\d{3}', line):
                continue
            
            line_lower = line.lower()
            
            if any(kw in line_lower for kw in EXCLUDE_FROM_NAME):
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
        
        return None
    
    def extract_email_and_location_from_header(self, text: str) -> Tuple[List[str], Optional[str]]:
        """Extract email and location."""
        emails = []
        location = None
        
        try:
            lines = text.split('\n')
            header = '\n'.join(lines[:20])
            
            email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
            emails = re.findall(email_pattern, header)
            if not emails:
                emails = re.findall(email_pattern, text)
            
            header_lines = lines[:10]
            location_patterns = [
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z]{2,})(?:\s+(\d{5}))?\b',
                r'\b([A-Z][a-z]+),\s*([A-Z][a-z]+)\b'
            ]
            
            for i, line in enumerate(header_lines):
                if any(kw in line.lower() for kw in ['skills', 'expertise']):
                    continue
                
                for pattern in location_patterns:
                    for match in re.finditer(pattern, line):
                        city = match.group(1)
                        region = match.group(2)
                        
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
            
        except Exception as e:
            logger.error("header_extraction_failed", error=str(e))
        
        return emails, location
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError))
    )
    async def extract_resume(self, text: str, filename: Optional[str] = None) -> dict:
        """Extract resume - FINAL PRODUCTION with comprehensive prompt AND enforcement."""
        try:
            if not text or not isinstance(text, str):
                raise ValueError("Resume text must be a non-empty string")
            
            if filename:
                logger.info("processing_resume", filename=filename)
            
            if len(text) > self.max_resume_length:
                text = text[:self.max_resume_length] + "\n[TRUNCATED]"
            
            name_from_header = self.extract_name_from_header(text)
            emails, location = self.extract_email_and_location_from_header(text)
            phones = self.extract_phones(text[:2000])
            links = self.extract_linkedin_url(text)
            
            products_list = ", ".join(sorted(SALESFORCE_PRODUCTS_CANONICAL))
            
            # COMPREHENSIVE PROMPT with What-How-Why
            prompt = f"""Parse resume following strict guidelines.

**COMPANY CLASSIFICATION:**
- vendor_consulting_firm: IT consulting/staffing/ISVs
- company_name: Direct employers

**CLIENT PROJECT EXTRACTION:**
When job description mentions work FOR another company via a vendor, extract into client_projects.

Trigger phrases:
- "project for [Company Name]"
- "working with [Company Name]"
- "[Company Name] implementation"
- "client: [Company Name]"

Extract client company name exactly as written into client_projects array.

**JOB SUMMARY (35-50 words, What-How-Why):**
1. Context: "[Role] for [size] [industry] for [duration]..."
2. How: Salesforce products/tools used
3. Why: Business outcome or scope

In job_summary: anonymize company names
In client_projects: use exact company names

**ANTI-HALLUCINATION:**
- NEVER invent metrics
- Extract ONLY stated facts
- Client names in client_projects must be exact

**PRODUCTS:** {products_list}

**CONTACT:**
Emails: {json.dumps(emails)}
Phones: {json.dumps(phones)}
LinkedIn: {json.dumps(links)}
Location: {json.dumps(location)}

**RESUME:**
{text}

**JSON:**
{{
  "full_name": {json.dumps(name_from_header) if name_from_header else '"EXTRACT"'},
  "emails": {json.dumps(emails)},
  "phones": {json.dumps(phones)},
  "links": {json.dumps(links)},
  "candidate_location": {json.dumps(location) if location else 'null'},
  "it_earliest_year": "YYYY",
  "sfdc_earliest_year": null,
  "candidate_overall_summary": "Third person, NO names",
  "education": [],
  "certifications": [],
  "experiences": [
    {{
      "company_name": "OR null",
      "vendor_consulting_firm": "OR null",
      "company_industry": "Derive",
      "job_title": "EXACT",
      "job_start_date": "YYYY-MM",
      "job_end_date": "YYYY-MM or Present",
      "job_summary": "Anonymized",
      "products": [],
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
          "project_end_client_name": "Exact name",
          "project_client_industry": "Derive",
          "via_vendor": "vendor_consulting_firm value",
          "products": []
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
            
            if name_from_header:
                parsed["full_name"] = name_from_header
            if emails:
                parsed["emails"] = emails
            if phones:
                parsed["phones"] = phones
            if links:
                parsed["links"] = links
            if location:
                parsed["candidate_location"] = location
            
            # FIX 3: SFDC year from profile
            profile_year = self.derive_sfdc_year_from_profile(text, current_year=2026)
            if profile_year:
                parsed["sfdc_earliest_year"] = profile_year
            
            # Fallback to job history
            if not parsed.get("sfdc_earliest_year"):
                min_year = None
                for exp in parsed.get("experiences", []):
                    title = exp.get("job_title", "").lower()
                    summary = exp.get("job_summary", "").lower()
                    if "salesforce" in title or "salesforce" in summary:
                        start = exp.get("job_start_date")
                        if start:
                            try:
                                year = int(str(start)[:4])
                                if min_year is None or year < min_year:
                                    min_year = year
                            except:
                                pass
                if min_year:
                    parsed["sfdc_earliest_year"] = str(min_year)
            
            # IT year
            if not parsed.get("it_earliest_year"):
                min_year = None
                for exp in parsed.get("experiences", []):
                    start = exp.get("job_start_date")
                    if start:
                        try:
                            year = int(str(start)[:4])
                            if min_year is None or year < min_year:
                                min_year = year
                        except:
                            pass
                if min_year:
                    parsed["it_earliest_year"] = str(min_year)
            
            # Process experiences
            for exp in parsed.get("experiences", []):
                # FIX 6: CRM Analytics
                self.ensure_crm_analytics(exp)
                
                # PYTHON FALLBACK: Extract clients if GPT missed them
                vendor = exp.get("vendor_consulting_firm")
                if vendor and (not exp.get("client_projects") or len(exp.get("client_projects", [])) == 0):
                    job_title = exp.get("job_title", "")
                    
                    if job_title:
                        # Find position of this job in original text
                        title_pos = text.lower().find(job_title.lower())
                        if title_pos > -1:
                            # Extract 500 chars as context
                            context = text[title_pos:title_pos+500]
                            extracted_clients = self.extract_clients_from_text(context, vendor)
                            
                            if extracted_clients:
                                exp["client_projects"] = extracted_clients
                                logger.info("clients_added_via_fallback", 
                                          vendor=vendor, 
                                          clients=[c["project_end_client_name"] for c in extracted_clients])
                
                # FIX 4: Repair job summary
                job_summary = exp.get("job_summary", "")
                word_count = len(job_summary.split())
                if word_count < 35:
                    exp["job_summary"] = await self.repair_job_summary(exp)
                
                # FIX 5: Redact company names
                exp["job_summary"] = self.redact_company_names(exp.get("job_summary", ""), exp)
                
                # Ensure skills
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
            
            logger.info("gpt_extraction_succeeded", name=parsed.get("full_name"))
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error("json_decode_failed", error=str(e))
            raise TypeError(f"Failed to parse GPT response as JSON: {e}")
        except Exception as e:
            logger.error("gpt_extraction_failed", error=str(e))
            raise TypeError(f"Extraction failed: {e}")

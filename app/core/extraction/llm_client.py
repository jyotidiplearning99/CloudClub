"""
GPT-4o client with STRICT anti-hallucination rules.

Critical fixes based on Julieta's resume issues:
1. Do NOT infer products from job titles/descriptions
2. Only extract products explicitly named in text
3. Admin/BA work does NOT automatically mean all Clouds
4. Summary must match calculated years
"""

import json
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


RESUME_SYSTEM_PROMPT = """You are an expert resume parser for a Salesforce/Commerce Cloud staffing platform.

**CRITICAL ANTI-HALLUCINATION RULES (based on real issues):**

1. **PRODUCTS - ZERO TOLERANCE FOR HALLUCINATION:**
   
   **DO NOT infer products from:**
   - Job titles (e.g., "Salesforce Admin" does NOT mean they used all Clouds)
   - Generic descriptions ("created objects, flows" does NOT mean specific Clouds)
   - Company type ("worked at Salesforce consulting firm" does NOT mean all products)
   
   **ONLY extract products if:**
   - Explicitly named: "worked on Sales Cloud", "implemented CPQ", "used Service Cloud"
   - Product is spelled out in full or common abbreviation (SFMC, FSC, etc.)
   
   **Example - WRONG hallucination:**
   Resume says: "Salesforce Administrator at Accenture. Created custom objects, fields, flows."
   WRONG: products: ["Sales Cloud", "Service Cloud", "Experience Cloud"] ❌
   CORRECT: products: [] ✅ (No products explicitly named!)
   
   **Example - CORRECT extraction:**
   Resume says: "Implemented Sales Cloud and CPQ for American Express"
   CORRECT: products: ["Sales Cloud", "CPQ"] ✅

2. **SUMMARY - MATCH CALCULATED YEARS:**
   
   - If sfdc_earliest_year = "2018" and current year = 2025, then sfdc_years = 7
   - Summary MUST say "7 years" NOT "6 years"
   - OR don't mention number: "since 2018" instead of "6 years"
   
   **Examples:**
   ✅ "Experienced Salesforce administrator with 7 years in the ecosystem"
   ✅ "Experienced Salesforce administrator since 2018"
   ❌ "Experienced Salesforce administrator with 6 years" (if sfdc_years=7)

3. **ADMIN VS DEVELOPER VS ARCHITECT:**
   
   - Admin work (objects, fields, layouts, flows, approval processes) = Admin skills, NOT products
   - Developer work (Apex, LWC, Visualforce) = Dev skills
   - DO NOT assume all Salesforce Clouds just because they're an admin

4. **CLIENT EXTRACTION - STILL AGGRESSIVE:**
   
   - Extract every client mentioned by name
   - Look for "(Client)" patterns
   - But still NO products if not explicitly stated for that client

5. **VENDOR VS COMPANY - KEYWORDS:**
   
   Consulting indicators:
   - "Freelance", "Contract", "Contractor", "Consulting", "Consultant"
   
   Direct employment indicators:
   - "Full time", "Full-time", "Employee", "Staff"

6. **DATES AND YEARS:**
   
   - Convert "October 2022" → "2022-10"
   - Current role: "Present"
   - Calculate sfdc_years: 2025 - int(sfdc_earliest_year)

7. **MISSING DATA:**
   
   - Use null for missing fields
   - Years as STRINGS: "2018" not 2018
   - links as dict or null, NEVER list

Return ONLY valid JSON. Zero hallucinations. Extract only explicitly stated facts."""


class GPT4oClient:
    """OpenAI GPT-4o client with strict anti-hallucination."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def extract_resume(self, text: str) -> dict:
        """
        Extract resume data with STRICT anti-hallucination rules.
        
        Based on real issues:
        - Julieta's resume: Admin work does NOT mean all Clouds
        - Summary years must match calculated years
        """
        if len(text) > settings.max_resume_length:
            logger.warning("resume_truncated", length=settings.max_resume_length)
            text = text[:settings.max_resume_length] + "\n[TRUNCATED]"
        
        # Provide clear examples
        context = {
            "salesforce_products": [
                "Sales Cloud", "Service Cloud", "CPQ", "Marketing Cloud",
                "Experience Cloud", "Financial Services Cloud", "Health Cloud",
                "Data Cloud", "Commerce Cloud", "Field Service"
            ],
            "admin_skills_NOT_products": [
                "Custom objects", "Page layouts", "Record types",
                "Flows", "Approval processes", "Validation rules",
                "Reports and dashboards", "User management"
            ],
            "hallucination_examples": {
                "WRONG": "Resume: 'Salesforce Admin, created objects' → products: ['Sales Cloud', 'Service Cloud']",
                "CORRECT": "Resume: 'Salesforce Admin, created objects' → products: [] (no products named!)",
                "CORRECT": "Resume: 'Implemented Sales Cloud and CPQ' → products: ['Sales Cloud', 'CPQ']"
            }
        }
        
        prompt = f"""Parse this resume with ZERO HALLUCINATIONS.

ANTI-HALLUCINATION CONTEXT:
{json.dumps(context, indent=2)}

RESUME TEXT:
{text}

CRITICAL EXTRACTION RULES:

1. **PRODUCTS - BE EXTREMELY CONSERVATIVE:**
   - Only list if product name explicitly appears in text
   - Admin tasks (objects, fields, flows) ≠ products
   - "Salesforce Administrator" ≠ any specific Cloud
   - If unsure, products: []

2. **SUMMARY - MATCH YEARS:**
   - Calculate: sfdc_years = 2025 - int(sfdc_earliest_year)
   - Summary must say same number OR avoid number
   - Example: If sfdc_years=7, say "7 years" OR "since 2018"

3. **CLIENT EXTRACTION:**
   - Extract every named client
   - Look for "(Client Name)" patterns
   - But products at client level: only if explicitly stated

4. **DATES:**
   - Convert: "January 2023" → "2023-01"
   - Current: "Present"

Return JSON with:
- full_name, emails, phones
- links: dict or null (NEVER list)
- candidate_location: "City, Country"
- it_earliest_year: STRING "YYYY"
- sfdc_earliest_year: STRING "YYYY"
- sfdc_years: INTEGER (2025 - int(sfdc_earliest_year))
- candidate_overall_summary: Match the sfdc_years number or omit number
- most_recent_job_title
- other_skills: Admin/dev skills (NOT products)
- certifications
- experiences:
  - company_name OR vendor_consulting_firm (one null)
  - job_title, job_start_date (YYYY-MM), job_end_date (YYYY-MM or "Present")
  - products: [] if no products explicitly named (BE CONSERVATIVE!)
  - skills: Admin/dev skills
  - client_projects: Extract ALL named clients
    - project_end_client_name
    - products: Only if explicitly stated for THIS client

**ZERO HALLUCINATIONS. ONLY EXTRACT EXPLICITLY STATED FACTS.**"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": RESUME_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,  # Zero temperature for consistency
                max_tokens=settings.llm_max_tokens
            )
            
            json_text = response.choices[0].message.content
            parsed = json.loads(json_text)
            
            logger.info(
                "gpt_extraction_succeeded",
                candidate=parsed.get("full_name"),
                experiences=len(parsed.get("experiences", [])),
                total_products=sum(len(exp.get("products", [])) for exp in parsed.get("experiences", [])),
                tokens_used=response.usage.total_tokens,
                cost_usd=round(response.usage.total_tokens * 0.000025, 4)
            )
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error("json_decode_failed", error=str(e))
            raise ValueError(f"GPT returned invalid JSON: {e}")
        except Exception as e:
            logger.error("gpt_extraction_failed", error=str(e), exc_info=True)
            raise

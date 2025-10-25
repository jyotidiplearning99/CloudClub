"""
Resume parser with comprehensive extraction and universal location support.
"""

import hashlib
import re
from typing import Optional, List, Set
from app.core.extraction.text_extractor import TextExtractor
from app.core.extraction.llm_client import GPT4oClient
from app.core.extraction.rules import apply_normalization_rules, classify_and_filter, PRODUCT_ALIASES, SALESFORCE_PRODUCTS_CANONICAL
from app.schemas.candidate import CandidateProfile
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ResumeParser:
    """Resume parser with comprehensive extraction."""
    
    def __init__(self):
        self.text_extractor = TextExtractor()
        self.llm_client = GPT4oClient()
    
    def _extract_name_fallback(self, text: str) -> str:
        """Robust name extraction from header."""
        lines = text.split('\n')
        
        for line in lines[:5]:
            line = line.strip()
            if not line or '@' in line:
                continue
            if any(c.isdigit() for c in line) and line.count(' ') < 3:
                continue
            if len(line) > 100:
                continue
            words = line.split()
            if 2 <= len(words) <= 4:
                if all(w[0].isupper() for w in words if w and len(w) > 1):
                    logger.info("name_extracted_fallback", name=line)
                    return line
        
        name_pattern = r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b'
        match = re.search(name_pattern, text[:500])
        if match:
            name = match.group(0)
            logger.warning("name_extracted_pattern", name=name)
            return name
        
        return "Unknown Candidate"
    
    def _extract_products_globally(self, text: str) -> Set[str]:
        """Extract products including Wave Analytics."""
        text_lower = text.lower()
        found = set()
        
        for alias, canonical in PRODUCT_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", text_lower):
                if canonical in SALESFORCE_PRODUCTS_CANONICAL:
                    found.add(canonical)
        
        logger.info("global_products_found", products=list(found), count=len(found))
        return found
    
    def _fix_summary_years_safely(self, data: dict) -> dict:
        """Safer summary fix - only touch "Salesforce ... years" patterns."""
        summary = data.get("candidate_overall_summary", "")
        sfdc_years = data.get("sfdc_years")
        
        if not summary or not sfdc_years:
            return data
        
        pattern = r'(\d+\+?)\s*years?(?=[^.\n]{0,30}\b(salesforce|sfdc)\b)'
        
        def repl(m):
            plus = '+' if '+' in m.group(1) else ''
            return f'{sfdc_years}{plus} years'
        
        new_summary = re.sub(pattern, repl, summary, flags=re.IGNORECASE)
        
        if new_summary != summary:
            logger.info("summary_years_fixed_safely")
        
        data["candidate_overall_summary"] = new_summary
        return data
    
    def _coerce_data_types(self, data: dict) -> dict:
        """Coerce data types (safer links handling)."""
        if data.get("it_earliest_year") is not None:
            data["it_earliest_year"] = str(data["it_earliest_year"])
        if data.get("sfdc_earliest_year") is not None:
            data["sfdc_earliest_year"] = str(data["sfdc_earliest_year"])
        
        if "links" in data and not isinstance(data["links"], dict):
            data["links"] = None
        
        experiences = data.get("experiences", [])
        if not isinstance(experiences, list):
            logger.error("experiences_not_list", type=type(experiences))
            data["experiences"] = []
            return data
        
        cleaned_experiences = []
        for exp in experiences:
            if not isinstance(exp, dict):
                logger.warning("experience_not_dict", type=type(exp))
                continue
            
            if exp.get("job_start_date") is not None:
                exp["job_start_date"] = str(exp["job_start_date"])
            if exp.get("job_end_date") is not None:
                exp["job_end_date"] = str(exp["job_end_date"])
            
            client_projects = exp.get("client_projects", [])
            if not isinstance(client_projects, list):
                exp["client_projects"] = []
            else:
                valid_projects = []
                for project in client_projects:
                    if not isinstance(project, dict):
                        continue
                    if not project.get("project_end_client_name"):
                        continue
                    if project.get("project_start_date") is not None:
                        project["project_start_date"] = str(project["project_start_date"])
                    if project.get("project_end_date") is not None:
                        project["project_end_date"] = str(project["project_end_date"])
                    valid_projects.append(project)
                exp["client_projects"] = valid_projects
            
            cleaned_experiences.append(exp)
        
        data["experiences"] = cleaned_experiences
        return data
    
    async def parse(self, file_bytes: bytes, filename: str, candidate_id: Optional[str] = None) -> CandidateProfile:
        """Parse with ALL fixes."""
        logger.info("parse_started", filename=filename, size_bytes=len(file_bytes))
        
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        
        try:
            text = self.text_extractor.extract(file_bytes, filename)
            logger.info("text_extracted", length=len(text), sha256=sha256)
        except Exception as e:
            logger.error("text_extraction_failed", error=str(e))
            raise ValueError(f"Failed to extract text: {e}")
        
        try:
            raw_data = await self.llm_client.extract_resume(text)
            
            if not raw_data.get("full_name"):
                fallback_name = self._extract_name_fallback(text)
                raw_data["full_name"] = fallback_name
                logger.warning("full_name_extracted_via_fallback", name=fallback_name)
            
            experiences = raw_data.get("experiences", [])
            
            total_skills = sum(
                sum(len(v) for v in e.get("skills", {}).values() if isinstance(v, list))
                for e in experiences if isinstance(e, dict)
            )
            
            total_companies = (
                sum(1 for e in experiences if e.get("company_name")) +
                sum(1 for e in experiences if e.get("vendor_consulting_firm")) +
                sum(len(e.get("client_projects", [])) for e in experiences if isinstance(e, dict))
            )
            
            logger.info(
                "llm_extraction_validation",
                candidate=raw_data.get("full_name"),
                experiences=len(experiences),
                total_skills=total_skills,
                total_companies=total_companies
            )
            
            if total_skills < 10:
                logger.error("ALERT_FEW_SKILLS", count=total_skills)
            if total_companies < 3:
                logger.error("ALERT_FEW_COMPANIES", count=total_companies)
            
        except Exception as e:
            logger.error("llm_extraction_failed", error=str(e))
            raise ValueError(f"Failed to parse: {e}")
        
        global_products = self._extract_products_globally(text)
        
        for exp in raw_data.get("experiences", []):
            if not exp.get("products"):
                exp["products"] = sorted(global_products)
        
        try:
            raw_data = classify_and_filter(raw_data)
            logger.info("companies_classified", sha256=sha256)
        except Exception as e:
            logger.error("classification_failed", error=str(e))
        
        try:
            raw_data = self._fix_summary_years_safely(raw_data)
        except Exception as e:
            logger.error("summary_fix_failed", error=str(e))
        
        try:
            raw_data = self._coerce_data_types(raw_data)
            logger.info("data_types_coerced", sha256=sha256)
        except Exception as e:
            logger.error("type_coercion_failed", error=str(e))
            raise ValueError(f"Failed to coerce types: {e}")
        
        try:
            normalized = apply_normalization_rules(raw_data)
            logger.info("normalization_applied", sha256=sha256)
        except Exception as e:
            logger.error("normalization_failed", error=str(e))
            raise ValueError(f"Failed to normalize: {e}")
        
        normalized['sha256'] = sha256
        normalized['raw_text_ref'] = f"resumes/{sha256}/{filename}"
        
        try:
            profile = CandidateProfile.model_validate(normalized)
        except Exception as e:
            logger.error("validation_failed", error=str(e), sha256=sha256)
            raise ValueError(f"Failed to validate: {e}")
        
        logger.info(
            "parse_completed",
            candidate=profile.full_name,
            sfdc_years=profile.sfdc_years,
            total_companies=len(profile.companies_summary.vendors) + len(profile.companies_summary.clients) if profile.companies_summary else 0,
            sha256=sha256
        )
        
        return profile

"""
Main resume parsing service with POST-PARSE VALIDATION.

Adds safety net to catch hallucinated products.
"""

import hashlib
import re
from typing import Optional, List, Any, Set
from app.core.extraction.text_extractor import TextExtractor
from app.core.extraction.llm_client import GPT4oClient
from app.core.extraction.rules import apply_normalization_rules
from app.schemas.candidate import CandidateProfile
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ResumeParser:
    """Main resume parsing service with anti-hallucination validation."""
    
    def __init__(self):
        self.text_extractor = TextExtractor()
        self.llm_client = GPT4oClient()
    
    def _extract_mentioned_products(self, text: str) -> Set[str]:
        """
        Extract all Salesforce/Commerce products explicitly mentioned in text.
        
        This is the safety net to catch hallucinations.
        
        Args:
            text: Resume text
            
        Returns:
            Set of product names found in text
        """
        text_lower = text.lower()
        
        # Product patterns to search for
        product_patterns = {
            "Sales Cloud": [r"sales\s+cloud", r"sfdc\s+sales", r"sales\s+force\s+cloud"],
            "Service Cloud": [r"service\s+cloud"],
            "CPQ": [r"\bcpq\b", r"configure\s+price\s+quote", r"revenue\s+cloud", r"steelbrick"],
            "Marketing Cloud": [r"marketing\s+cloud", r"\bsfmc\b", r"exacttarget"],
            "Experience Cloud": [r"experience\s+cloud", r"community\s+cloud", r"communities"],
            "Financial Services Cloud": [r"financial\s+services\s+cloud", r"\bfsc\b"],
            "Health Cloud": [r"health\s+cloud"],
            "Data Cloud": [r"data\s+cloud"],
            "Commerce Cloud": [r"commerce\s+cloud", r"demandware", r"\bsfcc\b", r"b2c\s+commerce"],
            "Field Service": [r"field\s+service"],
            "Industries Cloud": [r"industries\s+cloud"],
            "Tableau CRM": [r"tableau\s+crm", r"einstein\s+analytics"],
            "Marketing Cloud Account Engagement": [r"pardot", r"marketing\s+cloud\s+account\s+engagement"]
        }
        
        found_products = set()
        
        for product, patterns in product_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    found_products.add(product)
                    break
        
        return found_products
    
    def _validate_products(self, data: dict, source_text: str) -> dict:
        """
        POST-PARSE VALIDATION: Remove hallucinated products.
        
        Safety net based on Hunter's feedback:
        - Only keep products that appear in source text
        - Log removed products for review
        
        Args:
            data: Parsed data from LLM
            source_text: Original resume text
            
        Returns:
            Data with validated products
        """
        mentioned_products = self._extract_mentioned_products(source_text)
        
        logger.info(
            "products_found_in_text",
            products=list(mentioned_products),
            count=len(mentioned_products)
        )
        
        # Validate experience-level products
        for exp in data.get("experiences", []):
            original_products = exp.get("products", [])
            
            if original_products:
                # Keep only products found in source text
                validated_products = [
                    p for p in original_products 
                    if p in mentioned_products
                ]
                
                removed = set(original_products) - set(validated_products)
                
                if removed:
                    logger.warning(
                        "products_removed_hallucination",
                        company=exp.get("company_name") or exp.get("vendor_consulting_firm"),
                        removed=list(removed),
                        kept=validated_products
                    )
                
                exp["products"] = validated_products
            
            # Validate client-level products
            for project in exp.get("client_projects", []):
                original_client_products = project.get("products", [])
                
                if original_client_products:
                    validated_client_products = [
                        p for p in original_client_products 
                        if p in mentioned_products
                    ]
                    
                    removed = set(original_client_products) - set(validated_client_products)
                    
                    if removed:
                        logger.warning(
                            "client_products_removed_hallucination",
                            client=project.get("project_end_client_name"),
                            removed=list(removed),
                            kept=validated_client_products
                        )
                    
                    project["products"] = validated_client_products
        
        return data
    
    def _fix_summary_years(self, data: dict) -> dict:
        """
        Fix summary to match calculated sfdc_years.
        
        If summary says "6 years" but sfdc_years=7, fix it.
        
        Args:
            data: Parsed data
            
        Returns:
            Data with corrected summary
        """
        summary = data.get("candidate_overall_summary", "")
        sfdc_years = data.get("sfdc_years")
        
        if not summary or not sfdc_years:
            return data
        
        # Find year mentions in summary
        year_pattern = r'\b(\d+)\s*years?\b'
        matches = re.findall(year_pattern, summary, re.IGNORECASE)
        
        if matches:
            for match in matches:
                old_years = int(match)
                
                # If mismatch, replace
                if old_years != sfdc_years:
                    logger.warning(
                        "summary_years_mismatch_fixed",
                        summary_said=old_years,
                        calculated=sfdc_years
                    )
                    
                    # Replace old number with correct number
                    summary = re.sub(
                        rf'\b{old_years}\s*years?\b',
                        f'{sfdc_years} years',
                        summary,
                        flags=re.IGNORECASE
                    )
        
        data["candidate_overall_summary"] = summary
        return data
    
    def _coerce_data_types(self, data: dict) -> dict:
        """Coerce data types to match Pydantic schema."""
        # Year fields (int → str)
        if data.get("it_earliest_year") is not None:
            data["it_earliest_year"] = str(data["it_earliest_year"])
        
        if data.get("sfdc_earliest_year") is not None:
            data["sfdc_earliest_year"] = str(data["sfdc_earliest_year"])
        
        # Links field (list → dict or None)
        if "links" in data:
            if isinstance(data["links"], list):
                data["links"] = None if not data["links"] else {}
            elif not isinstance(data["links"], dict) and data["links"] is not None:
                data["links"] = None
        
        # Experiences
        if "experiences" in data:
            cleaned_experiences = []
            
            for exp in data["experiences"]:
                # Coerce dates
                if exp.get("job_start_date") is not None:
                    exp["job_start_date"] = str(exp["job_start_date"])
                if exp.get("job_end_date") is not None:
                    exp["job_end_date"] = str(exp["job_end_date"])
                
                # Clean client projects
                if "client_projects" in exp:
                    valid_projects = []
                    
                    for project in exp["client_projects"]:
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
    
    def _clean_experiences(self, experiences: List[dict]) -> List[dict]:
        """Remove completely empty experiences."""
        cleaned = []
        
        for idx, exp in enumerate(experiences):
            has_any_data = any([
                exp.get("company_name"),
                exp.get("vendor_consulting_firm"),
                exp.get("job_title"),
                exp.get("job_start_date"),
                exp.get("job_end_date"),
                exp.get("products") and len(exp.get("products", [])) > 0,
                exp.get("skills") and len(exp.get("skills", [])) > 0,
                exp.get("client_projects") and len(exp.get("client_projects", [])) > 0
            ])
            
            if not has_any_data:
                logger.warning("experience_skipped_empty", index=idx)
                continue
            
            cleaned.append(exp)
        
        return cleaned
    
    async def parse(
        self,
        file_bytes: bytes,
        filename: str,
        candidate_id: Optional[str] = None
    ) -> CandidateProfile:
        """
        Parse resume with POST-PARSE VALIDATION.
        
        Steps:
        1. Extract text
        2. GPT-4o extraction
        3. POST-PARSE VALIDATION (remove hallucinated products)
        4. Fix summary years mismatch
        5. Coerce data types
        6. Clean experiences
        7. Apply normalization
        8. Validate with Pydantic
        """
        logger.info("parse_started", filename=filename, size_bytes=len(file_bytes))
        
        # Step 1: SHA256
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        logger.info("hash_computed", sha256=sha256)
        
        # Step 2: Extract text
        try:
            text = self.text_extractor.extract(file_bytes, filename)
            logger.info("text_extracted", length=len(text), sha256=sha256)
        except Exception as e:
            logger.error("text_extraction_failed", error=str(e))
            raise ValueError(f"Failed to extract text: {e}")
        
        # Step 3: GPT-4o extraction
        try:
            raw_data = await self.llm_client.extract_resume(text)
            logger.info(
                "llm_extraction_succeeded",
                candidate=raw_data.get("full_name"),
                experiences_count=len(raw_data.get("experiences", []))
            )
        except Exception as e:
            logger.error("llm_extraction_failed", error=str(e))
            raise ValueError(f"Failed to parse with GPT-4o: {e}")
        
        # Step 3.5: POST-PARSE VALIDATION - Remove hallucinated products
        try:
            raw_data = self._validate_products(raw_data, text)
            logger.info("products_validated", sha256=sha256)
        except Exception as e:
            logger.error("product_validation_failed", error=str(e))
            # Continue anyway - validation is safety net
        
        # Step 3.6: Fix summary years mismatch
        try:
            raw_data = self._fix_summary_years(raw_data)
            logger.info("summary_years_fixed", sha256=sha256)
        except Exception as e:
            logger.error("summary_fix_failed", error=str(e))
        
        # Step 4: Coerce data types
        try:
            raw_data = self._coerce_data_types(raw_data)
            logger.info("data_types_coerced", sha256=sha256)
        except Exception as e:
            logger.error("type_coercion_failed", error=str(e))
            raise ValueError(f"Failed to coerce types: {e}")
        
        # Step 5: Clean experiences
        if "experiences" in raw_data:
            original_count = len(raw_data["experiences"])
            raw_data["experiences"] = self._clean_experiences(raw_data["experiences"])
            cleaned_count = len(raw_data["experiences"])
            
            if original_count != cleaned_count:
                logger.info(
                    "experiences_cleaned",
                    original=original_count,
                    cleaned=cleaned_count,
                    removed=original_count - cleaned_count
                )
        
        # Step 6: Apply normalization
        try:
            normalized = apply_normalization_rules(raw_data)
            logger.info("normalization_applied", sha256=sha256)
        except Exception as e:
            logger.error("normalization_failed", error=str(e))
            raise ValueError(f"Failed to normalize: {e}")
        
        # Step 7: Add metadata
        normalized['sha256'] = sha256
        normalized['raw_text_ref'] = f"resumes/{sha256}/{filename}"
        
        # Step 8: Validate with Pydantic
        try:
            profile = CandidateProfile.model_validate(normalized)
        except Exception as e:
            logger.error("validation_failed", error=str(e), sha256=sha256)
            raise ValueError(f"Failed to validate: {e}")
        
        # Log final metrics
        total_employers = sum(
            1 for exp in profile.experiences 
            if exp.company_name or exp.vendor_consulting_firm
        )
        total_clients = sum(len(exp.client_projects) for exp in profile.experiences)
        total_products = sum(
            len(exp.products) + sum(len(p.products) for p in exp.client_projects)
            for exp in profile.experiences
        )
        
        logger.info(
            "parse_completed",
            candidate=profile.full_name,
            sfdc_years=profile.sfdc_years,
            employers=total_employers,
            clients=total_clients,
            products_total=total_products,
            sha256=sha256
        )
        
        return profile
    
    def calculate_cost_estimate(self, text_length: int) -> float:
        """Estimate parsing cost."""
        input_tokens = text_length // 4
        output_tokens = input_tokens // 2
        
        input_cost = (input_tokens / 1_000_000) * 2.50
        output_cost = (output_tokens / 1_000_000) * 10.00
        
        return round(input_cost + output_cost, 4)

"""
API routes for resume parsing and matching.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import structlog

from app.core.extraction.resume_parser import ResumeParser
from app.schemas.candidate import CandidateProfile
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter()

# Dependency: Get parser instance
def get_parser() -> ResumeParser:
    return ResumeParser()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Status of the service
    """
    return {
        "status": "operational",
        "model": settings.llm_model,
        "version": "1.0.0"
    }


@router.post("/parse/resume", response_model=CandidateProfile)
async def parse_resume(
    file: UploadFile = File(...),
    parser: ResumeParser = Depends(get_parser)
):
    """
    Parse resume and return structured candidate profile.
    
    - Works with ANY resume format (PDF or DOCX)
    - Correctly calculates SFDC years (across entire resume)
    - Summarizes entire career (not per-page)
    - Extracts client projects with products (for lead generation)
    - Handles vendor vs company separation
    
    Supported formats:
    - PDF (.pdf)
    - Word (.docx, .doc)
    
    Time: 2-4 seconds per resume
    
    Args:
        file: Uploaded resume file
        
    Returns:
        Structured candidate profile with:
        - Basic info (name, emails, location)
        - Work experiences with client projects
        - Skills and certifications
        - Salesforce years calculation
        - Overall career summary
        
    Raises:
        400: Invalid file format or parsing error
        500: Internal server error
    """
    logger.info(
        "parse_request_received",
        filename=file.filename,
        content_type=file.content_type
    )
    
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    ext = file.filename.lower().split('.')[-1]
    if ext not in ('pdf', 'docx', 'doc'):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Only PDF and DOCX supported."
        )
    
    try:
        # Read file
        contents = await file.read()
        
        # Parse
        profile = await parser.parse(contents, file.filename)
        
        # Log success
        logger.info(
            "parse_successful",
            filename=file.filename,
            candidate=profile.full_name,
            clients_extracted=sum(len(exp.client_projects) for exp in profile.experiences)
        )
        
        return profile
        
    except ValueError as e:
        logger.error("parse_failed_validation", error=str(e), filename=file.filename)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("parse_failed_server", error=str(e), filename=file.filename, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during parsing")


@router.post("/parse/batch", response_model=List[CandidateProfile])
async def parse_batch(
    files: List[UploadFile] = File(...),
    parser: ResumeParser = Depends(get_parser)
):
    """
    Parse multiple resumes in batch.
    
    Useful for testing or onboarding multiple candidates.
    
    Args:
        files: List of resume files
        
    Returns:
        List of candidate profiles
    """
    logger.info("batch_parse_started", count=len(files))
    
    results = []
    errors = []
    
    for file in files:
        try:
            contents = await file.read()
            profile = await parser.parse(contents, file.filename)
            results.append(profile)
        except Exception as e:
            logger.error("batch_parse_file_failed", filename=file.filename, error=str(e))
            errors.append({"filename": file.filename, "error": str(e)})
    
    logger.info(
        "batch_parse_completed",
        total=len(files),
        successful=len(results),
        failed=len(errors)
    )
    
    if errors:
        logger.warning("batch_parse_had_errors", errors=errors)
    
    return results


@router.get("/cost/estimate")
async def estimate_cost(
    file_size_kb: int,
    num_resumes: int = 1
):
    """
    Estimate parsing cost.
    
    Args:
        file_size_kb: Average file size in KB
        num_resumes: Number of resumes to parse
        
    Returns:
        Cost estimate
    """
    # Rough estimate: 1KB ≈ 250 characters
    text_length = file_size_kb * 1000
    
    parser = ResumeParser()
    cost_per_resume = parser.calculate_cost_estimate(text_length)
    total_cost = cost_per_resume * num_resumes
    
    return {
        "cost_per_resume_usd": cost_per_resume,
        "total_cost_usd": total_cost,
        "num_resumes": num_resumes,
        "estimated_tokens": text_length // 4
    }

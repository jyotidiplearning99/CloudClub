"""
Cloud Club AI - Resume Parser POC
Main FastAPI application.


"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import structlog

from app.config import get_settings
from app.api.routes import router
from app.utils.logger import setup_logging, get_logger

settings = get_settings()

# Setup structured logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Cloud Club AI - Resume Parser POC",
    version="1.0.0",
    description="""
    State-of-the-art resume parsing using GPT-4o.
    
   
    
    ### ✅ Solves Document AI Limitations:
    - **Handles ANY resume format** - Not just well-formatted PDFs
    - **SFDC years calculated correctly** - Across entire resume (not per-page like Document AI)
    - **Entire career summary** - Not per-page summaries (Document AI bug)
    - **Vendor vs company separation** - Understands context automatically
    
    ### 💰 Cost Effective:
    - ~$0.025 per resume (25% cheaper than target)
    - Parse-once, use forever (cached by SHA256)
    
    ### 🎯 Business Model Support:
    - Extracts clients with their Salesforce products
    - Creates leads in Salesforce with product tags
    - Enables direct marketing to extracted companies
    
    ## Endpoints
    
    - **POST /api/v1/parse/resume** - Parse a single resume
    - **POST /api/v1/parse/batch** - Parse multiple resumes
    - **GET /api/v1/health** - Health check
    - **GET /api/v1/cost/estimate** - Estimate parsing cost
    - **GET /ui** - Web interface for testing
    - **GET /docs** - Interactive API documentation (Swagger)
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Parsing",
            "description": "Resume parsing operations"
        },
        {
            "name": "Health",
            "description": "Health check and status"
        }
    ]
)

# CORS middleware (configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web UI
try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    logger.info("static_files_mounted", directory="app/static")
except Exception as e:
    logger.warning("static_files_not_mounted", error=str(e))

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """
    Startup event handler.
    
    Logs application configuration and checks dependencies.
    """
    logger.info(
        "application_starting",
        model=settings.llm_model,
        max_resume_length=settings.max_resume_length,
        environment="production" if not settings.debug else "development"
    )
    
    # Check if OpenAI API key is configured
    if not settings.openai_api_key or settings.openai_api_key == "sk-proj-key-here":
        logger.error("openai_api_key_not_configured", 
                    message="Please set OPENAI_API_KEY in .env file")
    else:
        logger.info("openai_api_key_configured", key_prefix=settings.openai_api_key[:20])


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("application_shutting_down")


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information.
    
    Returns:
        dict: API metadata and available endpoints
    """
    return {
        "name": "Cloud Club AI - Resume Parser POC",
        "version": "1.0.0",
        "description": "GPT-4o powered resume parsing",
        "status": "operational",
        "model": settings.llm_model,
        "endpoints": {
            "ui": "GET /ui (Web interface for testing)",
            "parse_resume": "POST /api/v1/parse/resume",
            "parse_batch": "POST /api/v1/parse/batch",
            "health": "GET /api/v1/health",
            "cost_estimate": "GET /api/v1/cost/estimate",
            "docs": "GET /docs (Interactive API documentation)"
        },
        "features": [
            "Handles any resume format (PDF, DOCX)",
            "Client product extraction for lead generation"
        ],
        "key_improvements_over_document_ai": [
            "No manual labeling required (56 labels eliminated)",
            "Works with poorly formatted resumes",
            "Context-aware extraction (understands consulting vs direct)",
            "Calculates years across entire resume (not per-page)",
            "Summarizes entire career (not per-page)",
            "Full code control (not canned Google product)"
        ]
    }


@app.get("/ui", tags=["UI"], include_in_schema=False)
async def serve_ui():
    """
    Serve the web UI for testing resume parsing.
    
    This provides a drag-and-drop interface for:
    - Uploading resumes (PDF/DOCX)
    - Viewing parsed results
    - Inspecting client projects (for lead generation)
    - Seeing SFDC years calculation
    - Downloading raw JSON
    
    Returns:
        FileResponse: HTML page with embedded JavaScript UI
    """
    try:
        return FileResponse("app/static/index.html")
    except FileNotFoundError:
        logger.error("ui_file_not_found", path="app/static/index.html")
        return JSONResponse(
            status_code=404,
            content={
                "detail": "UI not found. Make sure app/static/index.html exists.",
                "help": "Create the file using the instructions provided."
            }
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled errors.
    
    Args:
        request: FastAPI request object
        exc: Exception that was raised
        
    Returns:
        JSONResponse: Error response with 500 status code
    """
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
            "path": request.url.path
        }
    )


# Health check for load balancers / monitoring
@app.get("/ping", tags=["Health"], include_in_schema=False)
async def ping():
    """Simple ping endpoint for monitoring."""
    return {"status": "ok"}


# For debugging (only in development)
if settings.debug:
    @app.get("/debug/config", tags=["Debug"], include_in_schema=False)
    async def debug_config():
        """Show current configuration (debug only)."""
        return {
            "llm_model": settings.llm_model,
            "max_resume_length": settings.max_resume_length,
            "llm_temperature": settings.llm_temperature,
            "llm_max_tokens": settings.llm_max_tokens,
            "api_key_configured": bool(settings.openai_api_key),
            "environment": "development"
        }

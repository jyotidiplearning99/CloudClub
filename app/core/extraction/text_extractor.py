"""
Extract text from PDF and DOCX files.
"""

import io
from pdfminer.high_level import extract_text as pdf_extract
from docx import Document
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TextExtractor:
    """Extract text from various document formats."""
    
    @staticmethod
    def extract_from_pdf(file_bytes: bytes) -> str:
        """
        Extract text from PDF file.
        
        Args:
            file_bytes: Raw PDF bytes
            
        Returns:
            Extracted text
        """
        try:
            text = pdf_extract(io.BytesIO(file_bytes))
            logger.info("pdf_extracted", length=len(text))
            return text.strip()
        except Exception as e:
            logger.error("pdf_extraction_failed", error=str(e))
            raise ValueError(f"Failed to extract PDF: {e}")
    
    @staticmethod
    def extract_from_docx(file_bytes: bytes) -> str:
        """
        Extract text from DOCX file.
        
        Args:
            file_bytes: Raw DOCX bytes
            
        Returns:
            Extracted text
        """
        try:
            doc = Document(io.BytesIO(file_bytes))
            paragraphs = [para.text for para in doc.paragraphs]
            text = "\n".join(paragraphs)
            logger.info("docx_extracted", length=len(text), paragraphs=len(paragraphs))
            return text.strip()
        except Exception as e:
            logger.error("docx_extraction_failed", error=str(e))
            raise ValueError(f"Failed to extract DOCX: {e}")
    
    @staticmethod
    def extract(file_bytes: bytes, filename: str) -> str:
        """
        Auto-detect format and extract text.
        
        Args:
            file_bytes: Raw file bytes
            filename: Original filename (for extension detection)
            
        Returns:
            Extracted text
        """
        ext = filename.lower().split('.')[-1]
        
        if ext == 'pdf':
            return TextExtractor.extract_from_pdf(file_bytes)
        elif ext in ('docx', 'doc'):
            return TextExtractor.extract_from_docx(file_bytes)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Only PDF and DOCX supported.")

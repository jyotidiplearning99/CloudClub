"""
Extract text from PDF and DOCX files with improved DOCX handling.
"""

import io
from pdfminer.high_level import extract_text as pdf_extract
from docx import Document
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TextExtractor:
    """Extract text from various document formats."""
    
    def extract(self, file_bytes: bytes, filename: str) -> str:
        """
        Auto-detect format and extract text with better DOCX support.
        
        Args:
            file_bytes: Raw file bytes
            filename: Original filename (for extension detection)
            
        Returns:
            Extracted text
        """
        ext = filename.lower().split('.')[-1]
        
        if ext == 'pdf':
            return self._extract_pdf(file_bytes)
        elif ext in ('docx', 'doc'):
            return self._extract_docx_better(file_bytes)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Only PDF and DOCX supported.")
    
    def _extract_pdf(self, file_bytes: bytes) -> str:
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
    
    def _extract_docx_better(self, file_bytes: bytes) -> str:
        """
        Better DOCX extraction preserving structure.
        
        Args:
            file_bytes: Raw DOCX bytes
            
        Returns:
            Extracted text
        """
        try:
            doc = Document(io.BytesIO(file_bytes))
            
            text_parts = []
            
            # Extract paragraphs with better formatting
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text.strip())
            
            # Extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = ' | '.join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        text_parts.append(row_text)
            
            text = '\n'.join(text_parts)
            logger.info("docx_extracted", length=len(text), paragraphs=len(doc.paragraphs))
            return text.strip()
        except Exception as e:
            logger.error("docx_extraction_failed", error=str(e))
            raise ValueError(f"Failed to extract DOCX: {e}")
    
    # Keep backward compatibility with static methods
    @staticmethod
    def extract_from_pdf(file_bytes: bytes) -> str:
        """Legacy method - use instance method instead."""
        extractor = TextExtractor()
        return extractor._extract_pdf(file_bytes)
    
    @staticmethod
    def extract_from_docx(file_bytes: bytes) -> str:
        """Legacy method - use instance method instead."""
        extractor = TextExtractor()
        return extractor._extract_docx_better(file_bytes)

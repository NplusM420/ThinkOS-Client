"""PDF processor service for multi-modal memory.

Processes PDF files to extract text content and generate thumbnails.
"""

import io
import logging
from pathlib import Path

from .attachment_storage import AttachmentMetadata, get_attachment_storage

logger = logging.getLogger(__name__)

# PDF MIME type
PDF_MIME_TYPE = "application/pdf"

# Thumbnail settings
THUMBNAIL_DPI = 72
THUMBNAIL_SIZE = (256, 256)


async def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text content from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text content
    """
    text_parts = []
    
    # Try PyMuPDF (fitz) first - fastest and most reliable
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
        doc.close()
        
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        logger.info("PyMuPDF not installed, trying alternative")
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed: {e}")
    
    # Try pdfplumber as fallback
    try:
        import pdfplumber
        
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text and text.strip():
                    text_parts.append(f"--- Page {i + 1} ---\n{text}")
        
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        logger.info("pdfplumber not installed, trying alternative")
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed: {e}")
    
    # Try PyPDF2 as last resort
    try:
        from PyPDF2 import PdfReader
        
        reader = PdfReader(pdf_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                text_parts.append(f"--- Page {i + 1} ---\n{text}")
        
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        logger.warning("No PDF library available (PyMuPDF, pdfplumber, or PyPDF2)")
    except Exception as e:
        logger.warning(f"PyPDF2 extraction failed: {e}")
    
    return ""


async def generate_pdf_thumbnail(pdf_path: Path, output_path: Path) -> bool:
    """Generate a thumbnail from the first page of a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        output_path: Path for thumbnail output
        
    Returns:
        True if successful, False otherwise
    """
    # Try PyMuPDF first
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        if len(doc) > 0:
            page = doc[0]
            # Render at low DPI for thumbnail
            mat = fitz.Matrix(THUMBNAIL_DPI / 72, THUMBNAIL_DPI / 72)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL for resizing
            from PIL import Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            img.save(output_path, "JPEG", quality=85)
            
            doc.close()
            logger.info(f"Generated PDF thumbnail: {output_path}")
            return True
        doc.close()
    except ImportError:
        logger.info("PyMuPDF not installed, skipping PDF thumbnail")
    except Exception as e:
        logger.warning(f"Failed to generate PDF thumbnail: {e}")
    
    # Try pdf2image as fallback
    try:
        from pdf2image import convert_from_path
        from PIL import Image
        
        images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=THUMBNAIL_DPI)
        if images:
            img = images[0]
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            img.save(output_path, "JPEG", quality=85)
            logger.info(f"Generated PDF thumbnail: {output_path}")
            return True
    except ImportError:
        logger.info("pdf2image not installed, skipping PDF thumbnail")
    except Exception as e:
        logger.warning(f"Failed to generate PDF thumbnail with pdf2image: {e}")
    
    return False


async def get_pdf_page_count(pdf_path: Path) -> int | None:
    """Get the number of pages in a PDF.
    
    Returns:
        Page count or None if failed
    """
    try:
        import fitz
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to get page count with PyMuPDF: {e}")
    
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to get page count with PyPDF2: {e}")
    
    return None


async def process_pdf(attachment: AttachmentMetadata) -> AttachmentMetadata:
    """Process a PDF attachment.
    
    Extracts text and generates thumbnail.
    
    Args:
        attachment: The attachment metadata
        
    Returns:
        Updated attachment metadata
    """
    storage = get_attachment_storage()
    pdf_path = Path(attachment.storage_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Extract text
    try:
        text = await extract_text_from_pdf(pdf_path)
        if text:
            attachment.extracted_text = text
            logger.info(f"Extracted {len(text)} chars from PDF {attachment.id}")
    except Exception as e:
        logger.error(f"Failed to extract PDF text: {e}")
    
    # Generate thumbnail
    thumb_path = storage.get_thumbnail_path(attachment.id)
    if await generate_pdf_thumbnail(pdf_path, thumb_path):
        attachment.thumbnail_path = str(thumb_path)
    
    # Get page count for description
    page_count = await get_pdf_page_count(pdf_path)
    if page_count:
        attachment.description = f"PDF document with {page_count} page{'s' if page_count != 1 else ''}"
    
    return attachment


def is_pdf(mime_type: str) -> bool:
    """Check if a MIME type is PDF."""
    return mime_type == PDF_MIME_TYPE

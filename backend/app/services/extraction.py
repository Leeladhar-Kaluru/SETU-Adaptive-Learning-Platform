import os
import io
import pymupdf as fitz
from typing import List, Dict, Any, Optional

try:
    import docx
except ImportError:
    docx = None

try:
    import pptx
except ImportError:
    pptx = None

class ExtractionService:
    def extract_document(self, file_bytes: bytes, filename: str, mime_type: str) -> List[Dict[str, Any]]:
        """
        Extracts structured page-level text and metadata from supported formats:
        PDF, DOCX, PPTX, TXT, MD, JPG, PNG.
        Enforces page awareness, quality indicators, and scanned/OCR detection.
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        pages: List[Dict[str, Any]] = []

        if ext == "pdf" or "pdf" in mime_type:
            pages = self._extract_pdf(file_bytes)
        elif ext == "docx" or "wordprocessingml" in mime_type:
            pages = self._extract_docx(file_bytes)
        elif ext == "pptx" or "presentationml" in mime_type:
            pages = self._extract_pptx(file_bytes)
        elif ext in ("txt", "md") or "text" in mime_type:
            pages = self._extract_text(file_bytes, filename)
        elif ext in ("jpg", "jpeg", "png") or "image" in mime_type:
            pages = self._extract_image_stub(file_bytes, filename)
        else:
            # Fallback to text decode attempt
            pages = self._extract_text(file_bytes, filename)

        return pages

    def _extract_pdf(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages: List[Dict[str, Any]] = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            images = page.get_images()
            char_count = len(text)
            words = text.split()
            word_count = len(words)
            
            # Scanned detection: few characters but has image drawings
            is_scanned = (char_count < 40 and len(images) > 0)
            quality = "low" if is_scanned else ("medium" if char_count < 100 else "high")

            pages.append({
                "page_number": page_num + 1,
                "text": text if text else "[Image-only or empty page; OCR indexing required]",
                "char_count": char_count,
                "word_count": word_count,
                "is_scanned_ocr_needed": is_scanned,
                "extraction_quality": quality,
                "metadata": {
                    "has_images": len(images) > 0,
                    "image_count": len(images),
                    "rect": [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1]
                }
            })
        doc.close()
        return pages

    def _extract_docx(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        if not docx:
            return [{"page_number": 1, "text": "DOCX extractor unavailable", "char_count": 0, "word_count": 0, "is_scanned_ocr_needed": False, "extraction_quality": "low", "metadata": {}}]
        
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n\n".join(paragraphs)
        
        # Word docs do not have native fixed pages; partition into logical pages (~400 words per page)
        words = full_text.split()
        page_size = 400
        pages: List[Dict[str, Any]] = []
        for i in range(0, max(len(words), 1), page_size):
            chunk_words = words[i:i + page_size]
            page_text = " ".join(chunk_words)
            pages.append({
                "page_number": (i // page_size) + 1,
                "text": page_text,
                "char_count": len(page_text),
                "word_count": len(chunk_words),
                "is_scanned_ocr_needed": False,
                "extraction_quality": "high",
                "metadata": {"format": "docx"}
            })
        return pages

    def _extract_pptx(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        if not pptx:
            return [{"page_number": 1, "text": "PPTX extractor unavailable", "char_count": 0, "word_count": 0, "is_scanned_ocr_needed": False, "extraction_quality": "low", "metadata": {}}]
        
        prs = pptx.Presentation(io.BytesIO(file_bytes))
        pages: List[Dict[str, Any]] = []
        for idx, slide in enumerate(prs.slides):
            slide_texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        if paragraph.text.strip():
                            slide_texts.append(paragraph.text.strip())
            
            text = "\n".join(slide_texts).strip()
            pages.append({
                "page_number": idx + 1,
                "text": text if text else "[Visual Slide without text]",
                "char_count": len(text),
                "word_count": len(text.split()),
                "is_scanned_ocr_needed": len(text) < 10,
                "extraction_quality": "high" if len(text) >= 10 else "medium",
                "metadata": {"format": "pptx", "slide_number": idx + 1}
            })
        return pages

    def _extract_text(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        try:
            content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = file_bytes.decode("latin-1", errors="replace")

        # Partition text into ~400 word pages
        words = content.split()
        page_size = 400
        pages: List[Dict[str, Any]] = []
        for i in range(0, max(len(words), 1), page_size):
            chunk_words = words[i:i + page_size]
            page_text = " ".join(chunk_words)
            pages.append({
                "page_number": (i // page_size) + 1,
                "text": page_text,
                "char_count": len(page_text),
                "word_count": len(chunk_words),
                "is_scanned_ocr_needed": False,
                "extraction_quality": "high",
                "metadata": {"format": "plain_text"}
            })
        return pages

    def _extract_image_stub(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        return [{
            "page_number": 1,
            "text": f"[Uploaded Image File: {filename} • OCR text extraction scheduled]",
            "char_count": len(file_bytes),
            "word_count": 0,
            "is_scanned_ocr_needed": True,
            "extraction_quality": "medium",
            "metadata": {"format": "image", "size_bytes": len(file_bytes)}
        }]

extraction_service = ExtractionService()

import io
import os
import unicodedata
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

# Symbol ranges that indicate corrupted font encoding
_DINGBAT_RANGES = [
    (0x2600, 0x27FF),   # Misc symbols, dingbats
    (0x2B00, 0x2BFF),   # Misc symbols and arrows
    (0xFB00, 0xFFFD),   # Specials, variation selectors
    (0xE000, 0xF8FF),   # Private use area (custom font glyphs)
]


class ExtractionService:
    """
    Page-aware document extraction with corruption detection and integrated Tesseract OCR.
    Supports PDF (digital + selective OCR for scanned/corrupted pages), DOCX, PPTX, TXT, MD, images.
    Documents up to 50MB and 300–500 pages are efficiently extracted.
    """

    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidate = os.path.join(base_dir, "tessdata")
        if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "eng.traineddata")):
            self.tessdata_path = candidate
        elif os.environ.get("TESSDATA_PREFIX") and os.path.exists(os.path.join(os.environ["TESSDATA_PREFIX"], "eng.traineddata")):
            self.tessdata_path = os.environ["TESSDATA_PREFIX"]
        else:
            self.tessdata_path = None

    def extract_document(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        progress_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        pages: List[Dict[str, Any]] = []

        if ext == "pdf" or "pdf" in mime_type:
            pages = self._extract_pdf(file_bytes, progress_callback)
        elif ext == "docx" or "wordprocessingml" in mime_type:
            pages = self._extract_docx(file_bytes)
        elif ext in ("pptx", "ppt") or "presentationml" in mime_type:
            pages = self._extract_pptx(file_bytes)
        elif ext in ("txt", "md") or "text" in mime_type:
            pages = self._extract_text(file_bytes, filename)
        elif ext in ("jpg", "jpeg", "png") or "image" in mime_type:
            pages = self._extract_image_stub(file_bytes, filename)
        else:
            pages = self._extract_text(file_bytes, filename)

        for page in pages:
            text = (page.get("text") or "").replace("\x00", "")
            # Decorative title fonts (e.g. NCERT chapter headers) sometimes encode
            # Latin letters in the Private Use Area: U+F04C == 'L'. Map them back.
            text = "".join(
                chr(ord(ch) - 0xF000) if 0xF000 <= ord(ch) <= 0xF0FF else ch
                for ch in text
            )
            page["text"] = text
            page["char_count"] = len(text)
            page["word_count"] = len(text.split()) if text else 0
        return pages

    # ------------------------------------------------------------------
    # Quality / corruption detection
    # ------------------------------------------------------------------

    def _is_corrupted_text(self, text: str, char_count: int) -> bool:
        """
        Returns True if text has a high density of non-printable or symbol characters
        indicating corrupted PDF font encoding (the ✙❡♠ problem).
        A clean page from an NCERT textbook scores > 90% printable ASCII + Devanagari.
        """
        if not text or char_count < 10:
            return False

        printable = 0
        symbol_hits = 0
        for ch in text:
            cp = ord(ch)
            # Accept printable ASCII
            if 0x20 <= cp <= 0x7E:
                printable += 1
                continue
            # Accept common Indian scripts: Devanagari, Telugu, Kannada, Tamil, Malayalam, Bengali, Gujarati, Gurmukhi
            if any(lo <= cp <= hi for lo, hi in [
                (0x0900, 0x097F), (0x0980, 0x09FF), (0x0A00, 0x0A7F),
                (0x0A80, 0x0AFF), (0x0B00, 0x0B7F), (0x0B80, 0x0BFF),
                (0x0C00, 0x0C7F), (0x0C80, 0x0CFF),
            ]):
                printable += 1
                continue
            # Accept whitespace and common punctuation
            if ch in '\n\r\t\u2019\u2018\u201c\u201d\u2013\u2014\u00B0\u00B2\u00B3':
                printable += 1
                continue
            # Check against dingbat/symbol ranges
            if any(lo <= cp <= hi for lo, hi in _DINGBAT_RANGES):
                symbol_hits += 1

        printable_ratio = printable / char_count
        symbol_ratio = symbol_hits / char_count

        # Corrupted if: less than 40% printable chars on a substantive page
        if char_count > 80 and printable_ratio < 0.40:
            return True
        # Corrupted if: > 12% dingbats/symbols
        if char_count > 40 and symbol_ratio > 0.12:
            return True
        return False

    # ------------------------------------------------------------------
    # Per-format extractors
    # ------------------------------------------------------------------

    def _extract_pdf(self, file_bytes: bytes, progress_callback: Optional[Any] = None) -> List[Dict[str, Any]]:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages: List[Dict[str, Any]] = []
        total_pages = len(doc)

        for page_num in range(total_pages):
            if progress_callback and (page_num % 10 == 0 or page_num == total_pages - 1):
                try:
                    progress_callback(page_num + 1, total_pages, f"Processing page {page_num + 1}/{total_pages}")
                except Exception:
                    pass

            page = doc[page_num]
            text = page.get_text("text").strip()
            images = page.get_images()
            char_count = len(text)

            is_scanned = char_count < 40 and len(images) > 0
            is_corrupted = not is_scanned and self._is_corrupted_text(text, char_count)
            needs_ocr = is_scanned or is_corrupted
            ocr_used = False

            if needs_ocr and self.tessdata_path:
                try:
                    # Pass full=True to avoid partial_ocr annotation hang
                    tp = page.get_textpage_ocr(full=True, tessdata=self.tessdata_path, language="eng", dpi=100)
                    ocr_text = tp.extractText().strip()
                    ocr_len = len(ocr_text)
                    if ocr_len >= 20 and not self._is_corrupted_text(ocr_text, ocr_len):
                        text = ocr_text
                        char_count = ocr_len
                        needs_ocr = False
                        is_scanned = False
                        is_corrupted = False
                        ocr_used = True
                except Exception:
                    # Fallback to pixmap OCR if get_textpage_ocr fails
                    try:
                        pix = page.get_pixmap(dpi=100)
                        ocr_bytes = pix.pdfocr_tobytes(language="eng", tessdata=self.tessdata_path)
                        ocr_doc = fitz.open("pdf", ocr_bytes)
                        ocr_text = ocr_doc[0].get_text().strip()
                        ocr_len = len(ocr_text)
                        if ocr_len >= 20 and not self._is_corrupted_text(ocr_text, ocr_len):
                            text = ocr_text
                            char_count = ocr_len
                            needs_ocr = False
                            is_scanned = False
                            is_corrupted = False
                            ocr_used = True
                    except Exception:
                        pass

            if needs_ocr:
                # OCR failed or was unavailable: never substitute placeholder text for real content.
                display_text = ""
                char_count = 0
                quality = "low"
            else:
                display_text = text
                quality = "high" if char_count >= 100 else "medium"

            # Extract diagrams from textbook page if present
            page_diagrams = []
            if images:
                for img_idx, img_info in enumerate(images[:2]):
                    xref = img_info[0]
                    try:
                        base_img = doc.extract_image(xref)
                        w = base_img.get("width", 0)
                        h = base_img.get("height", 0)
                        img_bytes = base_img.get("image")
                        ext = base_img.get("ext", "png")
                        if w >= 120 and h >= 80 and img_bytes:
                            page_diagrams.append({
                                "index": img_idx,
                                "width": w,
                                "height": h,
                                "format": ext,
                                "bytes": img_bytes,
                            })
                    except Exception:
                        pass

            pages.append({
                "page_number": page_num + 1,
                "text": display_text,
                "char_count": char_count,
                "word_count": len(display_text.split()) if display_text else 0,
                "is_scanned_ocr_needed": needs_ocr,
                "extraction_quality": quality,
                "diagrams": page_diagrams,
                "metadata": {
                    "has_images": len(images) > 0,
                    "image_count": len(images),
                    "is_corrupted": is_corrupted,
                    "ocr_applied": ocr_used,
                    "rect": [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1],
                },
            })
        doc.close()
        return pages

    def _extract_docx(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        if not docx:
            raise RuntimeError("DOCX extraction is unavailable on this worker.")
        
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
            raise RuntimeError("PPTX extraction is unavailable on this worker.")
        
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
            has_text = bool(text)
            pages.append({
                "page_number": idx + 1,
                "text": text,
                "char_count": len(text),
                "word_count": len(text.split()),
                "is_scanned_ocr_needed": not has_text,
                "extraction_quality": ("high" if len(text) >= 10 else "medium") if has_text else "low",
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
        if self.tessdata_path:
            try:
                img_doc = fitz.open()
                pix = fitz.Pixmap(file_bytes)
                page = img_doc.new_page(width=pix.width, height=pix.height)
                page.insert_image(page.rect, stream=file_bytes)
                tp = page.get_textpage_ocr(tessdata=self.tessdata_path, language="eng", dpi=150)
                ocr_text = tp.extractText().strip()
                img_doc.close()
                if len(ocr_text) >= 15:
                    return [{
                        "page_number": 1,
                        "text": ocr_text,
                        "char_count": len(ocr_text),
                        "word_count": len(ocr_text.split()),
                        "is_scanned_ocr_needed": False,
                        "extraction_quality": "high",
                        "metadata": {"format": "image_ocr", "size_bytes": len(file_bytes)}
                    }]
            except Exception:
                pass

        return [{
            "page_number": 1,
            "text": "",
            "char_count": 0,
            "word_count": 0,
            "is_scanned_ocr_needed": True,
            "extraction_quality": "low",
            "metadata": {"format": "image", "size_bytes": len(file_bytes)}
        }]

extraction_service = ExtractionService()

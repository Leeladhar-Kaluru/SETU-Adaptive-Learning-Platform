import pytest
import io
import fitz
from app.services.extraction import extraction_service

def test_extract_pdf_pages():
    # Create an in-memory 2-page PDF
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 50), "Chapter 5: The Fundamental Unit of Life. Every living organism is made of cells.")
    p2 = doc.new_page()
    p2.insert_text((50, 50), "5.2 What is a Cell Made Up of? The plasma membrane is selectively permeable.")
    pdf_bytes = doc.write()
    doc.close()

    pages = extraction_service.extract_document(pdf_bytes, "test_chapter.pdf", "application/pdf")
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "Fundamental Unit" in pages[0]["text"]
    assert pages[1]["page_number"] == 2
    assert "selectively permeable" in pages[1]["text"]
    assert pages[0]["is_scanned_ocr_needed"] is False

def test_extract_plain_text():
    text_content = "# Chapter 1: Real Numbers\nNatural numbers, whole numbers, and integers."
    pages = extraction_service.extract_document(text_content.encode("utf-8"), "notes.txt", "text/plain")
    assert len(pages) >= 1
    assert pages[0]["page_number"] == 1
    assert "Real Numbers" in pages[0]["text"]

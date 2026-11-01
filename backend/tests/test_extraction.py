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

def test_extract_strips_nul_bytes():
    pages = extraction_service.extract_document(
        b"Chapter 1\nWater\x00 is a compound.",
        "notes.txt",
        "text/plain",
    )
    assert "\x00" not in pages[0]["text"]
    assert "Water" in pages[0]["text"]


def test_extract_plain_text():
    text_content = "# Chapter 1: Real Numbers\nNatural numbers, whole numbers, and integers."
    pages = extraction_service.extract_document(text_content.encode("utf-8"), "notes.txt", "text/plain")
    assert len(pages) >= 1
    assert pages[0]["page_number"] == 1
    assert "Real Numbers" in pages[0]["text"]


def test_corrupted_symbol_font_detection():
    # Corrupted text filled with dingbats/symbols like ✙❡♠
    corrupted_sample = "✙❡♠✙❡♠" * 60  # 360 chars of dingbats
    is_corrupt = extraction_service._is_corrupted_text(corrupted_sample, len(corrupted_sample))
    assert is_corrupt is True

    clean_sample = "Every living organism is composed of microscopic cells containing organelles."
    is_clean = extraction_service._is_corrupted_text(clean_sample, len(clean_sample))
    assert is_clean is False


def test_tesseract_ocr_on_scanned_image_page():
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (400, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 30), 'SETU Photosynthesis and Respiration Notes', fill=(0, 0, 0))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    png_data = img_bytes.getvalue()

    doc = fitz.open()
    page = doc.new_page(width=400, height=100)
    page.insert_image(page.rect, stream=png_data)
    pdf_bytes = doc.write()
    doc.close()

    pages = extraction_service.extract_document(pdf_bytes, "scanned_notes.pdf", "application/pdf")
    assert len(pages) == 1
    # Check OCR extracted the text from the rendered image
    extracted = pages[0]["text"]
    assert any(w in extracted for w in ["Photosynthesis", "Respiration", "SETU", "Notes"])
    assert pages[0]["is_scanned_ocr_needed"] is False
    assert pages[0]["extraction_quality"] in ("high", "medium")


def test_large_multipage_document_scaling():
    doc = fitz.open()
    for i in range(1, 351):
        p = doc.new_page()
        if i % 25 == 1:
            p.insert_text((50, 50), f"Chapter {(i // 25) + 1}: Science Unit {(i // 25) + 1}\nIntroductory foundational concept.")
        else:
            p.insert_text((50, 50), f"Page {i} detailed content with scientific vocabulary and experimental observations.")
    pdf_bytes = doc.write()
    doc.close()

    pages = extraction_service.extract_document(pdf_bytes, "ncert_class10_science_full.pdf", "application/pdf")
    assert len(pages) == 350
    assert pages[0]["page_number"] == 1
    assert pages[349]["page_number"] == 350

    from app.services.lesson_generator import lesson_generator_service
    outline = lesson_generator_service.build_outline_from_pages(
        document_title="NCERT Class 10 Science",
        extracted_pages=[{"page_number": p["page_number"], "text": p["text"]} for p in pages],
        grade=10,
        subject="Science"
    )
    assert len(outline["chapters"]) >= 10


def test_extract_pptx_slides():
    import pptx
    prs = pptx.Presentation()
    # Slide 1
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])
    slide1.shapes.title.text = "Chapter 1: Chemical Reactions"
    slide1.shapes.placeholders[1].text = "Introduction to reactants and products in chemical equations."
    # Slide 2
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Types of Chemical Reactions"
    slide2.shapes.placeholders[1].text = "Combination, Decomposition, and Displacement reactions."

    pptx_bytes = io.BytesIO()
    prs.save(pptx_bytes)
    data = pptx_bytes.getvalue()

    pages = extraction_service.extract_document(data, "science_presentation.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "Chemical Reactions" in pages[0]["text"]
    assert pages[1]["page_number"] == 2
    assert "Displacement" in pages[1]["text"]
    assert pages[0]["metadata"]["format"] == "pptx"


def test_extract_uploaded_class10_english_book():
    import os
    pdf_path = r"C:\Users\LEELADHAR\.gemini\antigravity\brain\dac38554-337d-483e-a2ad-8d1bfa0a1d97\.user_uploaded\media_1793199307618_3adadd5d.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("Uploaded English 10th class book not found in test environment.")

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    # Extract first 12 pages containing cover, contents, and Chapter 1 "A Letter to God"
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    sub_doc = fitz.open()
    sub_doc.insert_pdf(doc, from_page=0, to_page=11)
    sub_bytes = sub_doc.write()
    doc.close()
    sub_doc.close()

    pages = extraction_service.extract_document(sub_bytes, "english_10th_class_book.pdf", "application/pdf")
    assert len(pages) == 12
    # Verify cover page was OCR extracted
    cover_text = pages[0]["text"]
    assert any(w in cover_text for w in ["First Flight", "Class X", "English", "Textbook"])

    # Verify Chapter 1 "A Letter to God" by G.L. Fuentes
    story_text = pages[10]["text"]
    assert "Lencho" in story_text
    assert "farmer" in story_text
    assert "letter to god" in story_text.lower()


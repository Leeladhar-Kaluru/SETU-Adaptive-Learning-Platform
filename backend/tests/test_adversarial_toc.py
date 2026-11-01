import json
import os
import sys
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.lesson_generator import lesson_generator_service


def test_empty_pages_raises_value_error():
    with pytest.raises(ValueError, match="no extractable text"):
        lesson_generator_service.build_outline_from_pages("empty.pdf", [], 10, "English")


def test_no_duplicate_prefix_when_toc_title_already_has_chapter_prefix():
    pages = [
        {"page_number": 1, "text": "Contents\nChapter 1: Real Numbers 1\nChapter 2: Polynomials 20\nChapter 3: Linear Equations 40"},
        {"page_number": 2, "text": "Chapter 1: Real Numbers\nBody of chapter 1."},
        {"page_number": 20, "text": "Chapter 2: Polynomials\nBody of chapter 2."},
        {"page_number": 40, "text": "Chapter 3: Linear Equations\nBody of chapter 3."},
        {"page_number": 60, "text": "End of book page 60."},
    ]
    outline = lesson_generator_service.build_outline_from_pages("math.pdf", pages, 10, "Math")
    chapters = outline["chapters"]
    assert len(chapters) == 3
    for idx, ch in enumerate(chapters, 1):
        assert ch["chapterTitle"] not in ("", None)
        assert ch["chapterTitle"].count("Chapter") == 1, f"Duplicate prefix detected in: {ch['chapterTitle']}"
        assert not ch["chapterTitle"].startswith(f"Chapter {idx}: Chapter")


def test_corrupt_character_filtering_in_fallback_headers():
    pages = [
        {"page_number": 1, "text": "Preface and title"},
        {"page_number": 2, "text": "Nk :Xkky\n*Corrupt Header*\nProse body here " * 10},
        {"page_number": 3, "text": "Nk :Xkky\n*Corrupt Header*\nProse body here " * 10},
        {"page_number": 4, "text": "Real Valid Chapter Title\nProse body here " * 10},
        {"page_number": 5, "text": "Real Valid Chapter Title\nProse body here " * 10},
        {"page_number": 6, "text": "Another Valid Chapter Title\nProse body here " * 10},
        {"page_number": 7, "text": "Another Valid Chapter Title\nProse body here " * 10},
    ]
    outline = lesson_generator_service.build_outline_from_pages("book.pdf", pages, 10, "English")
    for ch in outline["chapters"]:
        title = ch["chapterTitle"]
        assert "Nk :Xkky" not in title
        assert "*" not in title
        assert "_" not in title
        assert "[" not in title
        assert "]" not in title


def test_toc_indicator_font_shift_case_insensitivity():
    assert lesson_generator_service._is_toc_indicator(")UTZKTZY")
    assert lesson_generator_service._is_toc_indicator(")utzktzy")
    assert lesson_generator_service._is_toc_indicator("Table of Contents")
    assert lesson_generator_service._is_toc_indicator("INDEX")
    assert lesson_generator_service._is_toc_indicator("CONTENTS")
    assert not lesson_generator_service._is_toc_indicator("Random body line")


def test_two_parts_of_same_title_preserved():
    # E.g. "The Hundred Dresses - I" vs "The Hundred Dresses - II"
    t1 = "The Hundred Dresses - I"
    t2 = "The Hundred Dresses - II"
    # _mergeable_titles should return False so they don't collapse into one
    assert not lesson_generator_service._mergeable_titles(t1, t2), "Roman numeral parts must NOT be mergeable"


def test_first_flight_page_boundary_invariants():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures_first_flight_pages.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        pages = json.load(f)

    outline = lesson_generator_service.build_outline_from_pages("First_Flight.pdf", pages, 10, "English")
    chapters = outline["chapters"]

    assert len(chapters) == 11
    # Check start and end of book
    assert chapters[0]["pageStart"] == 11
    assert chapters[-1]["pageEnd"] == 172

    # Check each chapter start <= end
    for idx, ch in enumerate(chapters):
        assert ch["pageStart"] <= ch["pageEnd"], f"Ch {idx+1} has inverted bounds: {ch['pageStart']} > {ch['pageEnd']}"

    # Check contiguous: pageEnd == next_pageStart - 1
    for i in range(len(chapters) - 1):
        assert chapters[i]["pageEnd"] == chapters[i + 1]["pageStart"] - 1, (
            f"Gap or overlap between Ch {i+1} (end {chapters[i]['pageEnd']}) "
            f"and Ch {i+2} (start {chapters[i+1]['pageStart']})"
        )

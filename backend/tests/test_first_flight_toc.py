import json
import os
import pytest

from app.services.lesson_generator import lesson_generator_service


@pytest.fixture
def first_flight_pages():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures_first_flight_pages.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_first_flight_toc_parsing_extracts_all_11_chapters(first_flight_pages):
    """Verify TOC font-shift recognition and multi-line parsing extracts all 11 chapters."""
    assert len(first_flight_pages) == 172

    toc_entries = lesson_generator_service._parse_table_of_contents_pages(first_flight_pages)
    assert len(toc_entries) == 11, f"Expected 11 chapters from TOC, got {len(toc_entries)}: {toc_entries}"

    expected_titles = [
        "A Letter to God",
        "Nelson Mandela: Long Walk to Freedom",
        "Two Stories about Flying",
        "From the Diary of Anne Frank",
        "The Hundred Dresses - I",
        "The Hundred Dresses - II",
        "Glimpses of India",
        "Mijbil the Otter",
        "Madam Rides the Bus",
        "The Sermon at Benares",
        "The Proposal",
    ]

    for idx, (entry, expected) in enumerate(zip(toc_entries, expected_titles), 1):
        assert entry["chapterNumber"] == idx
        assert entry["title"] == expected


def test_first_flight_build_outline_from_pages(first_flight_pages):
    """Verify build_outline_from_pages produces clean, complete chapter structure."""
    outline = lesson_generator_service.build_outline_from_pages(
        document_title="First_Flight.pdf",
        extracted_pages=first_flight_pages,
        grade=10,
        subject="English",
    )

    chapters = outline["chapters"]
    assert len(chapters) == 11

    # Verify no corrupted titles
    for ch in chapters:
        title = ch["chapterTitle"]
        assert "Nk :Xkky" not in title
        assert "Xus Znk" not in title
        assert "Rosvyky" not in title
        assert not any(c in title for c in ["*", "_", "[", "]"])

    # Verify exact titles in order
    assert chapters[0]["chapterTitle"] == "Chapter 1: A Letter to God"
    assert chapters[1]["chapterTitle"] == "Chapter 2: Nelson Mandela: Long Walk to Freedom"
    assert chapters[2]["chapterTitle"] == "Chapter 3: Two Stories about Flying"
    assert chapters[3]["chapterTitle"] == "Chapter 4: From the Diary of Anne Frank"
    assert chapters[4]["chapterTitle"] == "Chapter 5: The Hundred Dresses - I"
    assert chapters[5]["chapterTitle"] == "Chapter 6: The Hundred Dresses - II"
    assert chapters[6]["chapterTitle"] == "Chapter 7: Glimpses of India"
    assert chapters[7]["chapterTitle"] == "Chapter 8: Mijbil the Otter"
    assert chapters[8]["chapterTitle"] == "Chapter 9: Madam Rides the Bus"
    assert chapters[9]["chapterTitle"] == "Chapter 10: The Sermon at Benares"
    assert chapters[10]["chapterTitle"] == "Chapter 11: The Proposal"

    # Verify page coverage: contiguous, starting at page 11, ending at page 172
    assert chapters[0]["pageStart"] == 11
    assert chapters[-1]["pageEnd"] == 172
    for i in range(len(chapters) - 1):
        assert chapters[i]["pageEnd"] == chapters[i + 1]["pageStart"] - 1

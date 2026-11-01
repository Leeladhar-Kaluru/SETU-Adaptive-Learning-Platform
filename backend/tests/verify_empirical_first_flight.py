import json
import os
import re
import sys

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.lesson_generator import lesson_generator_service

def run_empirical_verification():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures_first_flight_pages.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        pages = json.load(f)

    print(f"Total pages loaded: {len(pages)}")
    assert len(pages) == 172, f"Expected 172 pages, got {len(pages)}"

    # 1. Parse TOC entries
    toc_entries = lesson_generator_service._parse_table_of_contents_pages(pages)
    print(f"\nTOC entries extracted ({len(toc_entries)}):")
    for e in toc_entries:
        print(f"  Ch {e['chapterNumber']}: '{e['title']}' (print p.{e['printPageStart']}-{e['printPageEnd']}, tocPage={e['tocPage']})")

    # 2. Build full outline
    outline = lesson_generator_service.build_outline_from_pages("First_Flight.pdf", pages, 10, "English")
    chapters = outline["chapters"]
    print(f"\nChapters produced: {len(chapters)}")

    expected_titles = [
        "Chapter 1: A Letter to God",
        "Chapter 2: Nelson Mandela: Long Walk to Freedom",
        "Chapter 3: Two Stories about Flying",
        "Chapter 4: From the Diary of Anne Frank",
        "Chapter 5: The Hundred Dresses - I",
        "Chapter 6: The Hundred Dresses - II",
        "Chapter 7: Glimpses of India",
        "Chapter 8: Mijbil the Otter",
        "Chapter 9: Madam Rides the Bus",
        "Chapter 10: The Sermon at Benares",
        "Chapter 11: The Proposal",
    ]

    corrupt_markers = ["Nk :Xkky", "_", "*", "[", "]"]
    duplicate_prefix_re = re.compile(r"^(?:Chapter\s+\d+[:\s]+){2,}", re.IGNORECASE)

    print("\nDetailed Chapter Verifications:")
    all_titles_match = True
    no_dup_prefixes = True
    no_corrupt_chars = True

    for idx, (ch, exp) in enumerate(zip(chapters, expected_titles)):
        title = ch["chapterTitle"]
        print(f"[{idx+1:02d}] '{title}' | Pages: {ch['pageStart']} -> {ch['pageEnd']}")

        if title != exp:
            print(f"   FAIL: Title mismatch: Expected '{exp}', got '{title}'")
            all_titles_match = False

        if duplicate_prefix_re.search(title) or title.count("Chapter") > 1:
            print(f"   FAIL: Duplicate chapter prefix in '{title}'")
            no_dup_prefixes = False

        for bad in corrupt_markers:
            if bad in title:
                print(f"   FAIL: Corrupt marker '{bad}' found in '{title}'")
                no_corrupt_chars = False

    start_page_11 = (chapters[0]["pageStart"] == 11)
    end_page_172 = (chapters[-1]["pageEnd"] == 172)

    contiguity_ok = True
    for i in range(len(chapters) - 1):
        cur_end = chapters[i]["pageEnd"]
        next_start = chapters[i+1]["pageStart"]
        if cur_end != next_start - 1:
            print(f"   FAIL Contiguity gap between ch {i+1} (end {cur_end}) and ch {i+2} (start {next_start})")
            contiguity_ok = False

    print("\n--- EMPIRICAL VERIFICATION REPORT ---")
    print(f"1. Exactly 11 chapters: {len(chapters) == 11} (Count: {len(chapters)})")
    print(f"2. All 11 titles match dispatch requirements exactly: {all_titles_match}")
    print(f"3. No duplicate chapter prefixes: {no_dup_prefixes}")
    print(f"4. No corrupted characters (Nk :Xkky, _, *, [, ]): {no_corrupt_chars}")
    print(f"5. Chapter 1 starts at page 11: {start_page_11} (Actual: {chapters[0]['pageStart']})")
    print(f"6. Chapter 11 ends at page 172: {end_page_172} (Actual: {chapters[-1]['pageEnd']})")
    print(f"7. Contiguous page boundaries (pageEnd == next_pageStart - 1): {contiguity_ok}")

    all_passed = (
        len(chapters) == 11
        and all_titles_match
        and no_dup_prefixes
        and no_corrupt_chars
        and start_page_11
        and end_page_172
        and contiguity_ok
    )
    print(f"\nALL CRITICAL CHECKS PASSED: {all_passed}")
    return all_passed

if __name__ == "__main__":
    success = run_empirical_verification()
    sys.exit(0 if success else 1)

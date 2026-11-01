import os
import json
import re
import datetime
import difflib
import jsonschema
from collections import Counter
from typing import Dict, Any, List, Optional
from app.core.ai_provider import ai_provider
from app.services.text_sanitize import sanitize_tree

# Load schemas
_curr = os.path.dirname(os.path.abspath(__file__))
# Check root or parent
SCHEMA_DIR = os.path.abspath(os.path.join(_curr, "..", "..", "..", "SETU_V2_Research_Pack", "schemas"))
if not os.path.exists(SCHEMA_DIR):
    SCHEMA_DIR = os.path.abspath(os.path.join(_curr, "..", "..", "SETU_V2_Research_Pack", "schemas"))

LESSON_SCHEMA_PATH = os.path.join(SCHEMA_DIR, "lesson-package.schema.json")
VISUAL_SCHEMA_PATH = os.path.join(SCHEMA_DIR, "visual-spec.schema.json")

with open(LESSON_SCHEMA_PATH, "r", encoding="utf-8") as f:
    LESSON_PACKAGE_SCHEMA = json.load(f)

with open(VISUAL_SCHEMA_PATH, "r", encoding="utf-8") as f:
    VISUAL_SPEC_SCHEMA = json.load(f)

_HEADING = re.compile(
    r"^(chapter\b|unit\b|section\b|lesson\b|#{1,3}\s+|\d{1,2}(?:\.\d{1,2}){0,2}[.)]?\s+\S)",
    re.IGNORECASE,
)
_CHAPTER_MARKER = re.compile(
    r"^(chapter|unit)\s*([0-9oOilvxIVX](?:[\s.]*[0-9oOilvxIVX]){0,2})?\s*([:.\-\u2013|])?\s*(.*)$",
    re.IGNORECASE,
)
_ROMAN_NUMERALS = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
    "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12, "xiii": 13,
    "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19,
    "xx": 20, "xxi": 21, "xxii": 22, "xxiii": 23, "xxiv": 24,
}
_MARKER_SCAN_DEPTH = 30
_TITLE_CONNECTORS = {"and", "of", "the", "a", "an", "in", "on", "for", "to", "with", "or", "its"}
_SENTENCE_STARTERS = {
    "in", "the", "this", "some", "looking", "as", "a", "an", "when", "where",
    "why", "how", "what", "it", "we", "you", "there", "these", "those", "if",
    "consider", "suppose", "imagine", "observe", "figure", "table", "activity",
}
_SECTION_HEADING = re.compile(
    r"^(\d{1,2}(?:\.\d{1,2}){1,2})[.)]?\s+(.{3,110})$"
)
_SENTENCE_STOPWORDS = (
    " we ", " you ", " your ", " this chapter ", " in this ", " previous chapter ",
    " have learnt ", " have seen ", " have studied ", " you will ", " we will ",
    " for example ", " let us ", " consider the ", " what happens ", " do we ",
    " can you ", " why do ", " how do ", " it is ", " there are ", " these are ",
)

# Page furniture that repeats on many pages but is never a chapter title.
_NON_TITLE_HEADERS = {
    "try these", "do this", "think discuss and write", "exercise", "exercises",
    "let's work these out", "let us do", "activity", "activities", "glossary",
    "answers", "answer key", "appendix", "worksheet", "index", "contents",
    "note", "notes", "summary", "key points", "do you know",
    "what have we discussed", "learning further", "keywords", "reprint",
    "free distribution", "free distribution by", "government of", "scert", "ncert",
    "academic standards", "our national anthem", "national anthem", "pledge",
    "constitution of india", "preamble", "foreword", "preface",
}
_NON_TITLE_WORDS = {
    "notes", "solution", "example", "exercise", "exercises", "activity",
    "activities", "glossary", "summary", "appendix", "index", "fig", "figure",
    "table", "step", "statement", "therefore", "chapter", "unit", "section",
    "lesson", "answers", "answer", "note", "worksheet", "contents",
    "distribution", "preface", "foreword", "preamble", "anthem", "pledge",
}

_VISUAL_TYPES = {
    "number_line", "fraction_model", "algebra_balance", "coordinate_grid",
    "bar_chart", "line_chart", "geometry_diagram", "science_process",
    "timeline", "concept_map", "labelled_image", "table",
}
_GRADABLE_QUESTION_TYPES = {"multiple_choice", "numeric", "short_text"}
_QUESTION_TYPE_ALIASES = {
    "mcq": "multiple_choice",
    "multiple-choice": "multiple_choice",
    "multiplechoice": "multiple_choice",
    "fill_in_the_blank": "short_text",
    "fill_in_blank": "short_text",
    "fill-in-the-blank": "short_text",
    "short_answer": "short_text",
    "short-answer": "short_text",
    "text": "short_text",
    "true_false": "multiple_choice",
    "true/false": "multiple_choice",
    "numerical": "numeric",
    "number": "numeric",
}
_QUESTION_TYPE_ENUM = {
    "multiple_choice", "numeric", "short_text", "matching", "ordering",
    "diagram_label", "open_response",
}
_DIFFICULTY_ENUM = {"introductory", "standard", "challenge"}


def text_value(value: Any) -> str:
    """Coerce model output into a safe display string.

    This lives at module scope because both the normaliser and the generation
    entry point need it. It previously lived inside ``_normalise_package``, so
    ``generate_lesson_package`` raised ``NameError: text_value`` for every job.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "content", "body", "label"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value).strip()


class LessonGeneratorService:
    def build_outline_from_pages(
        self,
        document_title: str,
        extracted_pages: List[Dict[str, Any]],
        grade: int,
        subject: str,
    ) -> Dict[str, Any]:
        """Build chapter-sized sections from the document's own structure.

        Preference order:
        1. Running headers (a repeated book label plus a changing title), which
           clean textbooks use on every spread.
        2. Explicit chapter/unit markers.
        3. Numbered section headings.

        The result is always tied to page ranges in the extracted text; no
        chapter names are invented.
        """
        pages = []
        for page in extracted_pages:
            text = (page.get("text") or "").strip()
            if not text or text.startswith("[Image-only or empty page"):
                continue
            pages.append({"page_number": page.get("page_number") or 1, "text": text})
        if not pages:
            raise ValueError("This document has no extractable text to build a learning path.")

        page_by_number = {page["page_number"]: page for page in pages}

        # 1. Authoritative Table of Contents / Index detection
        toc_entries = self._parse_table_of_contents_pages(pages)
        sections: List[Dict[str, Any]] = []
        if len(toc_entries) >= 2:
            sections = self._toc_sections(toc_entries, pages, page_by_number)

        # 2. Fallback to running headers and chapter markers if no TOC
        if not sections:
            header_sections = self._running_header_sections(pages, page_by_number)
            marker_sections = self._chapter_marker_sections(pages, page_by_number)
            if marker_sections:
                # Marker sections carry the full opening-page title, so they win ties
                # over truncated running-header titles. Header runs that a chapter
                # marker falls inside are spanning multiple chapters; runs wholly
                # inside one marker-bounded range are redundant when they repeat the
                # marker's title, and single-word or two-page runs inside a range
                # are vertical-title art or section furniture, not chapters.
                first_marker_start = min(m["pageStart"] for m in marker_sections)
                marker_starts = sorted(m["pageStart"] for m in marker_sections)
                marker_ranges = [
                    (
                        marker_starts[i],
                        (marker_starts[i + 1] - 1) if i + 1 < len(marker_starts)
                        else (pages[-1]["page_number"] if pages else marker_starts[i]),
                    )
                    for i in range(len(marker_starts))
                ]
                marker_titles = [m.get("title") for m in marker_sections if m.get("title")]
                kept_headers = []
                for header in header_sections:
                    start = header["pageStart"]
                    end = max(header.get("pageEnd") or start, start)
                    if start < first_marker_start - 2:
                        continue
                    if any(start <= marker_start < end for marker_start in marker_starts):
                        continue
                    if marker_titles and any(
                        self._similar_titles(header["title"], title)
                        for title in marker_titles
                    ):
                        continue
                    if header.get("pageCount", 99) < 2:
                        # A title that repeats on a single page is vertical art on
                        # an opener, not a running header.
                        continue
                    if len((header.get("title") or "").split()) == 1 and any(
                        range_start <= start and end <= range_end
                        for range_start, range_end in marker_ranges
                    ):
                        continue
                    if any(
                        range_start <= start and end <= range_end
                        for range_start, range_end in marker_ranges
                    ) and self._title_is_section_heading(
                        page_by_number, start, end, header["title"]
                    ):
                        # A numbered section heading ("3.3 Loans from
                        # Cooperatives") repeated as a page header is not a chapter.
                        continue
                    kept_headers.append(header)
                header_sections = kept_headers
            sections = marker_sections + header_sections
            if len(sections) < 2:
                heading_sections = self._section_heading_sections(pages)
                if heading_sections:
                    sections = heading_sections
            if not sections:
                first = pages[0]
                sections = [{
                    "title": self._first_line(first["text"]),
                    "pageStart": first["page_number"],
                    "pageEnd": first["page_number"],
                }]

        # 3. If single chapter or short document (< 3 sections), expand into structured sub-lessons
        if len(sections) < 3:
            sections = self._expand_chapter_subsections(sections, pages, page_by_number)

        sections = self._finalise_sections(sections, pages)

        title = document_title.rsplit(".", 1)[0].replace("_", " ")
        return {
            "title": title,
            "grade": grade,
            "subject": subject,
            "chapters": sections,
        }

    # ------------------------------------------------------------------
    # Structure detection
    # ------------------------------------------------------------------

    def _is_furniture(self, title: str) -> bool:
        lower = (title or "").lower().strip()
        if not lower:
            return True
        normalised = re.sub(r"[^a-z0-9 ]+", " ", lower)
        normalised = re.sub(r"\s+", " ", normalised).strip()
        if any(
            normalised == bad or normalised.startswith(bad + " ")
            for bad in _NON_TITLE_HEADERS
        ):
            return True
        if len(re.findall(r"\d", lower)) >= 4:
            # Year/edition stamps like "Reprint2024-25" are furniture.
            return True
        return any(word in _NON_TITLE_WORDS for word in lower.split())

    def _clean_toc_title(self, title: str) -> str:
        t = (title or "").replace("\ufffd", "-").replace("\u2013", "-").replace("\u2014", "-")
        t = re.sub(r":([A-Za-z])", r": \1", t)
        t = re.sub(r"\s*-\s*(I|II|III|IV|V|VI)\b", r" - \1", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _is_toc_indicator(self, line: str) -> bool:
        clean = (line or "").strip()
        if re.search(r"\b(contents|table of contents|index)\b|\)?UTZKTZY", clean, re.IGNORECASE):
            return True
        return False

    def _parse_table_of_contents_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract authoritative chapters and printed page numbers from Table of Contents / Index."""
        single_line_re = re.compile(
            r"^(?:(?:chapter|unit|lesson)\s+)?(\d{1,2})[\s.:\-]+([A-Za-z][A-Za-z0-9\s,\-–:()?'’\"\ufffd]+?)\s*[\.…_—\-\s]*\s+(\d{1,4})(?:\s*-\s*\d{1,4})?$",
            re.IGNORECASE,
        )
        month_names = {
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        }
        entries = []
        in_toc = False
        last_toc_page_num = 0

        for page in pages[:18]:
            text = page.get("text", "")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            page_num = page.get("page_number", 0)

            is_toc = any(
                self._is_toc_indicator(l)
                for l in lines[:8]
            )
            if not is_toc and any(
                re.search(r"\bpart\s*-\s*[iIvVxX0-9]+\b", l, re.IGNORECASE)
                for l in lines[:8]
            ):
                is_toc = True

            # Check if this page is a direct continuation of a multi-page TOC (e.g., First Flight Page 10)
            if not is_toc and in_toc and (page_num == last_toc_page_num + 1):
                if any(
                    re.match(r"^(?:(?:chapter|unit|lesson)\s+)?\d{1,2}[\s.:\-]+", l, re.IGNORECASE)
                    or re.match(r"^\d{1,2}\.$", l)
                    for l in lines[:8]
                ):
                    is_toc = True

            if not is_toc:
                in_toc = False
                continue

            in_toc = True
            last_toc_page_num = page_num

            i = 0
            while i < len(lines):
                line = lines[i]

                # Pattern 1: Single-line entry
                m = single_line_re.match(line)
                if m:
                    ch_num, ch_title, p_start = m.groups()
                    clean_title = self._clean_toc_title(ch_title)
                    if clean_title and not clean_title.lower().startswith("page"):
                        entries.append({
                            "chapterNumber": int(ch_num),
                            "title": clean_title,
                            "printPageStart": int(p_start),
                            "printPageEnd": int(p_start),
                            "tocPage": page_num,
                        })
                    i += 1
                    continue

                # Pattern 2: Multi-line entry (title on line i, page on line i+1)
                m_ch = re.match(
                    r"^(?:(?:chapter|unit|lesson)\s+)?(\d{1,2})[\s.:\-]+([A-Za-z][A-Za-z0-9\s,\-–—:()?'’\"\ufffd]+)$",
                    line,
                    re.IGNORECASE,
                )
                if m_ch and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    pm = re.match(r"^(\d{1,4})(?:\s*-\s*(\d{1,4}))?$", next_line)
                    if pm:
                        ch_num = int(m_ch.group(1))
                        clean_title = self._clean_toc_title(m_ch.group(2))
                        p_start = int(pm.group(1))
                        p_end = int(pm.group(2)) if pm.group(2) else p_start
                        if clean_title and not clean_title.lower().startswith("page") and clean_title.lower() not in month_names:
                            entries.append({
                                "chapterNumber": ch_num,
                                "title": clean_title,
                                "printPageStart": p_start,
                                "printPageEnd": p_end,
                                "tocPage": page_num,
                            })
                            i += 2
                            continue

                # Pattern 3: Chapter number alone on line i (e.g. "10.\nThe Sermon at Benares\n133")
                m_num_dot = re.match(r"^(?:(?:chapter|unit|lesson)\s+)?(\d{1,2})\.?$", line, re.IGNORECASE)
                if m_num_dot and i + 2 < len(lines):
                    cand_title = lines[i + 1]
                    cand_page = lines[i + 2]
                    pm = re.match(r"^(\d{1,4})(?:\s*-\s*(\d{1,4}))?$", cand_page)
                    if pm and len(cand_title) >= 3 and not cand_title.isdigit() and cand_title.lower() not in month_names:
                        ch_num = int(m_num_dot.group(1))
                        clean_title = self._clean_toc_title(cand_title)
                        p_start = int(pm.group(1))
                        p_end = int(pm.group(2)) if pm.group(2) else p_start
                        if clean_title and not clean_title.lower().startswith("page"):
                            entries.append({
                                "chapterNumber": ch_num,
                                "title": clean_title,
                                "printPageStart": p_start,
                                "printPageEnd": p_end,
                                "tocPage": page_num,
                            })
                            i += 3
                            continue

                # Pattern 4: Standalone digit chapter number, but must maintain chapter continuity
                if line.isdigit() and 1 <= int(line) <= 60:
                    ch_num = int(line)
                    expected_next = (entries[-1]["chapterNumber"] + 1) if entries else 1
                    if abs(ch_num - expected_next) <= 2:
                        if i + 1 < len(lines):
                            cand_title = lines[i + 1]
                            if (
                                len(cand_title) >= 3
                                and not cand_title.isdigit()
                                and not cand_title.lower().startswith("part")
                                and cand_title.lower() not in month_names
                            ):
                                p_start = None
                                p_end = None
                                offset_used = 1

                                m_embedded = re.search(r"\s+(\d{1,4})\s*-\s*(\d{1,4})$", cand_title)
                                if m_embedded:
                                    p_start = int(m_embedded.group(1))
                                    p_end = int(m_embedded.group(2))
                                    cand_title = cand_title[:m_embedded.start()].strip()
                                else:
                                    for offset in (2, 3, 4):
                                        if i + offset < len(lines):
                                            cand_p = lines[i + offset]
                                            pm = re.match(r"^(\d{1,4})(?:\s*-\s*(\d{1,4}))?$", cand_p)
                                            if pm:
                                                p_start = int(pm.group(1))
                                                p_end = int(pm.group(2)) if pm.group(2) else p_start
                                                offset_used = offset
                                                break
                                if p_start is not None:
                                    clean_t = self._clean_toc_title(cand_title)
                                    entries.append({
                                        "chapterNumber": ch_num,
                                        "title": clean_t,
                                        "printPageStart": p_start,
                                        "printPageEnd": p_end or p_start,
                                        "tocPage": page_num,
                                    })
                                    i += offset_used + 1
                                    continue
                i += 1

        seen = set()
        deduped = []
        for e in entries:
            if e["chapterNumber"] not in seen:
                seen.add(e["chapterNumber"])
                deduped.append(e)
        return sorted(deduped, key=lambda x: x["chapterNumber"])

    def _toc_sections(
        self,
        toc_entries: List[Dict[str, Any]],
        pages: List[Dict[str, Any]],
        page_by_number: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Map Table of Contents entries to PDF page coordinates."""
        if not toc_entries:
            return []

        first_ch = toc_entries[0]
        first_ch_num = first_ch.get("chapterNumber", 1)
        first_print_page = first_ch.get("printPageStart", 1)
        first_title_words = [
            w.lower() for w in re.sub(r"[^a-zA-Z0-9\s]", "", first_ch.get("title", "")).split()
            if len(w) > 3 and w.lower() not in _NON_TITLE_WORDS
        ]

        last_toc_page = max(
            [p["page_number"] for p in pages[:18] if any(
                self._is_toc_indicator(l) for l in self._page_lines(p["text"])[:8]
            )] + [e.get("tocPage", 1) for e in toc_entries],
            default=1,
        )

        ch1_pdf_page = None
        for p in pages:
            p_num = p["page_number"]
            if p_num <= last_toc_page:
                continue
            if p_num > last_toc_page + 30:
                break
            top_lines = " ".join(self._page_lines(p["text"])[:8]).lower()
            if f"chapter{first_ch_num}" in top_lines or f"chapter {first_ch_num}" in top_lines:
                ch1_pdf_page = p_num
                break
            if first_title_words and all(w in top_lines for w in first_title_words[:2]):
                ch1_pdf_page = p_num
                break

        if ch1_pdf_page is not None:
            offset = ch1_pdf_page - first_print_page
        else:
            offset = max(0, (last_toc_page + 1) - first_print_page)

        total_pages = pages[-1]["page_number"]
        sections: List[Dict[str, Any]] = []
        for i, entry in enumerate(toc_entries):
            p_start = max(1, min(total_pages, entry["printPageStart"] + offset))
            p_end = max(p_start, min(total_pages, entry.get("printPageEnd", entry["printPageStart"]) + offset))
            t = entry["title"].strip()
            t = re.sub(r"^(?:chapter|unit|lesson)\s*\d+[\s:.-]*", "", t, flags=re.IGNORECASE).strip()
            sections.append({
                "title": t,
                "pageStart": p_start,
                "pageEnd": p_end,
                "source": "toc",
            })
        return sections

    def _expand_chapter_subsections(
        self,
        sections: List[Dict[str, Any]],
        pages: List[Dict[str, Any]],
        page_by_number: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """If document has fewer than 3 sections, break down into structured sub-lessons."""
        if len(sections) >= 3 or not sections:
            return sections

        expanded: List[Dict[str, Any]] = []
        for sec in sections:
            start = sec["pageStart"]
            end = sec.get("pageEnd", start)
            sec_pages = [p for p in pages if start <= p["page_number"] <= end]

            subsections = []
            seen_subs = set()
            for p in sec_pages:
                for line in self._page_lines(p["text"])[:30]:
                    m = _SECTION_HEADING.match(line)
                    if m:
                        sub_num, sub_title = m.groups()
                        sub_title = self._clean_title_fragment(sub_title)
                        if sub_title and len(sub_title) >= 4 and not self._is_furniture(sub_title):
                            k = sub_title.lower()
                            if k not in seen_subs:
                                seen_subs.add(k)
                                subsections.append({
                                    "title": f"{sub_num} {sub_title}",
                                    "pageStart": p["page_number"],
                                    "source": "subsection",
                                })

            if len(subsections) >= 2:
                for idx, sub in enumerate(subsections):
                    if idx + 1 < len(subsections):
                        sub["pageEnd"] = max(sub["pageStart"], subsections[idx + 1]["pageStart"] - 1)
                    else:
                        sub["pageEnd"] = end
                expanded.extend(subsections)
            elif len(sec_pages) >= 4:
                base_title = sec["title"]
                total_p = len(sec_pages)
                p1_end = sec_pages[max(0, int(total_p * 0.33) - 1)]["page_number"]
                p2_start = p1_end + 1
                p2_end = sec_pages[max(0, int(total_p * 0.67) - 1)]["page_number"]
                p3_start = p2_end + 1
                p3_end = sec_pages[-1]["page_number"]

                expanded.append({
                    "title": f"{base_title}: Foundations & Core Concepts",
                    "pageStart": start,
                    "pageEnd": p1_end,
                    "source": "pedagogical_split",
                })
                expanded.append({
                    "title": f"{base_title}: In-Depth Principles & Mechanisms",
                    "pageStart": p2_start,
                    "pageEnd": p2_end,
                    "source": "pedagogical_split",
                })
                expanded.append({
                    "title": f"{base_title}: Practical Applications & Problem Solving",
                    "pageStart": p3_start,
                    "pageEnd": p3_end,
                    "source": "pedagogical_split",
                })
            else:
                expanded.append(sec)

        return expanded if expanded else sections

    def _page_lines(self, text: str) -> List[str]:
        return [
            " ".join(raw.split())
            for raw in (text or "").splitlines()
            if raw.strip()
        ]

    def _running_header_sections(
        self,
        pages: List[Dict[str, Any]],
        page_by_number: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect chapters from repeated page-header lines."""
        if len(pages) < 4:
            return []

        _is_furniture = self._is_furniture

        def _candidates(text: str) -> List[str]:
            out: List[str] = []
            for raw in self._page_lines(text)[:3]:
                if raw.isdigit():
                    continue
                cleaned = self._clean_title_fragment(raw)
                if not cleaned or len(cleaned) < 3 or len(cleaned) > 60:
                    continue
                if len(re.findall(r"[A-Za-z]", cleaned)) < 4:
                    continue
                if "|" in cleaned:
                    continue
                if any(char in cleaned for char in ["*", "_", "[", "]", "{", "}", "\\", "/"]):
                    continue
                if re.search(r"[:;,]\S", cleaned):
                    continue
                if _is_furniture(cleaned):
                    continue
                out.append(cleaned)
            return out

        counter: Counter = Counter()
        for page in pages:
            for cand in _candidates(page["text"]):
                counter[cand] += 1
        if not counter:
            return []

        label, label_count = counter.most_common(1)[0]
        if label_count < max(4, int(len(pages) * 0.15)):
            label = None

        per_page: Dict[int, Optional[str]] = {}
        for page in pages:
            page_cands = _candidates(page["text"])
            header: Optional[str] = None
            for cand in page_cands:
                if label and cand == label:
                    continue
                if counter[cand] < 2:
                    continue
                if _is_furniture(cand):
                    continue
                if not self._is_title_like(cand):
                    continue
                header = cand
                break
            if header is None and label:
                follower = self._header_title(page["text"], label)
                if (
                    follower
                    and counter.get(follower, 0) >= 2
                    and self._is_title_like(follower)
                    and not _is_furniture(follower)
                ):
                    header = follower
            per_page[page["page_number"]] = header

        runs: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for page in pages:
            header = per_page.get(page["page_number"])
            if header is None:
                if current is not None:
                    current["lastHeader"] = page["page_number"]
                continue
            if current is None or not self._similar_titles(current["title"], header):
                if current is not None:
                    runs.append(current)
                current = {
                    "title": header,
                    "firstHeader": page["page_number"],
                    "lastHeader": page["page_number"],
                    "pageCount": 1,
                }
            else:
                current["lastHeader"] = page["page_number"]
                current["pageCount"] = current.get("pageCount", 1) + 1
        if current is not None:
            runs.append(current)

        first_chapter_page: Optional[int] = None
        for page in pages:
            marker = self._marker_line(page["text"])
            if marker and marker.get("number") is not None:
                first_chapter_page = page["page_number"]
                break
        if first_chapter_page is not None:
            # Front matter also carries the book label; only headers at or
            # after the first numbered chapter belong to the course outline.
            runs = [run for run in runs if run["lastHeader"] >= first_chapter_page]
        runs = [run for run in runs if not _is_furniture(run["title"])]
        runs = [run for run in runs if run["lastHeader"] > run["firstHeader"]]
        if len(runs) < 2:
            return []

        sections: List[Dict[str, Any]] = []
        for index, run in enumerate(runs):
            chapter_number = index + 1
            start = max(1, run["firstHeader"] - 1)
            title = run["title"]
            chosen: Optional[int] = None
            for candidate in range(max(1, run["firstHeader"] - 3), run["firstHeader"] + 2):
                page = page_by_number.get(candidate)
                if not page:
                    continue
                if self._section_heading_number(page["text"]) == chapter_number:
                    chosen = candidate
                    break
            if chosen is None:
                for candidate in range(max(1, run["firstHeader"] - 3), run["firstHeader"] + 2):
                    page = page_by_number.get(candidate)
                    if not page:
                        continue
                    if self._marker_line(page["text"]):
                        chosen = candidate
                        break
            if chosen is not None:
                start = chosen
                marker_title = self._title_from_marker_page(page_by_number[chosen]["text"])
                if marker_title and self._similar_titles(title, marker_title):
                    # The chapter-opening page usually spells the title more
                    # completely than a running header ("Food Securty").
                    title = marker_title
            if sections and start <= sections[-1]["pageStart"]:
                start = sections[-1]["pageStart"] + 1
            sections.append({
                "title": title,
                "pageStart": start,
                # lastHeader lets the outline builder cut runs that chapter
                # markers prove are spanning multiple chapters.
                "pageEnd": run["lastHeader"],
                "pageCount": run.get("pageCount", 99),
                "source": "header",
            })
        return sections

    def _header_title(self, text: str, label: str) -> Optional[str]:
        lines = self._page_lines(text)
        label_key = label.lower()
        for index, line in enumerate(lines[:8]):
            if line.lower() != label_key:
                continue
            for candidate in lines[index + 1:index + 6]:
                lower = candidate.lower()
                if not candidate or candidate.isdigit():
                    continue
                if lower.startswith("free distribution") or lower == label_key:
                    continue
                if len(candidate) < 4 or len(candidate) > 100:
                    continue
                if not re.search(r"[A-Za-z]", candidate):
                    continue
                cleaned = self._clean_title_fragment(candidate)
                if cleaned:
                    return cleaned
        return None

    def _chapter_marker_sections(
        self,
        pages: List[Dict[str, Any]],
        page_by_number: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        markers: List[Dict[str, Any]] = []
        last_page_number = pages[-1]["page_number"]
        page_span = last_page_number - pages[0]["page_number"]
        for page in pages:
            marker = self._marker_line(page["text"])
            if not marker:
                continue
            marker_lines = [
                line
                for line in self._page_lines(page["text"])[:_MARKER_SCAN_DEPTH]
                if self._marker_line(line)
            ]
            if len(marker_lines) >= 3:
                # A contents page lists every chapter; it is not a chapter start.
                continue
            marker_title = self._title_from_marker_page(page["text"])
            if page_span >= 20 and page["page_number"] >= last_page_number - 2:
                # End-of-book answer keys repeat chapter headings.
                continue
            if not marker.get("rest") and marker.get("number") is None:
                # A bare "Chapter" label with no number nearby is ambiguous
                # (story text, figure art); running headers cover those books.
                continue
            if (
                not marker.get("rest")
                and not marker_title
                and marker.get("line_index", 99) > 3
            ):
                # Title art glued deep in a page is a figure, not an opener;
                # a real opener keeps its label near the top of the page.
                continue
            if not marker_title and marker.get("number") is None:
                continue
            markers.append({
                "page_number": page["page_number"],
                "title": marker_title,
            })
        if not markers:
            return []

        sections: List[Dict[str, Any]] = []
        for index, marker in enumerate(markers):
            end = (
                markers[index + 1]["page_number"] - 1
                if index + 1 < len(markers)
                else last_page_number
            )
            title = marker["title"] or self._fallback_title(pages, marker["page_number"], end)
            if not title:
                continue
            start = marker["page_number"]
            marker_text = (page_by_number.get(start) or {}).get("text") or ""
            if re.search(r"notes for", marker_text, re.IGNORECASE):
                # NCERT chapter PDFs open with a "Notes for the Teacher" page;
                # the chapter itself starts on the next page.
                start += 1
            sections.append({
                "title": title,
                "pageStart": start,
                "pageEnd": marker["page_number"],
                "source": "marker",
            })
        return sections

    def _section_heading_sections(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []
        seen = set()
        for page in pages:
            for line in self._page_lines(page["text"])[:25]:
                match = _SECTION_HEADING.match(line)
                if not match:
                    continue
                title = self._clean_title_fragment(match.group(2))
                if not title or not self._is_title_like(title):
                    continue
                key = title.lower()
                if key in seen:
                    continue
                seen.add(key)
                sections.append({
                    "title": title,
                    "pageStart": page["page_number"],
                    "pageEnd": page["page_number"],
                    "source": "heading",
                })
                break
        return sections

    def _finalise_sections(
        self,
        sections: List[Dict[str, Any]],
        pages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        seen_starts = set()
        for section in sorted(sections, key=lambda item: item["pageStart"]):
            start = int(section["pageStart"])
            if start in seen_starts:
                continue
            seen_starts.add(start)
            cleaned.append({
                "title": (section.get("title") or "").strip(),
                "pageStart": start,
                "pageEnd": start,
                "source": section.get("source") or "unknown",
            })
        if not cleaned:
            return []

        # Merge adjacent sections that are the same chapter split across two
        # header runs (or a marker title plus its truncated running header).
        # Two distinct marker sections never merge: each CHAPTER marker is its
        # own chapter even when titles look alike (e.g. "Science Unit 1/2/3").
        merged: List[Dict[str, Any]] = []
        for section in cleaned:
            previous_is_marker = merged and merged[-1].get("source") == "marker"
            current_is_marker = section.get("source") == "marker"
            previous_is_toc = merged and merged[-1].get("source") == "toc"
            current_is_toc = section.get("source") == "toc"
            if (
                merged
                and self._mergeable_titles(merged[-1]["title"], section["title"])
                and not (previous_is_marker and current_is_marker)
                and not (previous_is_toc and current_is_toc)
            ):
                previous = merged[-1]
                previous_title = previous["title"]
                current_title = section["title"]
                merged[-1] = {
                    "title": (
                        previous_title
                        if len(previous_title.split()) >= len(current_title.split())
                        else current_title
                    ),
                    "pageStart": min(previous["pageStart"], section["pageStart"]),
                    "pageEnd": section["pageStart"],
                    "source": previous.get("source") or section.get("source") or "unknown",
                }
                continue
            merged.append(section)
        cleaned = merged

        if len(cleaned) > 24:
            step = len(cleaned) / 24
            cleaned = [cleaned[min(len(cleaned) - 1, int(index * step))] for index in range(24)]

        last_page = pages[-1]["page_number"]
        for index, section in enumerate(cleaned):
            if index + 1 < len(cleaned):
                section["pageEnd"] = max(section["pageStart"], cleaned[index + 1]["pageStart"] - 1)
            else:
                section["pageEnd"] = max(section["pageStart"], last_page)
            title = section["title"] or f"Section {index + 1}"
            if not re.match(r"^(chapter|unit|section|lesson)\b", title, re.IGNORECASE):
                title = f"Chapter {index + 1}: {title}"
            section["title"] = title[:180]
            section["chapterTitle"] = title[:180]
            section["chapterNumber"] = index + 1
            section["concepts"] = [title[:180]]
        return cleaned

    # ------------------------------------------------------------------
    # Title extraction
    # ------------------------------------------------------------------

    def _marker_line(self, text: str) -> Optional[Dict[str, Any]]:
        lines = self._page_lines(text)[:_MARKER_SCAN_DEPTH]
        for index, line in enumerate(lines):
            match = _CHAPTER_MARKER.match(line.strip())
            if not match:
                continue
            _, raw_number, separator, rest = match.groups()
            rest = (rest or "").strip()
            if rest and not separator and not raw_number:
                # "chapter that should be considered ..." is body text.
                continue
            if rest and not separator and not any(ch.isdigit() for ch in raw_number or ""):
                # "chapter iv" followed directly by prose is not a marker.
                continue
            number = None
            if raw_number:
                digits = re.findall(r"\d+", raw_number)
                if digits:
                    number = int("".join(digits))
                else:
                    number = _ROMAN_NUMERALS.get(raw_number.replace(" ", "").lower())
            glued = bool(raw_number) and (match.start(2) == 0 or not line[match.start(2) - 1].isspace())
            if glued and index > 8:
                # Glued "CHAPTER3" labels deep in a page are figure art
                # (inside exercises and covers), never chapter openers.
                continue
            if not rest and separator and number is None:
                # A sentence wrapping onto a line of its own ("...in this
                # chapter.") is body text, not a chapter opener.
                continue
            if len(rest.split()) > 14:
                cleaned_rest = self._clean_title_fragment(rest)
                if not cleaned_rest or len(cleaned_rest.split()) > 14:
                    continue
                rest = cleaned_rest
            if rest and not self._looks_like_title_fragment(rest):
                continue
            if number is None and not rest and index > 0:
                # NCERT openers print the chapter number on its own line just
                # above a bare "Chapter" label ("4" / "Chapter").
                previous = lines[index - 1].strip()
                if previous.isdigit() and len(previous) <= 3:
                    number = int(previous)
            if number is None and not rest and index + 1 < len(lines):
                # Some title art prints it below ("CHAPTER" / "13").
                following = lines[index + 1].strip()
                if following.isdigit() and len(following) <= 3:
                    number = int(following)
            return {
                "number": number,
                "separator": separator,
                "rest": rest,
                "line_index": index,
                "glued": glued,
            }
        return None

    def _section_heading_number(self, text: str) -> Optional[int]:
        for raw in text.splitlines():
            match = _SECTION_HEADING.match(raw.strip())
            if not match:
                continue
            digits = re.findall(r"\d+", match.group(1))
            if digits:
                return int(digits[0])
        return None

    def _title_from_marker_page(self, text: str) -> Optional[str]:
        lines = self._page_lines(text)
        marker_index = None
        marker = None
        for index, line in enumerate(lines[:_MARKER_SCAN_DEPTH]):
            found = self._marker_line(line)
            if found and found.get("glued") and index > 8:
                continue
            if found:
                marker_index = index
                marker = found
                break
        if marker is None or marker_index is None:
            return None

        rest = marker.get("rest") or ""
        number = marker.get("number")

        if not rest and (number is None or not marker.get("glued")):
            # A bare "Chapter" label sits BELOW the real title in NCERT books
            # ("Mindful Eating: A Path to a Healthy Body" / "3" / "Chapter").
            # The number may have been attached from the line above the label.
            # Story-first openers put body prose ABOVE the title — stop the
            # upward walk at the first body line once a fragment is collected.
            # Glued labels ("CHAPTER1") are the opposite convention: the title
            # follows the label, so they take the fragments path below.
            above: List[str] = []
            for line in reversed(lines[:marker_index]):
                if self._is_noise(line):
                    if not above:
                        continue
                    break
                cleaned = self._clean_title_fragment(line)
                if not cleaned or self._is_body_line(line, has_fragments=bool(above)):
                    if not above:
                        continue
                    break
                above.insert(0, cleaned)
                if len(above) >= 4:
                    break
            if above:
                title = self._merge_fragments(above)
                if self._is_title_like(title):
                    return title
            return None

        fragments: List[str] = []
        if rest and not rest.isdigit():
            cleaned = self._clean_title_fragment(rest)
            if cleaned:
                fragments.append(cleaned)

        for line in lines[marker_index + 1:marker_index + 14]:
            if self._is_noise(line):
                continue
            cleaned = self._clean_title_fragment(line)
            if not cleaned:
                continue
            if self._is_body_line(line, has_fragments=bool(fragments)):
                break
            words = cleaned.split()
            if fragments:
                first_word = words[0].lower() if words else ""
                if first_word in _TITLE_CONNECTORS:
                    if len(words) > 4 or any(char in cleaned for char in ",;") or cleaned.endswith("-"):
                        break
                elif first_word in _SENTENCE_STARTERS:
                    break
                elif len(words) > 6:
                    break
                lower = f" {cleaned.lower()} "
                if any(token in lower for token in (
                    " has ", " have ", " is ", " are ", " was ", " were ",
                    " this ", " that ", " these ", " those ", " many ", " some ",
                )):
                    # A complete title is followed by body prose, not verbs.
                    break
            else:
                if len(words) > 8:
                    break
            fragments.append(cleaned)
            if sum(len(fragment.split()) for fragment in fragments) >= 14:
                break

        if not fragments:
            return None
        title = self._merge_fragments(fragments)
        if not self._is_title_like(title):
            return None
        return title

    def _fallback_title(
        self,
        pages: List[Dict[str, Any]],
        start: int,
        end: int,
    ) -> Optional[str]:
        for page in pages:
            if page["page_number"] < start or page["page_number"] > end:
                continue
            for line in self._page_lines(page["text"])[:25]:
                match = _SECTION_HEADING.match(line)
                if not match:
                    continue
                title = self._clean_title_fragment(match.group(2))
                if title and len(title.split()) >= 2 and self._is_title_like(title):
                    return title
        for page in pages:
            if page["page_number"] != start:
                continue
            for line in self._page_lines(page["text"])[:8]:
                title = self._clean_title_fragment(line)
                if (
                    title
                    and 2 <= len(title.split()) <= 10
                    and not self._is_body_line(line, has_fragments=False)
                ):
                    return title
        return None

    def _clean_title_fragment(self, raw: str) -> str:
        text = (raw or "").replace("\ufffd", " - ").replace("\u2019", "'").replace("\u2018", "'")
        text = re.sub(r"\s+", " ", text).strip()
        if text.lower() in {"scert telangana", "ncert", "not to be republished", "social studies"}:
            return ""
        text = re.sub(r"^[^A-Za-z0-9]+", "", text)
        text = re.sub(r"^exe\s+(?=[A-Z])", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^d\s+(?=[A-Z])", "and ", text)
        text = re.sub(r"^a\s+([A-Z][a-z]+)$", r"\1", text)
        # OCR often splits a title into letters and words: "e Processes".
        text = re.sub(r"^[a-z]\s+(?=[A-Z])", "", text)
        text = re.sub(
            r"^[a-z]{1,4}\s+(?=[A-Z])",
            lambda match: match.group(0) if match.group(0).strip().lower() in _TITLE_CONNECTORS else "",
            text,
        )

        # A noisy page can put an all-caps title and the first sentence on
        # one line. Keep the all-caps title portion only.
        caps = re.match(r"^([A-Z0-9][A-Z0-9 ,'&:.\-]{5,}?)\s+(?=[A-Z][a-z])", text)
        if caps and len(caps.group(1).split()) >= 2:
            text = caps.group(1)

        text = re.sub(r"\s+\d{1,3}[.)]?$", "", text)
        text = re.sub(r"\s+", " ", text).strip(" ,;:-.")
        if not text:
            return ""

        letters = re.findall(r"[A-Za-z]", text)
        if len(letters) >= 6 and text == text.upper():
            small = {"of", "and", "the", "a", "an", "in", "on", "for", "to", "with", "or"}
            words = text.title().split()
            text = " ".join(
                word.lower() if index and word.lower() in small else word
                for index, word in enumerate(words)
            )
        return text[:120]

    def _merge_fragments(self, fragments: List[str]) -> str:
        text = " ".join(fragment for fragment in fragments if fragment)
        text = re.sub(r"\b([A-Z][a-z]{2,})\s+[A-Z]\s+\1\b", r"\1", text)
        text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
        words = text.split()
        if words and len(words) % 2 == 0 and words[: len(words) // 2] == words[len(words) // 2 :]:
            # "Consumer Rights Consumer Rights" — an art line repeated the title.
            text = " ".join(words[: len(words) // 2])
        return re.sub(r"\s+", " ", text).strip(" ,;:-")

    def _is_noise(self, line: str) -> bool:
        compact = " ".join((line or "").split())
        if len(compact) < 3:
            return True
        if len(re.findall(r"[A-Za-z]", compact)) < 3:
            return True
        digit_count = sum(1 for char in compact if char.isdigit())
        if digit_count > len(compact) * 0.4:
            return True
        if re.fullmatch(r"[\W_]+", compact):
            return True
        return False

    def _looks_like_title_fragment(self, line: str) -> bool:
        compact = " ".join((line or "").split())
        if not compact or not re.search(r"[A-Za-z]", compact):
            return False
        if compact[0].islower() and len(compact.split()) >= 4:
            return False
        return True

    def _is_body_line(self, line: str, has_fragments: bool) -> bool:
        compact = " ".join((line or "").split())
        words = compact.split()
        if len(compact) > 130:
            return True
        if compact[:1].islower() and "," in compact:
            # "to the school by the science teacher, Madam Sulekha, to" is
            # story prose, never a title fragment.
            return True
        lower = f" {compact.lower()} "
        if any(stopword in lower for stopword in _SENTENCE_STOPWORDS):
            return True
        if compact.endswith((".", "?", "!")) and len(words) >= 3:
            return True
        if has_fragments and len(words) >= 9:
            return True
        if not has_fragments and len(words) >= 12:
            return True
        if compact[:1].islower() and len(words) >= 4:
            return True
        return False

    def _is_title_like(self, title: str) -> bool:
        compact = " ".join((title or "").split())
        if not compact:
            return False
        words = compact.split()
        if len(words) > 14:
            return False
        if compact.endswith(".") and len(words) >= 4:
            return False
        lower = f" {compact.lower()} "
        if any(stopword in lower for stopword in _SENTENCE_STOPWORDS):
            return False
        if re.search(r"[A-Za-z]\d[A-Za-z]|\d[A-Za-z]", compact):
            return False
        return True

    def _mergeable_titles(self, first: str, second: str) -> bool:
        """True when two adjacent outline entries are the same chapter.

        Requires more than trivial overlap so distinct chapters like
        "Motion" and "Motion and Time" never collapse into one.
        """
        left = re.sub(r"[^a-z0-9 ]", "", (first or "").lower())
        right = re.sub(r"[^a-z0-9 ]", "", (second or "").lower())
        if not left or not right:
            return False
        if left == right:
            return True
        num_left = re.findall(r"\b(i|ii|iii|iv|v|vi|vii|viii|ix|x|1|2|3|4|5|6|7|8|9)\b", left)
        num_right = re.findall(r"\b(i|ii|iii|iv|v|vi|vii|viii|ix|x|1|2|3|4|5|6|7|8|9)\b", right)
        if num_left != num_right:
            return False
        shorter, longer = (left, right) if len(left) < len(right) else (right, left)
        return len(shorter.split()) >= 2 and shorter in longer

    def _title_is_section_heading(
        self,
        page_by_number: Dict[int, Dict[str, Any]],
        start: int,
        end: int,
        title: str,
    ) -> bool:
        """True when the given title is a numbered section heading
        ("3.3 Loans from Cooperatives") inside the page range."""
        key = re.sub(r"[^a-z0-9 ]", "", (title or "").lower()).strip()
        if not key:
            return False
        for page_number in range(start, end + 1):
            page = page_by_number.get(page_number)
            if not page:
                continue
            for line in self._page_lines(page["text"])[:30]:
                match = _SECTION_HEADING.match(line)
                if not match:
                    continue
                heading = self._clean_title_fragment(match.group(2))
                if heading and re.sub(r"[^a-z0-9 ]", "", heading.lower()).strip() == key:
                    return True
        return False

    def _similar_titles(self, first: str, second: str) -> bool:
        left = re.sub(r"[^a-z0-9 ]", "", (first or "").lower())
        right = re.sub(r"[^a-z0-9 ]", "", (second or "").lower())
        if not left or not right:
            return False
        if left == right:
            return True
        if left.startswith(right) or right.startswith(left):
            # A running header is often a truncated chapter title
            # ("Mindful Eating: A Path" vs the full opening-page title).
            return True
        left_tokens = left.split()
        right_tokens = right.split()
        part_tokens = {"i", "ii", "iii", "iv", "v", "vi", "part", "1", "2", "3"}
        left_tail = {token for token in left_tokens[-3:] if token in part_tokens}
        right_tail = {token for token in right_tokens[-3:] if token in part_tokens}
        if left_tail and right_tail and left_tail != right_tail:
            # "Independent India Part I" and "Part II" are different chapters.
            return False
        return difflib.SequenceMatcher(None, left, right).ratio() >= 0.9

    def _heading_for_page(self, text: str) -> Optional[str]:
        for raw in text.splitlines():
            line = raw.strip()
            if 4 <= len(line) <= 120 and _HEADING.match(line):
                return line[:120]
        return None

    def _first_line(self, text: str) -> str:
        for raw in text.splitlines():
            line = " ".join(raw.split())
            if len(line) >= 8:
                return line[:80]
        compact = " ".join(text.split())
        return compact[:80] or "Extracted section"

    def _normalise_package(
        self,
        package: Dict[str, Any],
        *,
        lesson_id: str,
        lesson_title: str,
        path_id: str,
        grade: int,
        subject_id: str,
        language_tag: str = "en-IN",
    ) -> Dict[str, Any]:
        """Normalise model output into the validated schema without inventing facts.

        IDs and container shapes are repaired deterministically. Educational
        content (objectives, explanations, questions, answers) is preserved as
        written by the model; malformed items are dropped, never fabricated.
        """
        if not isinstance(package, dict):
            raise RuntimeError("Lesson generation did not return a JSON object.")

        def string_list(value: Any) -> List[str]:
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, list):
                return []
            return [text_value(item) for item in value if text_value(item)]

        def normalise_question(raw: Any, index: int, fallback_concept: str) -> Optional[Dict[str, Any]]:
            if not isinstance(raw, dict):
                return None
            q = dict(raw)
            prompt = text_value(q.get("prompt"))
            if not prompt:
                return None
            q["prompt"] = prompt

            qtype = str(q.get("type") or "multiple_choice").strip().lower()
            qtype = _QUESTION_TYPE_ALIASES.get(qtype, qtype)
            if qtype not in _QUESTION_TYPE_ENUM:
                return None

            options = q.get("options")
            cleaned_options: List[str] = []
            if isinstance(options, list):
                for option in options:
                    value = text_value(option)
                    if value:
                        cleaned_options.append(value)
            if qtype == "multiple_choice":
                # A choice question without real choices is answerable only as text.
                qtype = "multiple_choice" if len(cleaned_options) >= 2 else "short_text"
            if qtype == "multiple_choice":
                q["options"] = cleaned_options
            else:
                q.pop("options", None)
            q["type"] = qtype

            answer = q.get("answerKey")
            if isinstance(answer, dict):
                if text_value(answer.get("answer")):
                    answer = dict(answer)
                    answer["answer"] = text_value(answer.get("answer"))
                else:
                    accepted = answer.get("acceptedAnswers")
                    if isinstance(accepted, list) and accepted and text_value(accepted[0]):
                        answer = dict(answer)
                        answer["answer"] = text_value(accepted[0])
                    else:
                        return None
            elif isinstance(answer, (int, float, bool)):
                answer = str(answer)
            else:
                answer = text_value(answer)
            if not text_value(answer):
                return None
            q["answerKey"] = answer

            concept_ids = string_list(q.get("conceptIds"))
            q["conceptIds"] = concept_ids or [fallback_concept]

            hints = string_list(q.get("hints"))
            if hints:
                q["hints"] = hints
            else:
                q.pop("hints", None)

            feedback = text_value(q.get("feedback")) or text_value(q.get("explanation"))
            q["feedback"] = feedback[:1000]

            question_id = text_value(q.get("questionId")) or f"q_{index}"
            q["questionId"] = question_id[:100]

            validator = text_value(q.get("validator")).lower()
            if validator not in ("deterministic", "rubric", "llm_assisted_review"):
                validator = "deterministic"
            q["validator"] = validator

            if q.get("difficulty") not in _DIFFICULTY_ENUM:
                q.pop("difficulty", None)
            if not isinstance(q.get("sourceRefs"), list):
                q.pop("sourceRefs", None)

            allowed = {
                "questionId", "type", "prompt", "options", "conceptIds",
                "difficulty", "answerKey", "rubric", "hints", "feedback",
                "sourceRefs", "validator",
            }
            return {key: value for key, value in q.items() if key in allowed}

        def normalise_visual(raw: Any, index: int) -> Optional[Dict[str, Any]]:
            if not isinstance(raw, dict):
                return None
            vtype = str(raw.get("type") or "").strip().lower()
            if vtype not in _VISUAL_TYPES:
                return None

            spec_source = raw.get("spec") if isinstance(raw.get("spec"), dict) else {}
            if isinstance(spec_source.get("data"), dict):
                data = dict(spec_source["data"])
            else:
                reserved = {
                    "schemaVersion", "visualId", "type", "title", "altText",
                    "description", "data", "interactions", "sourceRefs",
                    "rightsMetadataId", "fallbackText",
                }
                data = {
                    key: value
                    for key, value in spec_source.items()
                    if key not in reserved
                }
            if not data and isinstance(raw.get("data"), dict):
                data = dict(raw["data"])
            data = self._normalise_visual_data(vtype, data)
            if not data:
                return None

            title = text_value(raw.get("title")) or text_value(spec_source.get("title"))
            alt_text = text_value(raw.get("altText")) or text_value(spec_source.get("altText"))
            if not alt_text:
                labels: List[str] = []
                for node in data.get("nodes", []) if isinstance(data.get("nodes"), list) else []:
                    if isinstance(node, dict):
                        label = text_value(node.get("label") or node.get("id"))
                        if label:
                            labels.append(label)
                for key in ("steps", "items", "points", "labels", "rows"):
                    values = data.get(key)
                    if isinstance(values, list):
                        for value in values:
                            label = text_value(value)
                            if label:
                                labels.append(label)
                alt_text = f"{vtype.replace('_', ' ').title()}."
                if title:
                    alt_text = f"{vtype.replace('_', ' ').title()}: {title}."
                if labels:
                    alt_text += " Shows " + ", ".join(labels[:6]) + "."
            alt_text = alt_text.strip()[:500]
            if len(alt_text) < 5:
                return None

            visual_id = text_value(raw.get("visualId")) or f"visual_{index}"
            visual_id = visual_id[:100]
            spec: Dict[str, Any] = {
                "schemaVersion": "1.0.0",
                "visualId": visual_id,
                "type": vtype,
                "altText": alt_text,
                "data": data,
            }
            if title:
                spec["title"] = title[:180]
            description = text_value(raw.get("description")) or text_value(spec_source.get("description"))
            if description:
                spec["description"] = description[:1200]
            interactions = raw.get("interactions") or spec_source.get("interactions")
            if isinstance(interactions, list):
                allowed_interactions = {
                    "focus_node", "toggle_label", "reveal_step", "adjust_value",
                    "drag_point", "reset",
                }
                cleaned = [value for value in interactions if value in allowed_interactions]
                if cleaned:
                    spec["interactions"] = cleaned
            refs = raw.get("sourceRefs") or spec_source.get("sourceRefs")
            if isinstance(refs, list) and all(isinstance(item, str) for item in refs):
                spec["sourceRefs"] = refs
            fallback = text_value(raw.get("fallbackText")) or text_value(spec_source.get("fallbackText"))
            if fallback:
                spec["fallbackText"] = fallback[:2000]

            return {
                "visualId": visual_id,
                "type": vtype,
                "altText": alt_text,
                "spec": spec,
            }

        visuals: List[Dict[str, Any]] = []
        for index, raw in enumerate(package.get("visuals") or []):
            visual = normalise_visual(raw, index + 1)
            if visual:
                visuals.append(visual)
        visual_ids = {visual["visualId"] for visual in visuals}

        blocks: List[Dict[str, Any]] = []
        for index, raw in enumerate(package.get("blocks") or []):
            if not isinstance(raw, dict):
                continue
            block = dict(raw)
            content = block.get("content")
            if isinstance(content, dict):
                heading = text_value(content.get("title") or content.get("heading"))
                body = text_value(content.get("text") or content.get("content") or content.get("body"))
                block["content"] = body or json.dumps(content, ensure_ascii=False)
                if heading and not text_value(block.get("heading")):
                    block["heading"] = heading[:200]
            else:
                block["content"] = text_value(content)
            if not block["content"]:
                continue

            kind = text_value(block.get("kind")) or "explanation"
            if kind not in {
                "explanation", "example", "definition", "callout", "check",
                "summary", "vocabulary", "question_prompt", "source_excerpt",
            }:
                kind = "explanation"
            block["kind"] = kind
            block["blockId"] = text_value(block.get("blockId")) or f"block_{index + 1}"
            if block.get("visualId") not in visual_ids:
                block.pop("visualId", None)
            if block.get("heading") is not None:
                block["heading"] = text_value(block["heading"])[:200]
            if not isinstance(block.get("sourceRefs"), list):
                block.pop("sourceRefs", None)
            allowed = {"blockId", "kind", "heading", "content", "sourceRefs", "visualId"}
            blocks.append({key: value for key, value in block.items() if key in allowed})

        worked_examples: List[Dict[str, Any]] = []
        for raw in package.get("workedExamples") or []:
            if not isinstance(raw, dict):
                continue
            prompt = text_value(raw.get("prompt"))
            steps = string_list(raw.get("steps"))
            answer = text_value(raw.get("answer"))
            if not prompt or not steps or not answer:
                continue
            example = {"prompt": prompt, "steps": steps, "answer": answer}
            if isinstance(raw.get("sourceRefs"), list):
                example["sourceRefs"] = raw["sourceRefs"]
            worked_examples.append(example)

        fallback_concept = text_value(lesson_id) or "lesson_1"
        practice = [
            question
            for index, raw in enumerate(package.get("practice") or [])
            if (question := normalise_question(raw, index + 1, fallback_concept))
        ]
        checkpoint = [
            question
            for index, raw in enumerate(package.get("checkpointTest") or [])
            if (question := normalise_question(raw, len(practice) + index + 1, fallback_concept))
        ]

        seen_ids = set()
        for question in practice + checkpoint:
            base = question["questionId"]
            candidate = base
            suffix = 2
            while candidate in seen_ids:
                candidate = f"{base}_{suffix}"
                suffix += 1
            question["questionId"] = candidate
            seen_ids.add(candidate)

        normalised: Dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "lessonId": lesson_id,
            "lessonVersion": 1,
            "pathId": path_id,
            "pathVersion": 1,
            "title": lesson_title[:180],
            "grade": int(grade),
            "subjectId": subject_id,
            "languageTag": text_value(package.get("languageTag"))[:20] or (text_value(language_tag)[:20] or "en-IN"),
            "sourceRefs": [],
            "objectives": string_list(package.get("objectives")),
            "blocks": blocks,
            "workedExamples": worked_examples,
            "practice": practice,
            "checkpointTest": checkpoint,
            "takeaways": string_list(package.get("takeaways")),
            "validation": {"status": "draft", "checks": []},
        }
        if visuals:
            normalised["visuals"] = visuals
        translation_status = text_value(package.get("translationStatus"))
        if translation_status in {
            "original", "reviewed_translation", "ai_draft_unreviewed", "not_available",
        }:
            normalised["translationStatus"] = translation_status
        estimated_minutes = package.get("estimatedMinutes")
        if isinstance(estimated_minutes, int) and 1 <= estimated_minutes <= 240:
            normalised["estimatedMinutes"] = estimated_minutes
        return normalised

    async def generate_outline(self, document_title: str, extracted_pages: List[Dict[str, Any]], grade: int, subject: str) -> Dict[str, Any]:
        """Outline from the document's own headings and page ranges."""
        return self.build_outline_from_pages(document_title, extracted_pages, grade, subject)

    async def generate_lesson_package(
        self,
        lesson_id: str,
        lesson_title: str,
        path_id: str,
        grade: int,
        subject: str,
        evidence_chunks: List[Dict[str, Any]],
        language_tag: str = "en-IN",
    ) -> Dict[str, Any]:
        """
        Generates and strictly validates a complete lesson package matching lesson-package.schema.json.
        """
        # Keep the learner's chosen source language instead of silently forcing
        # English on a book that was uploaded in another language.
        safe_language = text_value(language_tag)[:20] or "en-IN"
        # Build prompt with evidence chunks
        evidence_str = "\n".join([
            f"- [Chunk {c['citationId']} (Page {c['pageStart']})]: {c['text'][:1500]}"
            for c in evidence_chunks[:4]
        ])

        source_refs = [
            {
                "citationId": c["citationId"],
                "chunkId": c["chunkId"],
                "documentVersionId": c["documentVersionId"],
                "pageStart": c["pageStart"],
                "pageEnd": c["pageEnd"],
                "headingPath": c.get("headingPath", []),
                "sourceTitle": c.get("sourceTitle") or "Uploaded document"
            }
            for c in evidence_chunks[:3]
        ]

        prompt = (
            f"You are the SETU Learning Engine for Class {grade} {subject}.\n"
            f"Generate a complete educational lesson package for '{lesson_title}'.\n"
            f"Ground all claims strictly in these provided source chunks:\n{evidence_str}\n\n"
            f"Return one JSON object with exactly these fields:\n"
            f"- schemaVersion: '1.0.0'\n"
            f"- lessonId: '{lesson_id}'\n"
            f"- lessonVersion: 1\n"
            f"- pathId: '{path_id}'\n"
            f"- pathVersion: 1\n"
            f"- title: '{lesson_title}'\n"
            f"- grade: {grade}; subjectId: '{subject}'; languageTag: '{safe_language}'\n"
            f"- objectives: [2-3 observable objectives]\n"
            f"- blocks: [{{'blockId': 'block_1', 'kind': 'explanation', 'heading': '...', 'content': 'plain text'}}]\n"
            f"  Allowed block kinds: explanation, example, definition, callout, check, summary, vocabulary, question_prompt, source_excerpt. content MUST be a string, not an object.\n"
            f"  Format explanations in clean, structured paragraphs with empty lines between them. Use bullet points (•) for lists.\n"
            f"- visuals: [{{'visualId': 'visual_1', 'type': 'concept_map', 'altText': 'what the visual shows', "
            f"'spec': {{'schemaVersion': '1.0.0', 'visualId': 'visual_1', 'type': 'concept_map', "
            f"'title': '...', 'altText': 'what the visual shows', 'data': {{'nodes': [], 'edges': []}}}}}}]\n"
            f"- workedExamples: [{{'prompt': '...', 'steps': ['...'], 'answer': '...'}}]\n"
            f"- practice: [at least 3-5 multiple_choice questions with progressive hints]\n"
            f"- checkpointTest: [at least 5 independent multiple_choice questions]\n"
            f"- takeaways: [2-3 key takeaway sentences]\n\n"
            f"Every question MUST include questionId, type, prompt, conceptIds, answerKey, feedback.\n"
            f"Every practice and checkpointTest question MUST be type 'multiple_choice' "
            f"with an options array of exactly 4 strings, and answerKey.answer equal to "
            f"exactly one of the options. No fill-in-the-blank or short-answer questions.\n"
            f"checkpointTest MUST contain at least 5 multiple_choice questions covering the key concepts.\n"
            f"practice MUST contain at least 3 multiple_choice questions with progressive hints.\n"
            f"conceptIds MUST be a non-empty array of short lowercase concept identifiers.\n"
            f"hints MUST be an array of strings. feedback MUST be a string.\n\n"
            f"Keep the whole JSON compact (at most 4 content blocks).\n"
            f"Never write LaTeX formulas, backslashes, dollar signs ($), or raw markdown in any text field.\n"
            f"Express all mathematical formulas, units, and symbols in clean Unicode text (e.g. 50 km/h, 82°30′ E, H₂O, CO₂, 25 m², x² + y²).\n"
            f"Write explanations and questions in the language identified by '{safe_language}'. "
            f"Keep source terms, names and numbers exactly as they appear in the chunks.\n"
            f"Return only the JSON object, with no markdown fences or commentary."
        )

        try:
            content = await ai_provider.generate_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=8000,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "setu_lesson_package",
                        "schema": LESSON_PACKAGE_SCHEMA,
                    },
                },
            )
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0].strip()
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                content = content[start:end + 1]

            try:
                package = json.loads(content)
            except json.JSONDecodeError as err:
                idx = content.find("{")
                if idx >= 0:
                    try:
                        package, _ = json.JSONDecoder().raw_decode(content[idx:])
                    except Exception:
                        last_brace = content.rfind("}")
                        if last_brace > 0:
                            package = json.loads(content[:last_brace + 1])
                        else:
                            raise err
                else:
                    raise err

            package = self._normalise_package(
                package,
                lesson_id=lesson_id,
                lesson_title=lesson_title,
                path_id=path_id,
                grade=grade,
                subject_id=subject,
                language_tag=safe_language,
            )
            package["sourceRefs"] = source_refs
            package["validation"] = {"status": "draft", "checks": []}
            # Practice and checkpoint must stay answerable in the UI: options only.
            def _is_mcq(q: Any) -> bool:
                if not isinstance(q, dict):
                    return False
                t = str(q.get("type") or "multiple_choice").strip().lower()
                opts = q.get("options")
                return t in ("multiple_choice", "multiple-choice", "mcq") or (isinstance(opts, list) and len(opts) >= 2)

            cleaned_practice = []
            for q in (package.get("practice") or []):
                if _is_mcq(q):
                    q["type"] = "multiple_choice"
                    cleaned_practice.append(q)
            package["practice"] = cleaned_practice

            cleaned_checkpoint = []
            for q in (package.get("checkpointTest") or []):
                if _is_mcq(q):
                    q["type"] = "multiple_choice"
                    cleaned_checkpoint.append(q)
            package["checkpointTest"] = cleaned_checkpoint
            # Strip LaTeX/markdown artifacts so lesson text renders as plain prose.
            package = sanitize_tree(package)
        except Exception as exc:
            raise RuntimeError(f"Lesson generation failed: {exc}") from exc

        # Validate against JSON schema
        validation_result = self.validate_package(package, evidence_chunks)
        package["validation"] = validation_result

        return package

    def _normalise_visual_data(self, vtype: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Turn model-shaped visual data into the shape the renderers consume."""

        def as_text(value: Any) -> str:
            if isinstance(value, str):
                return value.strip()
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, dict):
                for key in ("label", "text", "title", "name", "content", "value"):
                    nested = as_text(value.get(key))
                    if nested:
                        return nested
            return ""

        if vtype == "concept_map":
            raw_nodes = data.get("nodes")
            if not isinstance(raw_nodes, list):
                return None
            nodes: List[Dict[str, str]] = []
            label_to_id: Dict[str, str] = {}
            used_ids = set()
            for index, node in enumerate(raw_nodes):
                label = as_text(node)
                if not label:
                    continue
                raw_id = as_text(node.get("id")) if isinstance(node, dict) else ""
                node_id = raw_id or f"n{index + 1}"
                while node_id in used_ids:
                    node_id = f"{node_id}_{index + 1}"
                used_ids.add(node_id)
                nodes.append({"id": node_id, "label": label[:120]})
                label_to_id[label.lower()] = node_id
            if len(nodes) < 1:
                return None

            edges: List[List[str]] = []
            raw_edges = data.get("edges")
            if isinstance(raw_edges, list):
                for edge in raw_edges:
                    pair: List[Any] = []
                    if isinstance(edge, (list, tuple)) and len(edge) >= 2:
                        pair = [edge[0], edge[1]]
                    elif isinstance(edge, dict):
                        pair = [edge.get("from") or edge.get("source"), edge.get("to") or edge.get("target")]
                    if len(pair) != 2:
                        continue
                    start = label_to_id.get(as_text(pair[0]).lower(), as_text(pair[0]))
                    end = label_to_id.get(as_text(pair[1]).lower(), as_text(pair[1]))
                    if start in used_ids and end in used_ids:
                        edges.append([start, end])

            if not edges and isinstance(data.get("flow"), list):
                for flow in data["flow"]:
                    if not isinstance(flow, (list, tuple)) or len(flow) < 2:
                        continue
                    start = label_to_id.get(as_text(flow[0]).lower(), as_text(flow[0]))
                    end = label_to_id.get(as_text(flow[-1]).lower(), as_text(flow[-1]))
                    if start in used_ids and end in used_ids:
                        edges.append([start, end])

            normalised: Dict[str, Any] = {"nodes": nodes}
            if edges:
                normalised["edges"] = edges
            return normalised

        if vtype == "science_process":
            raw_steps = data.get("steps")
            if not isinstance(raw_steps, list):
                return None
            steps: List[Dict[str, str]] = []
            for step in raw_steps:
                label = as_text(step)
                if not label:
                    continue
                detail = ""
                if isinstance(step, dict):
                    detail = as_text(step.get("detail") or step.get("description"))
                entry = {"label": label[:120]}
                if detail:
                    entry["detail"] = detail[:300]
                steps.append(entry)
            if len(steps) < 2:
                return None
            normalised = {"steps": steps}
            title = as_text(data.get("title"))
            if title:
                normalised["title"] = title[:180]
            return normalised

        return data

    def validate_package(self, package: Dict[str, Any], evidence_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validates lesson package against schema, citations, and answer keys."""
        # Strip extraneous top-level keys added by LLM not present in schema
        allowed_keys = set(LESSON_PACKAGE_SCHEMA.get("properties", {}).keys())
        if allowed_keys:
            for k in list(package.keys()):
                if k not in allowed_keys:
                    package.pop(k, None)

        checks = []

        # 1. JSON Schema validation
        try:
            jsonschema.validate(instance=package, schema=LESSON_PACKAGE_SCHEMA)
            checks.append({"name": "schema_conformance", "passed": True, "details": "Conforms to lesson-package.schema.json"})
        except jsonschema.ValidationError as e:
            checks.append({"name": "schema_conformance", "passed": False, "details": str(e.message)})

        # 2. Source citation resolution check
        valid_chunk_ids = {c["chunkId"] for c in evidence_chunks}
        citations_valid = True
        for sref in package.get("sourceRefs", []):
            if sref.get("chunkId") and sref.get("chunkId") not in valid_chunk_ids:
                citations_valid = False
                break
        checks.append({
            "name": "citation_resolution",
            "passed": citations_valid,
            "details": "All citations map to verified source chunk IDs" if citations_valid else "Citation ID missing in source"
        })

        # 3. Visual spec validation
        visuals_valid = True
        visual_details = "All educational visual specs conform to safe visual schema"
        for vis in package.get("visuals", []):
            spec = vis.get("spec")
            if not isinstance(spec, dict):
                visuals_valid = False
                visual_details = "A visual has no safe render specification"
                break
            try:
                jsonschema.validate(instance=spec, schema=VISUAL_SPEC_SCHEMA)
            except Exception:
                visuals_valid = False
                visual_details = "A visual specification failed schema validation"
                break
        checks.append({
            "name": "visual_spec_validation",
            "passed": visuals_valid,
            "details": visual_details,
        })

        # 4. Pedagogical section completeness (Learn/Solve/Test)
        has_learn = len(package.get("blocks", [])) > 0
        has_solve = len(package.get("practice", [])) > 0
        has_test = len(package.get("checkpointTest", [])) > 0
        all_stages = has_learn and has_solve and has_test
        checks.append({
            "name": "learn_solve_test_complete",
            "passed": all_stages,
            "details": "Package contains explanation, guided practice, and checkpoint test"
        })

        all_questions = package.get("practice", []) + package.get("checkpointTest", [])
        source_refs_present = len(package.get("sourceRefs", [])) > 0
        answer_keys_present = all(
            str(question.get("answerKey") or "").strip() for question in all_questions
        )
        concept_ids_present = all(
            len(question.get("conceptIds") or []) > 0 for question in all_questions
        )
        question_ids = [question.get("questionId") for question in all_questions]
        question_ids_unique = all(question_ids) and len(question_ids) == len(set(question_ids))
        gradable_types = all(
            question.get("type") in _GRADABLE_QUESTION_TYPES
            for question in all_questions
        )
        choice_questions_have_options = all(
            len(question.get("options") or []) >= 2
            for question in all_questions
            if question.get("type") == "multiple_choice"
        )

        def answer_is_usable(question: Dict[str, Any]) -> bool:
            answer = question.get("answerKey")
            if isinstance(answer, dict):
                return bool(str(answer.get("answer") or "").strip())
            return bool(str(answer or "").strip())

        usable_answers = all(answer_is_usable(question) for question in all_questions)

        checks.extend([
            {
                "name": "source_refs_present",
                "passed": source_refs_present,
                "details": "Lesson cites at least one source reference" if source_refs_present else "Lesson has no source references",
            },
            {
                "name": "answer_keys_nonempty",
                "passed": answer_keys_present and usable_answers,
                "details": "Every question has a gradeable answer key" if answer_keys_present and usable_answers else "One or more questions have an unusable answer key",
            },
            {
                "name": "concept_ids_nonempty",
                "passed": concept_ids_present,
                "details": "Every question maps to a concept" if concept_ids_present else "One or more questions have no concept IDs",
            },
            {
                "name": "question_ids_unique",
                "passed": question_ids_unique,
                "details": "Question IDs are present and unique" if question_ids_unique else "Question IDs are missing or duplicated",
            },
            {
                "name": "gradable_question_types",
                "passed": gradable_types,
                "details": "Every question uses a server-gradable type" if gradable_types else "A question type cannot be graded by the attempt service",
            },
            {
                "name": "choice_options_present",
                "passed": choice_questions_have_options,
                "details": "Every multiple-choice question has at least two options" if choice_questions_have_options else "A multiple-choice question has fewer than two options",
            },
        ])

        all_passed = all(c["passed"] for c in checks)
        return {
            "status": "ready" if all_passed else "rejected",
            "checks": checks,
            "validatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }


lesson_generator_service = LessonGeneratorService()

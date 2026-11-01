import os
import json
import re
import datetime
import difflib
import jsonschema
from collections import Counter
from typing import Dict, Any, List, Optional
from app.core.ai_provider import ai_provider

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
    r"^(chapter|unit)\s*([0-9oOil|](?:[\s.]*[0-9oOil|]){0,2})?\s*([:.\-\u2013|])?\s*(.*)$",
    re.IGNORECASE,
)
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
        sections = self._running_header_sections(pages, page_by_number)
        if len(sections) < 2:
            marker_sections = self._chapter_marker_sections(pages, page_by_number)
            if marker_sections:
                sections = marker_sections
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
        """Detect chapters from a repeated header label and changing title."""
        counter: Counter = Counter()
        for page in pages:
            for line in self._page_lines(page["text"])[:8]:
                if (
                    3 <= len(line) <= 40
                    and re.search(r"[A-Za-z]", line)
                    and not line.isdigit()
                ):
                    counter[line] += 1
        if not counter:
            return []

        label, count = counter.most_common(1)[0]
        if count < max(4, int(len(pages) * 0.15)):
            return []

        first_chapter_page: Optional[int] = None
        for page in pages:
            marker = self._marker_line(page["text"])
            if marker and marker.get("number") is not None:
                first_chapter_page = page["page_number"]
                break

        headers: List[tuple] = []
        for page in pages:
            header_title = self._header_title(page["text"], label)
            if header_title:
                headers.append((page["page_number"], header_title))
        if len(headers) < 2:
            return []

        runs: List[Dict[str, Any]] = []
        for page_number, header_title in headers:
            if runs and self._similar_titles(runs[-1]["title"], header_title):
                runs[-1]["lastHeader"] = page_number
                continue
            runs.append({
                "title": header_title,
                "firstHeader": page_number,
                "lastHeader": page_number,
            })
        if len(runs) < 2:
            return []

        if first_chapter_page is not None:
            # Front matter also carries the book label ("Class X", "SOCIAL
            # STUDIES"); only running headers at or after the first numbered
            # chapter belong to the course outline.
            runs = [run for run in runs if run["lastHeader"] >= first_chapter_page]
        # A one-page run is usually a cover, contents page, or OCR noise.
        runs = [run for run in runs if run["lastHeader"] > run["firstHeader"]]
        if len(runs) < 2:
            return []

        sections: List[Dict[str, Any]] = []
        for run in runs:
            start = max(1, run["firstHeader"] - 1)
            title = run["title"]
            for candidate in range(max(1, run["firstHeader"] - 3), run["firstHeader"] + 2):
                page = page_by_number.get(candidate)
                if not page:
                    continue
                marker = self._marker_line(page["text"])
                if not marker:
                    continue
                start = candidate
                marker_title = self._title_from_marker_page(page["text"])
                if marker_title and self._similar_titles(title, marker_title):
                    # The chapter-opening page usually spells the title more
                    # completely than a running header ("Food Securty").
                    title = marker_title
                break
            if sections and start <= sections[-1]["pageStart"]:
                start = sections[-1]["pageStart"] + 1
            sections.append({
                "title": title,
                "pageStart": start,
                "pageEnd": start,
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
            marker_title = self._title_from_marker_page(page["text"])
            if page_span >= 20 and page["page_number"] >= last_page_number - 2:
                # End-of-book answer keys repeat chapter headings.
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
            sections.append({
                "title": title,
                "pageStart": marker["page_number"],
                "pageEnd": marker["page_number"],
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
            })
        if not cleaned:
            return []

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
            section["chapterTitle"] = title[:180]
            section["chapterNumber"] = index + 1
            section["concepts"] = [title[:180]]
            section.pop("title", None)
        return cleaned

    # ------------------------------------------------------------------
    # Title extraction
    # ------------------------------------------------------------------

    def _marker_line(self, text: str) -> Optional[Dict[str, Any]]:
        for line in self._page_lines(text)[:12]:
            match = _CHAPTER_MARKER.match(line.strip())
            if not match:
                continue
            _, raw_number, separator, rest = match.groups()
            rest = (rest or "").strip()
            if rest and not separator and not raw_number:
                # "chapter that should be considered ..." is body text.
                continue
            if len(rest.split()) > 14:
                cleaned_rest = self._clean_title_fragment(rest)
                if not cleaned_rest or len(cleaned_rest.split()) > 14:
                    continue
                rest = cleaned_rest
            if rest and not self._looks_like_title_fragment(rest):
                continue
            number = None
            if raw_number:
                digits = re.findall(r"\d+", raw_number)
                if digits:
                    number = int("".join(digits))
            return {"number": number, "separator": separator, "rest": rest}
        return None

    def _title_from_marker_page(self, text: str) -> Optional[str]:
        lines = self._page_lines(text)
        marker_index = None
        marker = None
        for index, line in enumerate(lines[:18]):
            if self._marker_line(line):
                marker_index = index
                marker = self._marker_line(line)
                break
        if marker is None or marker_index is None:
            return None

        fragments: List[str] = []
        rest = marker.get("rest") or ""
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
            if fragments:
                first_word = cleaned.split()[0].lower() if cleaned.split() else ""
                words = cleaned.split()
                if first_word in _TITLE_CONNECTORS:
                    if len(words) > 4 or any(char in cleaned for char in ",;") or cleaned.endswith("-"):
                        break
                elif first_word in _SENTENCE_STARTERS:
                    break
                elif len(words) > 6:
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

    def _similar_titles(self, first: str, second: str) -> bool:
        left = re.sub(r"[^a-z0-9 ]", "", (first or "").lower())
        right = re.sub(r"[^a-z0-9 ]", "", (second or "").lower())
        if not left or not right:
            return False
        if left == right:
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
            f"- visuals: [{{'visualId': 'visual_1', 'type': 'concept_map', 'altText': 'what the visual shows', "
            f"'spec': {{'schemaVersion': '1.0.0', 'visualId': 'visual_1', 'type': 'concept_map', "
            f"'title': '...', 'altText': 'what the visual shows', 'data': {{'nodes': [], 'edges': []}}}}}}]\n"
            f"- workedExamples: [{{'prompt': '...', 'steps': ['...'], 'answer': '...'}}]\n"
            f"- practice: [1-2 questions]\n"
            f"- checkpointTest: [1-2 independent questions]\n"
            f"- takeaways: [2-3 key takeaway sentences]\n\n"
            f"Every question MUST include questionId, type, prompt, conceptIds, answerKey, feedback.\n"
            f"type MUST be one of: multiple_choice, numeric, short_text.\n"
            f"multiple_choice MUST include an options array of at least two strings.\n"
            f"conceptIds MUST be a non-empty array of short lowercase concept identifiers.\n"
            f"hints MUST be an array of strings. feedback MUST be a string.\n\n"
            f"Keep the whole JSON compact (at most 4 content blocks).\n"
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
            except json.JSONDecodeError:
                # Attempt minor structural JSON recovery for unclosed brackets
                last_brace = content.rfind("}")
                if last_brace > 0:
                    package = json.loads(content[:last_brace + 1])
                else:
                    raise

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

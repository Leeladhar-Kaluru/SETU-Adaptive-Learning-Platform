import os
import json
import re
import datetime
import jsonschema
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


class LessonGeneratorService:
    def build_outline_from_pages(
        self,
        document_title: str,
        extracted_pages: List[Dict[str, Any]],
        grade: int,
        subject: str,
    ) -> Dict[str, Any]:
        """Build a course outline from headings and page ranges in the extracted text."""
        pages = []
        for page in extracted_pages:
            text = (page.get("text") or "").strip()
            if not text or text.startswith("[Image-only or empty page"):
                continue
            pages.append({"page_number": page.get("page_number") or 1, "text": text})
        if not pages:
            raise ValueError("This document has no extractable text to build a learning path.")

        sections: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for page in pages:
            heading = self._heading_for_page(page["text"])
            if heading:
                if current:
                    sections.append(current)
                current = {
                    "chapterTitle": heading,
                    "pageStart": page["page_number"],
                    "pageEnd": page["page_number"],
                    "concepts": [heading],
                }
            elif current:
                current["pageEnd"] = page["page_number"]
            else:
                title = self._first_line(page["text"])
                current = {
                    "chapterTitle": title,
                    "pageStart": page["page_number"],
                    "pageEnd": page["page_number"],
                    "concepts": [title],
                }
        if current:
            sections.append(current)

        if len(sections) > 24:
            step = len(sections) / 24
            sections = [sections[min(len(sections) - 1, int(i * step))] for i in range(24)]

        last_page = pages[-1]["page_number"]
        for index, section in enumerate(sections):
            if index + 1 < len(sections):
                section["pageEnd"] = max(section["pageStart"], sections[index + 1]["pageStart"] - 1)
            else:
                section["pageEnd"] = max(section["pageEnd"], last_page)
            section["chapterNumber"] = index + 1

        title = document_title.rsplit(".", 1)[0].replace("_", " ")
        return {
            "title": title,
            "grade": grade,
            "subject": subject,
            "chapters": sections,
        }

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
        evidence_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generates and strictly validates a complete lesson package matching lesson-package.schema.json.
        """
        # Build prompt with evidence chunks
        evidence_str = "\n".join([
            f"- [Chunk {c['citationId']} (Page {c['pageStart']})]: {c['text'][:400]}"
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
                "sourceTitle": f"Class {grade} {subject}"
            }
            for c in evidence_chunks[:3]
        ]

        prompt = (
            f"You are the SETU Learning Engine for Class {grade} {subject}.\n"
            f"Generate a complete educational lesson package for '{lesson_title}'.\n"
            f"Ground all claims strictly in these provided source chunks:\n{evidence_str}\n\n"
            f"Required JSON structure strictly conforming to SETU Lesson Package:\n"
            f"- schemaVersion: '1.0.0'\n"
            f"- lessonId: '{lesson_id}'\n"
            f"- lessonVersion: 1\n"
            f"- pathId: '{path_id}'\n"
            f"- pathVersion: 1\n"
            f"- title: '{lesson_title}'\n"
            f"- grade: {grade}\n"
            f"- subjectId: '{subject}'\n"
            f"- languageTag: 'en-IN'\n"
            f"- objectives: [2-3 observable bullet objectives]\n"
            f"- blocks: content blocks of kind 'explanation', 'definition', 'check'\n"
            f"- visuals: [1 visual spec of type 'concept_map' or 'science_process' or 'fraction_model']\n"
            "- workedExamples: [{ 'prompt': '...', 'steps': ['...'], 'answer': '...' }]\n"
            f"- practice: [1-2 practice questions with questionId, prompt, type, conceptIds, answerKey, hints, feedback, validator]\n"
            f"- checkpointTest: [1-2 independent questions]\n"
            f"- takeaways: [2-3 key takeaway sentences]\n\n"
            f"Return pure JSON."
        )

        try:
            content = await ai_provider.generate_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=6000
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

            package["sourceRefs"] = source_refs
            package["validation"] = {"status": "draft", "checks": []}

            # Strip any extraneous top-level keys added by LLM not present in schema
            allowed_keys = set(LESSON_PACKAGE_SCHEMA.get("properties", {}).keys())
            if allowed_keys:
                for k in list(package.keys()):
                    if k not in allowed_keys:
                        package.pop(k, None)
        except Exception as exc:
            raise RuntimeError(f"Lesson generation failed: {exc}") from exc

        # Validate against JSON schema
        validation_result = self.validate_package(package, evidence_chunks)
        package["validation"] = validation_result

        return package

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
        for vis in package.get("visuals", []):
            spec = vis.get("spec")
            if spec:
                try:
                    jsonschema.validate(instance=spec, schema=VISUAL_SPEC_SCHEMA)
                except Exception:
                    visuals_valid = False
                    break
        checks.append({
            "name": "visual_spec_validation",
            "passed": visuals_valid,
            "details": "All educational visual specs conform to safe visual schema"
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

        checks.extend([
            {
                "name": "source_refs_present",
                "passed": source_refs_present,
                "details": "Lesson cites at least one source reference" if source_refs_present else "Lesson has no source references",
            },
            {
                "name": "answer_keys_nonempty",
                "passed": answer_keys_present,
                "details": "Every question has an answer key" if answer_keys_present else "One or more questions have an empty answer key",
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
        ])

        all_passed = all(c["passed"] for c in checks)
        return {
            "status": "ready" if all_passed else "rejected",
            "checks": checks,
            "validatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }


lesson_generator_service = LessonGeneratorService()

"""Live acceptance run against a disposable API/worker with local storage.

Writes a structured JSON record to context/ACCEPTANCE_RUN.json. Every value in
that file must come from an observed HTTP response or DB-visible status.
"""
import json
import os
import sys
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8001/api/v1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIGITAL = os.path.join(ROOT, "acceptance", "e2e_science.pdf")
SCANNED = os.path.join(ROOT, "acceptance", "e2e_scanned_page.pdf")
OUT = os.path.join(os.path.dirname(ROOT), "context", "ACCEPTANCE_RUN.json")

OWNER = str(uuid.uuid4())
HEADERS = {"X-User-Id": OWNER}

record = {
    "ownerId": OWNER,
    "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "steps": {},
}


def log(message: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def save() -> None:
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)


def request(method: str, path: str, **kwargs):
    with httpx.Client(timeout=240.0) as client:
        response = client.request(method, f"{BASE}{path}", headers=HEADERS, **kwargs)
    return response


def poll_status(document_id: str, timeout: int = 600) -> dict:
    started = time.monotonic()
    last = None
    transitions = []
    while time.monotonic() - started < timeout:
        response = request("GET", f"/documents/{document_id}/status")
        if response.status_code != 200:
            raise RuntimeError(f"status {response.status_code}: {response.text}")
        body = response.json()
        if body.get("status") != last:
            last = body.get("status")
            transitions.append(
                {
                    "status": last,
                    "atSeconds": round(time.monotonic() - started, 2),
                    "progressMessage": body.get("progressMessage"),
                    "errorMessage": body.get("errorMessage"),
                }
            )
            log(f"  status={last} progress={body.get('progressMessage')!r} error={body.get('errorMessage')!r}")
        if last in ("awaiting_review", "failed", "needs_ocr", "ready"):
            body["transitions"] = transitions
            body["elapsedSeconds"] = round(time.monotonic() - started, 2)
            return body
        time.sleep(1.5)
    raise TimeoutError(f"document {document_id} did not settle in {timeout}s")


def upload(name: str, path: str) -> dict:
    with open(path, "rb") as handle:
        files = {"file": (os.path.basename(path), handle, "application/pdf")}
        response = request("POST", "/documents/upload", files=files)
    if response.status_code != 200:
        raise RuntimeError(f"upload {name} failed {response.status_code}: {response.text}")
    body = response.json()
    log(f"uploaded {name}: documentId={body['documentId']} status={body['status']}")
    return body


def main() -> int:
    log(f"owner={OWNER}")
    save()

    # 1. Digital PDF: upload, observe real extraction and indexing.
    upload_body = upload("digital", DIGITAL)
    digital_id = upload_body["documentId"]
    digital = poll_status(digital_id)
    record["steps"]["digitalUpload"] = {
        "documentId": digital_id,
        "uploadStatus": upload_body.get("status"),
        "finalStatus": digital.get("status"),
        "pageCount": digital.get("pageCount"),
        "chunkCount": digital.get("chunkCount"),
        "pagesNeedingOcr": digital.get("pagesNeedingOcr"),
        "canBuildPath": digital.get("canBuildPath"),
        "chapters": digital.get("chapters"),
        "transitions": digital.get("transitions"),
        "elapsedSeconds": digital.get("elapsedSeconds"),
    }
    save()

    if digital.get("status") != "awaiting_review":
        log(f"digital extraction did not reach awaiting_review: {digital}")
        return 1

    # 2. List endpoint exposes the same real chunk count.
    listed = request("GET", "/documents")
    listed_body = listed.json()
    listed_doc = next((d for d in listed_body if d["documentId"] == digital_id), None)
    record["steps"]["documentList"] = {
        "statusCode": listed.status_code,
        "chunkCount": (listed_doc or {}).get("chunkCount"),
        "pageCount": (listed_doc or {}).get("pageCount"),
        "errorMessage": (listed_doc or {}).get("errorMessage"),
        "progressMessage": (listed_doc or {}).get("progressMessage"),
    }
    log(f"list chunkCount={record['steps']['documentList']['chunkCount']} pageCount={record['steps']['documentList']['pageCount']}")
    save()

    # 3. Build a real learning path from detected headings.
    create = request(
        "POST",
        "/learning-paths",
        json={"documentId": digital_id, "grade": 9, "subjectId": "subject-science"},
    )
    if create.status_code != 200:
        log(f"path creation failed {create.status_code}: {create.text}")
        record["steps"]["pathCreation"] = {"statusCode": create.status_code, "error": create.text}
        save()
        return 1
    path_body = create.json()
    path_id = path_body["pathId"]
    record["steps"]["pathCreation"] = {
        "statusCode": create.status_code,
        "pathId": path_id,
        "firstLessonId": path_body.get("firstLessonId"),
        "totalLessons": path_body.get("totalLessons"),
        "status": path_body.get("status"),
    }
    log(f"path {path_id} created with {path_body.get('totalLessons')} lessons")
    save()

    # 4. Wait for every generated lesson to settle (ready/failed).
    lesson_id = None
    lesson_status = None
    started = time.monotonic()
    settled_statuses = []
    while time.monotonic() - started < 1200:
        detail = request("GET", f"/learning-paths/{path_id}")
        if detail.status_code != 200:
            raise RuntimeError(f"path detail {detail.status_code}: {detail.text}")
        detail_body = detail.json()
        lessons = detail_body.get("lessons", [])
        statuses = [lesson.get("status") for lesson in lessons]
        if statuses != settled_statuses:
            settled_statuses = statuses
            log(f"  lesson statuses={statuses} ({round(time.monotonic() - started, 1)}s)")
        first = lessons[0] if lessons else None
        if first and first.get("status") != lesson_status:
            lesson_status = first.get("status")
        if lessons and all(status in ("ready", "failed") for status in statuses):
            lesson_id = first.get("id") if first else None
            break
        time.sleep(3)
    record["steps"]["lessonGeneration"] = {
        "firstLessonId": lesson_id,
        "firstLessonStatus": lesson_status,
        "elapsedSeconds": round(time.monotonic() - started, 2),
        "allLessonStatuses": statuses,
        "allSettled": bool(lessons) and all(status in ("ready", "failed") for status in statuses),
    }
    save()
    if lesson_status != "ready":
        log(f"lesson generation did not succeed: {lesson_status}")
        return 1

    # 5. Fetch the ready lesson and record only real, redacted package facts.
    lesson = request("GET", f"/learning-paths/lessons/{lesson_id}", params={"pathId": path_id})
    if lesson.status_code != 200:
        log(f"lesson fetch failed {lesson.status_code}: {lesson.text}")
        return 1
    package = lesson.json()
    practice = package.get("practice") or []
    checkpoint = package.get("checkpointTest") or []
    source_refs = package.get("sourceRefs") or []
    visuals = package.get("visuals") or []
    record["steps"]["lessonPackage"] = {
        "statusCode": lesson.status_code,
        "lessonVersionId": package.get("lessonVersionId"),
        "pathId": package.get("pathId"),
        "sections": list(package.keys()),
        "practiceCount": len(practice),
        "checkpointCount": len(checkpoint),
        "answerKeysRedacted": all("answerKey" not in q for q in practice + checkpoint),
        "sourceRefs": [
            {
                "sourceTitle": ref.get("sourceTitle"),
                "pageStart": ref.get("pageStart"),
                "pageEnd": ref.get("pageEnd"),
                "headingPath": ref.get("headingPath"),
            }
            for ref in source_refs
        ],
        "visualCount": len(visuals),
        "visualsHaveAltText": all(
            bool((visual.get("altText") or "").strip()) for visual in visuals
        ),
        "visualSpecsValid": all(
            isinstance(visual.get("spec"), dict)
            and bool(visual["spec"].get("type"))
            and isinstance(visual["spec"].get("data"), dict)
            for visual in visuals
        ),
        "firstQuestion": {
            "questionId": (practice or checkpoint)[0].get("questionId") if (practice or checkpoint) else None,
            "type": (practice or checkpoint)[0].get("type") if (practice or checkpoint) else None,
            "hasOptions": bool((practice or checkpoint)[0].get("options")) if (practice or checkpoint) else None,
        },
    }
    log(f"lesson package: practice={len(practice)} checkpoint={len(checkpoint)} version={package.get('lessonVersionId')}")
    save()

    # 6. Submit a graded practice attempt using the real question key.
    if practice:
        question = practice[0]
        answer_key = None
        # The package is redacted; use the first option for a deterministic request.
        options = question.get("options") or []
        if options:
            answer_key = options[0] if isinstance(options[0], str) else options[0].get("id") or options[0].get("value")
        else:
            answer_key = "sample answer"
        attempt = request(
            "POST",
            "/attempts",
            json={
                "lessonVersionId": package["lessonVersionId"],
                "questionKey": question.get("questionId"),
                "response": answer_key,
                "elapsedSeconds": 12,
                "attemptKind": "practice",
                "syncIdempotencyKey": f"acceptance-{package['lessonVersionId']}-{question.get('questionId')}",
            },
        )
        record["steps"]["attempt"] = {
            "statusCode": attempt.status_code,
            "body": attempt.json() if attempt.headers.get("content-type", "").startswith("application/json") else attempt.text,
        }
        attempt_body = record["steps"]["attempt"]["body"]
        if isinstance(attempt_body, dict):
            record["steps"]["attempt"]["feedbackContradictsGrade"] = bool(
                attempt_body.get("isCorrect") is False
                and "correct!" in str(attempt_body.get("feedback") or "").casefold()
            )
        log(f"attempt status={attempt.status_code}")
        save()

    # 7. Ask a real doubt scoped to the path and verify citation source metadata.
    client_doubt_id = f"acceptance-{uuid.uuid4().hex[:10]}"
    doubt_attempts = []
    doubt_body = {}
    for doubt_attempt in range(3):
        doubt = request(
            "POST",
            "/doubts",
            json={
                "clientDoubtId": client_doubt_id,
                "questionText": "What is osmosis and why is the cell membrane called selectively permeable?",
                "pathId": path_id,
            },
        )
        doubt_body = (
            doubt.json()
            if doubt.headers.get("content-type", "").startswith("application/json")
            else {"raw": doubt.text}
        )
        doubt_attempts.append(
            {
                "attempt": doubt_attempt + 1,
                "statusCode": doubt.status_code,
                "status": doubt_body.get("status"),
            }
        )
        if doubt_body.get("status") == "answered":
            break
        time.sleep(2)

    citations = (doubt_body.get("answerJson") or {}).get("citations") or []
    record["steps"]["doubt"] = {
        "statusCode": doubt.status_code,
        "status": doubt_body.get("status"),
        "answer": (doubt_body.get("answerJson") or {}).get("answer"),
        "citations": citations,
        "citationSourceTitles": sorted(
            {citation.get("sourceTitle") for citation in citations if citation.get("sourceTitle")}
        ),
        "limitations": (doubt_body.get("answerJson") or {}).get("limitations"),
        "attempts": doubt_attempts,
        "answerLength": len(str((doubt_body.get("answerJson") or {}).get("answer") or "")),
        "answerEndsWithTerminalPunctuation": str(
            (doubt_body.get("answerJson") or {}).get("answer") or ""
        ).rstrip().endswith((".", "!", "?")),
        "containsCorruptBytes": "\ufffd" in str((doubt_body.get("answerJson") or {}).get("answer") or ""),
    }
    log(f"doubt status={record['steps']['doubt']['status']} citations={len(citations)}")
    save()

    # 8. Scanned image-only PDF: observe OCR, timing, and honesty fields.
    scanned_upload = upload("scanned", SCANNED)
    scanned_id = scanned_upload["documentId"]
    scanned = poll_status(scanned_id)
    record["steps"]["scannedUpload"] = {
        "documentId": scanned_id,
        "finalStatus": scanned.get("status"),
        "pageCount": scanned.get("pageCount"),
        "chunkCount": scanned.get("chunkCount"),
        "pagesNeedingOcr": scanned.get("pagesNeedingOcr"),
        "canBuildPath": scanned.get("canBuildPath"),
        "chapters": scanned.get("chapters"),
        "transitions": scanned.get("transitions"),
        "elapsedSeconds": scanned.get("elapsedSeconds"),
        "pages": scanned.get("pages"),
        "ocrAppliedOnAnyPage": any(
            bool((page or {}).get("ocrApplied")) for page in (scanned.get("pages") or [])
        ),
        "pagesWithReadableText": sum(
            1 for page in (scanned.get("pages") or []) if (page or {}).get("charCount", 0) > 0
        ),
    }
    log(f"scanned final={scanned.get('status')} pagesNeedingOcr={scanned.get('pagesNeedingOcr')} chunks={scanned.get('chunkCount')}")
    save()

    record["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record["result"] = "completed"
    save()
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        record["error"] = str(exc)
        save()
        raise

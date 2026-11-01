"""Comprehensive End-to-End Milestone 4 Verification Script.
Executes live HTTP API requests against FastAPI (http://127.0.0.1:8000)
and queries the live database to verify all 5 User Journeys.
"""
import sys
import os
import json
import uuid
import time
import urllib.request
import urllib.error

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings
import psycopg

API_BASE = "http://127.0.0.1:8000/api/v1"

def get_auth_token():
    """Obtain a genuine Supabase auth access token for student chotu2@gmail.com."""
    base_url = settings.SUPABASE_URL.rstrip('/')
    admin_url = base_url + '/auth/v1/admin/generate_link'
    headers = {
        'apikey': settings.SUPABASE_SECRET_KEY,
        'Authorization': 'Bearer ' + settings.SUPABASE_SECRET_KEY,
        'Content-Type': 'application/json'
    }
    payload = json.dumps({'type': 'magiclink', 'email': 'chotu2@gmail.com'}).encode('utf-8')
    req = urllib.request.Request(admin_url, data=payload, headers=headers, method='POST')
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        email_otp = res.get('email_otp')

    verify_url = base_url + '/auth/v1/verify'
    pub_headers = {
        'apikey': settings.SUPABASE_PUBLISHABLE_KEY or settings.SUPABASE_SECRET_KEY,
        'Content-Type': 'application/json'
    }
    verify_payload = json.dumps({'type': 'email', 'email': 'chotu2@gmail.com', 'token': email_otp}).encode('utf-8')
    vreq = urllib.request.Request(verify_url, data=verify_payload, headers=pub_headers, method='POST')
    with urllib.request.urlopen(vreq) as vresp:
        auth_data = json.loads(vresp.read().decode('utf-8'))
        token = auth_data.get('access_token')
        user_id = auth_data.get('user', {}).get('id')
        print(f"Authenticated as student {user_id} (chotu2@gmail.com)")
        return token, user_id


def http_request(endpoint, method="GET", token=None, body=None, content_type="application/json", timeout=30):
    url = f"{API_BASE}{endpoint}" if endpoint.startswith("/") else f"{API_BASE}/{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type

    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
        elif isinstance(body, bytes):
            data = body
        else:
            data = str(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content = resp.read().decode("utf-8")
        try:
            return json.loads(content)
        except Exception:
            return content


def run_verification():
    print("==================================================================")
    print("STARTING MILESTONE 4 END-TO-END VERIFICATION")
    print("==================================================================")

    token, student_id = get_auth_token()
    assert token and student_id == "f3ac32c7-1fd7-4762-9248-d0e2159f1512"

    # ------------------------------------------------------------------
    # JOURNEY 1: Document Upload & Ingestion
    # ------------------------------------------------------------------
    print("\n[JOURNEY 1] Document Upload & Ingestion Verification")
    with psycopg.connect(settings.DATABASE_URL, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM documents WHERE deleted_at IS NULL AND original_filename LIKE '%Flight%' LIMIT 1;")
            doc_id = str(cur.fetchone()[0])

    # 1.1 Verify DB invariants for First Flight
    with psycopg.connect(settings.DATABASE_URL, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, original_filename, status, page_count, size_bytes FROM documents WHERE id = %s;", (doc_id,))
            doc_row = cur.fetchone()
            assert doc_row is not None, f"Document {doc_id} not found in DB!"
            print(f"  DB Document: {doc_row[1]} | Status: {doc_row[2]} | Pages: {doc_row[3]} | Size: {doc_row[4]} bytes")
            assert doc_row[2] in ("awaiting_review", "ready"), f"Unexpected doc status: {doc_row[2]}"

            cur.execute("SELECT count(*) FROM document_pages WHERE document_id = %s;", (doc_id,))
            pages_count = cur.fetchone()[0]
            print(f"  DB DocumentPages: {pages_count} (expected: 172)")
            assert pages_count == 172, f"Expected 172 pages, got {pages_count}"

            cur.execute("SELECT count(*), count(*) FILTER (WHERE embedding_dimension = 768) FROM document_chunks WHERE document_id = %s;", (doc_id,))
            chunks_count, vectors_count = cur.fetchone()
            print(f"  DB DocumentChunks: {chunks_count} | 768-dim Vectors: {vectors_count} (expected: 222 / 222)")
            assert chunks_count == 222 and vectors_count == 222

    # 1.2 Verify Document Status API Endpoint
    status_res = http_request(f"/documents/{doc_id}/status", token=token)
    print(f"  API Status Response: title='{status_res.get('title')}', status='{status_res.get('status')}', "
          f"pagesRead={status_res.get('pagesRead')}, chunkCount={status_res.get('chunkCount')}, "
          f"canBuildPath={status_res.get('canBuildPath')}, chaptersCount={len(status_res.get('chapters', []))}")
    assert status_res.get("status") in ("awaiting_review", "ready")
    assert status_res.get("pagesRead") == 172
    assert status_res.get("chunkCount") == 222
    assert status_res.get("canBuildPath") is True
    assert len(status_res.get("chapters", [])) == 11
    print("  [JOURNEY 1 PASSED]: Ingestion invariants and status API verified.")

    # ------------------------------------------------------------------
    # JOURNEY 2: Outline Extraction (11 Chapters, Pages 11 to 172)
    # ------------------------------------------------------------------
    print("\n[JOURNEY 2] Outline Extraction Verification")
    with psycopg.connect(settings.DATABASE_URL, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM learning_paths WHERE owner_id = %s AND status = 'active' LIMIT 1;", (student_id,))
            path_id = str(cur.fetchone()[0])
    path_res = http_request(f"/learning-paths/{path_id}", token=token)
    print(f"  API LearningPath: title='{path_res.get('title')}', grade={path_res.get('grade')}, subjectId='{path_res.get('subjectId')}', status='{path_res.get('status')}'")
    assert path_res.get("id") == path_id
    assert path_res.get("status") == "active"

    outline_chapters = path_res.get("outline", {}).get("chapters", [])
    print(f"  Outline Chapters Count: {len(outline_chapters)} (expected: 11)")
    assert len(outline_chapters) == 11, f"Expected 11 chapters, got {len(outline_chapters)}"

    expected_chapters = [
        ("A Letter to God", 11, 25),
        ("Nelson Mandela: Long Walk to Freedom", 26, 41),
        ("Two Stories about Flying", 42, 57),
        ("From the Diary of Anne Frank", 58, 72),
        ("The Hundred Dresses - I", 73, 82),
        ("The Hundred Dresses - II", 83, 94),
        ("Glimpses of India", 95, 111),
        ("Mijbil the Otter", 112, 125),
        ("Madam Rides the Bus", 126, 142),
        ("The Sermon at Benares", 143, 151),
        ("The Proposal", 152, 172),
    ]

    for idx, (expected_title, exp_p_start, exp_p_end) in enumerate(expected_chapters):
        ch = outline_chapters[idx]
        title = ch.get("chapterTitle") or ch.get("title")
        p_start = ch.get("pageStart")
        p_end = ch.get("pageEnd")
        print(f"    Chapter {idx+1:2d}: '{title}' | Pages {p_start}-{p_end} (expected: {exp_p_start}-{exp_p_end})")
        assert title == expected_title, f"Chapter {idx+1} title mismatch: {title} != {expected_title}"
        assert p_start == exp_p_start, f"Chapter {idx+1} pageStart mismatch: {p_start} != {exp_p_start}"
        assert p_end == exp_p_end, f"Chapter {idx+1} pageEnd mismatch: {p_end} != {exp_p_end}"

    print(f"  Full span coverage: Page {outline_chapters[0].get('pageStart')} to Page {outline_chapters[-1].get('pageEnd')} (100% textbook chapters covered).")
    print("  [JOURNEY 2 PASSED]: 11 chapters with exact page spans verified.")

    # ------------------------------------------------------------------
    # JOURNEY 3: Lesson Reading (Rich Pedagogical Packages)
    # ------------------------------------------------------------------
    print("\n[JOURNEY 3] Lesson Reading Verification")
    lessons = path_res.get("lessons", [])
    assert len(lessons) == 11

    # Inspect first 3 chapters in detail
    for idx in range(3):
        lesson_item = lessons[idx]
        l_id = lesson_item.get("id")
        l_title = lesson_item.get("title")
        l_seq = lesson_item.get("sequence")

        pkg = http_request(f"/learning-paths/lessons/{l_id}?pathId={path_id}", token=token)
        print(f"\n  Checking Chapter {l_seq}: '{l_title}' (Lesson ID: {l_id})")
        print(f"    Title in package: '{pkg.get('title')}' | Version ID: {pkg.get('lessonVersionId')}")
        
        objectives = pkg.get("objectives", [])
        visuals = pkg.get("visuals", [])
        blocks = pkg.get("blocks", [])
        takeaways = pkg.get("takeaways", [])
        worked = pkg.get("workedExample")
        practice = pkg.get("practice", [])
        checkpoint = pkg.get("checkpointTest", [])

        print(f"    - Objectives ({len(objectives)}): {[o.get('description')[:40] for o in objectives]}")
        print(f"    - Visual Concept Map: {visuals[0].get('title') if visuals else 'None'} ({len(visuals[0].get('nodes', [])) if visuals else 0} nodes, {len(visuals[0].get('edges', [])) if visuals else 0} edges)")
        print(f"    - Reading Blocks: {len(blocks)} blocks ({', '.join(b.get('kind', '') for b in blocks[:4])}...)")
        print(f"    - Worked Example: {worked.get('title') if worked else 'None'}")
        print(f"    - Key Takeaways: {len(takeaways)}")
        print(f"    - Practice MCQs: {len(practice)}")
        print(f"    - Checkpoint MCQs: {len(checkpoint)}")

        assert len(objectives) >= 3, f"Expected >= 3 objectives, got {len(objectives)}"
        assert len(visuals) >= 1 and len(visuals[0].get("nodes", [])) >= 3, "Visual concept map missing or invalid!"
        assert len(blocks) >= 3, f"Expected >= 3 reading blocks, got {len(blocks)}"
        assert worked is not None and "steps" in worked, "Worked example missing!"
        assert len(takeaways) >= 3, f"Expected >= 3 takeaways, got {len(takeaways)}"
        assert len(checkpoint) >= 5, f"Expected >= 5 checkpoint MCQs, got {len(checkpoint)}"

    print("  [JOURNEY 3 PASSED]: Rich pedagogical packages verified across chapters.")

    # ------------------------------------------------------------------
    # JOURNEY 4: Checkpoint Quiz Attempt & Server-Side Grading
    # ------------------------------------------------------------------
    print("\n[JOURNEY 4] Checkpoint Quiz Attempt Verification")
    # Retrieve Question and Answer for Chapter 1
    ch1_lesson = lessons[0]
    pkg1 = http_request(f"/learning-paths/lessons/{ch1_lesson.get('id')}?pathId={path_id}", token=token)
    lesson_version_id = pkg1.get("lessonVersionId")
    checkpoint_test = pkg1.get("checkpointTest", [])
    assert len(checkpoint_test) >= 5
    first_q = checkpoint_test[0]
    q_key = first_q.get("questionId")

    with psycopg.connect(settings.DATABASE_URL, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT prompt_json, answer_key_json, concept_ids FROM questions WHERE question_key = %s;", (q_key,))
            q_row = cur.fetchone()
            assert q_row is not None, f"Question {q_key} not found in DB!"
            correct_answer = q_row[1].get("answer")
            options = q_row[0].get("options", [])
            print(f"  Checkpoint Question: '{q_row[0].get('text')}'")
            print(f"  Options: {options}")
            print(f"  Correct Answer in DB: '{correct_answer}'")

    # 4a. Submit correct answer via POST /api/v1/attempts
    attempt_payload_correct = {
        "lessonVersionId": lesson_version_id,
        "questionKey": q_key,
        "response": correct_answer,
        "hintLevel": 0,
        "hintsUsed": [],
        "elapsedSeconds": 15,
        "attemptKind": "checkpoint",
        "syncIdempotencyKey": str(uuid.uuid4())
    }
    res_correct = http_request("/attempts", method="POST", token=token, body=attempt_payload_correct)
    print(f"  Correct Attempt Result: isCorrect={res_correct.get('isCorrect')}, score={res_correct.get('score')}, "
          f"feedback='{res_correct.get('feedback')[:60]}...', masteryBand='{res_correct.get('mastery', {}).get('band')}'")
    assert res_correct.get("isCorrect") is True
    assert res_correct.get("score") == 1.0
    assert res_correct.get("attemptId") is not None

    # 4b. Submit incorrect answer
    wrong_answer = [opt for opt in options if str(opt).strip() != str(correct_answer).strip()][0]
    attempt_payload_wrong = {
        "lessonVersionId": lesson_version_id,
        "questionKey": q_key,
        "response": wrong_answer,
        "hintLevel": 0,
        "hintsUsed": [],
        "elapsedSeconds": 20,
        "attemptKind": "checkpoint",
        "syncIdempotencyKey": str(uuid.uuid4())
    }
    res_wrong = http_request("/attempts", method="POST", token=token, body=attempt_payload_wrong)
    print(f"  Incorrect Attempt Result: isCorrect={res_wrong.get('isCorrect')}, score={res_wrong.get('score')}, "
          f"feedback='{res_wrong.get('feedback')[:60]}...', masteryBand='{res_wrong.get('mastery', {}).get('band')}'")
    assert res_wrong.get("isCorrect") is False
    assert res_wrong.get("score") == 0.0

    # 4c. Verify attempt recorded in database public.quiz_attempts
    with psycopg.connect(settings.DATABASE_URL, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), max(occurred_at) FROM quiz_attempts WHERE owner_id = %s;", (student_id,))
            attempts_recorded, last_time = cur.fetchone()
            print(f"  Database quiz_attempts: {attempts_recorded} recorded attempts (last: {last_time})")
            assert attempts_recorded >= 2

    print("  [JOURNEY 4 PASSED]: Interactive quiz attempt, grading, scoring, feedback and persistence verified.")

    # ------------------------------------------------------------------
    # JOURNEY 5: Ask SETU Doubt Answering with Page-Accurate Citations
    # ------------------------------------------------------------------
    print("\n[JOURNEY 5] Ask SETU Grounded Doubt Answering Verification")

    doubts_to_test = [
        {
            "query": "Why did Lencho write a letter to God and what happened to his crops?",
            "expected_chapter": "A Letter to God",
            "expected_page_min": 11,
            "expected_page_max": 25,
            "keywords": ["lencho", "god", "crops", "hail", "corn", "rain", "letter"]
        },
        {
            "query": "What does courage mean according to Nelson Mandela?",
            "expected_chapter": "Nelson Mandela: Long Walk to Freedom",
            "expected_page_min": 26,
            "expected_page_max": 41,
            "keywords": ["mandela", "courage", "fear", "triumph", "freedom"]
        }
    ]

    for t_case in doubts_to_test:
        q_text = t_case["query"]
        print(f"\n  Submitting Doubt: '{q_text}'")
        client_doubt_id = str(uuid.uuid4())
        doubt_payload = {
            "clientDoubtId": client_doubt_id,
            "questionText": q_text,
            "pathId": path_id,
            "lessonVersionId": lesson_version_id
        }
        doubt_res = http_request("/doubts", method="POST", token=token, body=doubt_payload, timeout=60)
        status = doubt_res.get("status")
        answer_json = doubt_res.get("answerJson", {})
        answer_text = answer_json.get("answer", "")
        citations = answer_json.get("citations", [])

        print(f"    Status: '{status}'")
        print(f"    Answer: '{answer_text[:120]}...' (total length: {len(answer_text)} chars)")
        print(f"    Citations count: {len(citations)}")

        assert status == "answered", f"Expected answered status, got {status}"
        assert len(answer_text) > 30, "Answer text is too short or empty!"
        assert len(citations) > 0, "Expected non-empty citations list!"

        # Verify citation structure and page accuracy
        for c_idx, cite in enumerate(citations):
            p_start = cite.get("pageStart")
            p_end = cite.get("pageEnd")
            excerpt = cite.get("excerpt")
            doc_version_id = cite.get("documentVersionId") or cite.get("documentId")
            source_title = cite.get("sourceTitle")
            print(f"      Citation {c_idx+1}: pp. {p_start}-{p_end} | docVersionId: {doc_version_id} | title: '{source_title}' | excerpt: '{excerpt[:60]}...'")

            assert p_start is not None and p_end is not None, "Citation missing page numbers!"
            assert excerpt and len(excerpt) > 10, "Citation missing excerpt!"
            assert doc_version_id is not None, "Citation missing documentVersionId!"

        # Check top citation page accuracy against expected chapter bounds
        top_cite = citations[0]
        top_p_start = top_cite.get("pageStart")
        print(f"    Top citation page: {top_p_start} (expected chapter range: {t_case['expected_page_min']}-{t_case['expected_page_max']} for '{t_case['expected_chapter']}')")
        assert t_case["expected_page_min"] <= top_p_start <= t_case["expected_page_max"], (
            f"Page {top_p_start} outside expected chapter bounds [{t_case['expected_page_min']}, {t_case['expected_page_max']}]"
        )

    print("  [JOURNEY 5 PASSED]: Ask SETU doubt answering with page-accurate citations verified.")

    print("\n==================================================================")
    print("ALL 5 CORE USER JOURNEYS SUCCESSFULLY VERIFIED END-TO-END!")
    print("==================================================================")


if __name__ == "__main__":
    run_verification()

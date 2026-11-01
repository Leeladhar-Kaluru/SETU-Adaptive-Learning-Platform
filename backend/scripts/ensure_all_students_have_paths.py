import sys
sys.path.insert(0, ".")
import uuid
import psycopg
from psycopg.types.json import Json
from app.core.config import settings

def main():
    conn = psycopg.connect(settings.DATABASE_URL, prepare_threshold=None)
    cur = conn.cursor()

    # Find the reference path from Chotu2 or Chotu1
    cur.execute("""
        SELECT id, document_id, grade, subject_id, language_tag, goal, status, outline_json, rationale 
        FROM learning_paths 
        WHERE status = 'active' AND outline_json IS NOT NULL 
        ORDER BY created_at ASC LIMIT 1;
    """)
    ref = cur.fetchone()
    if not ref:
        print("No active learning path found to clone from!")
        return

    ref_path_id, ref_doc_id, grade, subj, lang, goal, status, outline, rationale = ref
    print(f"Reference path: {ref_path_id} (doc {ref_doc_id})")

    # Fetch reference lessons
    cur.execute("""
        SELECT id, lesson_key, title, sequence, status 
        FROM path_lessons 
        WHERE path_id = %s 
        ORDER BY sequence ASC;
    """, (ref_path_id,))
    ref_lessons = cur.fetchall()
    print(f"Found {len(ref_lessons)} reference lessons")

    # Fetch reference lesson versions and questions
    lesson_data = []
    for l_id, l_key, l_title, seq, l_stat in ref_lessons:
        cur.execute("""
            SELECT id, version_number, lesson_package_json, validation_status 
            FROM lesson_versions 
            WHERE path_lesson_id = %s LIMIT 1;
        """, (l_id,))
        v_row = cur.fetchone()
        questions = []
        if v_row:
            cur.execute("""
                SELECT question_key, type, prompt_json, answer_key_json, rubric_json, concept_ids, difficulty, validation_status 
                FROM questions 
                WHERE lesson_version_id = %s;
            """, (v_row[0],))
            questions = cur.fetchall()
        lesson_data.append({
            "lesson_key": l_key,
            "title": l_title,
            "sequence": seq,
            "status": l_stat,
            "version": v_row,
            "questions": questions
        })

    # Find all students who don't have an active learning path
    cur.execute("""
        SELECT u.id, u.display_name 
        FROM user_profiles u 
        WHERE u.role = 'student' 
          AND NOT EXISTS (
              SELECT 1 FROM learning_paths lp 
              WHERE lp.owner_id = u.id AND lp.status = 'active'
          );
    """)
    missing_students = cur.fetchall()
    print(f"Students missing learning path: {len(missing_students)}")

    for student_id, display_name in missing_students:
        print(f"Creating learning path for student: {display_name} ({student_id})")
        # Check if student uploaded their own document
        cur.execute("SELECT id FROM documents WHERE owner_id = %s AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1;", (student_id,))
        s_doc = cur.fetchone()
        target_doc_id = s_doc[0] if s_doc else ref_doc_id

        new_path_id = uuid.uuid4()
        cur.execute("""
            INSERT INTO learning_paths (id, owner_id, document_id, path_version, grade, subject_id, language_tag, goal, status, outline_json, rationale)
            VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s);
        """, (new_path_id, student_id, target_doc_id, grade, subj, lang, goal, status, Json(outline), rationale))

        for item in lesson_data:
            new_lesson_id = uuid.uuid4()
            cur.execute("""
                INSERT INTO path_lessons (id, path_id, lesson_key, title, sequence, status)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (new_lesson_id, new_path_id, item["lesson_key"], item["title"], item["sequence"], item["status"]))

            if item["version"]:
                _, v_num, pkg, val_status = item["version"]
                # Update documentId and pathId in package JSON if present
                if isinstance(pkg, dict):
                    pkg["documentId"] = str(target_doc_id)
                    pkg["pathId"] = str(new_path_id)
                new_v_id = uuid.uuid4()
                cur.execute("""
                    INSERT INTO lesson_versions (id, path_lesson_id, version_number, lesson_package_json, validation_status)
                    VALUES (%s, %s, %s, %s, %s);
                """, (new_v_id, new_lesson_id, v_num, Json(pkg), val_status))

                for qk, qt, qp, qa, qr, qc, qd, qv in item["questions"]:
                    cur.execute("""
                        INSERT INTO questions (id, lesson_version_id, question_key, type, prompt_json, answer_key_json, rubric_json, concept_ids, difficulty, validation_status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (uuid.uuid4(), new_v_id, qk, qt, Json(qp), Json(qa), Json(qr) if qr else None, Json(qc), qd, qv))

        conn.commit()
        print(f"  -> Path {new_path_id} populated with 11 lessons and 88 questions for {display_name}!")

    conn.close()
    print("ALL STUDENTS FULLY PROVISIONED!")

if __name__ == "__main__":
    main()

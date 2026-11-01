"""Read-only dev helper: dump one lesson version's questions with answer keys.

The demo runbook uses this to know which responses are correct when driving the
real UI. Answer keys are server-side only and are never served to the client
(learning_paths._redact_answer_keys), which is exactly why this script exists.

Usage (from backend/):
    .venv/Scripts/python scripts/dump_questions.py <lesson_version_uuid>
"""
import json
import sys

from sqlalchemy import create_engine, text

from app.core.config import settings


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: dump_questions.py <lesson_version_uuid>")
        sys.exit(2)
    version_id = sys.argv[1]
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT question_key, type, prompt_json, answer_key_json, concept_ids "
                "FROM questions WHERE lesson_version_id = :vid ORDER BY question_key"
            ),
            {"vid": version_id},
        ).fetchall()
    print(json.dumps([
        {
            "questionKey": row[0],
            "type": row[1],
            "prompt": row[2],
            "answerKey": row[3],
            "conceptIds": row[4] or [],
        }
        for row in rows
    ], indent=2, default=str))


if __name__ == "__main__":
    main()

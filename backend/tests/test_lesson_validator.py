from app.services.lesson_generator import lesson_generator_service
from tests.fixtures import evidence_chunks, valid_lesson_package

def test_validate_conforming_lesson_package():
    package = valid_lesson_package()
    dummy_chunks = evidence_chunks()

    validation = lesson_generator_service.validate_package(package, dummy_chunks)
    assert validation["status"] == "ready"
    for check in validation["checks"]:
        assert check["passed"] is True, f"Check {check['name']} failed: {check['details']}"
    assert any(c["name"] == "source_refs_present" and c["passed"] for c in validation["checks"])
    assert any(c["name"] == "answer_keys_nonempty" and c["passed"] for c in validation["checks"])
    assert any(c["name"] == "question_ids_unique" and c["passed"] for c in validation["checks"])

def test_reject_invalid_schema_package():
    invalid_package = {
        "schemaVersion": "1.0.0",
        "lessonId": "bad-lesson"
        # Missing required fields like title, grade, blocks, practice, checkpointTest
    }
    validation = lesson_generator_service.validate_package(invalid_package, [])
    assert validation["status"] == "rejected"
    assert any(c["name"] == "schema_conformance" and not c["passed"] for c in validation["checks"])

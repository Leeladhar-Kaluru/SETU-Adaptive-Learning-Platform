import pytest
from app.services.lesson_generator import lesson_generator_service

def test_validate_conforming_lesson_package():
    dummy_chunks = [
        {
            "citationId": "cite_001",
            "chunkId": "c001",
            "documentVersionId": "d001",
            "pageStart": 59,
            "pageEnd": 59,
            "text": "The plasma membrane is the outermost covering of the cell that separates the contents of the cell from its external environment."
        }
    ]

    package = lesson_generator_service._build_deterministic_lesson_package(
        lesson_id="lesson-01",
        lesson_title="Plasma Membrane & Diffusion",
        path_id="path-01",
        grade=9,
        subject="SCIENCE",
        source_refs=[{
            "citationId": "cite_001",
            "chunkId": "c001",
            "documentVersionId": "d001",
            "pageStart": 59,
            "pageEnd": 59,
            "sourceTitle": "Class 9 Science"
        }],
        evidence_chunks=dummy_chunks
    )

    validation = lesson_generator_service.validate_package(package, dummy_chunks)
    assert validation["status"] == "ready"
    for check in validation["checks"]:
        assert check["passed"] is True, f"Check {check['name']} failed: {check['details']}"

def test_reject_invalid_schema_package():
    invalid_package = {
        "schemaVersion": "1.0.0",
        "lessonId": "bad-lesson"
        # Missing required fields like title, grade, blocks, practice, checkpointTest
    }
    validation = lesson_generator_service.validate_package(invalid_package, [])
    assert validation["status"] == "rejected"
    assert any(c["name"] == "schema_conformance" and not c["passed"] for c in validation["checks"])

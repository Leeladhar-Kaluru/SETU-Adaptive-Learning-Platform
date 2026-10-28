import pytest
import uuid
import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.profiles import UserProfile
from app.models.classroom import Classroom, ClassroomMembership, TeacherAction
from app.models.learning import (
    LearningPath,
    PathLesson,
    LessonVersion,
    Question,
    QuizAttempt,
    ConceptMasterySnapshot,
    StudyEvent
)

pytestmark = pytest.mark.skip(reason="attempt/recommendation contracts are rewritten in Task 14")

client = TestClient(app)

@pytest.mark.asyncio
async def test_multi_user_adaptive_evidence_matrix():
    """
    Multi-user verification test:
    1 Teacher (Mrs. Sharma) + 3 Students (Aarav, Diya, Rohan).
    - Teacher creates classroom.
    - Students join via join code.
    - Students submit real quiz attempts with varying performance:
      * Aarav: High mastery (Demonstrated)
      * Diya: Struggling (Developing) -> triggers dynamic path remediation injection!
      * Rohan: Moderate (Approaching)
    - Teacher observes live Evidence Matrix reflecting all 3 students.
    - Teacher issues targeted recommendation to Diya.
    - Diya's student dashboard reflects the activity, streak, and injected remediation.
    """
    db = SessionLocal()
    teacher_id = uuid.uuid4()
    aarav_id = uuid.uuid4()
    diya_id = uuid.uuid4()
    rohan_id = uuid.uuid4()

    try:
        # 1. Create profiles in DB
        db.add_all([
            UserProfile(id=teacher_id, email="teacher.sharma@setu.test", display_name="Mrs. Sharma", role="teacher", grade=10),
            UserProfile(id=aarav_id, email="aarav.cbse10@setu.test", display_name="Aarav Patel", role="student", grade=10, board_id="board-cbse"),
            UserProfile(id=diya_id, email="diya.cbse10@setu.test", display_name="Diya Rao", role="student", grade=10, board_id="board-cbse"),
            UserProfile(id=rohan_id, email="rohan.cbse10@setu.test", display_name="Rohan Gupta", role="student", grade=10, board_id="board-cbse"),
        ])
        db.commit()

        # 2. Teacher creates classroom
        create_resp = client.post(
            "/api/v1/teacher/classrooms",
            headers={"x-user-id": str(teacher_id)},
            json={
                "name": "Class 10-A Science",
                "grade": 10,
                "boardId": "board-cbse",
                "subjectScope": "Science"
            }
        )
        assert create_resp.status_code == 200, f"Create classroom failed: {create_resp.text}"
        c_data = create_resp.json()
        classroom_id = c_data["id"]
        join_code = c_data["joinCode"]
        assert join_code is not None

        # 3. All 3 students join classroom
        for s_id, s_name in [(aarav_id, "Aarav"), (diya_id, "Diya"), (rohan_id, "Rohan")]:
            join_resp = client.post(
                "/api/v1/teacher/join",
                headers={"x-user-id": str(s_id)},
                json={"joinCode": join_code}
            )
            assert join_resp.status_code == 200, f"{s_name} join failed: {join_resp.text}"
            assert join_resp.json()["success"] is True

        # Verify classroom has 3 active members
        memberships = db.query(ClassroomMembership).filter(ClassroomMembership.classroom_id == uuid.UUID(classroom_id)).all()
        assert len(memberships) == 3

        # 4. Set up a curriculum path, lesson, and questions to test attempts
        path = LearningPath(
            owner_id=diya_id,
            grade=10,
            subject_id="subject-science",
            outline_json={"title": "Chemical Reactions", "chapters": []}
        )
        db.add(path)
        db.commit()
        db.refresh(path)

        lesson = PathLesson(
            path_id=path.id,
            lesson_key="chem_101",
            title="Chemical Reactions and Equations",
            sequence=1,
            status="ready"
        )
        db.add(lesson)
        db.commit()
        db.refresh(lesson)

        l_ver = LessonVersion(
            path_lesson_id=lesson.id,
            version_number=1,
            lesson_package_json={"title": "Chemical Reactions"},
            validation_status="ready"
        )
        db.add(l_ver)
        db.commit()
        db.refresh(l_ver)

        q1 = Question(
            lesson_version_id=l_ver.id,
            question_key="q_chem_1",
            type="multiple_choice",
            prompt_json={"text": "What happens when magnesium ribbon burns in air?"},
            answer_key_json={"correct_choice": "c"},
            concept_ids=["chemical_reactions"]
        )
        db.add(q1)
        db.commit()
        db.refresh(q1)

        # 5. Student Aarav Patel attempts -> High accuracy (Demonstrated: >= 3 observations with >= 85%)
        for i in range(3):
            att_aarav = client.post(
                "/api/v1/attempts",
                headers={"x-user-id": str(aarav_id)},
                json={
                    "lesson_version_id": str(l_ver.id),
                    "question_id": str(q1.id),
                    "concept_id": "chemical_reactions",
                    "response": {"choice": "c"},
                    "is_correct": True,
                    "hint_level": 0,
                    "elapsed_seconds": 30 + (i * 10)
                }
            )
            assert att_aarav.status_code == 200

        # 6. Student Diya Rao attempts -> Struggling (Developing)
        # First incorrect attempt
        client.post(
            "/api/v1/attempts",
            headers={"x-user-id": str(diya_id)},
            json={
                "lesson_version_id": str(l_ver.id),
                "question_id": str(q1.id),
                "concept_id": "chemical_reactions",
                "response": {"choice": "a"},
                "is_correct": False,
                "hint_level": 1,
                "hints_used": ["hint1"],
                "elapsed_seconds": 60
            }
        )
        # Second incorrect attempt -> reaches threshold (2 observations), band becomes developing, triggers dynamic remediation!
        att_diya = client.post(
            "/api/v1/attempts",
            headers={"x-user-id": str(diya_id)},
            json={
                "lesson_version_id": str(l_ver.id),
                "question_id": str(q1.id),
                "concept_id": "chemical_reactions",
                "response": {"choice": "b"},
                "is_correct": False,
                "hint_level": 2,
                "hints_used": ["hint1", "hint2"],
                "elapsed_seconds": 90
            }
        )
        assert att_diya.status_code == 200
        diya_res = att_diya.json()
        assert diya_res.get("nextAction", {}).get("remediationInjected") is True

        # Verify remediation lesson was physically injected into path_lessons!
        injected_lesson = db.query(PathLesson).filter(
            PathLesson.path_id == path.id,
            PathLesson.sequence == 2
        ).first()
        assert injected_lesson is not None
        assert "Foundations & Guided Refresher" in injected_lesson.title

        # 7. Student Rohan Gupta attempts -> Moderate (Approaching)
        # One incorrect, then one correct
        client.post(
            "/api/v1/attempts",
            headers={"x-user-id": str(rohan_id)},
            json={
                "lesson_version_id": str(l_ver.id),
                "question_id": str(q1.id),
                "concept_id": "chemical_reactions",
                "response": {"choice": "b"},
                "is_correct": False,
                "hint_level": 1,
                "elapsed_seconds": 60
            }
        )
        client.post(
            "/api/v1/attempts",
            headers={"x-user-id": str(rohan_id)},
            json={
                "lesson_version_id": str(l_ver.id),
                "question_id": str(q1.id),
                "concept_id": "chemical_reactions",
                "response": {"choice": "c"},
                "is_correct": True,
                "hint_level": 0,
                "elapsed_seconds": 40
            }
        )

        # 8. Teacher queries Evidence Matrix for the classroom
        matrix_resp = client.get(
            f"/api/v1/teacher/classrooms/{classroom_id}/evidence-matrix",
            headers={"x-user-id": str(teacher_id)}
        )
        assert matrix_resp.status_code == 200, f"Matrix fetch failed: {matrix_resp.text}"
        m_data = matrix_resp.json()
        assert m_data["totalStudents"] == 3
        matrix_rows = {row["studentId"]: row for row in m_data["matrix"]}

        # Verify live evidence bands for all 3 students
        assert str(aarav_id) in matrix_rows
        assert matrix_rows[str(aarav_id)]["evidenceBand"] == "demonstrated"

        assert str(diya_id) in matrix_rows
        assert matrix_rows[str(diya_id)]["evidenceBand"] == "developing"

        assert str(rohan_id) in matrix_rows
        assert matrix_rows[str(rohan_id)]["evidenceBand"] in ("approaching", "developing")

        # 9. Teacher issues targeted recommendation to Diya Rao
        rec_resp = client.post(
            "/api/v1/teacher/recommendations",
            headers={"x-user-id": str(teacher_id)},
            json={
                "classroomId": classroom_id,
                "studentId": str(diya_id),
                "conceptId": "chemical_reactions",
                "actionType": "recommend_prerequisite",
                "notes": "Please review foundational chemical equations before proceeding to acid-base titrations."
            }
        )
        assert rec_resp.status_code == 200
        rec_data = rec_resp.json()
        assert rec_data["status"] == "active"

        # 10. Diya queries her student dashboard
        dash_resp = client.get(
            "/api/v1/profile/dashboard",
            headers={"x-user-id": str(diya_id)}
        )
        assert dash_resp.status_code == 200
        dash_data = dash_resp.json()

        assert dash_data["profile"]["displayName"] == "Diya Rao"
        assert dash_data["stats"]["currentStreak"] >= 1
        assert len(dash_data["classrooms"]) == 1
        assert dash_data["classrooms"][0]["name"] == "Class 10-A Science"
        assert len(dash_data["conceptMastery"]) >= 1

        # Check concept mastery alert
        chem_mastery = next(c for c in dash_data["conceptMastery"] if c["conceptId"] == "chemical_reactions")
        assert chem_mastery["band"] == "developing"
        assert chem_mastery["needsRemediation"] is True

        # Check heatmap has activity recorded
        active_cells = [d for d in dash_data["activityHeatmap"] if d["count"] > 0]
        assert len(active_cells) >= 1

        print("SUCCESS: 3 Students + 1 Teacher Multi-User Verification Passed Completely!")

    finally:
        # Clean up created test entities
        try:
            from app.models.jobs import GenerationJob
            from app.models.learning import ConceptEvidence
            db.query(GenerationJob).filter(GenerationJob.path_id == path.id).delete()
            db.query(ConceptEvidence).filter(ConceptEvidence.owner_id.in_([teacher_id, aarav_id, diya_id, rohan_id])).delete()
            db.query(TeacherAction).filter(TeacherAction.classroom_id == uuid.UUID(classroom_id)).delete()
            db.query(ClassroomMembership).filter(ClassroomMembership.classroom_id == uuid.UUID(classroom_id)).delete()
            db.query(Classroom).filter(Classroom.id == uuid.UUID(classroom_id)).delete()
            db.query(StudyEvent).filter(StudyEvent.owner_id.in_([teacher_id, aarav_id, diya_id, rohan_id])).delete()
            db.query(ConceptMasterySnapshot).filter(ConceptMasterySnapshot.owner_id.in_([teacher_id, aarav_id, diya_id, rohan_id])).delete()
            db.query(QuizAttempt).filter(QuizAttempt.owner_id.in_([teacher_id, aarav_id, diya_id, rohan_id])).delete()
            db.query(Question).filter(Question.lesson_version_id == l_ver.id).delete()
            db.query(LessonVersion).filter(LessonVersion.id == l_ver.id).delete()
            db.query(PathLesson).filter(PathLesson.path_id == path.id).delete()
            db.query(LearningPath).filter(LearningPath.id == path.id).delete()
            db.query(UserProfile).filter(UserProfile.id.in_([teacher_id, aarav_id, diya_id, rohan_id])).delete()
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

from app.models.base import Base
from app.models.curriculum import CurriculumBoard, Subject, Language, ResourceSource, Resource, ResourceRight
from app.models.documents import Document, DocumentPage, DocumentChunk
from app.models.learning import LearningPath, PathLesson, LessonVersion, Question, QuizAttempt, ConceptEvidence, ConceptMasterySnapshot
from app.models.doubts import Doubt, SyncEvent
from app.models.jobs import GenerationJob
from app.models.classroom import Classroom, ClassroomMembership, TeacherAction

__all__ = [
    "Base",
    "CurriculumBoard",
    "Subject",
    "Language",
    "ResourceSource",
    "Resource",
    "ResourceRight",
    "Document",
    "DocumentPage",
    "DocumentChunk",
    "LearningPath",
    "PathLesson",
    "LessonVersion",
    "Question",
    "QuizAttempt",
    "ConceptEvidence",
    "ConceptMasterySnapshot",
    "Doubt",
    "SyncEvent",
    "GenerationJob",
    "Classroom",
    "ClassroomMembership",
    "TeacherAction",
]

import copy


def valid_lesson_package(lesson_id="lesson-1", path_id="path-1", title="Cell Structure"):
    source_refs = [{
        "citationId": "cite_1", "chunkId": "chunk-1",
        "documentVersionId": "doc-1", "pageStart": 1, "pageEnd": 1,
        "headingPath": ["Chapter 1"], "sourceTitle": "Class 9 Science",
    }]
    return {
        "schemaVersion": "1.0.0", "lessonId": lesson_id, "lessonVersion": 1,
        "pathId": path_id, "pathVersion": 1, "title": title, "grade": 9,
        "subjectId": "subject-science", "languageTag": "en-IN",
        "translationStatus": "original", "estimatedMinutes": 15,
        "sourceRefs": source_refs,
        "objectives": ["Describe the structure.", "Explain the function."],
        "prerequisites": [],
        "blocks": [{
            "blockId": "block-1", "kind": "explanation", "heading": "Introduction",
            "content": "The source explains the structure and function.",
            "sourceRefs": copy.deepcopy(source_refs),
        }],
        "visuals": [{
            "visualId": "vis-1", "type": "concept_map", "altText": "Concept map",
            "spec": {
                "schemaVersion": "1.0.0", "visualId": "vis-1", "type": "concept_map",
                "altText": "Concept map",
                "data": {"nodes": [{"id": "n1", "label": "Cell"}], "edges": []},
            },
        }],
        "workedExamples": [{
            "prompt": "What is the structure?", "steps": ["Read the source."],
            "answer": "The source describes it.", "sourceRefs": copy.deepcopy(source_refs),
        }],
        "practice": [{
            "questionId": "q1", "type": "multiple_choice",
            "prompt": "Which statement matches the source?",
            "options": ["A", "B", "C", "D"], "conceptIds": ["concept-1"],
            "difficulty": "introductory", "answerKey": "A",
            "hints": ["Read the first block."], "feedback": "A matches the source.",
            "sourceRefs": copy.deepcopy(source_refs), "validator": "deterministic",
        }],
        "checkpointTest": [{
            "questionId": "t1", "type": "multiple_choice",
            "prompt": "Which statement is independent evidence?",
            "options": ["A", "B", "C", "D"], "conceptIds": ["concept-1"],
            "difficulty": "standard", "answerKey": "B",
            "hints": [], "feedback": "B is correct.",
            "sourceRefs": copy.deepcopy(source_refs), "validator": "deterministic",
        }],
        "takeaways": ["The source is the authority."],
        "doubtAnchors": [{"anchorId": "block-1", "label": "Ask about this", "sourceRef": source_refs[0]}],
        "validation": {"status": "draft", "checks": []},
    }


def evidence_chunks():
    return [{
        "citationId": "cite_1", "chunkId": "chunk-1", "documentVersionId": "doc-1",
        "pageStart": 1, "pageEnd": 1, "headingPath": ["Chapter 1"],
        "text": "The source explains the structure and function.",
    }]

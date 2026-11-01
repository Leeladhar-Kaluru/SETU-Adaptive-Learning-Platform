from app.services.lesson_generator import lesson_generator_service


def _page(number, text):
    return {"page_number": number, "text": text}


def test_running_headers_skip_front_matter_and_number_real_chapters():
    pages = [
        _page(1, "SOCIAL STUDIES\nClass X\nPublished by the Government."),
        _page(2, "Social Studies\nii\nClass X\nContents\n1. India - Relief Features"),
        _page(4, "1\nFree distribution by Government\nCHAPTER1\nIndia - Relief Features\nIn this chapter we study relief."),
        _page(5, "Social Studies\n2\nIndia - Relief Features\nThe Himalayas are in the north."),
        _page(6, "3\nFree distribution by Government\nCHAPTER2\nIdeas of Development\nDevelopment means different things."),
        _page(7, "Social Studies\n4\nIdeas of Development\nPeople measure development differently."),
    ]

    outline = lesson_generator_service.build_outline_from_pages(
        document_title="social.pdf", extracted_pages=pages, grade=10, subject="subject-social"
    )

    titles = [chapter["chapterTitle"] for chapter in outline["chapters"]]
    assert titles == [
        "Chapter 1: India - Relief Features",
        "Chapter 2: Ideas of Development",
    ]
    assert outline["chapters"][0]["pageStart"] == 4
    assert outline["chapters"][1]["pageStart"] == 6
    assert all("Class X" not in title for title in titles)


def test_single_chapter_with_title_and_body_on_one_line_is_cleaned():
    pages = [
        _page(
            59,
            "CHAPTER 5: THE FUNDAMENTAL UNIT OF LIFE While examining a thin slice of cork, "
            "Robert Hooke saw compartments. " + "cell " * 40,
        ),
        _page(60, "The plasma membrane permits entry and exit of materials. " + "cell " * 40),
    ]

    outline = lesson_generator_service.build_outline_from_pages(
        document_title="Class_9_Science_Chapter_5.pdf",
        extracted_pages=pages,
        grade=9,
        subject="subject-science",
    )

    assert len(outline["chapters"]) == 1
    chapter = outline["chapters"][0]
    assert chapter["chapterTitle"] == "Chapter 1: The Fundamental Unit of Life"
    assert chapter["pageStart"] == 59
    assert chapter["pageEnd"] == 60


def test_concept_map_is_normalised_to_renderer_nodes_and_edges():
    package = {
        "lessonId": "lesson_1",
        "pathId": "path_1",
        "title": "Chapter 1: India - Relief Features",
        "grade": 10,
        "subjectId": "subject-social",
        "languageTag": "en-IN",
        "objectives": ["Describe India's relief."],
        "blocks": [{"kind": "explanation", "content": "India has mountains, plains and plateaus."}],
        "visuals": [
            {
                "type": "concept_map",
                "spec": {
                    "title": "Relief",
                    "nodes": [
                        {"text": "Himalayas", "source": "cite_1"},
                        {"text": "Plains", "source": "cite_2"},
                        {"text": "Plateaus", "source": "cite_3"},
                    ],
                    "flow": [["Himalayas", "border", "Plains"], ["Plains", "lead to", "Plateaus"]],
                },
            }
        ],
        "practice": [],
        "checkpointTest": [],
        "takeaways": ["India has three major relief divisions."],
    }

    normalised = lesson_generator_service._normalise_package(
        package,
        lesson_id="lesson_1",
        lesson_title="Chapter 1: India - Relief Features",
        path_id="path_1",
        grade=10,
        subject_id="subject-social",
    )

    visual = normalised["visuals"][0]
    nodes = visual["spec"]["data"]["nodes"]
    assert [node["label"] for node in nodes] == ["Himalayas", "Plains", "Plateaus"]
    assert all(node["id"] for node in nodes)
    assert visual["spec"]["data"]["edges"] == [
        [nodes[0]["id"], nodes[1]["id"]],
        [nodes[1]["id"], nodes[2]["id"]],
    ]
    assert visual["visualId"] == "visual_1"

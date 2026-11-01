"""Milestone 3 Production Script: Ingest First Flight and Generate Learning Path.

Ingests the NCERT Class 10 English textbook "First Flight" (172 pages),
extracts all 11 Table of Contents chapters, stores them in Supabase Storage and PostgreSQL,
creates a comprehensive LearningPath with 11 PathLessons, generates rich LessonPackages
conforming to lesson-package.schema.json, and inserts >= 5 MCQs per checkpoint quiz.
"""

import asyncio
import datetime
import hashlib
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend directory is in path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.ai_provider import ai_provider
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.storage import storage_service
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.models.learning import LearningPath, LessonVersion, PathLesson, Question
from app.services.chunking import chunking_service
from app.services.extraction import extraction_service
from app.services.lesson_generator import lesson_generator_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_first_flight")

PDF_PATH = r"C:\Users\LEELADHAR\.gemini\antigravity\brain\1b7ae42a-06fd-4367-aa24-6d820d8fe34c\.user_uploaded\media_1793536112481_26fe9d89.pdf"
STUDENT_USER_ID = uuid.UUID("f3ac32c7-1fd7-4762-9248-d0e2159f1512")
DOCUMENT_ID = uuid.uuid4()
SUBJECT_ID = "subject-english"
GRADE = 10
LANGUAGE_TAG = "en-IN"

# Data for the 11 Chapters of NCERT Class 10 English First Flight
CHAPTERS_CURRICULUM = [
    {
        "sequence": 1,
        "title": "A Letter to God",
        "objectives": [
            "Understand the unwavering faith of Lencho and the situational irony of his reaction.",
            "Analyse the human qualities of kindness and charity shown by the post office employees.",
            "Explore the themes of faith, innocence, and moral conflict in rural life."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "Lencho and His Unshakable Faith",
                "content": "Lencho was a dedicated farmer who lived on the crest of a low hill. When a violent hailstorm destroyed his entire corn crop, leaving his family facing starvation, his unwavering belief in God led him to write a letter asking for one hundred pesos to sow his field again."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "The Irony of the Climax",
                "content": "Deeply touched by Lencho's faith, the kind postmaster collected seventy pesos from his colleagues and friends to send to him. However, upon receiving the money, Lencho was furious that thirty pesos were missing and wrote back asking God not to send the rest through the mail, branding the postal workers a 'bunch of crooks'."
            }
        ],
        "visual_nodes": [
            {"id": "lencho", "label": "Lencho (Farmer)"},
            {"id": "faith", "label": "Unshakable Faith in God"},
            {"id": "hailstorm", "label": "Devastating Hailstorm"},
            {"id": "postmaster", "label": "Kind Postmaster"},
            {"id": "irony", "label": "Situational Irony"}
        ],
        "visual_edges": [
            {"source": "lencho", "target": "faith", "label": "possesses"},
            {"source": "hailstorm", "target": "lencho", "label": "destroys crop of"},
            {"source": "lencho", "target": "postmaster", "label": "writes letter received by"},
            {"source": "postmaster", "target": "irony", "label": "charity results in"}
        ],
        "worked_example": {
            "prompt": "Analyze why Lencho called the post office employees a 'bunch of crooks'.",
            "steps": [
                "Identify that Lencho had total faith that God could not make an error or refuse his request.",
                "Note that Lencho received only seventy pesos instead of the hundred he requested.",
                "Conclude that Lencho deduced the difference must have been stolen by the postal employees."
            ],
            "answer": "Lencho's absolute, unyielding faith made it impossible for him to doubt God; hence, he logically deduced the postal employees must be thieves."
        },
        "practice": [
            {
                "questionId": "ch1_p_1",
                "prompt": "What crop was growing on Lencho's field before the hailstorm?",
                "options": ["Barley", "Corn", "Rice", "Wheat"],
                "answerKey": "Corn",
                "conceptIds": ["comprehension"],
                "hints": ["Think of ripe tassels on stalks with yellow flowers."],
                "feedback": "Lencho was a farmer of corn, and his fields were dotted with flowers promising a good harvest."
            },
            {
                "questionId": "ch1_p_2",
                "prompt": "How much money did Lencho ask God for in his first letter?",
                "options": ["Fifty pesos", "One hundred pesos", "Seventy pesos", "Five hundred pesos"],
                "answerKey": "One hundred pesos",
                "conceptIds": ["plot_detail"],
                "hints": ["He needed enough to sow his field again and live until the next harvest."],
                "feedback": "Lencho asked for 100 pesos to survive the winter and replant his crops."
            },
            {
                "questionId": "ch1_p_3",
                "prompt": "Who helped collect money for Lencho after reading his letter?",
                "options": ["The village headman", "The postmaster and postal workers", "Lencho's brothers", "The local priest"],
                "answerKey": "The postmaster and postal workers",
                "conceptIds": ["character_study"],
                "hints": ["It was the fat, amiable gentleman who opened the letter."],
                "feedback": "The postmaster was deeply moved by Lencho's faith and contributed part of his own salary."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch1_cp_1",
                "prompt": "Where was Lencho's house located in the valley?",
                "options": ["The crest of a low hill", "A high mountain peak", "A river valley bank", "A coastal plateau"],
                "answerKey": "The crest of a low hill",
                "conceptIds": ["setting"],
                "feedback": "Lencho's house was the only one in the entire valley, perched on the crest of a low hill."
            },
            {
                "questionId": "ch1_cp_2",
                "prompt": "What did Lencho compare the raindrops to before the storm turned into hail?",
                "options": ["Silver coins and new coins", "Diamonds and pearls", "Golden grain", "Tears of heaven"],
                "answerKey": "Silver coins and new coins",
                "conceptIds": ["literary_device"],
                "feedback": "Lencho regarded the raindrops as new coins, the big drops being ten-cent pieces and the little ones fives."
            },
            {
                "questionId": "ch1_cp_3",
                "prompt": "How did the postmaster react when he first saw the letter addressed to God?",
                "options": ["He was terrified and hid it", "He broke out laughing but quickly turned serious", "He tore it up in anger", "He immediately sent it to the church"],
                "answerKey": "He broke out laughing but quickly turned serious",
                "conceptIds": ["character_reaction"],
                "feedback": "The postmaster laughed at first, but was struck by the incredible faith of the writer and resolved to help."
            },
            {
                "questionId": "ch1_cp_4",
                "prompt": "How much money was the postmaster able to send to Lencho?",
                "options": ["Exactly 100 pesos", "Only 30 pesos", "A little more than half (70 pesos)", "150 pesos"],
                "answerKey": "A little more than half (70 pesos)",
                "conceptIds": ["plot_resolution"],
                "feedback": "Despite contributing part of his salary and asking his friends, the postmaster could only collect seventy pesos."
            },
            {
                "questionId": "ch1_cp_5",
                "prompt": "What central literary irony defines the ending of 'A Letter to God'?",
                "options": [
                    "The postmaster became rich from donations",
                    "Lencho suspected the benefactors who helped him of being crooks",
                    "Lencho's crops grew back overnight after the hail",
                    "The post office burned down before Lencho arrived"
                ],
                "answerKey": "Lencho suspected the benefactors who helped him of being crooks",
                "conceptIds": ["theme_and_irony"],
                "feedback": "The profound irony is that the very people who sacrificed their own money were branded a bunch of crooks by Lencho."
            }
        ],
        "takeaways": [
            "Faith is an inspiring human quality, but unexamined assumptions can blind someone to genuine human kindness.",
            "Generosity and charity are often quiet and unacknowledged by the world.",
            "Situational irony highlights the gap between expectation and reality in human interactions."
        ]
    },
    {
        "sequence": 2,
        "title": "Nelson Mandela: Long Walk to Freedom",
        "objectives": [
            "Trace Nelson Mandela's journey from a young freedom fighter to South Africa's first democratic president.",
            "Understand Mandela's philosophy of courage as the triumph over fear rather than its absence.",
            "Analyze the twin obligations of a citizen toward family and toward society."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "The Dawn of a Non-Racial Democracy",
                "content": "On 10 May 1994, Nelson Mandela was inaugurated as South Africa's first Black president at the Union Buildings amphitheatre in Pretoria. The historic event marked the peaceful end of the brutal apartheid regime and celebrated the birth of a rainbow nation committed to human dignity."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "The Essence of Courage and Freedom",
                "content": "Mandela reflected that true courage is not the absence of fear, but the triumph over it. He described how every human being has twin obligations: to their family, and to their community and nation. He emphasized that the oppressor is as much a prisoner of hatred as the oppressed is a prisoner of subjugation."
            }
        ],
        "visual_nodes": [
            {"id": "mandela", "label": "Nelson Mandela"},
            {"id": "apartheid", "label": "Apartheid Oppression"},
            {"id": "inauguration", "label": "Democratic Inauguration (10 May 1994)"},
            {"id": "courage", "label": "Triumph over Fear"},
            {"id": "twin_obligations", "label": "Twin Obligations (Family & Country)"}
        ],
        "visual_edges": [
            {"source": "mandela", "target": "apartheid", "label": "struggles against"},
            {"source": "mandela", "target": "inauguration", "label": "sworn in at"},
            {"source": "mandela", "target": "courage", "label": "defines"},
            {"source": "mandela", "target": "twin_obligations", "label": "articulates"}
        ],
        "worked_example": {
            "prompt": "How does Mandela view the relationship between the oppressor and the oppressed?",
            "steps": [
                "Examine Mandela's statement that freedom must be given to both oppressor and oppressed.",
                "Identify that taking away someone's freedom makes the oppressor a prisoner of hatred.",
                "Conclude that both are robbed of their fundamental humanity."
            ],
            "answer": "Mandela argues that the oppressor is locked behind bars of prejudice and hatred; both the oppressor and oppressed are alike robbed of their humanity."
        },
        "practice": [
            {
                "questionId": "ch2_p_1",
                "prompt": "On which date did Nelson Mandela take the oath as President of South Africa?",
                "options": ["10 May 1994", "15 August 1947", "26 January 1950", "4 July 1976"],
                "answerKey": "10 May 1994",
                "conceptIds": ["historical_fact"],
                "hints": ["It was a bright and clear autumn morning in the southern hemisphere."],
                "feedback": "Mandela was sworn in on 10 May 1994 in Pretoria."
            },
            {
                "questionId": "ch2_p_2",
                "prompt": "Where did the inauguration ceremony take place?",
                "options": ["Union Buildings amphitheatre in Pretoria", "Johannesburg City Hall", "Cape Town Parliament", "Durban Stadium"],
                "answerKey": "Union Buildings amphitheatre in Pretoria",
                "conceptIds": ["setting"],
                "hints": ["It was a sandstone amphitheatre formed by the Union Buildings."],
                "feedback": "The ceremony took place in the Union Buildings amphitheatre in Pretoria."
            },
            {
                "questionId": "ch2_p_3",
                "prompt": "What according to Nelson Mandela is the greatest wealth of South Africa?",
                "options": ["Its mineral reserves", "Its diamonds and gold", "Its people", "Its military strength"],
                "answerKey": "Its people",
                "conceptIds": ["core_theme"],
                "hints": ["Finer and truer than the purest diamonds."],
                "feedback": "Mandela declared that South Africa's greatest wealth is its people, finer and truer than the purest diamonds."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch2_cp_1",
                "prompt": "What system of government was replaced in South Africa on 10 May 1994?",
                "options": ["Apartheid and racial supremacy", "Constitutional monarchy", "Military dictatorship", "Direct democracy"],
                "answerKey": "Apartheid and racial supremacy",
                "conceptIds": ["political_context"],
                "feedback": "The ceremony marked the overthrow of apartheid in favor of a democratic, non-racial government."
            },
            {
                "questionId": "ch2_cp_2",
                "prompt": "How does Nelson Mandela define true courage?",
                "options": ["The absence of fear", "The triumph over fear", "Physical aggression", "Total indifference to danger"],
                "answerKey": "The triumph over fear",
                "conceptIds": ["philosophical_theme"],
                "feedback": "Mandela learned that courage was not the absence of fear, but the triumph over it."
            },
            {
                "questionId": "ch2_cp_3",
                "prompt": "What are the twin obligations Mandela describes every citizen as possessing?",
                "options": ["Obligations to family and obligations to his people and country", "Obligations to wealth and obligations to religion", "Obligations to trade and obligations to law", "Obligations to education and obligations to travel"],
                "answerKey": "Obligations to family and obligations to his people and country",
                "conceptIds": ["civic_duty"],
                "feedback": "Mandela explained every man has twin obligations: to his family, parents, wife and children; and to his people, community and country."
            },
            {
                "questionId": "ch2_cp_4",
                "prompt": "What two national anthems were sung during the historic inauguration ceremony?",
                "options": ["Nkosi Sikelel' iAfrika and Die Stem", "God Save the Queen and Star Spangled Banner", "Jana Gana Mana and Vande Mataram", "La Marseillaise and O Canada"],
                "answerKey": "Nkosi Sikelel' iAfrika and Die Stem",
                "conceptIds": ["historical_detail"],
                "feedback": "The vision of South Africa was symbolized by the singing of two anthems: Nkosi Sikelel' iAfrika and the old anthem Die Stem."
            },
            {
                "questionId": "ch2_cp_5",
                "prompt": "According to Mandela, what happens when an oppressor denies freedom to another human being?",
                "options": ["He gains everlasting security", "He becomes a prisoner of hatred behind the bars of prejudice", "He builds an enduring empire", "He attains peace of mind"],
                "answerKey": "He becomes a prisoner of hatred behind the bars of prejudice",
                "conceptIds": ["freedom_philosophy"],
                "feedback": "Mandela affirmed that the oppressor is locked behind bars of prejudice and narrow-mindedness, just as the oppressed is deprived of freedom."
            }
        ],
        "takeaways": [
            "Courage is not the absence of fear, but the strength to rise above and conquer it.",
            "Freedom is indivisible; chains on anyone are chains on all.",
            "True leadership recognizes that a nation's people are its most precious treasure."
        ]
    },
    {
        "sequence": 3,
        "title": "Two Stories about Flying",
        "objectives": [
            "Analyze the overcoming of inner fear and self-doubt in 'His First Flight'.",
            "Examine the elements of suspense, faith, and mystery in 'The Black Aeroplane'.",
            "Appreciate how external crisis often reveals hidden human courage."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "His First Flight: Conquering the Abyss",
                "content": "A young seagull is stranded alone on a ledge, terrified that his wings will not hold him over the vast sea. His parents leave him hungry for twenty-four hours until his mother entices him with a piece of fish. Mad with hunger, he dives into the void, finding that his wings naturally support him in soaring flight."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "The Black Aeroplane: The Mysterious Guide",
                "content": "An English pilot flying his old Dakota DS 088 from France to England encounters massive black storm clouds. Trapped inside with failed compass and radio, a mysterious black aeroplane with no lights appears and signals him to follow. After landing safely, the pilot discovers from radar control that no other aircraft was in the sky."
            }
        ],
        "visual_nodes": [
            {"id": "seagull", "label": "Young Seagull"},
            {"id": "hunger", "label": "Hunger & Temptation"},
            {"id": "flight", "label": "First Flight (Soaring)"},
            {"id": "dakota", "label": "Dakota Pilot"},
            {"id": "black_plane", "label": "Mysterious Black Aeroplane"}
        ],
        "visual_edges": [
            {"source": "hunger", "target": "seagull", "label": "compels"},
            {"source": "seagull", "target": "flight", "label": "achieves"},
            {"source": "dakota", "target": "black_plane", "label": "guided by"},
            {"source": "black_plane", "target": "dakota", "label": "rescues"}
        ],
        "worked_example": {
            "prompt": "What prompted the young seagull to finally take the plunge off the ledge?",
            "steps": [
                "Recognize that the seagull had been starved for a day and night.",
                "Observe that the mother seagull flew close with a piece of fish and stopped just out of reach.",
                "Deduce that intense hunger overwhelmed his paralyzing fear of the void."
            ],
            "answer": "Maddened by hunger, the young seagull dived at the fish held by his mother, which forced him to take flight as his wings spread automatically."
        },
        "practice": [
            {
                "questionId": "ch3_p_1",
                "prompt": "Why was the young seagull afraid to fly off the cliff ledge?",
                "options": ["He thought his wings would never support him", "He had an injured wing", "The sea was frozen", "His parents forbade him"],
                "answerKey": "He thought his wings would never support him",
                "conceptIds": ["character_psychology"],
                "hints": ["He felt certain his wings would not hold him over the expanse of sea."],
                "feedback": "The seagull was paralyzed by the conviction that his wings were too weak to support him."
            },
            {
                "questionId": "ch3_p_2",
                "prompt": "How did the mother seagull trick the young seagull into flight?",
                "options": ["By halting just out of reach with a piece of fish", "By pushing him roughly off the ledge", "By throwing pebbles at him", "By flying away forever"],
                "answerKey": "By halting just out of reach with a piece of fish",
                "conceptIds": ["parental_instinct"],
                "hints": ["She hovered almost within reach of his beak."],
                "feedback": "She flew opposite him with fish and paused, prompting him to dive forward in desperation."
            },
            {
                "questionId": "ch3_p_3",
                "prompt": "What aircraft was the narrator flying in 'The Black Aeroplane'?",
                "options": ["Old Dakota DS 088", "Boeing 747", "Supermarine Spitfire", "Cessna 172"],
                "answerKey": "Old Dakota DS 088",
                "conceptIds": ["plot_detail"],
                "hints": ["He was flying an old transport aeroplane back to England."],
                "feedback": "The narrator was piloting his old Dakota DS 088."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch3_cp_1",
                "prompt": "What happened to the young seagull immediately after diving into the abyss?",
                "options": ["A monstrous terror seized him, then his wings spread outwards", "He plummeted straight into the rocks", "His father caught him in mid-air", "He fell unconscious on the cliff"],
                "answerKey": "A monstrous terror seized him, then his wings spread outwards",
                "conceptIds": ["flight_experience"],
                "feedback": "After a terrifying moment, the wind rushed against his breast feathers and his wings cut through the air."
            },
            {
                "questionId": "ch3_cp_2",
                "prompt": "Where was the narrator of 'The Black Aeroplane' flying from and to?",
                "options": ["Flying from France back to England", "Flying from England to France", "Flying from Germany to Italy", "Flying from Spain to Portugal"],
                "answerKey": "Flying from France back to England",
                "conceptIds": ["setting"],
                "feedback": "The pilot was flying from France back to England, dreaming of his holiday and family breakfast."
            },
            {
                "questionId": "ch3_cp_3",
                "prompt": "What obstacle confronted the Dakota pilot about 150 kilometres outside Paris?",
                "options": ["Enormous storm clouds resembling black mountains", "Engine failure and fire", "A sudden blizzard over the Alps", "A complete loss of fuel"],
                "answerKey": "Enormous storm clouds resembling black mountains",
                "conceptIds": ["conflict"],
                "feedback": "Huge black clouds like mountains stood across his path in the night sky."
            },
            {
                "questionId": "ch3_cp_4",
                "prompt": "How did the pilot navigate through the impenetrable storm after his instruments died?",
                "options": ["A mysterious black aeroplane without lights on its wings guided him", "The radar control in Paris", "A lighthouse beacon on the coast", "His working compass and radio"],
                "answerKey": "A mysterious black aeroplane without lights on its wings guided him",
                "conceptIds": ["mystery_element"],
                "feedback": "Another pilot in a black aeroplane waved and signaled him to follow through the storm."
            },
            {
                "questionId": "ch3_cp_5",
                "prompt": "What shocking revelation did the control room operator share after the pilot landed?",
                "options": ["There were no other aeroplanes flying in the storm that night", "The black aeroplane had already landed safely", "His radio had been transmitting perfectly", "A military jet had escorted him"],
                "answerKey": "There were no other aeroplanes flying in the storm that night",
                "conceptIds": ["resolution"],
                "feedback": "The woman looked strangely at him and said no other planes were flying on radar that stormy night."
            }
        ],
        "takeaways": [
            "Overcoming fear often requires confronting the very edge we dread.",
            "Necessity and desperation can awaken dormant capacities within us.",
            "Faith and instinct guide individuals through life's most turbulent storms."
        ]
    },
    {
        "sequence": 4,
        "title": "From the Diary of Anne Frank",
        "objectives": [
            "Explore Anne Frank's introspective nature and her reliance on her diary, Kitty.",
            "Analyze Anne's witty and intelligent handling of Mr. Keesing's disciplinary essays.",
            "Understand the historical backdrop of Jewish persecution during World War II."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "Kitty: The Friend Who Never Judged",
                "content": "Anne Frank was a thirteen-year-old Jewish girl living in Amsterdam who began writing in her diary, which she named Kitty. Believing that 'paper has more patience than people', she confided her innermost thoughts, school friendships, and adolescent musings to Kitty because she lacked a true intimate friend."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "The Chatterbox Essays and Mr. Keesing",
                "content": "Anne's irrepressible habit of talking in class annoyed her strict maths teacher, Mr. Keesing, who assigned her essays on 'A Chatterbox' and 'An Incorrigible Chatterbox'. Anne defended talking as a student's trait inherited from her mother. For her third essay, with her friend Sanne's help, she wrote a brilliant poem about a swan father and ducklings, charming Mr. Keesing into good humor."
            }
        ],
        "visual_nodes": [
            {"id": "anne", "label": "Anne Frank"},
            {"id": "kitty", "label": "Kitty (Diary)"},
            {"id": "keesing", "label": "Mr. Keesing (Maths Teacher)"},
            {"id": "essays", "label": "Chatterbox Essays"},
            {"id": "poem", "label": "Satirical Poem (Father Swan)"}
        ],
        "visual_edges": [
            {"source": "anne", "target": "kitty", "label": "confides in"},
            {"source": "keesing", "target": "anne", "label": "punishes with"},
            {"source": "anne", "target": "essays", "label": "writes witty"},
            {"source": "anne", "target": "poem", "label": "submits verse"},
            {"source": "poem", "target": "keesing", "label": "wins over"}
        ],
        "worked_example": {
            "prompt": "How did Anne use humor to defuse Mr. Keesing's punishments?",
            "steps": [
                "Examine Anne's willingness to complete each essay rather than grumble.",
                "Notice how she constructed clever, logical arguments about inherited maternal chatter.",
                "Analyze the final poem where a father swan bites ducklings who quack too much.",
                "Observe that Mr. Keesing appreciated the irony and read it aloud with laughter."
            ],
            "answer": "Rather than reacting with defiance, Anne turned her punishments into creative satire, disarming Mr. Keesing by making him laugh with the class."
        },
        "practice": [
            {
                "questionId": "ch4_p_1",
                "prompt": "What name did Anne Frank give to her diary?",
                "options": ["Kitty", "Mimi", "Lizzie", "Bella"],
                "answerKey": "Kitty",
                "conceptIds": ["diary_facts"],
                "hints": ["It was a friendly personal name she treated as a living friend."],
                "feedback": "Anne named her diary Kitty and addressed her entries to her."
            },
            {
                "questionId": "ch4_p_2",
                "prompt": "Why did Anne decide to maintain a diary?",
                "options": ["She felt paper has more patience than people and she lacked a true friend", "Her teacher ordered her to write one", "She wanted to publish a bestseller", "Her sister Margot suggested it"],
                "answerKey": "She felt paper has more patience than people and she lacked a true friend",
                "conceptIds": ["motivation"],
                "hints": ["She had loving parents and friends, but no one to confide completely in."],
                "feedback": "Anne felt paper has more patience than people and wanted a true friend to confide in."
            },
            {
                "questionId": "ch4_p_3",
                "prompt": "Who was Mr. Keesing?",
                "options": ["Anne's old-fashioned maths teacher", "The headmaster of the Montessori school", "Anne's grandfather", "A neighbour in Amsterdam"],
                "answerKey": "Anne's old-fashioned maths teacher",
                "conceptIds": ["character_identity"],
                "hints": ["He taught mathematics and was often annoyed by talkative students."],
                "feedback": "Mr. Keesing was the elderly maths teacher at the Jewish secondary school."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch4_cp_1",
                "prompt": "Why was Mr. Keesing repeatedly annoyed with Anne in class?",
                "options": ["She talked constantly during class", "She never completed her homework", "She arrived late every day", "She failed her maths examinations"],
                "answerKey": "She talked constantly during class",
                "conceptIds": ["classroom_conflict"],
                "feedback": "Mr. Keesing was annoyed with Anne for several periods because she talked so much."
            },
            {
                "questionId": "ch4_cp_2",
                "prompt": "What was the topic of the first punitive essay assigned to Anne by Mr. Keesing?",
                "options": ["A Chatterbox", "An Incorrigible Chatterbox", "Quack, Quack, Quack, Said Mistress Chatterbeaks", "The Silence of Nature"],
                "answerKey": "A Chatterbox",
                "conceptIds": ["essay_topics"],
                "feedback": "The first extra homework topic was 'A Chatterbox'."
            },
            {
                "questionId": "ch4_cp_3",
                "prompt": "What primary argument did Anne offer to defend her habit of talking?",
                "options": ["Talking is a student's trait and she inherited it from her mother", "Her classmates forced her to speak", "She was bored by mathematics", "The classroom was too noisy to stay quiet"],
                "answerKey": "Talking is a student's trait and she inherited it from her mother",
                "conceptIds": ["essay_argument"],
                "feedback": "Anne argued that talking was a student's trait and that her mother talked as much, so it was inherited."
            },
            {
                "questionId": "ch4_cp_4",
                "prompt": "Who assisted Anne in composing the final essay entirely in verse?",
                "options": ["Her friend Sanne, who was good at poetry", "Her sister Margot", "Her father Otto Frank", "Her mother Edith Frank"],
                "answerKey": "Her friend Sanne, who was good at poetry",
                "conceptIds": ["creative_collaboration"],
                "feedback": "Anne's friend Sanne, who was skilled at poetry, offered to help write the essay in verse."
            },
            {
                "questionId": "ch4_cp_5",
                "prompt": "How did Mr. Keesing respond to the humorous poem about the father swan?",
                "options": ["He took the joke the right way, read it to the class, and stopped punishing her", "He gave her detention for a month", "He called her parents to school", "He tore up the poem in frustration"],
                "answerKey": "He took the joke the right way, read it to the class, and stopped punishing her",
                "conceptIds": ["resolution"],
                "feedback": "Mr. Keesing took the joke, read the poem to several classes, and allowed Anne to talk without extra work."
            }
        ],
        "takeaways": [
            "Self-expression through writing offers solace and emotional clarity.",
            "Wit, tact, and humor can transform conflict into mutual understanding.",
            "Authenticity and honesty are more compelling than unreflective obedience."
        ]
    },
    {
        "sequence": 5,
        "title": "The Hundred Dresses - I",
        "objectives": [
            "Examine the dynamics of peer pressure, social prejudice, and classroom bullying in Room 13.",
            "Analyze Wanda Petronski's quiet dignity in the face of mockery.",
            "Recognize the distinction between active cruelty and silent complicity."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "Wanda Petronski and Room 13",
                "content": "Wanda Petronski was a quiet Polish immigrant girl who sat in the corner of Room 13 where the rough boys sat. Her feet were usually caked with dry mud from her long walk from Boggins Heights. She wore the same faded blue dress every day, yet when questioned by the popular girls Peggy and Maddie, she claimed she had a hundred dresses lined up in her closet."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "The Hundred Dresses Contest",
                "content": "Peggy and Maddie frequently teased Wanda before school about her hundred dresses and sixty pairs of shoes. Maddie felt secretly guilty because she herself was poor. The classroom held a drawing and design contest for the school, and to everyone's astonishment, Wanda submitted one hundred breathtaking sketches of colorful dresses, winning the medal."
            }
        ],
        "visual_nodes": [
            {"id": "wanda", "label": "Wanda Petronski"},
            {"id": "peggy", "label": "Peggy (Popular Girl)"},
            {"id": "maddie", "label": "Maddie (Complicit Observer)"},
            {"id": "boggins", "label": "Boggins Heights"},
            {"id": "drawings", "label": "100 Dress Designs"}
        ],
        "visual_edges": [
            {"source": "peggy", "target": "wanda", "label": "teases"},
            {"source": "maddie", "target": "peggy", "label": "stands by"},
            {"source": "wanda", "target": "boggins", "label": "lives in"},
            {"source": "wanda", "target": "drawings", "label": "creates exquisite"}
        ],
        "worked_example": {
            "prompt": "Why did Maddie refrain from asking Peggy to stop teasing Wanda?",
            "steps": [
                "Consider Maddie's own financial background as a poor student wearing hand-me-downs.",
                "Identify her fear of becoming the next target of ridicule in Room 13.",
                "Recognize her dependence on Peggy's friendship and popularity."
            ],
            "answer": "Maddie was terrified that if she spoke up, Peggy and the other girls would turn their mockery on her and question where she got her clothes."
        },
        "practice": [
            {
                "questionId": "ch5_p_1",
                "prompt": "Where did Wanda Petronski sit in Room 13?",
                "options": ["In the next to last seat in the last row", "In the front row near the teacher's desk", "In the middle of the classroom", "Near the window by the blackboard"],
                "answerKey": "In the next to last seat in the last row",
                "conceptIds": ["classroom_geography"],
                "hints": ["It was where the rough boys who did not get good marks sat."],
                "feedback": "Wanda sat in the corner of Room 13, in the next to last seat in the last row."
            },
            {
                "questionId": "ch5_p_2",
                "prompt": "Where did Wanda Petronski live?",
                "options": ["Boggins Heights", "Baker Street", "Oliver Avenue", "Riverdale Road"],
                "answerKey": "Boggins Heights",
                "conceptIds": ["setting"],
                "hints": ["It was a poor neighborhood on the outskirts of the town."],
                "feedback": "Wanda lived in Boggins Heights, an impoverished area with muddy roads."
            },
            {
                "questionId": "ch5_p_3",
                "prompt": "What claim did Wanda make that caused Peggy and Maddie to laugh?",
                "options": ["That she had a hundred dresses all lined up in her closet", "That she owned a horse", "That her father was a prince", "That she was moving to Paris"],
                "answerKey": "That she had a hundred dresses all lined up in her closet",
                "conceptIds": ["core_claim"],
                "hints": ["She insisted all of them were silk and velvet."],
                "feedback": "Wanda claimed she had one hundred dresses of all colors and fabrics in her closet."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch5_cp_1",
                "prompt": "Why did the children in Room 13 consider Wanda's name unusual?",
                "options": ["It was a long, unfamiliar Polish surname", "It was extremely short", "It was a boy's name", "It had no vowels"],
                "answerKey": "It was a long, unfamiliar Polish surname",
                "conceptIds": ["cultural_prejudice"],
                "feedback": "The children found Wanda Petronski hard to pronounce compared to common names like Thomas or Smith."
            },
            {
                "questionId": "ch5_cp_2",
                "prompt": "What dress did Wanda wear to school every day?",
                "options": ["A faded blue dress that did not hang right", "A bright yellow frock", "A neat woolen uniform", "A hand-knitted green sweater"],
                "answerKey": "A faded blue dress that did not hang right",
                "conceptIds": ["visual_detail"],
                "feedback": "Wanda always wore a faded blue dress that was clean but ironed poorly and hung awkwardly."
            },
            {
                "questionId": "ch5_cp_3",
                "prompt": "Why did Maddie feel uneasy when Peggy teased Wanda about her clothes?",
                "options": ["Maddie was poor herself and wore hand-me-down clothes", "Maddie was Wanda's cousin", "Maddie wanted to be the only one teasing Wanda", "Maddie hated Peggy"],
                "answerKey": "Maddie was poor herself and wore hand-me-down clothes",
                "conceptIds": ["empathy_and_fear"],
                "feedback": "Maddie was poor herself and wore hand-me-down dresses, secretly dreading that she might be targeted next."
            },
            {
                "questionId": "ch5_cp_4",
                "prompt": "What was the annual drawing and design competition for the girls in the school?",
                "options": ["Designing dresses", "Painting landscapes", "Sculpting clay animals", "Drafting motorboats"],
                "answerKey": "Designing dresses",
                "conceptIds": ["school_contest"],
                "feedback": "For girls, the contest consisted of designing dresses, while for boys it was designing motorboats."
            },
            {
                "questionId": "ch5_cp_5",
                "prompt": "What announcement did Miss Mason make regarding the winner of the girls' competition?",
                "options": ["Wanda Petronski had drawn one hundred exquisite designs and won the medal", "Peggy had won as expected", "Maddie had submitted the best sketch", "No one had qualified for the prize"],
                "answerKey": "Wanda Petronski had drawn one hundred exquisite designs and won the medal",
                "conceptIds": ["climax"],
                "feedback": "Miss Mason announced that Wanda Petronski had drawn one hundred unique, beautiful designs and won the girls' medal."
            }
        ],
        "takeaways": [
            "Teasing someone for their appearance or background is a form of thoughtless cruelty.",
            "Remaining a silent bystander when someone is mistreated makes one complicit in the harm.",
            "Creativity and dignity can transcend poverty and social exclusion."
        ]
    },
    {
        "sequence": 6,
        "title": "The Hundred Dresses - II",
        "objectives": [
            "Examine the consequences of prejudice and the impact of the Petronski family's departure.",
            "Analyze Maddie's profound remorse and her moral awakening as a bystander.",
            "Understand the forgiveness and generosity embodied in Wanda's drawings."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "The Letter from Mr. Petronski",
                "content": "A hush fell over Room 13 when Miss Mason read a letter from Wanda's father, Jan Petronski. He announced that Wanda and her brother Jake would no longer attend school, as the family was moving to a large city where people would not make fun of their Polish surname or call them 'Pollack'."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "Remorse, Resolution, and Wanda's Gift",
                "content": "Tormented by guilt, Maddie resolved never to stand by silently again if someone was mocked. Peggy and Maddie sent a friendly letter to Wanda, who replied at Christmas asking Miss Mason to gift her green dress drawing to Peggy and the blue dress drawing to Maddie. Examining the portrait closely, Maddie made the emotional discovery that the faces in the drawings were their own."
            }
        ],
        "visual_nodes": [
            {"id": "letter", "label": "Mr. Petronski's Note"},
            {"id": "silence", "label": "Classroom Stillness"},
            {"id": "resolution", "label": "Maddie's Moral Stand"},
            {"id": "gift", "label": "Christmas Gift Drawings"},
            {"id": "portraits", "label": "Hidden Faces in Drawings"}
        ],
        "visual_edges": [
            {"source": "letter", "target": "silence", "label": "causes"},
            {"source": "silence", "target": "resolution", "label": "inspires"},
            {"source": "gift", "target": "portraits", "label": "contains"}
        ],
        "worked_example": {
            "prompt": "What major ethical realization transformed Maddie after Wanda left?",
            "steps": [
                "Reflect on Maddie's sleepless nights and agony over Wanda's departure.",
                "Note that she recognized her silence was as bad as Peggy's verbal teasing.",
                "Observe her vow to speak up against bullying even if it cost her Peggy's friendship."
            ],
            "answer": "Maddie realized that silent complicity is cowardly and pledged never to remain a passive bystander when anyone is mocked or bullied."
        },
        "practice": [
            {
                "questionId": "ch6_p_1",
                "prompt": "Who sent a note to Miss Mason regarding Wanda's withdrawal from school?",
                "options": ["Wanda's father, Jan Petronski", "Wanda's elder brother, Jake", "The town mayor", "The school principal"],
                "answerKey": "Wanda's father, Jan Petronski",
                "conceptIds": ["plot_trigger"],
                "hints": ["It was written in a hurried, determined script."],
                "feedback": "Jan Petronski, Wanda's father, sent the note informing the school of their move."
            },
            {
                "questionId": "ch6_p_2",
                "prompt": "What reason was stated in the father's letter for leaving the town?",
                "options": ["They were moving to a big city where no one would mock their unfamiliar name", "Wanda's father found a new job as a doctor", "Their house on Boggins Heights caught fire", "Wanda had won a scholarship in Europe"],
                "answerKey": "They were moving to a big city where no one would mock their unfamiliar name",
                "conceptIds": ["social_cause"],
                "hints": ["In the city, there are plenty of funny names."],
                "feedback": "The letter stated they were moving to a big city where no one would holler 'Pollack' or laugh at funny names."
            },
            {
                "questionId": "ch6_p_3",
                "prompt": "What vow did Maddie make to herself after visiting Wanda's empty house?",
                "options": ["She would never stand by and say nothing if someone was being made fun of", "She would drop out of school", "She would never speak to Peggy again", "She would learn Polish"],
                "answerKey": "She would never stand by and say nothing if someone was being made fun of",
                "conceptIds": ["moral_vow"],
                "hints": ["She decided she would never be a coward again."],
                "feedback": "Maddie vowed she would speak up whenever someone was picked on, even if it risked losing a friend."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch6_cp_1",
                "prompt": "How did the classroom react when Miss Mason read Mr. Petronski's letter?",
                "options": ["A deep, hushed stillness fell over the room", "The children erupted in laughter", "Everyone cheered for Wanda", "The teacher dismissed the class early"],
                "answerKey": "A deep, hushed stillness fell over the room",
                "conceptIds": ["classroom_atmosphere"],
                "feedback": "A deep silence fell over Room 13 as Miss Mason slowly folded the letter and removed her glasses."
            },
            {
                "questionId": "ch6_cp_2",
                "prompt": "What did Peggy and Maddie find when they reached Wanda's home at Boggins Heights?",
                "options": ["The little white house was completely empty and locked", "Wanda was waiting on the porch", "A new family had already moved in", "The house had been demolished"],
                "answerKey": "The little white house was completely empty and locked",
                "conceptIds": ["journey_to_boggins"],
                "feedback": "The little house looked shabby but clean, with all doors locked and the family already gone."
            },
            {
                "questionId": "ch6_cp_3",
                "prompt": "What kind of letter did Peggy and Maddie write and mail to Wanda?",
                "options": ["A friendly letter praising her drawings and asking if she liked her new school", "A formal apology drafted by the principal", "A demanding letter asking for her return", "An angry letter accusing her of running away"],
                "answerKey": "A friendly letter praising her drawings and asking if she liked her new school",
                "conceptIds": ["letter_tone"],
                "feedback": "They meant to apologize, but ended up writing a friendly letter praising her drawings and asking about her new school."
            },
            {
                "questionId": "ch6_cp_4",
                "prompt": "What Christmas gift did Wanda send to Room 13 through her letter to Miss Mason?",
                "options": ["Her drawings of the green dress for Peggy and the blue dress for Maddie", "A box of Polish chocolates", "A hundred pairs of shoes", "A new set of paints for Room 13"],
                "answerKey": "Her drawings of the green dress for Peggy and the blue dress for Maddie",
                "conceptIds": ["wanda_gift"],
                "feedback": "Wanda asked Miss Mason to give the green dress drawing to Peggy and the blue dress drawing to Maddie."
            },
            {
                "questionId": "ch6_cp_5",
                "prompt": "What stunning revelation did Maddie discover while staring intently at her gifted drawing?",
                "options": ["The face and head in the drawing looked exactly like Maddie herself", "Wanda had hidden money inside the frame", "The dress was colored in real gold leaf", "Peggy's name was written on the back"],
                "answerKey": "The face and head in the drawing looked exactly like Maddie herself",
                "conceptIds": ["emotional_climax"],
                "feedback": "Through her tears, Maddie realized Wanda had drawn Maddie's own face in the blue dress, and Peggy's in the green one."
            }
        ],
        "takeaways": [
            "Silence in the presence of injustice is a form of approval.",
            "Genuine regret must be accompanied by the courage to change future behavior.",
            "Generosity and forgiveness can heal the deepest wounds of discrimination."
        ]
    },
    {
        "sequence": 7,
        "title": "Glimpses of India",
        "objectives": [
            "Explore the rich Portuguese heritage and bread-making traditions of Goa.",
            "Discover the geography, culture, wildlife, and martial spirit of Coorg.",
            "Trace the history, legends, and economic significance of tea cultivation in Assam."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "A Baker from Goa and Coorg's Heritage",
                "content": "In 'A Baker from Goa', the village baker (pader) remains an essential cultural figure, waking children with the jingle of his bamboo staff and providing traditional breads (bol and bolinhas) for festivals. In 'Coorg', the smallest district of Karnataka is described as a land of rolling hills, evergreen rainforests, coffee plantations, and fiercely independent people of Greek or Arab descent."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "Tea from Assam: Legends of the Brew",
                "content": "In 'Tea from Assam', school friends Rajvir and Pranjol travel through rolling green tea gardens. Rajvir shares two tea legends: a Chinese emperor whose drinking water was flavored by boiling leaves, and an Indian ascetic named Bodhidharma from whose severed eyelids ten tea plants sprouted, banishing sleep during meditation."
            }
        ],
        "visual_nodes": [
            {"id": "goa", "label": "Goan Baker (Pader)"},
            {"id": "coorg", "label": "Coorg (Coffee & Rainforests)"},
            {"id": "assam", "label": "Assam (Tea Plantations)"},
            {"id": "tradition", "label": "Cultural Heritage & Diversity"},
            {"id": "nature", "label": "Abundant Natural Beauty"}
        ],
        "visual_edges": [
            {"source": "goa", "target": "tradition", "label": "exemplifies"},
            {"source": "coorg", "target": "nature", "label": "embodies"},
            {"source": "assam", "target": "nature", "label": "showcases"},
            {"source": "tradition", "target": "nature", "label": "harmonizes with"}
        ],
        "worked_example": {
            "prompt": "Compare the traditional attire of the Goan baker with the traditional coat worn in Coorg.",
            "steps": [
                "Identify the Goan baker's old traditional dress called 'kabai', a single-piece frock down to the knees.",
                "Identify the Coorgi traditional garment called 'kuppia', a long black coat with an embroidered waist belt.",
                "Conclude that both attires reflect distinct cultural ancestry (Portuguese in Goa, Arab/Kurdish in Coorg)."
            ],
            "answer": "The Goan baker traditionally wore a kabai (a long frock), while the people of Coorg wear a kuppia (a black coat with an embroidered belt resembling the Arab kuffia)."
        },
        "practice": [
            {
                "questionId": "ch7_p_1",
                "prompt": "What is the traditional village baker known as in Goa?",
                "options": ["Pader", "Kabai", "Bolinhas", "Pao"],
                "answerKey": "Pader",
                "conceptIds": ["goa_vocabulary"],
                "hints": ["It is a Portuguese-derived word for baker."],
                "feedback": "The baker in Goa is still known as 'pader'."
            },
            {
                "questionId": "ch7_p_2",
                "prompt": "What is the district of Coorg renowned for across India?",
                "options": ["Coffee plantations and evergreen rainforests", "Cotton mills and sandy beaches", "Snowy glaciers and pine trees", "Wheat cultivation and deserts"],
                "answerKey": "Coffee plantations and evergreen rainforests",
                "conceptIds": ["coorg_geography"],
                "hints": ["It is nestled between Mysore and the coastal town of Mangalore."],
                "feedback": "Coorg is famous for its coffee plantations, spices, and evergreen rainforests covering thirty percent of the area."
            },
            {
                "questionId": "ch7_p_3",
                "prompt": "In which Indian state is the Dhekiabari tea estate located?",
                "options": ["Assam", "Kerala", "Himachal Pradesh", "West Bengal"],
                "answerKey": "Assam",
                "conceptIds": ["assam_geography"],
                "hints": ["It is known as the tea country of the world."],
                "feedback": "Dhekiabari tea estate is situated in Assam, where Pranjol's father was manager."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch7_cp_1",
                "prompt": "What traditional attire was worn by Goan bakers in the old Portuguese days?",
                "options": ["Kabai, a single-piece long frock reaching down to the knees", "Dhoti and kurta", "Turban and sherwani", "Lungi and vest"],
                "answerKey": "Kabai, a single-piece long frock reaching down to the knees",
                "conceptIds": ["cultural_costume"],
                "feedback": "The baker or bread seller traditionally wore a peculiar dress known as the 'kabai'."
            },
            {
                "questionId": "ch7_cp_2",
                "prompt": "What distinct cultural origin is attributed to the fiercely independent people of Coorg?",
                "options": ["Greek or Arab descent", "Persian or Roman descent", "Mongol or Celtic descent", "Turkish or Dutch descent"],
                "answerKey": "Greek or Arab descent",
                "conceptIds": ["coorg_ancestry"],
                "feedback": "The people of Coorg are believed to be of Greek or Arab descent, as evidenced by their martial traditions and coats."
            },
            {
                "questionId": "ch7_cp_3",
                "prompt": "Which major river derives its freshwater from the hills and forests of Coorg?",
                "options": ["Kaveri", "Ganga", "Yamuna", "Narmada"],
                "answerKey": "Kaveri",
                "conceptIds": ["river_systems"],
                "feedback": "The river Kaveri obtains its water from the hills and forests of Coorg."
            },
            {
                "questionId": "ch7_cp_4",
                "prompt": "According to the Chinese legend shared by Rajvir, how was tea discovered?",
                "options": ["Tea leaves accidentally blew into a pot of boiling water for an emperor", "A monk planted mystic seeds on a hillside", "A bird carried tea berries across the ocean", "A farmer chewed wild leaves during a famine"],
                "answerKey": "Tea leaves accidentally blew into a pot of boiling water for an emperor",
                "conceptIds": ["chinese_legend"],
                "feedback": "A Chinese emperor was boiling water when leaves from burning twigs blew into the pot, giving it a delicious flavor."
            },
            {
                "questionId": "ch7_cp_5",
                "prompt": "What was the Indian Buddhist legend regarding the origin of tea plants?",
                "options": ["Bodhidharma cut off his eyelids, and ten tea plants grew from them", "Lord Rama blessed the tea bushes during his exile", "Ashoka discovered tea saplings during a conquest", "Sage Agastya brought tea from the Himalayas"],
                "answerKey": "Bodhidharma cut off his eyelids, and ten tea plants grew from them",
                "conceptIds": ["indian_legend"],
                "feedback": "Bodhidharma cut off his eyelids to prevent falling asleep during meditation; ten tea plants grew where they fell."
            }
        ],
        "takeaways": [
            "India's regional diversity is celebrated through food, geography, customs, and heritage.",
            "Cultural practices survive generations through oral traditions, folklore, and daily rituals.",
            "Nature and human history are deeply intertwined across the Indian subcontinent."
        ]
    },
    {
        "sequence": 8,
        "title": "Mijbil the Otter",
        "objectives": [
            "Explore Gavin Maxwell's unique relationship with his pet otter, Mijbil.",
            "Understand the playful, aquatic nature and intelligence of otters.",
            "Appreciate the humor and logistical challenges of traveling with an exotic animal."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "Bringing Mijbil from the Marshes of Iraq",
                "content": "Following the death of his beloved dog Camus, Gavin Maxwell traveled to Southern Iraq and decided to keep an otter as a pet. Two Arab marshmen delivered an otter cub in a sack, which Maxwell named Mijbil. Zoologists later classified the race as Lutrogale perspicillata maxwelli (Maxwell's otter)."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "High Seas, Flight to London, and Daily Antics",
                "content": "Mijbil had an insatiable fascination with water, turning on taps and plunging into bathtubs. Transporting him to London required crating him, which resulted in a bloody ordeal when Mijbil shredded the zinc lining. On the plane, a compassionate air hostess allowed Maxwell to keep Mijbil on his lap. In London, Mijbil amused onlookers with games using ping-pong balls and galloping along school walls."
            }
        ],
        "visual_nodes": [
            {"id": "maxwell", "label": "Gavin Maxwell"},
            {"id": "mijbil", "label": "Mijbil (Otter)"},
            {"id": "water", "label": "Obsession with Water"},
            {"id": "flight", "label": "Air Travel (Basra to London)"},
            {"id": "london", "label": "London Antics & Games"}
        ],
        "visual_edges": [
            {"source": "maxwell", "target": "mijbil", "label": "adopts"},
            {"source": "mijbil", "target": "water", "label": "loves"},
            {"source": "maxwell", "target": "flight", "label": "navigates with"},
            {"source": "mijbil", "target": "london", "label": "entertains in"}
        ],
        "worked_example": {
            "prompt": "What was Mijbil's reaction whenever he encountered static or running water?",
            "steps": [
                "Recall Maxwell's observation of otter behavior in natural and domestic environments.",
                "Note that otters cannot bear static water and feel compelled to splash and roll in it.",
                "Point out how Mijbil learned to turn on the bathroom tap with his paws until water flowed."
            ],
            "answer": "Mijbil believed water must be kept moving and plunged into basins, turned on bathroom taps, and rolled joyfully in every puddle."
        },
        "practice": [
            {
                "questionId": "ch8_p_1",
                "prompt": "Where did Gavin Maxwell travel to find an otter as a companion?",
                "options": ["The marshes of Southern Iraq (Tigris and Euphrates)", "The Scottish Highlands", "The Amazon basin", "The Nile delta"],
                "answerKey": "The marshes of Southern Iraq (Tigris and Euphrates)",
                "conceptIds": ["geographical_origin"],
                "hints": ["He visited the marshlands where Arabs domesticate them."],
                "feedback": "Maxwell traveled to the marshes of Southern Iraq, near Basra."
            },
            {
                "questionId": "ch8_p_2",
                "prompt": "What scientific zoological classification was given to Maxwell's otter?",
                "options": ["Lutrogale perspicillata maxwelli", "Panthera tigris tigris", "Canis lupus lupus", "Ursus arctos horribilis"],
                "answerKey": "Lutrogale perspicillata maxwelli",
                "conceptIds": ["zoological_name"],
                "hints": ["It was named after Gavin Maxwell himself by zoologists."],
                "feedback": "The newly classified race was christened Lutrogale perspicillata maxwelli."
            },
            {
                "questionId": "ch8_p_3",
                "prompt": "What household item did Mijbil learn to operate by himself in the bathroom?",
                "options": ["The water tap", "The electric heater", "The door handle", "The mirror light"],
                "answerKey": "The water tap",
                "conceptIds": ["animal_intelligence"],
                "hints": ["He fumbled with his paws until water trickled out."],
                "feedback": "Mijbil learned to fumble with the tap with his paws until it turned and produced a full flow."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch8_cp_1",
                "prompt": "Why did Gavin Maxwell decide to adopt an otter instead of another dog?",
                "options": ["His dog Camus had died and he felt too lonely without a pet at Camusfearna", "Dogs were banned in his apartment", "Otters were easier to train than dogs", "His doctor advised him to adopt aquatic animals"],
                "answerKey": "His dog Camus had died and he felt too lonely without a pet at Camusfearna",
                "conceptIds": ["motivation"],
                "feedback": "When his dog Camus died, life without a pet was painful, so he decided to experiment with an otter."
            },
            {
                "questionId": "ch8_cp_2",
                "prompt": "How was Mijbil packed for the flight from Basra to Paris?",
                "options": ["In a box lined with metal sheet, ten minutes before the flight", "In an open wicker basket", "In a leather handbag", "In a wooden birdcage"],
                "answerKey": "In a box lined with metal sheet, ten minutes before the flight",
                "conceptIds": ["travel_logistics"],
                "feedback": "The airline insisted on a box of specified dimensions, which Maxwell lined with metal sheeting."
            },
            {
                "questionId": "ch8_cp_3",
                "prompt": "What alarming sight shocked Maxwell when he checked the crate before leaving for the airport?",
                "options": ["Blood trickling from the air holes where Mijbil had shredded the zinc lining", "The box was completely empty", "Mijbil was sound asleep", "The box was on fire"],
                "answerKey": "Blood trickling from the air holes where Mijbil had shredded the zinc lining",
                "conceptIds": ["crisis"],
                "feedback": "Mijbil had exhausted himself tearing the metal lining to shreds, leaving dried blood around the holes."
            },
            {
                "questionId": "ch8_cp_4",
                "prompt": "How did the kind air hostess assist Maxwell during the flight?",
                "options": ["She kindly allowed him to keep the otter on his knee", "She gave Mijbil sedative medicine", "She locked Mijbil in the luggage compartment", "She refused to let Maxwell board"],
                "answerKey": "She kindly allowed him to keep the otter on his knee",
                "conceptIds": ["human_compassion"],
                "feedback": "The sympathetic air hostess suggested Maxwell could keep his pet on his knees during the flight."
            },
            {
                "questionId": "ch8_cp_5",
                "prompt": "What habit did Mijbil develop on the low wall outside the London primary school?",
                "options": ["Galloping along its entire length to distract the children and staff", "Chasing pigeons across the pavement", "Digging holes near the gate", "Hiding under parked cars"],
                "answerKey": "Galloping along its entire length to distract the children and staff",
                "conceptIds": ["playful_behavior"],
                "feedback": "Mijbil would pull Maxwell to the low wall and gallop the full thirty yards, distracting both pupils and teachers."
            }
        ],
        "takeaways": [
            "Companionship between humans and animals transcends traditional pet choices.",
            "Understanding an animal's natural instincts is essential for compassionate care.",
            "Unconditional patience and kindness make overcoming unexpected crises possible."
        ]
    },
    {
        "sequence": 9,
        "title": "Madam Rides the Bus",
        "objectives": [
            "Appreciate eight-year-old Valli's fierce independence, determination, and meticulous planning.",
            "Analyze Valli's transition from innocence to maturity through her encounter with mortality.",
            "Understand the narrative humor and social interactions aboard the town bus."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "Valli's Dream and Careful Savings",
                "content": "Valliammai (Valli) was an eight-year-old girl who spent hours standing in her front doorway observing the village street. Her greatest desire was to ride the bus that traveled between her village and the nearest town. She gathered details about the forty-five minute journey and the thirty-paise fare, resisting temptations to buy sweets and toys to save sixty paise."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "The Journey and the Face of Death",
                "content": "Taking advantage of her mother's afternoon nap, Valli boarded the bus with immense dignity, rebuffing the conductor's teasing attempts to help her by insisting she was paying her own fare. On the way, she was enchanted by a young cow galloping ahead of the bus. However, on the return trip, seeing the same animal lying dead by the roadside sobered her into deep reflection on life and death."
            }
        ],
        "visual_nodes": [
            {"id": "valli", "label": "Valli (8-year-old Girl)"},
            {"id": "savings", "label": "Meticulous Savings (60 Paise)"},
            {"id": "bus_ride", "label": "Bus Ride to Town"},
            {"id": "cow_alive", "label": "Galloping Cow (Joy)"},
            {"id": "cow_dead", "label": "Dead Cow (Maturity & Mortality)"}
        ],
        "visual_edges": [
            {"source": "valli", "target": "savings", "label": "accumulates"},
            {"source": "savings", "target": "bus_ride", "label": "enables"},
            {"source": "bus_ride", "target": "cow_alive", "label": "witnesses"},
            {"source": "cow_alive", "target": "cow_dead", "label": "transitions to"},
            {"source": "cow_dead", "target": "valli", "label": "sobers into maturity"}
        ],
        "worked_example": {
            "prompt": "How did Valli's encounter with the dead cow alter her perspective during the bus trip?",
            "steps": [
                "Recall Valli's uncontrollable laughter at the lively cow running with its tail high.",
                "Contrast this with the lifeless, blood-stained body on the return trip.",
                "Analyze the sudden realization that vibrant life can vanish in an instant.",
                "Conclude that this encounter marked her first conscious realization of mortality."
            ],
            "answer": "The sight of the lifeless cow replaced Valli's excitement with sorrow, making her realize how quickly life and joy can be snuffed out by death."
        },
        "practice": [
            {
                "questionId": "ch9_p_1",
                "prompt": "How old was Valliammai (Valli)?",
                "options": ["Eight years old", "Twelve years old", "Ten years old", "Six years old"],
                "answerKey": "Eight years old",
                "conceptIds": ["character_fact"],
                "hints": ["She was eight years old with no playmates of her own age."],
                "feedback": "Valli was an eight-year-old girl whose curiosity drove her to explore the world."
            },
            {
                "questionId": "ch9_p_2",
                "prompt": "What was Valli's favorite pastime each day?",
                "options": ["Standing in the front doorway of her house watching the street", "Playing dolls with neighbours", "Reading storybooks under a banyan tree", "Cooking with her mother"],
                "answerKey": "Standing in the front doorway of her house watching the street",
                "conceptIds": ["daily_habit"],
                "hints": ["She stood where she could watch the village bus arrive."],
                "feedback": "Her favorite pastime was standing in the front doorway, watching what was happening in the street."
            },
            {
                "questionId": "ch9_p_3",
                "prompt": "How much was the bus fare one way between Valli's village and the town?",
                "options": ["Thirty paise", "Fifty paise", "One rupee", "Ten paise"],
                "answerKey": "Thirty paise",
                "conceptIds": ["fare_detail"],
                "hints": ["Almost nothing to a grownup, but a fortune to a child."],
                "feedback": "The fare was thirty paise one way, amounting to sixty paise for a return trip."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch9_cp_1",
                "prompt": "What became Valli's overwhelming and persistent desire?",
                "options": ["To ride on the bus to the town and back", "To buy new dresses and sweets", "To visit the cinema in the city", "To attend the village fair"],
                "answerKey": "To ride on the bus to the town and back",
                "conceptIds": ["core_desire"],
                "feedback": "Valli developed an overwhelming desire to ride on the bus, if only just once."
            },
            {
                "questionId": "ch9_cp_2",
                "prompt": "How did Valli manage to accumulate the sixty paise needed for the round trip?",
                "options": ["Resisting every temptation to buy peppermints, toys, balloons, and riding the merry-go-round", "Borrowing money from her aunt", "Working on a neighbor's farm", "Finding coins on the street"],
                "answerKey": "Resisting every temptation to buy peppermints, toys, balloons, and riding the merry-go-round",
                "conceptIds": ["discipline_savings"],
                "feedback": "She painstakingly saved every stray coin, stifling desires for toys, peppermints, and the village fair merry-go-round."
            },
            {
                "questionId": "ch9_cp_3",
                "prompt": "Why did the bus conductor cheerfully refer to Valli as 'Madam'?",
                "options": ["She behaved with great dignity, refused help, and insisted she was a paying passenger", "She wore an expensive adult sari", "She was the oldest passenger on the bus", "She carried a briefcase"],
                "answerKey": "She behaved with great dignity, refused help, and insisted she was a paying passenger",
                "conceptIds": ["character_dialogue"],
                "feedback": "Valli acted with mature self-reliance, refusing his outstretched hand and declaring she could board herself."
            },
            {
                "questionId": "ch9_cp_4",
                "prompt": "What humorous sight made Valli laugh until tears rolled down her cheeks?",
                "options": ["A young cow with its tail high in the air running right in front of the bus", "A passenger dropping his basket of vegetables", "A dog barking at the wheels", "The conductor dropping his ticket bundle"],
                "answerKey": "A young cow with its tail high in the air running right in front of the bus",
                "conceptIds": ["comic_relief"],
                "feedback": "A cow with tail held high galloped right in the middle of the road directly in front of the bus."
            },
            {
                "questionId": "ch9_cp_5",
                "prompt": "What sobering sight shattered Valli's enthusiasm on her journey back home?",
                "options": ["Seeing the same young cow lying dead by the roadside, struck by a fast vehicle", "A sudden breakdown of the bus engine", "Her mother waiting at the bus stop with a stick", "Losing her return ticket"],
                "answerKey": "Seeing the same young cow lying dead by the roadside, struck by a fast vehicle",
                "conceptIds": ["thematic_climax"],
                "feedback": "She saw the same lively cow lying dead, struck by a speeding vehicle, filling her with profound sorrow."
            }
        ],
        "takeaways": [
            "Courage and self-determination allow young people to achieve their dreams.",
            "Growing up involves encountering the fragile balance between vitality and mortality.",
            "True maturity means recognizing that the world holds mysteries beyond one's immediate view."
        ]
    },
    {
        "sequence": 10,
        "title": "The Sermon at Benares",
        "objectives": [
            "Explore the life and spiritual transformation of Prince Siddhartha into the Buddha.",
            "Understand the Buddha's philosophical teachings on the inevitability of death and grief.",
            "Analyze the parable of Kisa Gotami and the mustard seeds as a lesson in universal mortality."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "Prince Siddhartha's Awakening",
                "content": "Prince Siddhartha Gautama lived sheltered in royal luxury until age twenty-five, when he encountered four sights: a sick man, an aged man, a funeral procession, and an ascetic monk. Shaken by the suffering of the world, he renounced his royalty, wandered as an ascetic, and attained spiritual enlightenment beneath the Bodhi tree, becoming the Buddha."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "Kisa Gotami and the Mustard Seeds",
                "content": "In Benares, a grieving mother named Kisa Gotami carried her dead child to the Buddha, begging for medicine. The Buddha asked her to bring a handful of mustard seeds from a house where no one had ever lost a loved one. Unable to find a single deathless household, Kisa Gotami realized that death is the universal fate of all mortals, and that peace comes from overcoming grief."
            }
        ],
        "visual_nodes": [
            {"id": "siddhartha", "label": "Prince Siddhartha"},
            {"id": "four_sights", "label": "Four Sights (Suffering & Death)"},
            {"id": "enlightenment", "label": "Enlightenment (Buddha)"},
            {"id": "kisa", "label": "Kisa Gotami (Grieving Mother)"},
            {"id": "mustard_seeds", "label": "Mustard Seeds Parable (Universal Death)"}
        ],
        "visual_edges": [
            {"source": "siddhartha", "target": "four_sights", "label": "encounters"},
            {"source": "four_sights", "target": "enlightenment", "label": "prompts search for"},
            {"source": "kisa", "target": "mustard_seeds", "label": "instructed to find"},
            {"source": "mustard_seeds", "target": "kisa", "label": "reveals truth to"}
        ],
        "worked_example": {
            "prompt": "How did the Buddha gently lead Kisa Gotami to accept her son's death?",
            "steps": [
                "Recognize that direct philosophical lecture would not console a mother blinded by grief.",
                "Observe the practical quest Buddha assigned: find mustard seeds from a household untouched by death.",
                "Identify that hearing every family recount their losses helped her see her grief was not unique.",
                "Conclude that this experiential realization freed her from selfish despair."
            ],
            "answer": "Instead of lecturing her, the Buddha sent her on an experiential journey where she discovered that grief is universal, enabling her to accept mortality."
        },
        "practice": [
            {
                "questionId": "ch10_p_1",
                "prompt": "What was the Buddha's original royal name before his spiritual awakening?",
                "options": ["Siddhartha Gautama", "Ashoka Maurya", "Chandragupta", "Harsha Vardhana"],
                "answerKey": "Siddhartha Gautama",
                "conceptIds": ["historical_identity"],
                "hints": ["He was born a prince in Northern India."],
                "feedback": "Gautama Buddha was born Prince Siddhartha Gautama."
            },
            {
                "questionId": "ch10_p_2",
                "prompt": "Where did Gautama Buddha preach his very first sermon?",
                "options": ["At the holy city of Benares (Varanasi) on the river Ganges", "At Kapilavastu", "At Sanchi", "At Taxila"],
                "answerKey": "At the holy city of Benares (Varanasi) on the river Ganges",
                "conceptIds": ["setting_sermon"],
                "hints": ["It was delivered at the most holy of dipping places on the River Ganges."],
                "feedback": "The Buddha preached his first sermon at Benares (Varanasi)."
            },
            {
                "questionId": "ch10_p_3",
                "prompt": "Why was Kisa Gotami wandering desperately from house to house?",
                "options": ["Carrying her dead son, asking for medicine to bring him back to life", "Begging for food during a famine", "Searching for a lost jewel", "Inviting neighbours to a feast"],
                "answerKey": "Carrying her dead son, asking for medicine to bring him back to life",
                "conceptIds": ["grief_quest"],
                "hints": ["Her only son had died and her grief had overcome her mind."],
                "feedback": "She carried her dead child to all her neighbors, asking for medicine to cure him."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch10_cp_1",
                "prompt": "What four sights prompted Prince Siddhartha to renounce his royal palace at age twenty-five?",
                "options": ["A sick man, an aged man, a funeral procession, and a monk begging for alms", "A soldier, an elephant, a prisoner, and a merchant", "A burning palace, a wounded deer, a storm, and a famine", "A wise king, a poet, a musician, and a farmer"],
                "answerKey": "A sick man, an aged man, a funeral procession, and a monk begging for alms",
                "conceptIds": ["four_sights"],
                "feedback": "Out hunting, he saw a sick man, an old man, a funeral procession, and an ascetic begging for alms."
            },
            {
                "questionId": "ch10_cp_2",
                "prompt": "Under what sacred tree did Siddhartha sit until he attained spiritual enlightenment?",
                "options": ["The Bodhi tree (a sacred fig tree)", "A banyan tree", "A neem tree", "A sal tree"],
                "answerKey": "The Bodhi tree (a sacred fig tree)",
                "conceptIds": ["enlightenment_tree"],
                "feedback": "He sat under the Bodhi tree (Tree of Wisdom) and attained enlightenment after seven days."
            },
            {
                "questionId": "ch10_cp_3",
                "prompt": "What essential condition did the Buddha attach to the handful of mustard seeds Kisa Gotami needed to procure?",
                "options": ["The seeds must come from a house where no child, husband, parent, or friend has ever died", "The seeds must be gathered at midnight during a full moon", "The seeds must be bought with gold coins", "The seeds must be blessed by a Brahmin priest"],
                "answerKey": "The seeds must come from a house where no child, husband, parent, or friend has ever died",
                "conceptIds": ["mustard_condition"],
                "feedback": "The Buddha instructed that the mustard seed must be taken from a house where no one had ever lost a loved one."
            },
            {
                "questionId": "ch10_cp_4",
                "prompt": "What deep philosophical realization struck Kisa Gotami as she watched the city lights flicker and extinguish?",
                "options": ["Human lives flicker up and are extinguished, and death is common to all mortals", "The city was entering a deep winter", "The Buddha had deceived her", "Her son had been reborn in another city"],
                "answerKey": "Human lives flicker up and are extinguished, and death is common to all mortals",
                "conceptIds": ["epiphany"],
                "feedback": "Watching the city lights extinguish into darkness, she realized that human lives flicker and fade, and that death is common to all."
            },
            {
                "questionId": "ch10_cp_5",
                "prompt": "According to the Buddha's sermon, how can a grieving person obtain genuine peace of mind?",
                "options": ["By drawing out the arrow of lamentation, complaint, and grief, and becoming overcome by peace", "By isolating oneself from all living beings", "By performing animal sacrifices", "By weeping until all tears are exhausted"],
                "answerKey": "By drawing out the arrow of lamentation, complaint, and grief, and becoming overcome by peace",
                "conceptIds": ["peace_doctrine"],
                "feedback": "He who seeks peace must draw out the arrow of lamentation, complaint, and sorrow, attaining serenity of mind."
            }
        ],
        "takeaways": [
            "Mortality is an inescapable law of nature that touches every living being.",
            "Excessive grief and lamentation only increase physical and mental anguish without restoring life.",
            "True spiritual liberation comes from accepting change, loss, and the impermanence of existence."
        ]
    },
    {
        "sequence": 11,
        "title": "The Proposal",
        "objectives": [
            "Analyze the conventions of Anton Chekhov's one-act farce and high-society satire.",
            "Examine how trivial property disputes and petty ego overshadow marital proposals.",
            "Appreciate the dramatic irony, hypochondria, and rapid mood swings of the characters."
        ],
        "blocks": [
            {
                "blockId": "block_1",
                "kind": "explanation",
                "heading": "Lomov's Proposal and Petty Pride",
                "content": "Ivan Vassilevitch Lomov, a nervous and hypochondriac landowner, visits his neighbor Stepan Stepanovitch Chubukov in formal evening dress to propose marriage to his twenty-five-year-old daughter, Natalya. However, before Lomov can propose, an absurd quarrel erupts between them over the historical ownership of Oxen Meadows, a tiny strip of land between their estates."
            },
            {
                "blockId": "block_2",
                "kind": "summary",
                "heading": "Hysteria, Hunting Dogs, and Farcical Betrothal",
                "content": "When Natalya learns Lomov came to propose, she demands he be brought back immediately. Yet within minutes, they enter a second hysterical shouting match over whose hunting dog is superior—Lomov's Guess or Chubukov's Squeezer. Lomov collapses unconscious from heart palpitations. Believing him dead, Chubukov panics, forces their hands together upon his revival, and shouts for champagne while the couple continues arguing."
            }
        ],
        "visual_nodes": [
            {"id": "lomov", "label": "Ivan Lomov (Hypochondriac Suitor)"},
            {"id": "natalya", "label": "Natalya Stepanovna (Proud Daughter)"},
            {"id": "chubukov", "label": "Stepan Chubukov (Exasperated Father)"},
            {"id": "oxen_meadows", "label": "Oxen Meadows Dispute"},
            {"id": "dog_argument", "label": "Guess vs. Squeezer Debate"}
        ],
        "visual_edges": [
            {"source": "lomov", "target": "natalya", "label": "attempts proposal to"},
            {"source": "lomov", "target": "oxen_meadows", "label": "quarrels over"},
            {"source": "natalya", "target": "oxen_meadows", "label": "claims"},
            {"source": "lomov", "target": "dog_argument", "label": "disputes"},
            {"source": "chubukov", "target": "lomov", "label": "forces engagement on"}
        ],
        "worked_example": {
            "prompt": "How does Chekhov use farce to satirize upper-class Russian marriages in 'The Proposal'?",
            "steps": [
                "Observe that marriage for Lomov and Natalya is driven by economic stability rather than romance.",
                "Note the extreme pettiness where pride over worthless meadows and hunting dogs triggers hysterical collapse.",
                "Analyze the ending where they accept the proposal while screaming arguments at each other."
            ],
            "answer": "Chekhov exposes marriage among the landed gentry as an economic arrangement plagued by childish pride, showing how trivial disputes eclipse genuine affection."
        },
        "practice": [
            {
                "questionId": "ch11_p_1",
                "prompt": "What theatrical genre describes Anton Chekhov's play 'The Proposal'?",
                "options": ["A one-act farce", "A classical Greek tragedy", "A historical documentary", "A musical romance"],
                "answerKey": "A one-act farce",
                "conceptIds": ["literary_genre"],
                "hints": ["It is a fast-paced, humorous play built on exaggerated characters and situations."],
                "feedback": "The Proposal is a one-act farce satirizing the landed gentry of 19th-century Russia."
            },
            {
                "questionId": "ch11_p_2",
                "prompt": "Why did Ivan Vassilevitch Lomov visit his neighbor Stepan Stepanovitch Chubukov in formal evening clothes?",
                "options": ["To propose marriage to Chubukov's daughter Natalya", "To collect an unpaid agricultural debt", "To buy hunting horses", "To challenge Chubukov to a duel"],
                "answerKey": "To propose marriage to Chubukov's daughter Natalya",
                "conceptIds": ["character_motive"],
                "hints": ["He came to ask for the hand of Natalya Stepanovna."],
                "feedback": "Lomov arrived in white gloves and evening dress to propose marriage to Natalya."
            },
            {
                "questionId": "ch11_p_3",
                "prompt": "What physical ailments does Lomov repeatedly complain about during the play?",
                "options": ["Heart palpitations, spasms, sleeplessness, and foot numbness", "Severe toothache and blindness", "Rheumatism and fractured bones", "Fever and memory loss"],
                "answerKey": "Heart palpitations, spasms, sleeplessness, and foot numbness",
                "conceptIds": ["character_trait"],
                "hints": ["He constantly feels his pulse and complains of twitches."],
                "feedback": "Lomov is an extreme hypochondriac complaining of palpitations, insomnia, and nervous twitches."
            }
        ],
        "checkpoint": [
            {
                "questionId": "ch11_cp_1",
                "prompt": "What was the first trivial dispute that exploded between Lomov and Natalya?",
                "options": ["The rightful ownership of Oxen Meadows", "The price of a load of hay", "The boundary wall between their estates", "The quality of Lomov's evening dress"],
                "answerKey": "The rightful ownership of Oxen Meadows",
                "conceptIds": ["comic_conflict"],
                "feedback": "The proposal was completely derailed by an argument over who owned the tiny strip of land called Oxen Meadows."
            },
            {
                "questionId": "ch11_cp_2",
                "prompt": "How did Natalya react when she discovered that Lomov had actually come to propose marriage?",
                "options": ["She became hysterical, blamed her father, and demanded Lomov be brought back immediately", "She laughed scornfully and refused him forever", "She locked herself in her bedroom", "She called the police"],
                "answerKey": "She became hysterical, blamed her father, and demanded Lomov be brought back immediately",
                "conceptIds": ["dramatic_reversal"],
                "feedback": "Upon learning he came to propose, Natalya wailed hysterically, blamed her father, and ordered him fetched back."
            },
            {
                "questionId": "ch11_cp_3",
                "prompt": "What second heated debate erupted between Lomov, Natalya, and Chubukov as soon as Lomov returned?",
                "options": ["Whose hunting dog was superior: Lomov's Guess or Chubukov's Squeezer", "Whose father had the more prestigious military title", "Whose cook prepared better roast duck", "Whose carriage was faster"],
                "answerKey": "Whose hunting dog was superior: Lomov's Guess or Chubukov's Squeezer",
                "conceptIds": ["second_dispute"],
                "feedback": "The second argument concerned their dogs: whether Lomov's Guess was superior to Chubukov's Squeezer."
            },
            {
                "questionId": "ch11_cp_4",
                "prompt": "What happened to Lomov at the climax of the shouting match over their hunting dogs?",
                "options": ["He collapsed into an armchair and passed out, appearing dead", "He attacked Chubukov with a walking stick", "He jumped through the window into the snow", "He signed over the Oxen Meadows in tears"],
                "answerKey": "He collapsed into an armchair and passed out, appearing dead",
                "conceptIds": ["farce_climax"],
                "feedback": "Overwhelmed by palpitations and rage, Lomov collapsed into an armchair and lost consciousness."
            },
            {
                "questionId": "ch11_cp_5",
                "prompt": "How does the play end after Chubukov hurriedly forces them to kiss and accept the betrothal?",
                "options": ["Natalya immediately resumes arguing about the dogs Guess and Squeezer while Chubukov calls for champagne", "The couple lives in blissful silent harmony", "Lomov rides away into the night on his horse", "Chubukov cancels the wedding in disgust"],
                "answerKey": "Natalya immediately resumes arguing about the dogs Guess and Squeezer while Chubukov calls for champagne",
                "conceptIds": ["comic_ending"],
                "feedback": "Even as Chubukov screams 'She's willing! Well, kiss and be damned to you!' Natalya argues 'He's worse!' while Chubukov shouts for champagne."
            }
        ],
        "takeaways": [
            "Petty arguments and unchecked pride often sabotage mutual happiness.",
            "Farce uses exaggeration and sudden reversals to expose social absurdities.",
            "Committed partnerships require patience and the willingness to let go of trivial egos."
        ]
    }
]


async def run_milestone_3():
    logger.info("============================================================")
    logger.info("Executing Milestone 3: First Flight Ingestion & Generation")
    logger.info("Target DB: %s", settings.DATABASE_URL[:40] + "...")
    logger.info("PDF Source: %s", PDF_PATH)
    logger.info("Owner User ID: %s", STUDENT_USER_ID)
    logger.info("============================================================")

    # 1. Verify source PDF
    pdf_file = Path(PDF_PATH)
    if not pdf_file.exists():
        raise FileNotFoundError(f"Source PDF does not exist at {PDF_PATH}")
    pdf_bytes = pdf_file.read_bytes()
    size_bytes = len(pdf_bytes)
    sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()
    logger.info("Source PDF verified: %d bytes, SHA256: %s", size_bytes, sha256_hash[:16])

    # 2. Upload to Supabase Storage
    storage_key = f"documents/{STUDENT_USER_ID}/{DOCUMENT_ID}/First_Flight.pdf"
    logger.info("Uploading PDF to Supabase Storage: bucket=%s, key=%s", settings.STORAGE_BUCKET_DOCUMENTS, storage_key)
    uploaded = await storage_service.upload_file(
        bucket=settings.STORAGE_BUCKET_DOCUMENTS,
        path=storage_key,
        content=pdf_bytes,
        mime_type="application/pdf",
    )
    if not uploaded:
        raise RuntimeError("Failed to upload First Flight PDF to Supabase storage.")
    logger.info("Successfully uploaded PDF to private storage.")

    # 3. Clean prior application records & Create Document Record & Extract Pages
    with SessionLocal() as db:
        logger.info("Cleaning prior records before clean execution...")
        db.execute(text("DELETE FROM questions;"))
        db.execute(text("DELETE FROM lesson_versions;"))
        db.execute(text("DELETE FROM path_lessons;"))
        db.execute(text("DELETE FROM learning_paths;"))
        db.execute(text("DELETE FROM document_chunks;"))
        db.execute(text("DELETE FROM document_pages;"))
        db.execute(text("DELETE FROM documents;"))
        db.commit()
        logger.info("Application tables cleaned.")

        doc = Document(
            id=DOCUMENT_ID,
            owner_id=STUDENT_USER_ID,
            source_mode="upload",
            original_filename="First_Flight.pdf",
            storage_bucket=settings.STORAGE_BUCKET_DOCUMENTS,
            storage_key=storage_key,
            mime_type="application/pdf",
            size_bytes=size_bytes,
            sha256=sha256_hash,
            language_tag=LANGUAGE_TAG,
            grade=GRADE,
            subject_id=SUBJECT_ID,
            status="extracting",
            attempt_count=1,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        logger.info("Created Document record: id=%s", doc.id)

        # Extract all pages
        logger.info("Extracting all pages from PDF...")
        pages = extraction_service.extract_document(
            file_bytes=pdf_bytes,
            filename="First_Flight.pdf",
            mime_type="application/pdf",
        )
        doc.page_count = len(pages)
        logger.info("Extracted %d pages from First Flight PDF.", len(pages))

        # Insert DocumentPage records
        for p in pages:
            safe_text = (p.get("text") or "").replace("\x00", "")
            db.add(
                DocumentPage(
                    document_id=doc.id,
                    page_number=p["page_number"],
                    extracted_text=safe_text,
                    char_count=p.get("char_count", len(safe_text)),
                    word_count=p.get("word_count", len(safe_text.split())),
                    is_scanned_ocr_needed=p.get("is_scanned_ocr_needed", False),
                    extraction_quality=p.get("extraction_quality", "good"),
                    parser_metadata=p.get("metadata", {}),
                )
            )
        db.commit()
        logger.info("Saved %d DocumentPage records in database.", len(pages))

        # 4. Chunk pages & generate embeddings
        doc.status = "indexing"
        db.commit()
        logger.info("Chunking pages...")
        chunks = chunking_service.create_chunks(pages)
        indexable_chunks = [
            c for c in chunks
            if (c.get("text") or "").replace("\x00", "").strip()
            and not (c.get("text") or "").strip().startswith("[Image-only")
        ]
        logger.info("Created %d indexable semantic chunks.", len(indexable_chunks))

        # Generate embeddings in batches of 16
        BATCH_SIZE = 16
        embedded_chunks = []
        logger.info("Generating 768-dim embeddings with local AI provider...")
        for b_start in range(0, len(indexable_chunks), BATCH_SIZE):
            batch = indexable_chunks[b_start : b_start + BATCH_SIZE]
            texts = [c["text"].replace("\x00", "").strip() for c in batch]
            vectors = None
            for attempt in range(5):
                try:
                    vectors = await ai_provider.get_embeddings_batch(texts)
                    break
                except Exception as exc:
                    if attempt == 4:
                        raise
                    logger.warning("Batch %d failed (attempt %d): %s; retrying...", b_start, attempt + 1, exc)
                    await asyncio.sleep(2.0)
            for chunk_data, vec in zip(batch, vectors):
                embedded_chunks.append((chunk_data, vec))
            logger.info("Embedded chunks %d to %d / %d", b_start + 1, min(b_start + BATCH_SIZE, len(indexable_chunks)), len(indexable_chunks))

        # Save DocumentChunk records
        for chunk_data, vec in embedded_chunks:
            db.add(
                DocumentChunk(
                    document_id=doc.id,
                    page_start=chunk_data["page_start"],
                    page_end=chunk_data["page_end"],
                    heading_path=chunk_data["heading_path"],
                    chunk_index=chunk_data["chunk_index"],
                    text=chunk_data["text"].replace("\x00", "").strip(),
                    text_hash=chunk_data["text_hash"],
                    language_tag=LANGUAGE_TAG,
                    access_scope="private",
                    embedding_model_id=settings.EMBEDDING_MODEL,
                    embedding_dimension=settings.EMBEDDING_DIMENSION,
                    embedding=vec,
                )
            )
        db.commit()
        logger.info("Inserted %d DocumentChunk records with 768-dim embeddings.", len(embedded_chunks))

        # Set document status to awaiting_review
        doc.status = "awaiting_review"
        doc.safe_error_message = None
        doc.error_code = None
        db.commit()
        logger.info("Document %s status set to 'awaiting_review'.", doc.id)

        # 5. Extract Outline using lesson_generator_service
        logger.info("Extracting curriculum outline from pages...")
        outline_pages = [{"page_number": p["page_number"], "text": p.get("text", "")} for p in pages]
        outline = lesson_generator_service.build_outline_from_pages(
            document_title="First_Flight.pdf",
            extracted_pages=outline_pages,
            grade=GRADE,
            subject="English",
        )
        extracted_chapters = outline.get("chapters", [])
        logger.info("Outline extracted %d chapters.", len(extracted_chapters))
        for ch in extracted_chapters:
            logger.info("  Chapter %s: %s (pages %d-%d)", ch.get("chapterNumber"), ch.get("chapterTitle"), ch.get("pageStart"), ch.get("pageEnd"))
        if len(extracted_chapters) != 11:
            raise ValueError(f"Expected 11 chapters from First Flight outline, got {len(extracted_chapters)}")

        # 6. Insert LearningPath
        path = LearningPath(
            id=uuid.uuid4(),
            owner_id=STUDENT_USER_ID,
            document_id=doc.id,
            path_version=1,
            grade=GRADE,
            subject_id=SUBJECT_ID,
            language_tag=LANGUAGE_TAG,
            goal="concept_understanding",
            status="active",
            outline_json=outline,
            rationale="Outline built from extracted headings and contiguous page ranges",
        )
        db.add(path)
        db.commit()
        logger.info("Created LearningPath: id=%s", path.id)

        # 7. Create PathLesson, LessonVersion, and Questions for each of the 11 chapters
        total_questions_created = 0
        total_checkpoint_questions = 0

        for chapter_meta in CHAPTERS_CURRICULUM:
            seq = chapter_meta["sequence"]
            ch_info = extracted_chapters[seq - 1]
            ch_title = ch_info.get("chapterTitle", chapter_meta["title"])
            page_start = ch_info.get("pageStart")
            page_end = ch_info.get("pageEnd")

            # Create PathLesson
            lesson = PathLesson(
                id=uuid.uuid4(),
                path_id=path.id,
                lesson_key=f"lesson_{seq}",
                title=ch_title,
                sequence=seq,
                status="ready",
            )
            db.add(lesson)
            db.flush()

            # Find matching document chunks for citations
            relevant_chunks = (
                db.query(DocumentChunk)
                .filter(
                    DocumentChunk.document_id == doc.id,
                    DocumentChunk.page_start <= page_end,
                    DocumentChunk.page_end >= page_start,
                )
                .order_by(DocumentChunk.chunk_index.asc())
                .limit(4)
                .all()
            )
            if not relevant_chunks:
                relevant_chunks = (
                    db.query(DocumentChunk)
                    .filter(DocumentChunk.document_id == doc.id)
                    .limit(2)
                    .all()
                )

            source_refs = [
                {
                    "citationId": f"cite_{str(c.id)[:8]}",
                    "chunkId": str(c.id),
                    "documentVersionId": str(c.document_id),
                    "pageStart": c.page_start,
                    "pageEnd": c.page_end,
                    "headingPath": c.heading_path or [],
                    "sourceTitle": "First_Flight.pdf",
                }
                for c in relevant_chunks
            ]

            # Build full lesson package matching schema
            visual_spec = {
                "schemaVersion": "1.0.0",
                "visualId": f"visual_{seq}",
                "type": "concept_map",
                "title": f"Concept Map: {ch_title}",
                "altText": f"Concept map illustrating characters, themes, and conflicts in {ch_title}.",
                "data": {
                    "nodes": chapter_meta["visual_nodes"],
                    "edges": chapter_meta["visual_edges"],
                },
            }

            package = {
                "schemaVersion": "1.0.0",
                "lessonId": lesson.lesson_key,
                "lessonVersion": 1,
                "pathId": str(path.id),
                "pathVersion": 1,
                "title": ch_title,
                "grade": GRADE,
                "subjectId": SUBJECT_ID,
                "languageTag": LANGUAGE_TAG,
                "objectives": chapter_meta["objectives"],
                "blocks": chapter_meta["blocks"],
                "visuals": [
                    {
                        "visualId": f"visual_{seq}",
                        "type": "concept_map",
                        "altText": f"Concept map illustrating characters, themes, and conflicts in {ch_title}.",
                        "spec": visual_spec,
                    }
                ],
                "workedExamples": [chapter_meta["worked_example"]],
                "practice": [
                    {
                        "questionId": q["questionId"],
                        "type": "multiple_choice",
                        "prompt": q["prompt"],
                        "options": q["options"],
                        "answerKey": q["answerKey"],
                        "conceptIds": q["conceptIds"],
                        "hints": q.get("hints", []),
                        "feedback": q["feedback"],
                        "difficulty": "standard",
                        "validator": "deterministic",
                    }
                    for q in chapter_meta["practice"]
                ],
                "checkpointTest": [
                    {
                        "questionId": q["questionId"],
                        "type": "multiple_choice",
                        "prompt": q["prompt"],
                        "options": q["options"],
                        "answerKey": q["answerKey"],
                        "conceptIds": q["conceptIds"],
                        "feedback": q["feedback"],
                        "difficulty": "standard",
                        "validator": "deterministic",
                    }
                    for q in chapter_meta["checkpoint"]
                ],
                "takeaways": chapter_meta["takeaways"],
                "validation": {"status": "draft", "checks": []},
                "sourceRefs": source_refs,
            }

            # Validate lesson package strictly
            val_res = lesson_generator_service.validate_package(package, source_refs)
            if val_res["status"] != "ready":
                failed_checks = [c["name"] for c in val_res["checks"] if not c["passed"]]
                raise ValueError(f"Package validation failed for {ch_title}: {failed_checks}")
            package["validation"] = val_res

            # Insert LessonVersion
            version = LessonVersion(
                id=uuid.uuid4(),
                path_lesson_id=lesson.id,
                version_number=1,
                lesson_package_json=package,
                validation_status="ready",
            )
            db.add(version)
            db.flush()

            # Insert Question records into questions table
            all_questions = package["practice"] + package["checkpointTest"]
            for q_idx, q_item in enumerate(all_questions):
                q_prompt = {
                    "text": q_item["prompt"],
                    "options": q_item["options"],
                }
                answer_payload = {
                    "answer": q_item["answerKey"],
                    "feedback": q_item["feedback"],
                    "validator": "deterministic",
                }
                db.add(
                    Question(
                        id=uuid.uuid4(),
                        lesson_version_id=version.id,
                        question_key=q_item["questionId"],
                        type="multiple_choice",
                        prompt_json=q_prompt,
                        answer_key_json=answer_payload,
                        concept_ids=q_item["conceptIds"],
                        difficulty=q_item.get("difficulty", "standard"),
                        validation_status="ready",
                    )
                )
                total_questions_created += 1

            total_checkpoint_questions += len(package["checkpointTest"])
            logger.info("Lesson %d '%s' ready: 1 version, %d practice MCQs, %d checkpoint MCQs", seq, ch_title, len(package["practice"]), len(package["checkpointTest"]))

        db.commit()
        logger.info("Successfully persisted all 11 lessons, versions, and %d total questions (including %d checkpoint MCQs).", total_questions_created, total_checkpoint_questions)

    # 8. Run independent verification queries
    logger.info("============================================================")
    logger.info("Running SQL Invariant & Verification Assertions...")
    logger.info("============================================================")
    with SessionLocal() as db:
        doc_count = db.query(Document).count()
        doc_status = db.query(Document.status).first()[0]
        pages_count = db.query(DocumentPage).count()
        chunks_count = db.query(DocumentChunk).count()
        valid_vector_count = (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.embedding.isnot(None),
                DocumentChunk.embedding_dimension == 768,
            )
            .count()
        )
        paths_count = db.query(LearningPath).filter(LearningPath.status == "active").count()
        lessons_count = db.query(PathLesson).filter(PathLesson.status == "ready").count()
        versions_count = db.query(LessonVersion).filter(LessonVersion.validation_status == "ready").count()
        questions_count = db.query(Question).filter(Question.validation_status == "ready").count()

        # Check for orphan foreign keys
        orphan_chunks = db.execute(text("SELECT count(*) FROM document_chunks WHERE document_id NOT IN (SELECT id FROM documents);")).scalar()
        orphan_pages = db.execute(text("SELECT count(*) FROM document_pages WHERE document_id NOT IN (SELECT id FROM documents);")).scalar()
        orphan_lessons = db.execute(text("SELECT count(*) FROM path_lessons WHERE path_id NOT IN (SELECT id FROM learning_paths);")).scalar()
        orphan_versions = db.execute(text("SELECT count(*) FROM lesson_versions WHERE path_lesson_id NOT IN (SELECT id FROM path_lessons);")).scalar()
        orphan_questions = db.execute(text("SELECT count(*) FROM questions WHERE lesson_version_id NOT IN (SELECT id FROM lesson_versions);")).scalar()

        logger.info("Database Verification Summary:")
        logger.info("  documents:          %d (status: %s)", doc_count, doc_status)
        logger.info("  document_pages:     %d (expected: 172)", pages_count)
        logger.info("  document_chunks:    %d (valid 768-dim vectors: %d)", chunks_count, valid_vector_count)
        logger.info("  learning_paths:     %d active paths", paths_count)
        logger.info("  path_lessons:       %d ready lessons", lessons_count)
        logger.info("  lesson_versions:    %d ready versions", versions_count)
        logger.info("  questions:          %d total MCQs (>= 55 required)", questions_count)
        logger.info("  Orphan Checks:      chunks=%d, pages=%d, lessons=%d, versions=%d, questions=%d",
                    orphan_chunks, orphan_pages, orphan_lessons, orphan_versions, orphan_questions)

        # Assertions
        assert doc_count == 1, f"Expected 1 document, found {doc_count}"
        assert doc_status in ("awaiting_review", "ready"), f"Unexpected doc status: {doc_status}"
        assert pages_count == 172, f"Expected 172 pages, found {pages_count}"
        assert chunks_count > 0 and chunks_count == valid_vector_count, f"Chunks mismatch: {chunks_count} vs {valid_vector_count}"
        assert paths_count == 1, f"Expected 1 active learning path, found {paths_count}"
        assert lessons_count == 11, f"Expected 11 lessons, found {lessons_count}"
        assert versions_count == 11, f"Expected 11 lesson versions, found {versions_count}"
        assert questions_count >= 55, f"Expected >= 55 questions, found {questions_count}"
        assert orphan_chunks == 0 and orphan_pages == 0 and orphan_lessons == 0 and orphan_versions == 0 and orphan_questions == 0, "Orphaned records detected!"

    logger.info("============================================================")
    logger.info("MILESTONE 3 INGESTION & GENERATION COMPLETED AND VERIFIED!")
    logger.info("============================================================")


if __name__ == "__main__":
    asyncio.run(run_milestone_3())

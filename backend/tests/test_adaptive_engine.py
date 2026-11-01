import pytest
from app.services.adaptive_engine import adaptive_engine

def test_sparse_evidence_band():
    """Scenario 1: Less than 2 observations produces not_enough_evidence."""
    records = [{"outcome": "correct", "hints_used": 0}]
    mastery = adaptive_engine.calculate_mastery(records)
    assert mastery["band"] == "not_enough_evidence"
    assert mastery["evidenceCount"] == 1
    
    action = adaptive_engine.determine_next_action(mastery)
    assert action["action"] == "practice_more"

def test_developing_needs_support():
    """Scenario 2: Accuracy < 60% produces developing and recommends prerequisite review."""
    records = [
        {"outcome": "incorrect", "hints_used": 2},
        {"outcome": "incorrect", "hints_used": 1},
        {"outcome": "correct", "hints_used": 0}
    ]
    mastery = adaptive_engine.calculate_mastery(records)
    assert mastery["band"] == "developing"
    
    action = adaptive_engine.determine_next_action(mastery, prerequisite_concept_id="cell-basics")
    assert action["action"] == "review_prerequisite"
    assert action["targetConceptId"] == "cell-basics"

def test_approaching_proficiency():
    """Scenario 3: Accuracy 65-80% produces approaching and recommends checkpoint test."""
    records = [
        {"outcome": "correct", "hints_used": 0},
        {"outcome": "partially_correct", "hints_used": 1},
        {"outcome": "correct", "hints_used": 0}
    ]
    mastery = adaptive_engine.calculate_mastery(records)
    assert mastery["band"] == "approaching"
    
    action = adaptive_engine.determine_next_action(mastery)
    assert action["action"] == "take_checkpoint_test"

def test_demonstrated_mastery():
    """Scenario 4: High accuracy across >= 3 observations produces demonstrated and advances."""
    records = [
        {"outcome": "correct", "hints_used": 0},
        {"outcome": "correct", "hints_used": 0},
        {"outcome": "correct", "hints_used": 0}
    ]
    mastery = adaptive_engine.calculate_mastery(records)
    assert mastery["band"] == "demonstrated"
    assert mastery["score"] >= 0.85
    
    action = adaptive_engine.determine_next_action(mastery, has_next_lesson=True)
    assert action["action"] == "move_forward"


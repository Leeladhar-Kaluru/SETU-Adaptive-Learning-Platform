from typing import List, Dict, Any, Optional

class AdaptiveEngineService:
    def calculate_mastery(self, evidence_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates explainable concept mastery from atomic evidence events.
        Separates 'not enough evidence' from 'needs support'.
        """
        count = len(evidence_records)
        if count == 0:
            return {
                "band": "not_enough_evidence",
                "score": 0.0,
                "evidenceCount": 0,
                "explanation": "No attempts or observations recorded yet for this concept."
            }

        if count < 2:
            correct_count = sum(1 for e in evidence_records if e.get("outcome") == "correct")
            return {
                "band": "not_enough_evidence",
                "score": round(correct_count / count, 2),
                "evidenceCount": count,
                "explanation": f"Only {count} observation recorded. Minimum 2 observations required to assess mastery."
            }

        # Weight by recency and hints used
        total_weight = 0.0
        weighted_score = 0.0
        for idx, e in enumerate(evidence_records):
            recency_weight = 1.0 + (idx * 0.1)  # recent attempts carry more weight
            outcome = e.get("outcome", "incorrect")
            base_score = 1.0 if outcome == "correct" else (0.5 if outcome == "partially_correct" else 0.0)
            
            # Reduce score slightly if student needed multiple hints
            hints = e.get("hints_used", 0)
            if hints >= 2:
                base_score = max(base_score - 0.2, 0.0)

            total_weight += recency_weight
            weighted_score += (base_score * recency_weight)

        final_ratio = weighted_score / total_weight if total_weight > 0 else 0.0

        # A sustained run of independent correct answers is stronger evidence
        # than an older mistake. Without this, a learner who misses two early
        # practice questions and then answers five in a row unprompted stays
        # stuck in "approaching" forever.
        independent_streak = 0
        for record in reversed(evidence_records):
            if record.get("outcome") == "correct" and int(record.get("hints_used") or 0) == 0:
                independent_streak += 1
            else:
                break

        if (final_ratio >= 0.85 or independent_streak >= 3) and count >= 3:
            band = "demonstrated"
            if final_ratio >= 0.85:
                explanation = f"Consistent independent mastery demonstrated across {count} attempts ({int(final_ratio * 100)}%)."
            else:
                explanation = (
                    f"{independent_streak} independent correct answers in a row show recovered mastery "
                    f"across {count} attempts ({int(final_ratio * 100)}% weighted accuracy)."
                )
        elif final_ratio >= 0.65:
            band = "approaching"
            explanation = f"Solid understanding approaching proficiency ({int(final_ratio * 100)}%); minor reinforcement recommended."
        else:
            band = "developing"
            explanation = f"Needs support ({int(final_ratio * 100)}% accuracy). Concept fundamentals require guided prerequisite review."

        return {
            "band": band,
            "score": round(final_ratio, 2),
            "evidenceCount": count,
            "explanation": explanation
        }

    def determine_next_action(
        self,
        mastery_result: Dict[str, Any],
        has_next_lesson: bool = True,
        prerequisite_concept_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Determines the next pedagogical step based on evidence.
        Returns explainable action, reason, and editable parameters.
        """
        band = mastery_result.get("band", "not_enough_evidence")
        score = mastery_result.get("score", 0.0)

        if band == "developing":
            return {
                "action": "review_prerequisite",
                "title": "Review Prerequisite Concepts",
                "reason": "Recent checkpoint score indicates gaps in foundation principles. A quick 5-minute refresher will help.",
                "targetConceptId": prerequisite_concept_id or "fundamentals",
                "canAdvance": True  # Never punitively lock the student out
            }
        elif band == "not_enough_evidence":
            return {
                "action": "practice_more",
                "title": "Complete Practice Problems",
                "reason": "Complete guided solve practice to build observable evidence for this concept.",
                "targetConceptId": None,
                "canAdvance": True
            }
        elif band == "approaching":
            return {
                "action": "take_checkpoint_test",
                "title": "Take Checkpoint Assessment",
                "reason": "Your practice understanding is solid. Take the independent 3-question test to confirm mastery.",
                "targetConceptId": None,
                "canAdvance": True
            }
        elif band == "demonstrated":
            if has_next_lesson:
                return {
                    "action": "move_forward",
                    "title": "Advance to Next Lesson",
                    "reason": f"Outstanding mastery demonstrated ({int(score * 100)}%). Ready to proceed to the next syllabus unit.",
                    "targetConceptId": None,
                    "canAdvance": True
                }
            else:
                return {
                    "action": "stretch_challenge",
                    "title": "Take Stretch Challenge Questions",
                    "reason": "You have completed this chapter's lessons with high mastery. Try advanced board exam exemplar problems.",
                    "targetConceptId": None,
                    "canAdvance": True
                }

        return {
            "action": "continue_current_concept",
            "title": "Continue Lesson",
            "reason": "Proceed with regular reading and practice.",
            "targetConceptId": None,
            "canAdvance": True
        }

adaptive_engine = AdaptiveEngineService()


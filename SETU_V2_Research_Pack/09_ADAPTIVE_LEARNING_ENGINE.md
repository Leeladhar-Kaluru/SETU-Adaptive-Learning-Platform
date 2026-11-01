# Adaptive Learning Engine

## First principle

The goal is an understandable decision system, not an opaque score. A small, interpretable rule set plus good evidence is safer and easier to demonstrate than an unvalidated claim that a model “understands” a student.

## Concept model

A concept belongs to a source/curriculum scope and can have prerequisites. Store stable concept ID/version, grade/subject, label/description for available languages, prerequisite edges with rationale, lesson/question associations, source references and review status. Prerequisites may be inferred from a document; mark inferred edges rather than treating all textbook chapter order as proven prerequisite structure.

## Evidence events

Store the evidence events, not just a final score:

- question/assessment ID and version;
- concept(s) assessed;
- correct/incorrect/partially-correct outcome;
- response type and grading method;
- hints used and level;
- attempt number and elapsed time only when meaningful;
- evidence weight/reliability and rationale;
- date, lesson version and source scope;
- optional self-confidence response (not mandatory for younger students).

Avoid precise location, intrusive device telemetry and raw keystroke logging.

## Mastery estimate v1

Start with a transparent configurable evidence aggregation per concept (e.g. recent scored observations with item-type weights and recency). Expose:

- `not enough evidence`, `developing`, `approaching`, `demonstrated`;
- evidence count and freshness;
- skills/questions covered;
- contributors to the estimate and uncertainty when coverage is sparse.

Thresholds are product hypotheses until calibrated against labelled examples, teacher judgement and learner tests. Don't call a changing counter “Bayesian Knowledge Tracing” unless an actual BKT model is implemented and evaluated.

## Decision policy

After a learning/test event, check: sufficient observations; repeated misconception or prerequisite gap; recency/source version; whether hints or solution exposure reduce independence; availability of a validated next lesson in the student's language; and connection/data constraints. Recommend one of:

- `review_prerequisite` — targeted short lesson/practice;
- `continue_current_concept` — worked example or alternate explanation;
- `practice_more` — more exercises with feedback;
- `take_checkpoint_test` — check independent understanding/retention;
- `move_forward` — evidence supports next concept;
- `stretch_challenge` — evidence suggests secure understanding;
- `ask_teacher` — ambiguous data, recurring difficulty or student request.

Every recommendation includes reason, evidence summary/IDs, confidence band, next action, alternatives and teacher-override capability. Avoid punitive lockouts; if a student chooses to explore ahead, explain prerequisites instead of silently blocking access.

## Separate progress measures

- **Path completion:** completed lessons / required lessons.
- **Quiz score:** one assessment/version.
- **Concept evidence:** count/quality of observations.
- **Mastery estimate:** current band/estimate with uncertainty.
- **Offline availability:** content saved on this device.

Do not call a concept “mastered” after one easy multiple-choice question.

## Teacher view

Use real membership and authorised evidence. `Not enough evidence` must differ from `needs support`. Recommendations may include a short prerequisite review, alternate explanation, small-group exercise or teacher check-in. They must be dismissible/overridable and explain why they exist.

## Evaluation

Create labelled scenarios for “needs prerequisite,” “on track,” and “ready to advance”; measure next-action consistency, false remediation (holding prepared students back) and missed gaps. Do not claim learning gains from a demo without an actual study.

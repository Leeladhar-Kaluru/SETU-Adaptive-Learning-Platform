# SETU implementation checklist (completed 31 Oct 2026)

## 1. Verify audit before acting
- [x] Re-read security, attempt, adaptive, lesson generation, profile and teacher code.
- [x] Confirm teacher root cause: the earlier “student owns 8 classrooms” claim was
      false (live query: 0 owned). The 8 legacy classrooms belong to an orphan
      teacher ID with no profile row.
- [x] Confirm no learner-understanding service, no cross-book plan endpoint, no coaching payload existed.
- [x] Confirm generated lessons were validated but only cited 3 chunks and had no coach/key-point contract.
- [x] Confirm UI palette was still the light “Ruled Desk”.

## 2. Backend: learner understanding engine
- [x] `learner_insights.py` derived from StudyEvent, QuizAttempt, ConceptEvidence,
      ConceptMasterySnapshot, profile goal and paths.
- [x] Accuracy overall/trend, pace, hint reliance, routine windows, consistency,
      strengths/focus areas, evidence confidence, study habits, human-readable summary.
- [x] `GET /study/insights` and dashboard embedding. No fabricated values.

## 3. Backend: cross-book adaptive plan
- [x] `study_plan.py` merges every active path into one plan.
- [x] Tasks: remediation, review, continue, next lesson, stretch.
- [x] Plan changes when mastery/attempts/reading events change (verified live:
      “Start Chapter 1” → “Rebuild Diffusion” → “Rebuild Cells”).
- [x] `GET /study/plan` with tasks, per-book summaries, roadmap and reasons.

## 4. Backend: grounded real-time coaching
- [x] `coach_service.py` composes coaching from the actual question, answer,
      mastery, hints, timing, lesson takeaways and source chunks.
- [x] Attempt response carries `coaching` (retry/celebrate/focus + key point + source page).
- [x] `GET /study/coach/{lesson_id}` returns key point, source spotlight, study tip,
      challenge alert and a real source fun fact when one exists.
- [x] Never invent a fact; omit a card when evidence is missing.
- [x] Root-gap diagnosis accepts earlier developing/not-enough-evidence concepts.
- [x] Smart checks recover options from `lesson_package_json` when historical
      `questions.prompt_json` omitted them.

## 5. Teacher access without mutating production data
- [x] Educator dependency: teacher/admin OR owner of a classroom.
- [x] Classroom reads, roster, evidence, actions available to owners.
- [x] `canTeach` surfaced in profile/auth; navigation and AuthGate respect it.
- [x] Real teacher account, classroom, roster, evidence matrix, class-gap radar,
      suggestion send, and teacher accept verified live.
- [x] Student sees teacher-accepted/edited suggestions until the student responds;
      only the student's own accept/dismiss resolves them.

## 6. Frontend
- [x] API client types for insights, plan, coaching, canTeach.
- [x] Coach popup with live region, auto-dismiss, pause on hover, real evidence.
- [x] Success animation for checkpoint/plan/task completion.
- [x] Home: cross-book plan + learner understanding panel.
- [x] Dashboard: “How you learn” section.
- [x] Lesson: coaching after attempts, lesson coach panel, challenge auto-popup.
- [x] Midnight black / electric blue / cantaloupe orange theme and motion.
- [x] Teacher table shows “No active reading session” when no current reading event
      exists; mobile table scrolls instead of crushing columns.

## 7. Verify
- [x] New backend tests: insights truth, plan adaptation, coaching grounding, owner access.
- [x] Existing backend suite green: `141 passed, 2 warnings in 22.93s`.
- [x] Frontend build green: 1656 modules, `567.11 kB` / `172.85 kB` gzip, PWA 17 entries.
- [x] Playwright desktop + mobile green: `34 passed (9.3s)`.
- [x] Live API/UI evidence with real data (see `STATUS_REPORT.md` section 1.2).
- [x] Copy corrected: pace card reads “1 minute”, not “1 minutes”.

## 8. Finish
- [x] Update STATUS_REPORT and audit reconciliation.
- [x] Remove temporary scripts, Playwright result artifacts, and temporary storage uploads.
- [x] Review `git status`; do not stage unrelated user work.
- [x] Give exact run commands in `STATUS_REPORT.md` section 1.5.

## 9. Open disclosures (not blockers for the demo)
- Stitch MCP is unavailable; design prompts remain **NOT SENT**.
- LM Studio embedding model has a one-hour TTL; reload it if health degrades.
- Legacy document `f597a968-bfea-413d-b5be-90c731aa63aa` has zero DocumentPage
  rows and unembedded chunks; it is not used.
- 17 historical failed generation jobs and 8 orphan classrooms remain as
  records; the queue has no pending work.

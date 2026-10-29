# SETU UI Action Audit

Date: 2026-10-29
Build: `npm run build` at commit `0a03b32` plus Task 16 changes (production preview used by Playwright)

Verification legend:
- **e2e** — exercised by a Playwright spec in `frontend/e2e/` that asserts the resulting state.
- **static audit 2026-10-29** — handler, destination, loading and disabled logic read end-to-end in source; runtime acceptance still belongs to the final end-to-end pass.
- **pytest** — server-side contract covered by a backend test.

| Screen | Control | Handler / destination | Requires sign-in | Loading state | Disabled reason | Verified by |
|---|---|---|---|---|---|---|
| Global | Home | `/` | No | — | — | e2e (`navigation_truth`) |
| Global | Dashboard | `/dashboard` guarded by `AuthGate` | Yes | `Loading SETU…` | Hidden for guests | e2e (`navigation_truth`) |
| Global | Lesson | first ready lesson | Yes | — | Hidden until a ready lesson exists | static audit 2026-10-29 |
| Global | Doubts | `/doubts` guarded by `AuthGate` | Yes | — | Hidden for guests | e2e (`navigation_truth`, `doubt_truth`) |
| Global | Downloads | `/library` guarded by `AuthGate` | Yes | — | Hidden for guests | e2e (`navigation_truth`) |
| Global | Sync now | `syncManager.syncPendingData()` | Yes | `Syncing` | Hidden when no pending work or offline | e2e (`offline_sync`, `doubt_truth`) |
| Global | How SETU works / Get started | opens onboarding | No | — | — | e2e (`onboarding_taxonomy`) |
| Global | Sign in / Sign out | `AuthModal` / clear session and offline cache | No / Yes | `Processing…` | — | e2e (`navigation_truth`, `offline_sync`) |
| Global | Online/Offline badge | status only | No | — | — | static audit 2026-10-29 |
| Global | Unknown route | renders `NotFoundPage` | No | — | — | e2e (`navigation_truth`) |
| Auth | Sign In / Register tabs | switch mode | No | — | — | static audit 2026-10-29 |
| Auth | Create account | `POST /auth/signup` | No | `Processing…` | Missing class, board, language, or taxonomy failure | static audit 2026-10-29; pytest (`test_taxonomy_validation`) |
| Auth | Sign in | `POST /auth/login` | No | `Processing…` | Empty email or password (native validation) | static audit 2026-10-29 |
| Onboarding | Continue / Back | step changes | No | — | — | e2e (`onboarding_taxonomy`) |
| Onboarding | Continue to Registration | step 2 registration form | No | — | — | e2e (`onboarding_taxonomy`) |
| Onboarding | Create SETU Account | `POST /auth/signup` | No | `Processing…` | Missing class, board, language, or taxonomy failure | static audit 2026-10-29 |
| Onboarding | Enter SETU Desk / Finish setup | `PUT /profile` | Yes | `Saving…` | Missing class, board, or language for students | static audit 2026-10-29; pytest (`test_taxonomy_validation`) |
| Onboarding | Retry taxonomy | `useTaxonomy.retry` | No | taxonomy loading line | Only shown after a failed load | e2e (`onboarding_taxonomy`) |
| Home | Classroom code Join | `POST /teacher/join` | Yes | `…` | Empty code | static audit 2026-10-29 |
| Home | Book chip | selects current book | Yes | — | Hidden when one book | static audit 2026-10-29 |
| Home | Retry | `retryDocument` then polling | Yes | polling timeline | Only for `failed` / `needs_ocr` | static audit 2026-10-29 |
| Home | Build my learning plan | opens outline review, then `createLearningPath` | Yes | `Building the plan…` | Not awaiting review/ready or a plan already exists | static audit 2026-10-29 |
| Home | Not now | closes outline review | Yes | — | — | static audit 2026-10-29 |
| Home | Unit row | navigates to a ready lesson | Yes | — | Native `disabled` unless status is `ready` | static audit 2026-10-29 |
| Home | Read | navigates to first ready lesson | Yes | — | Hidden until a ready lesson exists | static audit 2026-10-29 |
| Home | Download | `api.getLesson` then `saveLessonOffline` | Yes | `Saving…` | Same lesson already saving | static audit 2026-10-29 |
| Home | Upload / Cancel | upload XHR / `abort()` | Yes | `Uploading…`, progress percent | File over 50MB or unsupported type | static audit 2026-10-29 |
| Lesson | Learn / Solve / Test | tab switch | Yes | — | — | e2e (`lesson_attempts`) |
| Lesson | Save Offline | `saveLessonOffline` | Yes | `Saving...` | Already saved | static audit 2026-10-29 |
| Lesson | Ask Doubt / Send | online doubt or genuine-offline queue | Yes | `Sending…` | Empty question | e2e (`doubt_truth`) |
| Lesson | Check Answer | `POST /attempts`, offline queue when offline | Yes | `Checking…` | Empty response or already submitting | e2e (`lesson_attempts`, `offline_sync`) |
| Lesson | Citation chip | opens source excerpt drawer | Yes | — | — | static audit 2026-10-29 |
| Lesson | Submit checkpoint | server-graded `POST /attempts` per question | Yes | `Submitting…` | Missing lesson version or no answers | e2e (`lesson_attempts`) |
| Dashboard | Edit Academic Profile | opens modal | Yes | — | — | e2e (`student_dashboard_truth`) |
| Dashboard | Save Changes | `PUT /profile` | Yes | `Saving…` | Missing class, board, language, or taxonomy failure | e2e (`student_dashboard_truth`) |
| Dashboard | Join Classroom | `POST /teacher/join` | Yes | `Joining…` | Empty code | static audit 2026-10-29 |
| Teacher | New classroom | toggles form | Yes | — | Teacher role enforced by `AuthGate` | e2e (`teacher_evidence`) |
| Teacher | Create classroom | `POST /teacher/classrooms` | Teacher | `Creating…` | Missing name, class, board, subject, or taxonomy failure | static audit 2026-10-29; pytest (`test_taxonomy_validation`) |
| Teacher | Copy code | clipboard | Teacher | — | No code available | static audit 2026-10-29 |
| Teacher | Student row | selects student for a suggestion | Teacher | — | Removed accounts are not selectable | e2e (`teacher_evidence`) |
| Teacher | Send suggestion | `POST /teacher/recommendations` | Teacher | `Sending…` | No student, evidenced concept, note, or taxonomy failure | e2e (`teacher_evidence`) |
| Teacher | Retry roster / classrooms | refetch | Teacher | loading line | Only shown after a failed load | static audit 2026-10-29 |
| Doubts | Sync now | `syncPendingData` | Yes | `Syncing` | — | e2e (`doubt_truth`) |
| Doubts | Retry | `POST /doubts` with the same client ID | Yes | `Retrying…` | Only for retryable online failures | e2e (`doubt_truth`) |
| Library | Open Offline | lesson route | Yes | — | — | static audit 2026-10-29 |
| Library | Delete | `deleteOfflineLesson` | Yes | — | — | static audit 2026-10-29 |
| Not found | Back to SETU | `/` | No | — | — | e2e (`navigation_truth`) |

## Defects found and corrected in this task

1. **Guest navigation exposed protected routes.** Guests saw Dashboard, Doubts, and Downloads links; those routes rendered without a sign-in prompt. Guests now see only Home, and protected routes use `AuthGate`.
2. **Unit rows used a click handler on `<li>`.** Not keyboard operable, no disabled semantics. They are now real buttons, disabled unless the lesson is ready.
3. **Download had no success/failure feedback.** `saveLessonOffline` failures were unhandled promise rejections in `HomePage` and only logged in `LessonReaderPage`. Both surfaces now show a success or error state, and the lesson button reports storage failure.
4. **Unknown routes rendered a blank main region.** A catch-all route now renders `NotFoundPage`.
5. **`science_process` visuals rendered cell-membrane art.** The renderer now requires real process steps and otherwise states the visual is unavailable.
6. **Claims outran the implementation.** "Verified textbooks", "zero hallucinations", "Verified Textbook Citation", and a hardcoded "Class 9 Textbook" fallback were replaced with source-grounded wording and the uploaded document's real metadata.

## Remaining manual acceptance (not yet claimed)

The final end-to-end pass still needs to exercise with a real account and real upload: book chip, retry ingestion, build-plan review, upload cancel, citation drawer, checkpoint submit, offline library open/delete, and classroom join from both Home and Dashboard. Those rows stay marked static until that run is recorded in `context/ACCEPTANCE_MATRIX.md`.

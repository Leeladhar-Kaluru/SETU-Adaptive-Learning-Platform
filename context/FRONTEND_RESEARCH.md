# SETU Frontend Research — "The Learning Desk"

Read-only pass. No application code was changed. Stitch was **not** used: `list_mcp_resources` returns 0 servers/templates and no Stitch tool is exposed. Section 3 contains the prompts that would have been sent. `ui-ux-pro-max` was consulted (`--design-system` returned a generic blue SaaS/landing pattern; rejected with reason in §2) and `frontend-design` guidance was applied.

Evidence: source only (no screenshots). Counts below are measured with ripgrep/PowerShell over `frontend/src`.

---

## 1. Current visual language audit

### What is distinctive and should survive

- **Ink rail + paper canvas + indigo.** `Navigation.module.css:1-10`, `tokens.css:3,16`. The dark rail is a real frame, not a generic top bar.
- **The logo is an ownable mark.** `public/setu-logo.svg` is a path with two nodes (indigo + green), i.e. a route with a start and a demonstrated end. It is only used as a favicon; the rail shows a letter tile (`Navigation.module.css:26-34`). The best brand asset is unused.
- **The teacher and doubt copy is honest and specific.** "Nothing here is filled in until a student joins and studies" (`TeacherDashboardPage.tsx:426-428`); "Every question you asked SETU, with its real state" (`DoubtQueuePage.tsx:212-215`). This voice is a product asset.
- **Mono codes** (`TeacherDashboardPage.module.css:50-53`, `StudentDashboardPage.module.css:473-482`) feel like real classroom material.
- **`DoubtQueuePage` sets the quality floor**: 44px targets, visible focus, reduced motion, one responsive breakpoint (`DoubtQueuePage.module.css:33,59,78,93,346`). Copy this pattern.

### What reads as generic / templated

- **Home is five equal panels.** Same radius, border, shadow and 16px `h2` (`HomePage.module.css:845-856`); nothing says which surface is primary.
- **66 of 119 classes in `HomePage.module.css` are unused** (measured), including `.hero`, `.pathsGrid`, `.catalogueList`, `.materialRow` — leftovers from a catalogue UI that no longer renders. The page reads assembled, not designed.
- **KPI cards with a 3px indigo top bar** and tracked all-caps labels (`StudentDashboardPage.module.css:113-149`); emoji as icons (`HomePage.tsx:438,446,454`; `LessonReaderPage.tsx:550`); middle-dot metadata strings everywhere (`HomePage.tsx:540-542`; `LessonReaderPage.tsx:435-437`). These are the documented AI-design tells.
- **The lesson is a blog post in a card**: 32px content card, 15px/1.7 body (`LessonReaderPage.module.css:113-122,159-163`). It does not feel like a study spread.
- **45 hardcoded hex values and 41 inline `style={{}}` objects in `LessonReaderPage.tsx`; 26 hex and 24 inline styles in `OfflineLibraryPage.tsx`** (measured). `OfflineLibraryPage` has no CSS module at all.
- **Two visual systems**: student pages use shadows; teacher panels have none (`TeacherDashboardPage.module.css:28-33`). The teacher half looks like an internal admin tool.

### Accessibility, contrast, hierarchy and mobile risks

| Risk | Evidence | Effect |
|---|---|---|
| Muted text fails AA | `--ink-muted #7E8B9F` on `#F7F6F1` = **3.19:1** (3.45:1 on white), `tokens.css:12`; used at 11–13px in `HomePage.module.css:918-922,977-983`, `StudentDashboardPage.module.css:143-149,513-518`, `TeacherDashboardPage.module.css:96-104` | Fails 1.4.3 for normal text |
| Focus is largely undefined | Only **6** `:focus-visible` rules in the whole app (grep). Global button reset `tokens.css:95-100`; inputs remove outline (`AuthModal.module.css:106-110`, `HomePage.module.css:476-480`, `LessonReaderPage.module.css:383-386`); no skip link (no "Skip to" match) | Keyboard users lose their place |
| Click targets are not controls | Citation `<span onClick>` `LessonReaderPage.tsx:524-532`; heatmap `<div onClick>` `StudentDashboardPage.tsx:299-305`; overlay divs `LessonReaderPage.tsx:787-817` | Cannot be reached or operated by keyboard |
| Dialogs are incomplete | `AuthModal.tsx:83-91` (role/aria, no focus trap, no Escape); student edit modal is a bare div `StudentDashboardPage.tsx:468-471`; lesson drawers are bare divs | Focus stays behind; screen readers are not contained |
| Icon-only buttons unlabeled | Offline delete `OfflineLibraryPage.tsx:127-133`; drawer close `LessonReaderPage.tsx:792,825` (Auth close is correctly labeled) | No accessible name |
| Meaning by color only | Test options `LessonReaderPage.module.css:289-300` + `LessonReaderPage.tsx:709-713`; heatmap levels `StudentDashboardPage.module.css:229-233` with values only in `title` (`StudentDashboardPage.tsx:299-305`) | Color-blind and keyboard users cannot read results; chart guidance requires focus-revealed values + table fallback |
| Faux weights, small inputs | Fonts load 400–700 (`index.html:11`) but CSS asks 800/650 (`HomePage.module.css:39,880`; `StudentDashboardPage.module.css:153`); inputs are 13–14px (`AuthModal.module.css:103`) | Synthetic bold; iOS zooms on focus |
| Mobile layout gaps | **Zero media queries** in Student and Lesson CSS (measured); `minmax(460px,1fr)` `StudentDashboardPage.module.css:270` overflows below ~508px; nav becomes three stacked rows with horizontal scroll `Navigation.module.css:132-154`; Offline header + quota card is an unwrapped flex row `OfflineLibraryPage.tsx:47-68`; lesson header actions unwrapped `LessonReaderPage.module.css:10-20,51-55` | Horizontal overflow and cramped reading |
| Guest home breaks mid-width | 3 card columns until 768px viewport (`HomePage.module.css:91-101`) while the rail takes 220px (`Navigation.module.css:2`) | ~120px text columns at 769–1000px |
| Cascade collisions | `.modalContent` declared twice (`HomePage.module.css:700-711` vs `1136-1144`) loses `max-height/overflow`; `.modalBackdrop` z-index 1000 vs 20 (`688-698` vs `1126-1134`); `--shadow-xs` used at `HomePage.module.css:108` but never defined | Long outline modal clips on phones; layering is unpredictable |
| Heading outline is flat | Dashboard section titles are divs (`StudentDashboardPage.tsx:260,324,379,426`); Home `h2` is 16px (`HomePage.module.css:853-856`) while Teacher `h2` falls back to 24px (no `.panel h2` rule) | Same semantic level renders at different sizes; no navigable outline |
| Honesty drift in display | Board from `boardId.replace().toUpperCase()` `StudentDashboardPage.tsx:183`; concept ids title-cased `StudentDashboardPage.tsx:344`, `TeacherDashboardPage.tsx:36-39`, `HomePage.tsx:404-407`; `'Student'` fallback `TeacherDashboardPage.tsx:875`; `minutes ?? 0` `TeacherDashboardPage.tsx:663`; transport failure shown as "0 of N correct" `LessonReaderPage.tsx:375-386` | Derived labels and zeros can read as real evidence |
| Hardcoded grade range | `index.html:8`, `vite.config.ts:14`, `HomePage.tsx:413`, `AuthModal.tsx:142`, `OnboardingTour.tsx:228,269,349` | Contradicts taxonomy-driven, subject/board-agnostic rule |
| No offline-storage failure state | `OfflineLibraryPage.tsx:18-37` has no `catch` around IndexedDB reads/deletes | A blocked DB leaves "Checking IndexedDB..." forever |

Additional hierarchy note: `HomePage.tsx:377-384` infers "Preparing" vs "Queued" from `sequence <= 2`, and "First two units" progress from a hardcoded count. That is not API state; later units may be actively generating while labelled "Queued".

---

## 2. Design direction for "The Learning Desk"

### Thesis: **Ruled Desk**

SETU is a desk where one school document is open and the product annotates it. The interface borrows from the exercise-book margin, the index card and the teacher's mark book — not from SaaS dashboards. The distinctive claim (every lesson cites a page you gave it) becomes the distinctive layout: **a margin rule with citations hanging in it**.

Why this and not the current defaults: the `ui-ux-pro-max` match was "Minimalism & Swiss Style" with a generic `#2563EB` SaaS palette and a landing-page pattern — exactly the templated result the brief warns about, so it was rejected. Warm cream + serif display + terracotta is also rejected: this product is used under mixed light at a desk, and that combination is the current editorial-AI default. Indigo/navy is kept because the logo, theme color and existing recognition depend on it. Literata is confined to **reading content**; it is never the marketing display face.

### Color (6 core + semantic state inks)

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--ink` | `#101B2F` | Text, rail, rules of emphasis | 15.19:1 on paper |
| `--paper` | `#EEF1F4` | Desk canvas (replaces warm `#F7F6F1`) | — |
| `--sheet` | `#FFFFFF` | Reading sheets, forms | — |
| `--indigo` | `#3E4FD8` | One primary action, focus, active mark | 6.34:1 with white |
| `--check` | `#1D7A5B` | Correct / evidenced / saved | 5.27:1 on sheet |
| `--rule` | `#C8D1DD` | Decorative hairlines only | 1.36:1 (not for controls) |

Derived inks: `--ink-soft #4C5A6E` (6.19:1 on paper), `--ink-faint #5A6678` (5.14:1), `--control #7C8BA0` (3.47:1 on white, for input borders). Semantic inks: `--warn #96520E` (5.28:1 on paper), `--error #B3362A` (5.33:1). These are darker than today's warning/error so they still pass on the cooler canvas. No cream, no terracotta, no gradients.

### Type

| Role | Face | Size / line | Weight |
|---|---|---|---|
| Page title | Archivo | 28 / 32, `-0.01em` | 600 |
| Chapter / lesson title | Literata | 32 / 38 | 600 |
| Section | Archivo | 19 / 26 | 600 |
| UI body | Archivo | 15 / 22 | 400 |
| Reading body | Literata | 18 / 30, max 66ch | 400 |
| Meta | Archivo | 13 / 18 | 400 |
| Label | Archivo | 11 / 16, sentence case, `+0.01em` | 600 |
| Data / refs | JetBrains Mono | 12 / 16, `tabular-nums` | 500 |

Replace Plus Jakarta Sans with Archivo (UI) and add Literata (reading only). Load exactly 400/500/600/700 Archivo, 400/500/600 + italic 400 Literata, keep JetBrains Mono. Ban 800/650 and tracked all-caps eyebrows; label case is sentence case. Reserve `·` for inline units/citations, not every metadata row.

### Layout concept

- **Desk frame:** 208px ink rail; content max 1120px; 12 columns, 24px gutters; 32px page margin.
- **The margin rule:** a 1px `--rule` at 72px from the sheet edge. Section numbers (`3.2`), page refs (`p. 41`), dates and status marks live in that margin. It is wayfinding, not decoration. Nav is **not** numbered because it is not a sequence; unit and lesson numbers are, and only they use numerals.
- **Ledger rows, not cards:** units, roster and attempts are ruled rows with columns. A row hover tints the rule, not the whole surface. One sheet per section.
- **Paper layers:** 8px sheet radius, 1px rule, no shadow. Shadow is reserved for overlays and the source drawer.
- **Ink actions:** one filled indigo button per screen. Secondary actions are underlined text. Status is an icon + word, never a pill.
- **Evidence in the margin:** citations are superscript numbers aligned to the sentence; the matching page ref sits in the margin and opens a right-hand source sheet. On mobile the sheet rises from the bottom.
- **The one bold moment:** the source sheet slide-in (180ms, answers the click). No page-load cascade, no hover lift on every card. `prefers-reduced-motion` respected.

### Wireframes

Home (desk):
```
+----------+--------------------------------------------------------------+
| SETU     | Thursday 29 October                     join code [______]  |
|          | Hello, Asha                                                  |
| Desk     | +--------------------------------+  +----------------------+  |
| Dashboard| | CURRENT BOOK                   |  | UNIT LEDGER          |  |
| Doubts   | | || biology-9.pdf               |  | 1 Matter      ready  |  |
| Library  | | || 142 pages - ready           |  | 2 Cells       ...    |  |
|          | | [Continue ->]                  |  | 3 Tissues     ...    |  |
| -------- | +--------------------------------+  | 4 Nutrition   failed |  |
| o online | +----------------------------------------------------------+  |
| A. Rao   | | UPLOAD TRAY  Drop a PDF, DOCX, image...        [choose]  |  |
| Student  | +----------------------------------------------------------+  |
+----------+--------------------------------------------------------------+
```

Lesson reader:
```
+----------+------+-------------------------------------+------------------+
| <- Desk  | 3.2  | What is a cell?                     | SOURCE           |
|          |      |                                     | p. 41            |
| Learn    | [1]  | Cells are the basic unit of life.   | +--------------+ |
| Solve    |      |                                     | | excerpt from | |
| Test     | [2]  | The membrane controls what enters.  | | your upload  | |
|          |      |                                     | +--------------+ |
| p. 41    |      | ...                                 | Open page ->     |
+----------+------+-------------------------------------+------------------+
```

Student dashboard:
```
+----------+--------------------------------------------------------------+
| Desk     | Asha                                        [Edit details]   |
| Dashboard| Class 9 - CBSE - English            (rendered only if set)   |
| Doubts   | ============================================================ |
| Library  | STREAK 0 days   TIME 0 min   CHECKS -   SESSIONS 0            |
|          | ============================================================ |
| 12 weeks | LAST 12 WEEKS   [][][][][][][][][][][][]   [Table view]      |
|          | ============================================================ |
|          | CONCEPT LEDGER                    RECENT CHECKS              |
|          | cell-membrane - 3 checks          lesson - correct - 42s     |
|          | no evidence yet                   no attempts yet             |
+----------+--------------------------------------------------------------+
```

Teacher (mark book):
```
+----------+--------------------------------------------------------------+
| SETU     | Morning Science          code 7K2M4Q   [copy] [rotate]       |
|          | 1 joined - updated 14:32                                     |
| Classroom| ------------------------------------------------------------ |
|          | STUDENT          MIN  LAST OPENED      CHECKS  CHANGE        |
| -------- | Asha             24   Light            75%     steady        |
| o online |   cell-membrane - approaching - 3 checks                     |
|          | Ravi              0   Not opened yet    -       -             |
|          | -- select a student to open the evidence sheet --            |
+----------+--------------------------------------------------------------+
```

Mobile shell:
```
+----------------------------+
| SETU            o online  |  56px top bar; sync lives here
+----------------------------+
|                            |
|   one sheet, 16px margins  |
|                            |
+----------------------------+
| Desk  Dashboard  Doubts  Library |  64px + safe-area, 4 tabs
+----------------------------+
Lesson routes replace the bottom bar with:  Learn | Solve | Test
```

---

## 3. Stitch prompt set — **NOT SENT**

> **Status: NOT SENT.** Stitch MCP is unavailable in this environment (0 MCP resources; no stitch tool). These are the exact prompts that would have been sent, in order. Every value in `{{braces}}` is runtime-bound; Stitch must render the token, not invent a value. Empty states use real copy and must not be filled with sample rows.

**SHARED SYSTEM (prepend to every prompt):**
"Design SETU, a source-grounded study desk for school students. Product name is always SETU, never a version suffix. Canvas `#EEF1F4`, sheets `#FFFFFF`, ink `#101B2F`, primary indigo `#3E4FD8`, evidence green `#1D7A5B`, hairlines `#C8D1DD`. Type: Archivo for UI and headings, Literata only for lesson reading, JetBrains Mono for page references, codes and counts. Geometry: 8px sheet radius, 1px rules, no gradients, no glass, no shadow except overlays and the source sheet. Layout: a 208px ink rail with the wordmark and plain nav labels; a 1120px, 12-column content area with a 72px ruled margin for section numbers, page refs and status. Status is an icon plus a word, never a colored pill. No emoji. No tracked all-caps eyebrows. No cream background, no terracotta. Every control shows a real state; no invented students, scores, counts or citations. Responsive frames: 1440 and 390."

1. **Home — guest.** Frame 1440. Rail: SETU wordmark (use the arc path mark from the logo, not a letter tile), nav "Desk" only, foot "o online", "Get started". Content: ruled margin; title "Welcome to SETU"; body "Upload a school document. SETU reads it, shows you what it found, and builds lessons that cite the pages you gave it." Buttons "Get Started ->" (indigo) and "Sign In" (underlined ink). Below, a ruled four-step sequence (real sequence, so numbers are allowed): "01 Upload a PDF, DOCX, PPTX, TXT, MD, or image", "02 Review the pages SETU found", "03 Learn, Solve, Test", "04 Ask a doubt and get the page it came from". No testimonials, no logos, no fake stats.

2. **Home — signed in, nothing uploaded.** Frame 1440. Rail: Desk, Dashboard, Doubts, Library; foot shows connection state and name. Content: "Hello, {{displayName}}"; margin note "No pace set" only when the API returns no pace. Sheet 1 "Current book": empty line "No book yet. Upload one and a plan is built from its units." Sheet 2 "Units": "Units appear here after the book has been read and you build the plan." Full-width "Upload" tray: "Choose a PDF, DOCX, PPTX, TXT, MD, or image. Up to 50MB." Do not show the six-step timeline until an upload exists. Sheet 3 "Study record": "Nothing has been studied yet. Time and check results appear after you open a unit."

3. **Home — book processing / ready / failed.** Frame 1440. Same shell. Processing sheet: filename `{{filename}}`, `{{pageCount}} pages`, status word from API, progress line `{{progressMessage}}`; timeline only for the active job: "Uploading the file", "Stored", "Reading pages", "Indexing", then unit statuses. Unit ledger rows: "1 {{title}} - ready - Open ->", "2 {{title}} - {{status}}", "3 {{title}} - failed - Could not prepare". Failed book: inline error `{{errorMessage}}` + "Retry". Needs OCR: "{{pagesNeedingOcr}} pages could not be read after text extraction and OCR. Those pages are not indexed and will not appear in your lessons." Ready: "Build my learning plan". Never write "0 of 0" or a percentage the API did not send.

4. **Lesson — Learn.** Frame 1440. Rail retained. Header: "<- Desk", "Class {{grade}}" only if grade is non-null, subject name from taxonomy (not the raw id), title in Literata. Tabs "1. Learn (Source Explanation)", "2. Solve (Guided Practice)", "3. Test (Checkpoint Assessment)". Reading sheet: "Learning Objectives"; body blocks 18px Literata, 66ch; superscript citation numbers; margin refs "p. {{pageStart}}" aligned to each paragraph. Right source sheet on citation click: "Source Provenance", "Source citation", `{{sourceTitle}}`, "Page {{pageStart}}", excerpt in a ruled box, "Extracted from the document you uploaded." Buttons "Save Offline" / "Saved Offline", "Ask Doubt".

5. **Lesson — Solve / Test states.** Frame 1440. Solve: "Guided Practice Problems"; helper "Work through these problems with progressive hints. Attempts are recorded for your teacher evidence matrix." Option rows A–D; revealed hint box; "Need help? Reveal Hint {{n}}"; "Check Answer"; feedback "Correct." or "Not quite." plus `{{feedback}}`; offline line "Saved offline. This answer will be graded when you reconnect." Test: "Checkpoint Test"; "Independent assessment without hints. Complete all questions to calculate your adaptive mastery score."; "Submit Checkpoint Test"; "Checking your answers..."; result "Checkpoint: {{correct}} of {{total}} correct"; offline "Checkpoint saved offline" + "The answers are stored on this device. Results appear after they sync." If grading fails, show "The checkpoint could not be graded. Try again." — never a score of 0.

6. **Student dashboard.** Frame 1440. Header: name, academic context only from API; "Edit Academic Profile". One summary rule row: "Current streak", "Total time studied", "Checkpoint accuracy", "Study sessions" — numbers in mono, `—` when there are no attempts. 84-day strip with a visible "Table view" disclosure; each cell focusable, showing "{{date}}: {{minutes}} min across {{count}} activities"; no color-only meaning. "Concept Mastery Matrix" rows: concept code in mono (until the API provides a display name), band word, score, "{{evidenceCount}} evidence points". "Recent Practice Checkpoints" ruled table. "Enrolled Classrooms"; empty "You have not joined a classroom." Fresh state copy: "No study activity yet. Open a ready lesson to start the heatmap.", "No concept mastery evidence yet. Answer a checkpoint to build evidence.", "No checkpoint attempts yet."

7. **Teacher — classroom mark book.** Frame 1440. Title "Classroom"; lede "Members, study time, and the unit they last opened. Nothing here is filled in until a student joins and studies." Toolbar: classroom chips, "New classroom". Sheet header: `{{classroom.name}}`, "Join code {{joinCode}}" or "Code unavailable", "Copy code", "Rotate code", "{{memberCount}} joined - updated {{time}}". Ruled table: "Student and evidenced topics", "Minutes", "Last opened", "Checks", "Change". Empty: "No students have joined. Share the code above. Their minutes and checks will show here after they study." "Membership" list with Active/Removed. "Suggestion" composer with student, evidenced topic, action, note; "Send suggestion". "Sent suggestions" table. Disabled controls include the reason in text next to them.

8. **Doubts + Offline library (two frames, 1440 and 390).** Doubts: title "Doubts"; lede "Every question you asked SETU, with its real state. Questions asked while the device was offline are stored here until they can be answered."; "Sync now"; rows with "Answered", "Needs retry", "Rejected", "Waiting to sync"; answered block "Answer from your sources" with page refs; retry block "The tutor could not answer this when you last asked. Your question is saved - you can retry it now."; empty "No doubts yet." Offline library: title "Offline library"; quota "{{count}} packages - {{size}}"; empty "No offline lessons downloaded yet" + "Open any lesson from your Desk and click "Save Offline" to download all explanations, worked examples, and diagrams." + "Browse Desk"; delete is a labeled icon button with confirm. Mobile frames: 56px top bar, bottom 4-tab bar, sheets full width, no horizontal scroll.

---

## 4. Prioritized implementation plan

| Phase | Files | Change | Guard |
|---|---|---|---|
| **P0 Tokens + truth** | `frontend/src/tokens.css`, `index.html`, `vite.config.ts` | New palette/type/spacing/focus tokens; fix `--ink-muted`; define `--control`; replace font link; manifest colors; remove "Classes 6–10" from meta/manifest. Remove range copy in `HomePage.tsx:413`, `AuthModal.tsx:142`, `OnboardingTour.tsx:228,269,349`. | No TSX logic. Re-run `onboarding_taxonomy`, `navigation_truth`. |
| **P1 Primitives** | new `frontend/src/styles/desk.module.css`; `main.tsx` only if a global reset is needed | `.sheet`, `.rule`, `.margin`, `.ledgerRow`, `.status`, `.btn`, `.btnPrimary`, `.field`, `.label`; pages opt in with `composes`. Add global `:focus-visible` (`:where(...)`) and `#main` skip link in `App.tsx`. | Keep CSS Modules; no Tailwind/shadcn; no mass class rewrite. |
| **P2 Shell + Home** | `Navigation.tsx/.module.css`, `App.module.css`, `HomePage.tsx/.module.css` | Rail becomes the margin: plain labels Desk/Dashboard/Doubts/Library (drop the dynamic "Lesson" link; lessons open from the ledger). Mobile: 56px top bar + 4-tab bottom bar. Home: 2-column desk (book + unit ledger), upload tray full width, study record as a ruled strip. Delete the 66 dead classes and the duplicate `.modal*`/`.heatmap` blocks. Move book chips out of inline styles. | Preserve `Get Started ->`, `Sign In`, `Build my learning plan`, `Continue`, `Save Offline`; preserve polling and all empty/error copy. |
| **P3 Lesson reader** | `LessonReaderPage.tsx/.module.css`; `VisualUnavailable` if needed | Extract 45 hex/41 inline styles into the module. Literata 18/30, 66ch. Citation spans -> buttons with superscript number + margin ref; source sheet as `role="dialog"`, labelled, Escape, focus return. Tabs keep numbered labels. Fix transport failure state (`:375-386`) to a failure panel. Add mobile: header wraps, tab bar sticks, drawer full width. | Do not change attempt payloads, idempotency keys, offline queueing or mastery rendering. |
| **P4 Dashboards** | `StudentDashboardPage.tsx/.module.css`, `TeacherDashboardPage.tsx/.module.css` | Replace 4 KPI cards with one summary rule row; heatmap cells -> buttons with `aria-label` + table view; section titles -> `h2`; board name from `useTaxonomy`, fallback to mono id (not uppercase munge); concept ids as mono codes; teacher ledger + student evidence sheet (drawer on mobile); "updated {{time}}" under the class header. | Do not replace `?? 0` with invented values: show `0` only when the API says `0`, otherwise `—`/`No checks yet`. Keep "Account removed", "Code unavailable", band labels. |
| **P5 Offline + doubts + dialogs** | new `OfflineLibraryPage.module.css`, `OfflineLibraryPage.tsx`, `DoubtQueuePage.module.css`, `AuthModal.tsx/.module.css`, `StudentDashboardPage` modal, `OnboardingTour` | Create the missing CSS module; add `catch` + retry + `role="alert"` for IndexedDB failure; labeled delete + confirm; 44px targets. Align Doubts statuses to the new type. Add focus trap/Escape/labels to all dialogs. | Keep the offline merge logic and status vocabulary; `needs_retry` must stay retry-only-online. |
| **P6 Verification** | e2e specs | Run `npm run build`, then `navigation_truth`, `student_dashboard_truth`, `lesson_attempts`, `offline_sync`, `doubt_truth`, `teacher_evidence`, `onboarding_taxonomy`. Check 375/768/1024/1440 and keyboard-only. | No screenshot baseline exists; do not claim visual parity. |

**Do not change:** API contracts, fetch/poll logic, `role="alert"/"status"` semantics, disabled predicates, status vocabularies, idempotency keys, offline merge precedence, empty/error strings asserted by e2e, zero values that are real. Do not add sample students, average scores, "25 min" defaults, or placeholder rows to make a layout look full. Do not hide a failure behind a skeleton or convert it to `0`.

**Deliberately deferred:** true dark mode (tokens are light-only; a half-done dark theme would fail contrast), a component library, and any lesson-retry UI until the API exposes a lesson error/retry contract. The current failed-unit row can only say "Could not prepare"; that is honest but incomplete.

---

## 5. Honest UI states that must remain visible

| State | Where | Required visible behavior |
|---|---|---|
| Empty offline library | `OfflineLibraryPage.tsx:72-85` | "No offline lessons downloaded yet" + how to save + "Browse Desk". No fake cards. |
| IndexedDB read/delete failure | `OfflineLibraryPage.tsx:18-37` (missing) | "SETU could not read offline storage on this device." + Retry; never a permanent "Checking IndexedDB...". |
| Failed extraction | `HomePage.tsx:218-227,484-504,548-550` | The API `errorMessage`, "Retry", and the exact failed status; never "ready". |
| Pages needing OCR | `HomePage.tsx:751-754` | "{{n}} pages could not be read... Those pages are not indexed and will not appear in your lessons." |
| Load failure (books/plan) | `HomePage.tsx:485-504` | "SETU could not load your books/learning plan. Check your connection, then retry." + Retry. |
| Lesson preparing / queued | `HomePage.tsx:582-588`, `LessonReaderPage.tsx:411-422` | Actual status word; "Preparing this lesson" + "Return to Desk". Do not infer "Queued" from sequence. |
| Lesson failed | `HomePage.tsx:585` | "Could not prepare", disabled with a visible reason. No retry until a real endpoint exists. |
| Offline attempt queued | `LessonReaderPage.tsx:307-310` | "Saved offline. This answer will be graded when you reconnect." |
| Checkpoint queued offline | `LessonReaderPage.tsx:752-759` | "Checkpoint saved offline" + "Results appear after they sync." |
| Checkpoint grading failure | `LessonReaderPage.tsx:375-386` | "The checkpoint could not be graded. Try again." — not "0 of N correct". |
| Doubt `needs_retry` | `DoubtQueuePage.tsx:307-332` | "Needs retry", saved-question explanation, Retry enabled only online ("Retry when online"). |
| Doubt waiting to sync | `DoubtQueuePage.tsx:334-338` | "Saved on this device. It will be sent when SETU is reachable." |
| Doubt rejected | `DoubtQueuePage.tsx:340-345` | "This question was rejected because it was empty or malformed." + how to ask again. |
| Doubt insufficient evidence | `LessonReaderPage.tsx:867-871` | "The uploaded source does not contain enough evidence for a grounded answer." |
| Unauthorized teacher | `AuthGate.tsx:30-38` | "Teacher account required" + explanation; no classroom data leaks. |
| Fresh student dashboard | `StudentDashboardPage.tsx:279-282,329-332,384-387,431-433` | Zero/— with the four honest empty lines; no default class, board, goal or mastery band. |
| Teacher empty roster | `TeacherDashboardPage.tsx:601-605` | "No students have joined. Share the code above. Their minutes and checks will show here after they study." |
| Missing join code | `TeacherDashboardPage.tsx:556-561` | "Code unavailable"; copy/rotate disabled with the reason. |
| Removed account in roster | `TeacherDashboardPage.tsx:626-627` | "Account removed", not a generic student name. |
| Taxonomy unavailable | `AuthModal.tsx:152-168`, `StudentDashboardPage.tsx:534-546`, `TeacherDashboardPage.tsx:522-536` | Error + Retry; selects disabled; Save disabled; no built-in board/subject fallback. |
| Offline connectivity | `Navigation.tsx:88-104` | "Offline. Work is saved on this device and syncs when you reconnect." + pending count + "Sync now". |

# Design System and UI Direction

## Thesis: “The Learning Desk”

Make SETU feel like a thoughtful learning workspace—not a generic AI dashboard. Use a calm editorial foundation, precise interactive learning surfaces and strong information hierarchy. A few exceptional, consistent components beat dozens of inconsistent gradients/cards.

- Warm off-white canvas, deep ink/navy navigation, confident indigo action colour, restrained mint/amber status colours.
- Readable editorial heading face paired with a robust multilingual sans. Noto Sans or equivalent should be tested for English, Telugu, Devanagari, Urdu/Arabic and selected scripts; verify actual glyph coverage before shipping.
- Compact navigation: Home, My Learning, Resource Library, Offline, Doubts and role-gated Teaching.
- Lesson reader: readable central column, clear explanation/diagram/practice hierarchy, source pane on desktop and collapsible source context on mobile.
- Density is intentional: library and teacher tables can be dense; lesson reading is quiet; visual focus is wide; phone actions remain touch-friendly.
- Only real progress/status. Never fake activity, completion or citations.

## Provisional tokens

These are starting tokens, not final brand approval. Calculate contrast rather than assuming a pair passes.

| Token | Value | Use |
|---|---|---|
| `--color-ink` | `#15233B` | Main text/nav |
| `--color-indigo` | `#4055D9` | Primary actions/current focus |
| `--color-canvas` | `#F7F6F1` | Page canvas |
| `--color-surface` | `#FFFFFF` | Main surfaces |
| `--color-border` | `#D9DEEA` | Separators |
| `--color-success` | `#23795B` | Completed/synced/valid |
| `--color-warning` | `#A65B12` | Pending/retry caution |
| `--color-danger` | `#B42335` | Failure/destructive warning |
| `--color-muted` | `#596579` | Secondary text |

Target WCAG 2.2 AA; include non-colour indicators, visible keyboard focus and clear focus order.

## Interaction rules

- Avoid layout shift during upload/generation; reserve progress space.
- Skeletons resemble known layout only; never appear as fake lesson content.
- Every async state has a clear noun/verb status and recovery action.
- Prefer one clear primary action per section: `Create path`, `Continue lesson`, `Save offline`, `Sync doubts`.
- Explain why a recommendation exists, how source grounding works and what a next step means.
- Do not hide limitations in a tiny tooltip; every button works or is visibly disabled with a reason.
- Confirm destructive actions: delete source, clear downloads, remove account data.

## Accessibility and age appropriateness

- Target WCAG 2.2 AA; test keyboard use, focus order, zoom, reduced motion and screen-reader labels.
- Diagrams require alt text and long descriptions when necessary.
- Use clear language and non-shaming feedback: “This step is tricky; let's review the prerequisite,” not “You failed.”
- Avoid manipulative streak loss, punitive countdowns and shame-driven gamification.
- Make language switching obvious; don't mix scripts unintentionally.

## Responsive rules

Design for lower-end Android phones first, not merely shrink desktop screens. Mobile lessons are single-column, source context collapses, actions respect safe areas, typography wraps for Telugu/Devanagari, and downloads are small/explicit. Teacher dashboards need a usable tablet/laptop view plus a meaningful mobile summary.

## CSS architecture

Use CSS custom properties and CSS Modules. Keep type/spacing/component variants consistent. Avoid global CSS sprawl, duplicate one-off colours, giant monolithic components and `!important` patches. No Tailwind v4 or shadcn.

## Use of reference boards

See `reference-images/` and `REFERENCE_IMAGE_INDEX.md`. These are generated mood/hierarchy boards, not product screenshots. Sample data, book covers, counts and citations are illustrative; don't copy them into production. Implement the real workflows and review screenshots from a live browser.

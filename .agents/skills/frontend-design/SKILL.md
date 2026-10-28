---
name: frontend-design
description: Guidelines for high-end, production-grade frontend design, avoiding generic AI templates, enforcing typographic hierarchy, custom tokens, and responsive layout.
---

# Production Frontend Design Skill

1. Avoid "AI slop": no default generic purple/indigo gradients on cards, no uninspired cookie-cutter templates, no fake metrics, no repetitive card grids.
2. Establish a clear aesthetic personality: "The Learning Desk" — editorial warmth, deep ink typography (`#15233B`), calm warm canvas (`#F7F6F1`), crisp white surfaces (`#FFFFFF`), purposeful indigo actions (`#4055D9`), restrained success/warning states (`#23795B`, `#A65B12`).
3. Strict typography scale: high readability for educational reading (Classes 6–10), generous line height (1.6 for lesson text), intentional font weights, support for multilingual Indian scripts (Latin, Devanagari, Telugu, Urdu).
4. Information hierarchy: Primary actions are singular and obvious (`Start learning`, `Save offline`, `Sync now`). Dense views (library, teacher evidence table) have purposeful structure; lesson reader is calm, focused, distraction-free.
5. Micro-interactions: Clear focus rings, tactile active states, smooth collapsible sections, no unexpected layout shift during data loading or extraction.
6. CSS architecture: Strict CSS Modules with custom properties. No utility class soup, no Tailwind v4, no shadcn dependencies.

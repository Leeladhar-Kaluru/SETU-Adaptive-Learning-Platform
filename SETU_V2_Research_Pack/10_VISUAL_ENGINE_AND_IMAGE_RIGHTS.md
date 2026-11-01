# Visual Engine and Image Rights

## Objective

Give students accurate visual explanations, interactive where appropriate. Do not let the LLM return arbitrary HTML/SVG/JavaScript and inject it. The model may propose a typed **visual specification** from an allowlist; trusted React/SVG components render it.

## A. Deterministic first-party educational diagrams (preferred)

Build reusable renderers for:
- number lines and fraction models;
- algebra balance/area models and equation steps;
- coordinate grids and charts;
- geometry shapes with labelled sides/angles and safe interactions;
- simple science process flows, plant/animal diagrams and states of matter;
- tables, timelines and cause-effect diagrams for social studies;
- language examples such as syllable/word structures where content accuracy is validated.

Use SVG/CSS for most diagrams; Canvas only if a measured need exists. Provide alt text, keyboard/touch interaction, reset action and a static fallback. Math notation can use KaTeX or an equivalent maintained renderer, with an accessible text alternative.

## B. External reference photos/images

Use sources that permit the intended display and retain attribution/licence metadata. [Openverse API](https://api.openverse.org/v1/) is a discovery source for openly licensed media, but every individual asset and licence needs verification. Store title, creator, source landing page, licence name/version/URL, access date, attribution string, source image URL or permitted cached object, alt text and offline-caching permission.

Do not assume Google Images results, random URLs, Unsplash or Pexels automatically permit any use. Check API hotlink/credit/rate-limit/non-redistribution rules. If rights are unclear, use a first-party diagram or link to the source.

## C. Uploaded textbook/media

A student-selected page region may be tied to their uploaded document with page and bounding box/source reference. Keep it private and subject to the applicable rights. Do not make uploaded third-party textbook illustrations globally reusable without permission.

## Visual-spec contract

A visual spec contains allowlisted renderer `type`, schema version, ID, data/labels/numbers/nodes/edges/coordinates, allowed interaction vocabulary, optional source/media refs, alt text/teaching description and layout limits. Reject unknown types, invalid numeric ranges, excessive nodes/points, arbitrary CSS/HTML/JS and unverified URLs. The renderer owns DOM and event handling.

## Quality principles

- A visual must teach a concept, not decorate whitespace.
- Don't reuse one stock illustration for unrelated subjects.
- Keep labels readable on small phones and keyboard/touch accessible.
- Provide source attribution beside the asset or in an accessible source detail.
- Never invent a creator/caption. When no provenance exists, mark it as first-party/generated or omit it.
- Language-aware labels and descriptions; use language-neutral diagrams when appropriate.
- No photo? Use a diagram or explanation. Lesson generation must not fail just because a suitable photo was not found.

## Included generated UI boards

`reference-images/` contains four AI-generated concept boards for hierarchy and product direction. They are not existing product screenshots, source evidence, actual textbook pages or final approved screens. Their text/metrics/covers can be wrong. Rebuild actual working interfaces from data and compare real browser screenshots later.

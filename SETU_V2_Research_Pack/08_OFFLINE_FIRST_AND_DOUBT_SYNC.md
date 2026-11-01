# Offline-First PWA and Doubt Queue

## Principle

Offline capability is proven by disabling network in a real browser and continuing a user journey—not by displaying an “offline ready” badge.

## Client storage split

- **Cache Storage/service worker:** versioned app shell, JS/CSS, icons/fonts and other public static assets. Use explicit cache rules and purge obsolete versions.
- **IndexedDB:** lesson-pack records, structured visuals, saved authorised blobs/assets, quiz data, notes, local progress events, doubt outbox, sync state and cached answer/citation payloads.
- **Backend database:** canonical records and server sync outcomes.
- **Supabase Storage:** private original documents and permitted assets, fetched only through authorised flows.

Use IndexedDB through Dexie or a thin maintained wrapper. `localStorage` is only for tiny non-sensitive preferences—not the core lesson/outbox data.

## Downloading lesson packs

- Student explicitly chooses a lesson/path segment.
- Fetch immutable lesson JSON and required permitted assets; verify checksum/version if available.
- Write complete package transactionally, then set `available_offline`. Never mark a partially written pack ready.
- Show estimated size, progress, asset count, storage estimate and remove action.
- Don't cache signed URLs/private API responses in a globally shared service-worker cache. Keep personal data user-scoped in IndexedDB, and carefully handle logout/account changes.
- If source PDFs cannot lawfully be cached, store permitted generated derivatives/citations only—not a copy of the textbook.

## Browser storage reality

Browser storage has quota and eviction limits. Use `navigator.storage.estimate()` and request persistence with `navigator.storage.persist()` where supported; handle denial and quota errors. Explain that browser settings can clear site data. Do not promise local data is permanently safe; provide sync/export recovery where practical.

## Doubt outbox record

```json
{
  "clientDoubtId": "uuid-v4-or-uuidv7",
  "serverId": null,
  "courseId": "...",
  "lessonId": "...",
  "lessonVersion": "...",
  "questionText": "...",
  "context": {"blockId": "...", "sourcePage": 12, "questionId": null},
  "attachmentLocalRefs": [],
  "createdAtClient": "ISO timestamp",
  "status": "queued_offline",
  "attemptCount": 0,
  "lastSyncError": null,
  "answerCache": null
}
```

The server derives owner identity from the authenticated session; client IDs/timestamps do not prove ownership.

## Sync algorithm

1. Trigger when connection appears available, app becomes visible/focused, session is restored, or user taps `Sync now`.
2. Acquire a local lock to prevent two tabs sending the same item.
3. Send pending records with a stable client ID as idempotency key.
4. Server enforces uniqueness on `(authenticated_user_id, client_doubt_id)`; it returns stable server ID/status.
5. If model answer generation is asynchronous, store the doubt, enqueue a durable server job, and return `processing`.
6. Poll/subscribe for the answer; validate citation references; store answer/citations in IndexedDB before marking `answered`.
7. Retry transient errors with backoff. Permanent validation/auth issues remain visible and actionable.
8. Keep queue entries through reload/restart; don't silently discard failed items.
9. On logout/account switch, never expose a previous user's private cache under another account. Offer clear/retain/export behaviour consistent with policy.

## Background Sync is optional

MDN marks Background Synchronization as limited availability. Use it where supported, but also sync on app resume, `online`, focus, authenticated startup and manual action. Never promise a closed browser will sync immediately.

## Offline boundaries

- Saved lessons, diagrams and supported quiz types work offline.
- Deterministic grading can work offline if the rule is included in the lesson package.
- New LLM answers, generation and server-only grading wait until connection returns.
- Successfully cached answers remain available offline.
- Web images are not offline unless permitted and included in the pack; prefer compact first-party SVG diagrams.

## Acceptance tests

- Download pack + visuals, disable network, close/reopen and navigate to lesson.
- Complete supported quiz offline; result persists locally.
- Add doubt offline; reload; it remains pending.
- Restore connection; retries create only one server record; answer arrives and citations are cached.
- Simulated model timeout leaves doubt visible with retry status.
- Account switch/logout doesn't leak cached private content.
- Quota error is handled with no half-downloaded pack marked ready.
- Sync works without the Background Sync API.

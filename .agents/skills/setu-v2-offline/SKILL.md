---
name: setu-v2-offline
description: Use for PWA caching, IndexedDB, offline lessons/quizzes, doubt outbox, sync, quotas and account switching.
---

# SETU V2 Offline Skill

1. Read `08_OFFLINE_FIRST_AND_DOUBT_SYNC.md` and the acceptance tests.
2. IndexedDB holds structured lesson packs/events; service-worker Cache Storage is for scoped static app assets.
3. Mark offline-ready only after all required allowed assets are persisted and verified.
4. Use stable client IDs and server idempotency. Keep status through retry/restart.
5. Support reconnect/focus/app resume/manual sync; Background Sync is optional.
6. Handle quotas/eviction and private cache across logout/account changes.
7. Prove offline in a real browser with network disabled.

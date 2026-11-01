# Security, Privacy and Clean Supabase Reset

## Student privacy and safety

Primary users are 11–16. Minimise personal data. Avoid precise location, ad tracking, intrusive behaviour telemetry, public student profiles and automatic public sharing of uploaded documents. Get appropriate consent and follow institutional policy/law before broad deployment. UNESCO's GenAI education guidance supports a human-centred approach and privacy/age-appropriate safeguards; it is not a substitute for local legal review.

## Secrets

- Hosted LLM keys, embedding keys and Supabase service/secret keys stay server-side.
- The browser may use a publishable key only with correct RLS and least privilege; never expose a service-role/secret key.
- Do not echo `.env`, run `cat .env`, paste values into agent notes, or generate `.env.example` from real values. Inspect only variable names and whether values are set, using redacted scripts.
- `.env`, `.env.local`, database URLs with passwords, private credentials, dumps and learner data must be Git-ignored.
- Rotate keys if they appear in logs/screenshots/repo history. The user says they recovered keys; this pack repeats none.

## Upload security

Follow the OWASP upload guidance: allowlist extension and verify file signature; cap bytes/pages/decompressed size/CPU/time; use generated object keys; authorise upload/download; keep files private; protect parsers; consider scanning/sandboxing; don't accept ZIP archives in MVP without need; treat uploaded text as untrusted; sanitise Markdown/HTML and use trusted visual renderers only.

## RLS/tenant tests

Test at least two student identities and a teacher. Student A cannot list/download/retrieve/query Student B's documents/chunks/answers; private objects have no public URLs; teacher requires explicit current membership; service keys do not reach frontend; retrieval checks access before evidence reaches the LLM. Storage policies and API checks must both be tested.

## Deletion

Deletion should remove source objects and derived page/chunk/vector/lesson copies according to retention policy, clear local caches where possible, and preserve only necessary tombstone/audit metadata. Surface partial failure and retry; don't leave orphaned embeddings.

## Clean reset plan for the reused Supabase project

The user has explicitly requested a clean SETU V2 data state while keeping configured credentials. The clean reset must target SETU application-owned data and schema—not casually drop the entire hosted Supabase platform.

### Before any destructive operation

1. Identify the target project using existing environment without printing credentials.
2. Inventory migration history, tables, views, functions, policies, extensions, buckets, storage objects and related test users. Record object names only; redact PII.
3. Create a backup/export using Supabase's supported method and verify the dump is readable. Export a storage/object manifest and preserve irreplaceable files if any.
4. Save an old schema/migration snapshot outside the new repository or in a securely ignored directory. Never commit it.
5. List exactly which app-owned tables/objects/buckets/test records will be removed or recreated. Do not touch unrelated project data.
6. Confirm whether real learner data exists. If it might, stop and choose a retention-safe plan.

### Clean rebuild

- Prefer new versioned migrations for the target schema.
- Remove only verified SETU-owned tables/rows/objects that are safe to replace. If an old table is shared with other data, do not wipe it.
- Recreate private buckets and policies through documented scripts where practical.
- Keep Supabase-managed `auth`/`storage` schemas and platform objects intact. Delete test auth users only if confirmed disposable and included in the reset scope.
- Reapply RLS/storage policies before the app is enabled.
- Seed only verified source metadata and isolated test fixtures; no fake production progress/classes.
- Validate final schema against migrations and run cross-user RLS checks.

### Do not do these things

- Never `DROP SCHEMA auth CASCADE` or `DROP SCHEMA storage CASCADE`.
- Don't drop all extensions, delete platform tables, print credentials, or run a destructive remote `db reset` before verifying the target project.
- Don't delete `.env` files or the research pack.

The goal is a clean **application data model** with the same project credentials—not accidental destruction of Supabase infrastructure.

## Content rights

A public URL is not redistribution permission. Store rights metadata per source/media asset. Don't put complete copyrighted textbooks or substantial copied passages into shared/offline lesson packs without permission. Keep student uploads private and within permitted use.

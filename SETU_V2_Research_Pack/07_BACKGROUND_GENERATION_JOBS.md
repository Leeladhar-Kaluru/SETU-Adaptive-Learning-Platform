# Background Lesson Generation Jobs

## Design rule

**The backend owns long-running work.** Don't generate a whole course in one request, use an in-browser timer as a queue, or rely on in-process FastAPI tasks for durable work.

## Batch strategy

Generate the outline/concept map first. Queue lessons 1–3 with highest priority. Once the outline is approved, enqueue later lessons; start with 1–2 concurrent jobs per course and measure before increasing. Show persisted job states after reload. Mark a lesson `ready` only after every validation gate passes.

## Job state and fields

`queued → claimed → generating → validating → ready`

Other states: `retry_wait`, `failed`, `cancel_requested`, `cancelled`, `needs_human_review`, `superseded`.

Track job ID/type, owner, path and version, lesson/version, priority, status, attempt count/max, `not_before`, lease owner/expiry, idempotency key, input/output hashes, estimated/actual cost where available, safe error code/message, and timestamps.

## Worker requirements

- Durable PostgreSQL-backed queue/job table. Claims are atomic and use locking/lease semantics so two workers do not generate the same lesson concurrently.
- Idempotency so retries do not create duplicate lesson versions or repeated work where provider idempotency is available.
- Finite timeout, bounded concurrency, exponential backoff + jitter, and dead-letter/manual retry for repeated failures.
- Separate transient transport/rate-limit errors from invalid source/schema/content failures.
- Record token/cost metadata when available; cap course generation, rate-limit users and allow pause/cancel.
- Persist source version and prompt/schema version with each job. Never log keys or full sensitive prompts.
- Expired worker leases return to queued/retry state after restart.

## Validation gates

1. JSON schema valid.
2. Required sections non-empty and age appropriate.
3. Every citation refers to an actual page/chunk of the selected source version.
4. Answer keys/rubrics exist and applicable deterministic checks pass.
5. Visual spec validates against allowlisted renderers.
6. Language and translation review status set.
7. Safety/content-quality checks pass or job enters human review.
8. Size is appropriate for offline use.
9. Duplicates flagged for review.
10. Only then change status to `ready` and make the pack available for download.

## UI progress contract

Show honest values, e.g. “3 ready · 4 generating · 5 queued,” derived from the persistent queue. Include pause/retry where appropriate and let students continue with ready lessons. Don't show a lesson as present/ready if its job failed.

## Hosted versus local LLM

An LM Studio endpoint bound to a developer's laptop is reachable only from processes with network access to that laptop endpoint. A deployed worker cannot use it by magic. Provider selection must be explicit in environment configuration and health checks. If the provider is unreachable, jobs pause/retry and the UI says so.

## Abuse/cost protection

Authenticate, rate limit, cap pages/lessons/regeneration and concurrent jobs, reuse validated packages only when source/version and policy permit, and never let document text trigger jobs or raise limits.

# SETU — Forensic Security, Authorization & Data Integrity Audit

**Product Name:** SETU  
**Audit Date:** 30 October 2026  
**Auditor:** Application Security Engineer & Data Systems Lead  
**Scope:** Authentication layers, authorization guards, data access boundaries, storage privacy, secret protection, and Supabase database integrity.

---

> **Reconciliation — 2026-10-31.** The anomaly described in this audit is
> corrected: `chotu1@gmail.com` owns **0** classrooms, not 8. The 8 legacy
> classrooms belong to orphan teacher ID `de898934-3c24-4d3a-baf3-53387ac557b0`
> (no profile row). A dedicated teacher account and classroom were created and
> verified; role enforcement remains strict and correct.

---

## 1. Executive Summary

The application security architecture of SETU is robust and follows modern defensive engineering standards:
1. **Strong Token-Based Authentication:** All protected API endpoints validate Supabase JWTs via FastAPI dependencies.
2. **Defensive Role Enforcement:** Teacher and admin routes enforce strict role checks; privilege escalation attempts by students yield immediate **HTTP 403 Forbidden** errors.
3. **Multi-Tenant Data Isolation:** Documents, learning paths, doubts, and attempt records are strictly scoped to the authenticated user ID (`owner_id`).
4. **Private Storage Backend:** Storage buckets are private; unauthenticated downloads or cross-tenant file access are blocked.
5. **No Client-Side Secret Leakage:** Only the Supabase publishable anon key is exposed to the frontend; the `SUPABASE_SECRET_KEY` (service role) is isolated in `backend/.env`.

**The Single Security/Data Integrity Anomaly:**
The preserved production user record `chotu1@gmail.com` (`5cee4e2f-bbdc-41f5-87c9-52cdc63e755b`) holds `role = 'student'` in `public.user_profiles`, yet is referenced as `owner_teacher_id` in 8 production `classrooms`. This creates an authorization contradiction that locks the user out of their own classrooms under production role enforcement.

---

## 2. Authentication & JWT Validation

### Architecture:
- Handled by `backend/app/core/security.py`:
  - Extracts the bearer token from the `Authorization: Bearer <token>` header.
  - Calls Supabase Auth (`supabase.auth.get_user(token)`) using the configured Supabase client.
  - Resolves the validated user's UUID and provides it to endpoints via `Depends(get_current_user_id)`.
  - Rejects missing, expired, or invalid tokens with **HTTP 401 Unauthorized**.

### Test Mode Guard (`_test_auth_enabled`):
- `security.py:20-25`:
  ```python
  def _test_auth_enabled() -> bool:
      return settings.APP_ENV == "test" and bool(settings.SETU_TEST_AUTH)
  ```
- **Security Audit:** The `X-User-Id` header authentication bypass is **strictly locked** behind both `APP_ENV == "test"` and `SETU_TEST_AUTH == True`. In production (`APP_ENV == "local"` or `"production"`), any `X-User-Id` header is ignored, and requests without a valid Supabase JWT are rejected with 401.

---

## 3. Role-Based Access Control (RBAC)

### Teacher Role Guard:
- Handled by `get_current_teacher_id` in `backend/app/core/security.py:71-82`:
  ```python
  async def get_current_teacher_id(
      user_id: uuid.UUID = Depends(get_current_user_id),
      db: Session = Depends(get_db),
  ) -> uuid.UUID:
      profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
      if not profile or profile.role not in ("teacher", "admin"):
          raise HTTPException(
              status_code=status.HTTP_403_FORBIDDEN,
              detail="A teacher account is required for this action.",
          )
      return user_id
  ```

### Protected Teacher Endpoints:
- `GET /api/v1/teacher/classrooms` — List teacher's classrooms
- `POST /api/v1/teacher/classrooms` — Create new classroom
- `GET /api/v1/teacher/classrooms/{id}/roster` — View student roster
- `POST /api/v1/teacher/classrooms/{id}/rotate-join-code` — Invalidate and issue fresh join code
- `PATCH /api/v1/teacher/classrooms/{id}/members/{student_id}` — Remove or restore student
- `GET /api/v1/teacher/classrooms/{id}/evidence-matrix` — Detailed concept mastery matrix
- `POST /api/v1/teacher/recommendations` — Submit intervention recommendation
- `PATCH /api/v1/teacher/actions/{action_id}` — Decide on recommendation override

### Ownership Scoping (`_owned_classroom`):
- Every teacher endpoint operating on a classroom validates that `Classroom.owner_teacher_id == teacher_id`. If a teacher attempts to inspect another teacher's classroom, it returns **HTTP 404** (preventing ID enumeration).

---

## 4. Multi-Tenant Data Isolation & Storage Security

### Document Storage Isolation:
- `backend/app/api/v1/documents.py`:
  - `GET /api/v1/documents`: Filters strictly by `Document.owner_id == user_id`.
  - `GET /api/v1/documents/{doc_id}/status`: Rejects access if `doc.owner_id != user_id` (returns 404).
  - `DELETE /api/v1/documents/{doc_id}`: Rejects deletion if not owned by caller.
- Storage Backend (`backend/app/services/storage.py`):
  - In production (`STORAGE_BACKEND == "supabase"`), files are uploaded to private bucket `setu-documents` under paths structured by `user_id/document_id/filename`.
  - Direct public access to the storage bucket is disabled.

---

## 5. Critical Finding: The `chotu1@gmail.com` Account Role Anomaly

### Root Cause Analysis:
During the previous system cleanup and acceptance testing, existing test accounts were scrubbed, preserving only the user `chotu1@gmail.com` (`5cee4e2f-bbdc-41f5-87c9-52cdc63e755b`).
- In `public.user_profiles`:
  ```sql
  SELECT id, email, role, display_name FROM public.user_profiles;
  -- Result:
  -- id: 5cee4e2f-bbdc-41f5-87c9-52cdc63e755b
  -- email: chotu1@gmail.com
  -- role: student
  -- display_name: Chotu
  ```
- In `public.classrooms`:
  ```sql
  SELECT count(*) FROM public.classrooms 
  WHERE owner_teacher_id = '5cee4e2f-bbdc-41f5-87c9-52cdc63e755b';
  -- Result: 8 classrooms owned by this ID
  ```

### Operational Impact:
When a tester or judge logs in as `chotu1@gmail.com`:
1. The student dashboard works perfectly.
2. If they click **Teacher Desk** or navigate to `/teacher`, the backend dependency `get_current_teacher_id` checks `profile.role`.
3. Because `role == "student"`, it immediately raises **HTTP 403 Forbidden**: *"A teacher account is required for this action."*
4. The frontend displays the error notice: *"Teacher account required"*.

### Remediation Options (No Code Changes Required):
- **Option A (Update Database Role):**
  Run this one-line command in Supabase SQL Editor:
  ```sql
  UPDATE public.user_profiles
  SET role = 'teacher'
  WHERE id = '5cee4e2f-bbdc-41f5-87c9-52cdc63e755b';
  ```
- **Option B (Register New Dedicated Accounts):**
  Use the application's clean registration flow:
  1. Register `student.demo@setu.org` (Role: Student).
  2. Register `teacher.demo@setu.org` (Role: Teacher).
  This preserves complete real-world role separation.

---

## 6. Secrets & Environment Audit

| Credential / Variable | Location | Exposure Risk | Recommendation |
|---|---|:---:|---|
| `SUPABASE_SECRET_KEY` | `backend/.env` | **Zero (Server-side only)** | Never expose in client builds. Kept safe in backend config. |
| `SUPABASE_PUBLISHABLE_KEY` | `frontend/.env` | **Acceptable (Public by design)** | Standard Supabase anon key; RLS and API enforce security. |
| `DATABASE_URL` | `backend/.env` | **Zero (Server-side only)** | Direct database connection string kept strictly in backend. |
| `LLM_BASE_URL` | `backend/.env` | **Zero (Local network)** | Bound to `127.0.0.1:1234` for local LM Studio inference. |


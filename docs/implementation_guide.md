# Event Registration System — Implementation Guide

A phase-based build plan for a Django + PostgreSQL (Supabase) + Bootstrap 5 event
registration system, deployed on Render. Each phase produces a stable, committable
layer. Follow them in order — later phases assume earlier ones are working and tested.

---

## 1. Architecture Overview

### 1.1 Project layout

```
event_reg/                     # repo root
├── manage.py
├── requirements.txt
├── .env.example
├── README.md
├── config/                    # Django project package (settings, urls, wsgi/asgi)
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── accounts/                  # custom user, auth, roles, password reset
├── events/                    # Event, Session, StaffAssignment, permission helpers
├── registrations/             # Registration, RegistrationEvent, DismissedAlert,
│                               # transition logic, CSV import/export, expiry command
├── dashboard/                 # aggregated read-only views, charts, alerts list
├── templates/                 # shared base.html, partials, per-app template dirs
├── static/                    # local static overrides (Bootstrap/Chart.js via CDN)
└── tests/ (or per-app tests.py / tests/ packages)
```

**Why this split:** `events` owns "what exists" (events, sessions, who is assigned).
`registrations` owns "what happens" (attendee lifecycle, audit trail). `dashboard`
is purely read-only aggregation over the other two — it never mutates data. This
keeps permission logic close to the models it protects and keeps the dashboard
app simple and safe to change without touching business rules.

### 1.2 Core cross-cutting patterns (design before you code)

These four patterns are used in almost every phase. Decide their shape now so
later phases just call them.

**A. Role + assignment check helpers (`events/permissions.py`)**
```python
def user_is_organizer(user) -> bool: ...
def user_can_manage_session(user, session) -> bool:
    # True if organizer, or if a StaffAssignment(user, session) row exists
def require_session_access(user, session):
    # raises PermissionDenied (-> Django's 403) if user_can_manage_session is False
```
Every view that touches a session or its registrations calls
`require_session_access` at the top, **before** any mutation. This is the single
choke point that satisfies "enforce on the server in every view."

**B. The `transition()` helper (`registrations/services.py`)**
```python
ALLOWED_TRANSITIONS = {
    "reserved":   {"confirmed", "cancelled", "expired"},
    "confirmed":  {"checked_in", "cancelled", "expired"},
    "checked_in": set(),      # terminal — nothing leaves checked_in
    "expired":    set(),      # terminal
    "cancelled":  set(),      # terminal
}

def transition(registration, new_status, changed_by, note=None):
    """
    Single entry point for every status change in the app.
    - Validates new_status against ALLOWED_TRANSITIONS[old_status]
    - Raises TransitionError (a ValidationError subclass) if illegal
    - Saves the Registration
    - Writes exactly one RegistrationEvent row (append-only)
    All of it happens inside one atomic block.
    """
```
No code path is ever allowed to call `registration.status = X; registration.save()`
directly outside this function. Reviewing this file alone tells you every legal
lifecycle move in the system.

**C. Capacity-safe reservation (`registrations/services.py`)**
```python
def reserve_seat(session, attendee_name, attendee_email, created_by):
    with transaction.atomic():
        locked_session = Session.objects.select_for_update().get(pk=session.pk)
        expire_stale_reservations(locked_session)          # lazy expiry, see Phase 6
        seats_taken = compute_seats_taken(locked_session)   # reserved+confirmed+checked_in
        if seats_taken >= locked_session.capacity:
            raise CapacityFullError(...)
        registration = Registration.objects.create(session=locked_session, ...)
        transition(registration, "reserved", changed_by=created_by)  # writes audit row
        return registration
```
`select_for_update()` locks the session row for the duration of the transaction,
so two concurrent requests serialize on that lock and the second one re-reads
`seats_taken` after the first commits — no double-booking race.

**D. Alert state (`dashboard`/`events` — computed, not stored)**
```python
def session_is_at_capacity(session) -> bool:
    return compute_seats_taken(session) >= session.capacity

def session_alert_is_active(session) -> bool:
    return session_is_at_capacity(session) and not DismissedAlert.objects.filter(session=session).exists()
```
`DismissedAlert` rows are deleted the instant a session drops below capacity
(inside `transition()` and inside `expire_reservations`, anywhere seats_taken can
decrease), so "dismissed" never survives a refill — it just naturally recomputes.

### 1.3 Request flow summary

Browser → Django template (server-rendered, Bootstrap 5 via CDN) → view function
(role/assignment check → service function → model) → template response. No REST
API, no SPA. The "little vanilla JS" is limited to: CSV file input UX, chart
rendering via Chart.js CDN reading a JSON `<script>` block the view renders, and
maybe a debounce on the search box. Nothing else needs JS.

### 1.4 Environment / hosting shape

- Postgres connection string comes from Supabase, read via `dj_database_url` from
  an env var `DATABASE_URL`. Never hardcode credentials.
- `settings.py` reads all secrets/env-dependent values (`SECRET_KEY`, `DEBUG`,
  `ALLOWED_HOSTS`, `DATABASE_URL`, `RESERVATION_HOLD_MINUTES`, email backend
  settings) via `django-environ` or plain `os.environ`, with a documented
  `.env.example`.
- Static files served via WhiteNoise on Render (no separate CDN needed for your
  own static assets; Bootstrap/Chart.js remain external CDN links in templates).
- One `Procfile`/Render start command running `gunicorn config.wsgi`, plus a
  release/build step running `migrate` (and optionally `seed_demo_data` for a
  fresh demo deploy).

---

## 2. Phase Plan

Each phase below lists: goal, what you build, key implementation notes, and a
"definition of done" you can literally use as a commit message / PR checklist.

### Phase 0 — Project scaffolding
**Goal:** an empty but runnable Django project talking to Supabase Postgres.

- `django-admin startproject config .`
- Create apps: `accounts`, `events`, `registrations`, `dashboard`
  (`python manage.py startapp <name>`), register all in `INSTALLED_APPS`.
- `requirements.txt`: `Django`, `psycopg[binary]` (or `psycopg2-binary`),
  `dj-database-url`, `django-environ`, `whitenoise`, `gunicorn`.
- `settings.py`: `DATABASES` from `DATABASE_URL` env var, `AUTH_USER_MODEL`
  placeholder (set in Phase 1 before first migration), `TEMPLATES` DIRS pointing
  at `templates/`, WhiteNoise middleware, `RESERVATION_HOLD_MINUTES = 30` as a
  named setting (never hardcode 30 anywhere else in the code).
- `.env.example` documenting every required env var.
- Base template `templates/base.html` with Bootstrap 5 CDN `<link>`/`<script>`
  tags and a nav placeholder.

**Definition of done:** `python manage.py runserver` boots, `python manage.py
migrate` succeeds against Supabase, homepage renders base template with no
errors.
**Commit:** `chore: project scaffolding, settings, Supabase Postgres wiring`

---

### Phase 1 — Accounts app (auth foundation)
**Goal:** email+password login, two roles, forgot-password flow, before any
other model exists (everything else FKs to `User`).

- Custom `User(AbstractBaseUser, PermissionsMixin)` in `accounts/models.py`:
  `email` (unique, `USERNAME_FIELD`), `full_name`, `role` (`CharField` choices
  `organizer`/`staff`), standard `is_active`/`is_staff`/`is_superuser`,
  `is_admin`-style flags as needed for Django admin login.
- Custom `UserManager` with `create_user`/`create_superuser` keyed on email.
- Set `AUTH_USER_MODEL = "accounts.User"` **before the first migration ever
  runs** — this cannot be changed later without a painful reset.
- Django's built-in auth views for login/logout
  (`django.contrib.auth.views.LoginView`, etc.), pointed at custom templates.
- Forgot password: reuse Django's built-in `PasswordResetView` /
  `PasswordResetConfirmView` chain (no need to hand-roll). Configure an email
  backend — console backend for local/dev is enough to prove it works; document
  the real SMTP env vars needed for production.
- Register `User` in `accounts/admin.py` with a **read-only** note for later
  phases (Phase 9 will forbid registration-event tampering, not this).
- `accounts/permissions.py` re-exports the helpers described in §1.2A, or you
  can house them here instead of `events/` — pick one place and stick to it. This
  guide assumes `events/permissions.py` since sessions live there, but the
  functions themselves reference `User.role`, so `accounts` is equally valid.

**Definition of done:** can create an organizer and a staff user via
`createsuperuser`/shell, log in/out through templates, trigger a password reset
email that prints to console in dev.
**Commit:** `feat(accounts): custom user model, email auth, roles, password reset`

---

### Phase 2 — Events app: Event model + CRUD + archive
**Goal:** organizers can create/edit/archive/restore events; everyone can browse
non-archived events by default.

- `Event` model: `name`, `description`, `start_date`, `end_date`, `venue`,
  `is_archived` (bool, default `False`), timestamps.
- Views (function-based, explicit names): `event_list`, `event_detail`,
  `event_create`, `event_update`, `event_archive`, `event_restore`.
- `event_list` default queryset excludes `is_archived=True`; add a
  `?show_archived=1` query param for organizers to see archived events too
  (still server-side filtered, not hidden by CSS).
- Every mutating view (`create`/`update`/`archive`/`restore`) starts with
  `if not user_is_organizer(request.user): raise PermissionDenied` — staff never
  reach the form even if they guess the URL.
- Archiving is a flag flip, never a delete — write the view as
  `event.is_archived = True; event.save()`, not a queryset `.delete()`.

**Definition of done:** organizer can create/edit/archive/restore an event
through templates; staff user hitting any mutating event URL directly gets 403;
archived event disappears from default list but its (still-empty) detail page
still loads.
**Commit:** `feat(events): Event model, CRUD, archive/restore, organizer-only guards`

---

### Phase 3 — Sessions
**Goal:** sessions nested under events, organizer-only management, capacity field
established (enforcement comes in Phase 5).

- `Session` model: FK `event`, `title`, `start_time`, `duration_minutes`,
  `location`, `capacity` (positive integer).
- Event detail page (`event_detail`) lists its sessions.
- Views: `session_create`, `session_update`, `session_delete`, all nested under
  an event (`/events/<event_id>/sessions/...`), organizer-only via the same
  `user_is_organizer` guard as Phase 2 (session capacity/creation/edit is
  explicitly organizer-only per the spec — staff never get these views).
- `session_delete`: decide and document behavior when registrations exist
  (recommend: block delete with an error message if any registrations reference
  the session, rather than cascading — call this out in your "known
  limitations" section if you choose to allow cascade instead).

**Definition of done:** organizer can add/edit/delete sessions from an event's
page; staff gets 403 on all three; event detail page correctly lists sessions.
**Commit:** `feat(events): Session model, nested CRUD, organizer-only guards`

---

### Phase 4 — StaffAssignment + the permission choke point
**Goal:** the assignment table and the reusable access-check function every
later view will call. This is the phase that makes Phase 1's spec item
("staff gets 403 on unassigned sessions") testable end-to-end.

- `StaffAssignment` model: FK `staff` (`User`, role constrained to staff at the
  form/view level, not necessarily at the DB level), FK `session`,
  `unique_together = ("staff", "session")`.
- `events/permissions.py`: implement `user_can_manage_session`,
  `require_session_access` exactly as sketched in §1.2A.
- Views: `assignment_create`, `assignment_delete` — organizer-only (staff cannot
  assign themselves or others).
- `staff_session_list` view: "every session I'm assigned to" page, one per
  logged-in staff user (`StaffAssignment.objects.filter(staff=request.user)`,
  `select_related("session__event")`).
- **Write the staff-403 test now**, even though registrations don't exist yet:
  a staff user hitting a session-scoped URL they're not assigned to (start with
  `session_update` from Phase 3, or a placeholder registration URL you'll fill
  in Phase 5) must get 403. This test is cheap insurance that later phases don't
  regress the choke point.

**Definition of done:** organizer can assign/unassign staff to sessions; staff
member's "my sessions" page lists only their assignments; automated test proves
403 on an unassigned session.
**Commit:** `feat(events): StaffAssignment, permission choke point, staff-403 test`

---

### Phase 5 — Registrations: model, transition(), capacity-safe reservation
**Goal:** the heart of the app — lifecycle-correct, concurrency-safe
registrations with an immutable audit trail.

- `Registration` model: FK `session`, `attendee_name`, `attendee_email`,
  `status` (choices: `reserved`, `confirmed`, `checked_in`, `expired`,
  `cancelled`), `reserved_at` (auto on creation), FK `created_by` (nullable, for
  CSV imports / system actions).
- `RegistrationEvent` model: FK `registration`, `old_status` (nullable, null on
  the creation event), `new_status`, FK `changed_by` (nullable), `note`
  (nullable text), `created_at` (auto). **No `update`/`delete` methods, no admin
  change/delete permission — see Phase 9 for the hard enforcement.**
- `registrations/services.py`: implement `ALLOWED_TRANSITIONS`, `transition()`,
  `compute_seats_taken(session)`, `reserve_seat(...)` exactly as sketched in
  §1.2B/C. This is the only file that ever touches `Registration.status`.
- Views: `registration_create` (reserve), `registration_confirm`,
  `registration_check_in`, `registration_cancel` — every one starts with
  `require_session_access(request.user, session)`, then calls `transition()` or
  `reserve_seat()`. Views never manipulate status directly.
- `TransitionError`/`CapacityFullError` → caught in the view, re-shown as a
  clear form error message (per spec: "rejected server side with a clear error
  message").
- **Write the two core tests now:**
  1. Reserve up to capacity, assert the next reservation raises
     `CapacityFullError` / returns a clear error, not a 6th row.
  2. Attempt an illegal transition (e.g. `checked_in` → `reserved`) and assert
     `transition()` raises and no `RegistrationEvent`/status change occurred.
  3. (Optional but recommended) a `TransactionTestCase` simulating two
     near-simultaneous `reserve_seat()` calls against a session with 1 remaining
     seat, asserting only one succeeds — this is what actually exercises
     `select_for_update`.

**Definition of done:** full reserve → confirm → check-in flow works through
templates for an organizer and for correctly-assigned staff; capacity refusal
and illegal-transition tests pass; every status change produces exactly one
`RegistrationEvent` row.
**Commit:** `feat(registrations): Registration/RegistrationEvent models, transition() engine, concurrency-safe reserve_seat()`

---

### Phase 6 — Expiry: management command + lazy check
**Goal:** stale reservations free their seat, both via a runnable command and
automatically whenever seats are counted.

- `RESERVATION_HOLD_MINUTES = 30` already lives in `settings.py` (Phase 0) —
  every reference to "30 minutes" in code reads this setting, never a literal.
- `registrations/services.py`: `expire_stale_reservations(session)` — finds
  `reserved` registrations for that session older than the hold window and runs
  each through `transition(reg, "expired", changed_by=None, note="auto-expired")`.
  This is what `reserve_seat()` already calls before counting seats (Phase 5),
  so demo data self-corrects the moment anyone views a session.
- `registrations/management/commands/expire_reservations.py`: a `BaseCommand`
  that runs `expire_stale_reservations` across **all** sessions (not scoped to
  one), so it can be cron'd (`python manage.py expire_reservations`). Print a
  short summary (`N registrations expired across M sessions`) for operator
  visibility.
- Because expiry can drop a session below capacity, this is also where the
  `DismissedAlert` cleanup from §1.2D belongs — call the same "delete dismissed
  alert if now under capacity" helper from both `transition()` (for
  cancel/expire paths) and this command.

**Definition of done:** a reservation older than the hold window, when its
session is next viewed or the command is run, flips to `expired` with a
`RegistrationEvent` row; running the command twice in a row is a no-op the
second time; a `DismissedAlert` disappears the moment expiry drops the session
below capacity.
**Commit:** `feat(registrations): reservation expiry — lazy check + expire_reservations command`

---

### Phase 7 — Registration search / list (DB-level filtering)
**Goal:** one page listing every registration the logged-in user can see, fully
filtered/searched/paginated in the database.

- `registration_list` view: base queryset scoped by role —
  organizer: `Registration.objects.all()`;
  staff: `Registration.objects.filter(session__staffassignment__staff=request.user)`.
- Apply search (`Q(attendee_name__icontains=q) | Q(attendee_email__icontains=q)`),
  filters (`event`, `status`, `session` — validate against the same
  role-scoped querysets so staff can't filter into sessions they can't see),
  ordering, and `django.core.paginator.Paginator` — **all before hitting the
  database once**, i.e. build the queryset incrementally and let Django/Postgres
  do the work; never call `list(queryset)` and filter in Python.
- Template shows total match count (`paginator.count`) and current filter state
  reflected back into the form (so reloading/paginating doesn't lose filters).
- `select_related("session", "session__event")` to avoid N+1s when rendering
  event/session names per row.

**Definition of done:** search, each filter, and pagination each independently
narrow results correctly; staff never sees a registration outside their
assigned sessions even via crafted query params; total count shown matches the
actual filtered row count.
**Commit:** `feat(registrations): unified DB-filtered/searched/paginated registration list`

---

### Phase 8 — CSV bulk import/export
**Goal:** import an attendee list into a session with a per-row report; export
a session roster.

- Import view: organizer or assigned staff only (`require_session_access`),
  accepts a CSV upload, parses with `csv.DictReader`, and **for each row**
  independently attempts `reserve_seat(...)` inside its own error handling so
  one bad row doesn't roll back good ones — do **not** wrap the whole file in
  one `transaction.atomic()` block (that would roll back valid rows on the
  first failure); each row gets its own atomic reservation attempt via
  `reserve_seat()` (which is already atomic internally).
- Per-row outcome classification:
  - `created` — new reservation made.
  - `duplicate` — an active (non-cancelled/non-expired) registration with that
    email already exists for this session; skip, don't create a second one.
  - `rejected` — validation failure (bad email format, missing name,
    session at capacity) with a human-readable reason string.
- Render a per-row report table after import (row number, email, outcome,
  reason if rejected) — no need to persist this report, it's a one-time
  response view.
- Export view: `session_roster_csv` — streams a CSV (`HttpResponse` with
  `Content-Type: text/csv` and `Content-Disposition: attachment`) of every
  registration for the session with its status, using the same DB-level query
  approach (no loading-then-filtering).

**Definition of done:** a CSV with a mix of valid/duplicate/malformed rows
produces the correct three-way report and only valid+non-duplicate rows create
reservations (respecting capacity); export downloads a correct, complete CSV.
**Commit:** `feat(registrations): CSV bulk import with per-row report, roster CSV export`

---

### Phase 9 — Immutable history + hard admin lockdown
**Goal:** make `RegistrationEvent` provably tamper-proof, including through
Django admin.

- Confirm (from Phase 5) `RegistrationEvent` has no path to mutation anywhere
  in `registrations/services.py`, `views.py`, or forms.
- `registrations/admin.py`: register `RegistrationEvent` with a
  `ModelAdmin` that overrides `has_change_permission` → always `False`,
  `has_delete_permission` → always `False`. Leave `has_add_permission` also
  `False` unless you specifically want superusers creating rows outside
  `transition()` (recommend `False` — force even admin-created corrections
  through the same code path, or document as a limitation if you need manual
  admin fixes).
- `registration_timeline` view/template: for a given registration, list all its
  `RegistrationEvent` rows ordered by `created_at`, showing old→new status, who
  changed it (or "system" if `changed_by` is null), timestamp, note.
- Add a test that attempts to `PATCH`/POST an edit to a `RegistrationEvent` via
  admin (as a superuser) and asserts it's rejected, plus a direct
  model-layer test asserting there is no update/delete call anywhere reachable
  from a view.

**Definition of done:** timeline page renders full history for a registration
correctly; admin change/delete links for `RegistrationEvent` are absent/blocked
even for superusers; test proves it.
**Commit:** `feat(registrations): immutable timeline view, admin lockdown on RegistrationEvent`

---

### Phase 10 — At-capacity alerts
**Goal:** live alert list + nav badge that self-heals on refill, per §1.2D.

- `DismissedAlert` model: FK `session`, FK `dismissed_by`, `dismissed_at`.
- Confirm the "delete on drop-below-capacity" cleanup from Phase 6 is wired
  into every path that can reduce `seats_taken`: `transition()` for
  cancel/expire/(any status leaving reserved/confirmed pool), and the expiry
  command.
- `alerts_list` view: role-scoped sessions (organizer: all; staff: assigned)
  where `session_alert_is_active(session)` is `True`.
- `alert_dismiss` view: organizer-only (per spec — "Organizers can dismiss");
  creates a `DismissedAlert` row.
- Nav badge: a small context processor or template tag computing the active
  alert count for the logged-in user, rendered in `base.html`'s nav — kept as a
  single small query, not N+1 across sessions (annotate/aggregate rather than
  looping `session_is_at_capacity` in Python where avoidable, or accept the
  loop if session counts are small and document it).

**Definition of done:** a session hitting capacity appears in the alert list and
nav badge; dismissing removes it; a cancellation/expiry dropping it below
capacity clears the dismissal automatically; refilling to capacity again makes
the alert reappear without any manual action.
**Commit:** `feat(dashboard): at-capacity alerts, dismiss, self-healing on refill`

---

### Phase 11 — Dashboard
**Goal:** role-appropriate landing page with the required stats and a 14-day
check-in chart.

- `dashboard_home` view, role-scoped session queryset (organizer: all; staff:
  assigned), computing via DB aggregation (`aggregate`/`annotate`, not Python
  loops over all rows):
  - sessions happening today (`start_time__date=today`)
  - attendees checked in today (`RegistrationEvent` rows with
    `new_status="checked_in"`, `created_at__date=today`)
  - registrations expired this week (`RegistrationEvent`,
    `new_status="expired"`, `created_at__gte=start_of_week`)
  - sessions currently at capacity (reuse `session_is_at_capacity`/the alert
    logic from Phase 10)
  - breakdown of registrations by status (`Registration.objects.values("status").annotate(count=Count("id"))`)
  - breakdown by session (same pattern, grouped by `session`)
- 14-day check-in line chart data: group `RegistrationEvent` rows where
  `new_status="checked_in"` by `created_at__date` over the last 14 days
  (`TruncDate` + `annotate(Count)`), fill any zero-count days so the chart
  doesn't have gaps, serialize to JSON in the view/template, render with
  Chart.js via CDN reading that JSON from a `<script type="application/json">`
  block (this is the "essential vanilla JS" — just the tiny snippet that
  instantiates the Chart.js chart from that JSON).

**Definition of done:** every listed stat matches what a manual query against
seed data returns; staff dashboard only reflects their assigned sessions;
chart renders 14 points (including zero-days) with correct counts.
**Commit:** `feat(dashboard): role-scoped stats, status/session breakdowns, 14-day check-in chart`

---

### Phase 12 — Seed data + final polish pass
**Goal:** `seed_demo_data` management command populating a realistic, non-empty
demo, plus a pass over UX/error-message polish.

- `events/management/commands/seed_demo_data.py` (or under whichever app you
  prefer): idempotent-ish command (safe to note it's meant for a fresh DB, or
  guard with a `--flush` flag) creating:
  - a couple of organizer users, a handful of staff users
  - 3–5 events, spanning past/current/future dates, at least one archived
  - multiple sessions per event with varied capacities (some tiny — e.g.
    capacity 2 — so it's easy to demo "at capacity" and CSV rejection; some
    large)
  - staff assignments covering: a staff member assigned to sessions across
    different events, a session with multiple staff, and at least one session
    with no staff (to demo the "unassigned" 403 path if desired)
  - registrations across every status (reserved, confirmed, checked_in,
    expired, cancelled) — including some `reserved` rows deliberately
    backdated past the hold window so the lazy-expiry behavior is visible
    immediately on first page load
  - corresponding `RegistrationEvent` rows for every status a registration has
    passed through (don't hand-insert these — call `transition()`/
    `reserve_seat()` from the seed script itself so the audit trail is
    generated the same way production data would be, which also
    double-checks your own transition table is internally consistent)
  - a couple of `DismissedAlert` rows on sessions that are *not* currently at
    capacity, to prove they don't wrongly suppress anything
- Final polish pass: consistent flash/error messaging (Django `messages`
  framework) for every rejected action (403s, capacity-full, illegal
  transition, CSV rejections), consistent Bootstrap 5 styling across templates,
  empty-state messaging where lists can be empty.

**Definition of done:** `migrate` + `seed_demo_data` on a clean DB produces a
fully populated, internally consistent demo — dashboard, alerts, and
registration list all show non-trivial, correct numbers immediately.
**Commit:** `feat: seed_demo_data command, final UX polish pass`

---

### Phase 13 — Tests consolidation + Render/Supabase deployment
**Goal:** confirm the required test set is complete and the app deploys clean.

- Consolidate/confirm the non-negotiable tests exist and pass:
  1. Staff gets 403 acting on a session they're not assigned to (Phase 4).
  2. Reservation is refused once a session is at capacity (Phase 5).
  3. An illegal status transition is rejected (Phase 5).
  4. (Recommended addition) concurrency test on `reserve_seat` (Phase 5).
  5. (Recommended addition) `RegistrationEvent` immutability via admin (Phase 9).
  6. (Recommended addition) CSV import partial-success (valid rows survive
     invalid ones) (Phase 8).
- `README.md`: setup from clean clone (venv, `pip install -r requirements.txt`,
  `.env` from `.env.example`, `migrate`, `seed_demo_data`, `runserver`) — this
  is your "zero setup friction" contract, so actually run through it once on a
  clean checkout before calling it done.
- Render: web service pointed at this repo, build command `pip install -r
  requirements.txt && python manage.py collectstatic --noinput`, start command
  `gunicorn config.wsgi`, release/pre-deploy command running `python manage.py
  migrate`. Env vars: `DATABASE_URL` (Supabase connection string, using the
  Supabase **pooler** connection string for serverless-friendly connection
  counts), `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS` set to the Render
  domain, `RESERVATION_HOLD_MINUTES`, email backend vars.
- Supabase: create the Postgres project, copy the pooled connection string,
  confirm SSL is required (`?sslmode=require` in the URL, or the
  `OPTIONS={"sslmode": "require"}` DB setting).

**Definition of done:** `python manage.py test` green; a genuinely clean clone
+ documented steps produces a working local app; Render deploy against
Supabase succeeds and the seeded demo is reachable at the public URL.
**Commit:** `test: consolidate required test suite; docs: deployment + README`

---

## 3. Data Model / Schema

```
User (accounts)
├─ id
├─ email               (unique, USERNAME_FIELD)
├─ full_name
├─ role                choices: organizer | staff
├─ password             (hashed, via AbstractBaseUser)
├─ is_active, is_staff, is_superuser
└─ date_joined

Event (events)
├─ id
├─ name
├─ description
├─ start_date
├─ end_date
├─ venue
├─ is_archived          default False
├─ created_at / updated_at

Session (events)
├─ id
├─ event                FK -> Event
├─ title
├─ start_time            datetime
├─ duration_minutes      int
├─ location
├─ capacity              positive int

StaffAssignment (events)
├─ id
├─ staff                 FK -> User
├─ session               FK -> Session
├─ unique_together(staff, session)
├─ created_at

Registration (registrations)
├─ id
├─ session                FK -> Session
├─ attendee_name
├─ attendee_email
├─ status                 choices: reserved | confirmed | checked_in | expired | cancelled
├─ reserved_at             datetime (set on creation)
├─ created_by              FK -> User, nullable (CSV import / system)
├─ updated_at

RegistrationEvent (registrations)   — append-only, no update/delete path
├─ id
├─ registration            FK -> Registration
├─ old_status               nullable (null on the creation event)
├─ new_status
├─ changed_by                FK -> User, nullable (null = system/automated)
├─ note                       nullable text
├─ created_at

DismissedAlert (registrations or dashboard — pick one app, be consistent)
├─ id
├─ session                 FK -> Session
├─ dismissed_by              FK -> User
├─ dismissed_at
```

**Relationships at a glance:**
`Event 1—N Session`, `Session 1—N Registration`, `Session N—M User` (through
`StaffAssignment`), `Registration 1—N RegistrationEvent`, `Session 1—N
DismissedAlert` (in practice at most one *active* undismissed-until-refill row
at a time, but the table itself doesn't need to enforce that — the "at most one
row per currently-at-capacity session" invariant is maintained by application
logic: delete-on-drop-below-capacity + get-or-create-on-dismiss).

**Key constraints to actually declare in Django, not just enforce in views:**
- `StaffAssignment.unique_together = ("staff", "session")`
- `Session.capacity` — `PositiveIntegerField`, plus a `CheckConstraint(capacity__gt=0)` if you want DB-level backup for the "capacity must be positive" rule.
- `Event.start_date <= Event.end_date` — enforce in `clean()`/form validation (DB `CheckConstraint` across two date fields is possible in Postgres but adds complexity; form-level validation is sufficient here).
- Consider a DB `CheckConstraint` restricting `Registration.status` to the five valid choices as defense-in-depth beyond Django's `choices=`.

---

## 4. Assumptions & Known Limitations (flag these explicitly to yourself)

- **Session delete with existing registrations:** the guide recommends blocking
  delete rather than cascading, to avoid silently destroying registration
  history. Decide and document whichever you implement.
- **`RegistrationEvent` admin add permission:** set to `False` above, meaning
  even superusers can't hand-create a correction row outside `transition()`. If
  you need manual data-fix capability later, that's a deliberate trade-off
  against "genuinely impossible to edit" — don't loosen `has_change_permission`
  to work around it.
- **Staff role on `StaffAssignment.staff`:** the guide doesn't add a DB-level
  constraint forcing `staff.role == "staff"` (an organizer *could* technically
  be assigned). Enforce this at the form/view layer when creating assignments,
  and note it as a soft constraint.
- **Email delivery in production:** the plan uses Django's console backend for
  local dev; you must configure real SMTP credentials (env vars) before forgot-
  password actually emails anyone in production.
- **Nav badge query cost:** if session counts grow large, the "active alerts"
  computation looping `session_is_at_capacity` per session should be revisited
  as a single annotated query; fine for demo-scale data as specified.
- **CSV import row-level atomicity:** each row's reservation is atomic via
  `reserve_seat()`, but the import as a whole is intentionally *not* one
  transaction, per the spec requirement that valid rows survive invalid ones
  in the same file — this means a mid-import crash could leave a partially
  processed file with no automatic resume; re-running the same file is safe
  because already-registered emails will show as `duplicate`.
- **Timezone handling:** "today"/"this week" calculations in the dashboard use
  Django's configured `TIME_ZONE`/`USE_TZ` — pick one timezone deliberately in
  settings; the guide doesn't design multi-timezone event support.

# AI prompts

The prompts you actually used, in the order you used them, grouped by what you were trying to achieve. For each significant one: what you asked, what you got back, and what you had to correct.

Include at least one prompt that produced something wrong, and what you did about it.

If you did not use AI at all, say so here, and describe your process instead.

## <What you were trying to achieve>
To create a comprehensive and reliable implementation plan covering the application's architecture, database schema, implementation details, and technology stack.

### Prompt
1. I am building an event registration system in Django. This is a web application meant to be hosted on Render with Postgres Supabase as the Database hosting platform. It is meant to have zero setup friction and every feature mentioned below is to be implemented correctly. Prioritize correctness and runnability and in turn polish.

TECH CONSTRAINTS - follow exactly.

- Django (latest stable LTS), Python
    
- Database: PostgreSQL for Supabase hosting
    
- Frontend: plain Django templates + online templates via CDN like Boostrap 5
    
- Charts: I will use online available charting JS libraries with CDN.
    
- This is a no Javascript application. A little vanilla JS is fine only when it is essential and improves UX.
    
- Single Django Project, multiple small apps by domain: accounts, events, registrations, dashboard. Since there is no separate frontend service, no REST API layer is required, templates render server-side.
    
- I also want to have a requirements.txt, a working manage.py and a seed management command that populates realistic demo data (a few events, sessions with varied capacities, staff assignments and registrations across every status) so the app is not empty when I run it.
    

DATA MODEL - schema to be implemented:

- User (custom user model, email and password login with forgot password ability) with two roles: organizer or staff.
    
- Event: name, description, a start date, an end date, venue and all of this is editable. The events can also be archived, archiving hides an event from the default views without destroying its sessions or registrations.
    
- Session: Each session belongs to only one event. Title, start time, duration minutes, location, capacity.
    
- StaffAssignment: Joing table between User (staff) and session, unique per pair.
    
- Registration: belongs to exactly one session. attendee name, attendee email, status (reserved, confirmed, checked in / expired / cancelled), reserved at, created by (nullable FK to User, for CSV imports).
    
- RegistrationEvent: immutable audit row per status change, registration FK, old status (nullable), new status, changed by (nullable FK to User - null for system/automated changes), note (nullable text), created at. No update or delete code path should ever touch this model.
    
- DismissedAlert: session FK, dismissed by FK, dismissed at. A row here means "hide the at capacity alert for this session until it drops below capacity and refills"
    

REQUIRED FEATURES (ALL OF THESE ARE TO BE IMPLEMENTED, EACH FEATURE SHOULD WORK WHEN CLICKED)

1. Accounts and roles: Email+password login. Two roles: organizer, staff. Organizers can create/archive events, create sessions and set capacity and create/confirm/cancel/check-in registrations for any session. Staff can do the same only for sessions they are assigned to via StaffAssignment and cannot create events, create sessions or edit capacity. Enforce this on the server in every view - never rely on hiding a button in a template. Staff member gets a HTTP 403 when acting on a session they are not assigned to. A test proving this should be there.
    
2. Events: Organizers can create events (name, description, start date, end date, venue) and edit them later. Events can be archived and restored. Archiving hides the event from default views without deleting its sessions or registrations.
    
3. Sessions: Every session belongs to exactly one event: title start time, duration minutes, location, capacity. Organizers can create, edit and delete sessions. Opening an event's detail page lists its sessions.
    
4. Registration lifecycle with rules: Registration holds attendee name + email for one session. Lifecycle: Reserved -> Confirmed -> Checked in. Reserving requires room left in capacity where 'seats taken' = count of Reserved + Confirmed + Checked in registrations for that session - the server must refuse a reservation once that count reaches capacity, no exceptions, and this must be safe under concurrent requests (use select_for_update inside a transaction when checking capacity and creating a registration - do not just count-then-insert without locking). A reserved registration older than a configurable holding window (default 30 minutes, put it in settings) is automatically marked expired, freeing its seat - implement this as a management command (expire_reservations) I can run manually or on a schedule, And as a lazy check applied whenever seats-taken is computed, so demo data shows correct behaviour even without the scheduled job running. A registration can be Cancelled from reserved or confirmed (frees the seat) but never from Checked in. Any transition not explicitly allowed must be rejected server side with a clear error message - implement this as one small transition() helper function used everywhere a status changes, backed by an explicit table of legal transitions, not scattered if-statements.
    
5. Assignment: Any number of staff can be assigned to a session. a staff Member can be assigned to any number of sessions across any event. Only organizers can add/remove assignments. Each staff member has one page listing every session they're assigned to.
    
6. Finding registrations: One server-rendered list of registrations across every session the logged-in user can see (all sessions for organizers, only assigned sessions for staff). Must support: text search over attendee name and email. filters for event/status/session, pagination with the total match count shown. All filtering, search, sorting and pagination must happen in the database query - do not load everything and filter in Python or in the browser.
    
7. Bulk actions: CSV import of an attendee list into a session, producing a per row report: created (new reservation), duplicate (email already registered for that session), or rejected (invalid with a reason) - valid rows must still be created even when other rows in the same file are rejected. CSV export of a session's full roster (every registration + status) as a downloadable file.
    
8. Dashboard: A landing page (role-appropriate: organizer sees everything, staff sees their sessions) showing: sessions happening today, attendees checked in today, registrations expired this week, sessions currently at capacity, a breakdown of registrations by status, a breakdown by session, and a line chart of check-ins per day over the last 14 days, computed from RegistrationEvent rows.
    
9. Immutable history: Every registration has a timeline view showing creation and every status change (old status, new status, who changed it, when, any note). This must be genuinely impossible to edit or delete through the app, including the organizers - no view, form or admin permission should allow modifying a RegistrationEvent after creation.
    
10. At capacity alerts: A session that reaches full capacity shows up in an alerts list, with a count badge in the nav. Organizers can dismiss a session's alert. If the session later drops below capacity (cancellation or expiry) and the fills back up to capacity again, the alert must reappear automatically - model this as "alert is active iff seats_taken >= capacity AND no DismissedAlert row exists" and delete the DismissedAlert row the moment the session drops below capacity so it naturally reappears on refill.
    

QUALITY BAR - NON NEGOTIABLE

- The app must run with zero errors after setting it up from a clean slate.
    
- Every view that changes data must check both the user's role and for staff, their specific assignment - do not gate only at the URL/menu level.
    
- Prefer explicit, readable code over cleverness - I need this to be able to understand each part of the code, which will make it easy for me to debug, if any bugs arise. Use proper conventional naming of functions that make the code readable and understandable.
    
- Include at least a handful of tests: the staff-403 test from goal 1, a test proving reservation is refused once a session is at capacity, and a test proving an illegal status transition is rejected.
    
- After all this, provide me with any assumptions or anything you might flag as a known limitation of the application.
    

Using this information. Create a module/phase-based implementation guide that I will follow with code to build the application. Include a proper architecture of the application, the entire plan in theory and steps first, then implementation and at last the schema of the application.

All the modules are structurally formed such that each module helps me build a stable layer over the other and I can document it while committing it to GitHub.


### What you got
An implementation guide in Markdown format was generated and stored as `implementation_guide.md` in the `docs` directory.

### What you corrected
Made multiple code changes throughout the entire coding phase of the project, as mentioned below.

## <What you were trying to achieve>
Build the initial `accounts` app in Django, starting with the creation of different apps such as `accounts`, `dashboard`, `events`, and `registrations`. In the `accounts` app, models such as `UserManager` and `User` were created. The goal was to build a basic application skeleton along with an initial roles and authentication system.

### Prompt
2. Follow-up prompts based on the initial master prompt.

### What you got
I got working code for the initial authentication system.

### What you corrected
One issue I corrected was Django's default behavior of redirecting users to the `/profile/` URL after a successful login. Since the profile page had not been implemented yet, and I wanted users to be redirected to their dashboard after logging in, I changed the predefined URL settings to the appropriate paths.

In this case, `LOGIN_URL`, `LOGIN_REDIRECT_URL`, and `LOGOUT_REDIRECT_URL` were configured as follows:

- `LOGIN_URL` -> `accounts:login`
- `LOGIN_REDIRECT_URL` -> `dashboard:home`
- `LOGOUT_REDIRECT_URL` -> `accounts:login`

These follow the Django URL naming convention:

`<app_name>:<url_name>`

## <What you were trying to achieve>
To build a CSV bulk import feature that allows a CSV file to be uploaded to a session and used to bulk import registrations. Each row should be processed independently, so a failure or rejection in one row should not prevent the remaining rows from being processed.

Along with this, I wanted to build a CSV roster export feature that exports the current registrations of a session, including their statuses and other relevant details, into a CSV file.

### Prompt
3. Follow-up prompt to the master prompt to build the CSV bulk import feature under Phase 8 of `implementation_guide.md`.

### What you got
I got a working CSV bulk import and roster export feature. However, the bulk import feature was initially accessible to both staff and organizers for their respective assigned sessions, whereas the requirement was for the bulk import feature to be exclusive to organizers.

### What you corrected
I restricted the CSV bulk import feature to organizers only.

The CSV roster export feature remains available to both staff and organizers, but users can only export the roster of sessions they are assigned to.

## <What you were trying to achieve>
To conduct a comprehensive review of the entire project codebase before deployment, identifying any bugs, security vulnerabilities, performance issues, configuration problems, or other necessary fixes that should be addressed to ensure the application is stable, secure, and production-ready.

### Prompt
4. Context

This is a Django (5.2) event registration system, built incrementally over
many sessions with an AI pair-programmer, now feature-complete against its
original spec and about to be deployed to Render with a Supabase-hosted
PostgreSQL database. Before deploying, I want a thorough, skeptical code
review — not a rewrite, not a style pass. Assume the code works (it has
passing tests and has been manually exercised extensively), and focus on:
correctness bugs that tests might not catch, security gaps, performance
problems, deployment risks, and genuine improvements.

Please read through the actual codebase yourself rather than relying only on
what's in this prompt — this document is context to help you look in the
right places and know what "correct" is supposed to mean, not a substitute
for reading the code.

Tech stack

- Django 5.2 (LTS), Python 3.14
- PostgreSQL (Supabase-hosted in production; local Docker Postgres in dev)
- Server-rendered Django templates + Bootstrap 5 (CDN) — no REST API layer,
  no SPA framework
- Chart.js (CDN) for one dashboard chart; otherwise no JavaScript beyond a
  handful of small, essential inline scripts
- WhiteNoise for static files, gunicorn for the production server
- django-environ for settings, dj-database-url for parsing DATABASE_URL

Project structure

Four Django apps, each owning one domain:
- `accounts` — custom User model (email login, `role`: organizer/staff)
- `events` — Event, Session, StaffAssignment, and `permissions.py` (the
  central authorization module)
- `registrations` — Registration, RegistrationEvent, DismissedAlert, and
  `services.py` (all business logic: the state machine, capacity-safe
  reservation, expiry, CSV import/export, alert logic)
- `dashboard` — read-only aggregated views/stats, no models of its own

Every app with business logic follows the same pattern: a thin `views.py`
that does permission checks and calls into `services.py`, which holds the
actual logic and is unit-tested independently of any HTTP layer.

Original requirements (all claimed complete except where noted)

1. **Accounts/roles**: email+password login, organizer/staff roles, every
   mutating view enforces role/assignment server-side (not just hiding UI).
   **Forgot-password was deliberately NOT implemented** — no signup flow
   exists, so there's no self-serve account to recover; this was a scoping
   decision, not an oversight. Please don't flag this as missing unless you
   see a concrete reason it's actually needed.
2. **Events**: full CRUD, archive/restore (a flag, never a delete),
   organizer-only.
3. **Sessions**: full CRUD nested under events, organizer-only, capacity
   field.
4. **Registration lifecycle**: Reserved → Confirmed → Checked-in, with
   Cancelled reachable from Reserved/Confirmed only (never from Checked-in).
   All transitions go through one function (`transition()` in
   `registrations/services.py`) backed by an explicit
   `ALLOWED_TRANSITIONS` table. Capacity enforcement uses
   `select_for_update()` inside `transaction.atomic()` to prevent
   overbooking under concurrent requests — this was specifically validated
   against real PostgreSQL with a multi-threaded `TransactionTestCase`
   (SQLite silently no-ops `select_for_update`, so that test is meaningless
   there). Stale reservations (default 30 min, `settings.RESERVATION_HOLD_MINUTES`)
   expire via both a lazy check (on every capacity computation) and a
   standalone `expire_reservations` management command, sharing one
   function (`expire_stale_reservations`).
5. **Assignment**: `StaffAssignment` join table, unique per (staff, session)
   pair, organizer-only to create/remove.
6. **Finding registrations**: one list view, role-scoped (organizer sees
   all, staff sees only assigned-session registrations), with search
   (name/email), filters (event/status/session), and pagination — all
   claimed to be database-level, not Python-side filtering. There's a
   `assertNumQueries` test pinning this view to a fixed query count
   regardless of row count, specifically to catch N+1 regressions.
7. **Bulk actions**: CSV import (per-row created/duplicate/rejected report,
   valid rows survive invalid ones in the same file — deliberately NOT
   wrapped in one transaction) and CSV roster export. Import is
   organizer-only; export is available to organizer + assigned staff.
   Duplicate-email detection lives in `reserve_seat()` itself (shared by
   both the manual registration form and CSV import), scoped per-session,
   excluding cancelled/expired registrations.
8. **Dashboard**: role-scoped stats (sessions today, checked-in today,
   expired this week, sessions at capacity, status breakdown, session
   breakdown), plus a multi-line Chart.js chart (Reservations/
   Confirmations/Check-ins per day) with a selectable 7/14/30-day range.
9. **Immutable history**: `RegistrationEvent` is append-only. Django admin's
   `has_add/change/delete_permission` are hardcoded to `False` on
   `RegistrationEventAdmin`, regardless of user — including superusers.
   There's a dedicated timeline view per registration.
10. **At-capacity alerts**: `DismissedAlert` model. An alert is active iff
    `seats_taken >= capacity AND no DismissedAlert row exists`. The
    dismissal is deleted automatically the instant a session drops below
    capacity (hooked into `transition()` itself, so it fires for both
    manual cancellation and automated expiry) — meaning a session that
    refills back to capacity later shows the alert again with zero manual
    re-triggering. There's a nav badge (a context processor) showing a live
    count.

Known, deliberate design trade-offs — please don't flag these as bugs

- Session delete is blocked if it has any registrations (or check whether
  this was actually implemented — verify against `events/views.py`
  `session_delete`, since this was a documented open decision at one point
  and may not have been resolved consistently).
- `RegistrationEvent` cannot be created outside `transition()`/`reserve_seat()`
  — not even by an admin — by design. There is no manual "fix a bad audit
  row" escape hatch.
- `StaffAssignment.staff` has no DB-level constraint forcing `role=staff`
  — an organizer could theoretically be assigned. This is a soft
  constraint, enforced (if at all) only at the form/view layer — please
  check whether it's actually enforced anywhere and flag if not.
- The nav badge / dashboard "sessions at capacity" logic loops over
  sessions in Python calling a per-session function, rather than a single
  aggregated SQL query — a known, accepted trade-off for the expected
  scale of this app (please sanity check whether this is actually fine, or
  whether it's a bigger problem than assumed).
- No per-event timezone support — one global `settings.TIME_ZONE` for the
  whole app.
- Email delivery isn't configured (no SMTP set up yet) — expected, since
  forgot-password wasn't implemented; verify nothing else silently depends
  on outbound email actually working.

Specific things to scrutinize closely

This codebase went through a lot of iterative debugging. Several bug
*patterns* recurred multiple times during development — please specifically
grep/search for other instances of these same patterns elsewhere in the
codebase, since if it happened repeatedly by accident, it likely happened
somewhere it hasn't been caught yet:

1. **Template variable / context dict key mismatches.** At least twice, a
   view passed a dict key that didn't exactly match the name used in
   `{% for %}`/`{{ }}` in the corresponding template (e.g. singular vs.
   plural), which fails completely silently — no error, just empty output.
   Please check every `render()` call's context dict against the template
   it renders for exact-name matches.
2. **URL reversal args landing outside a `{% for %}` loop**, producing an
   empty-string argument and a `NoReverseMatch`. Please check every
   `{% url %}` call inside a table/list template is actually inside the
   loop that defines the variables it references.
3. **Settings read without proper type coercion** — `env(...)` instead of
   `env.int(...)`/`env.bool(...)`/etc., which silently returns a string
   where a real type is expected. Check every setting read via
   `django-environ` in `config/settings.py` against how it's actually
   *used* downstream.
4. **Business logic accidentally bypassing `transition()`** — anywhere a
   `Registration.status` might be set directly via `.save()` or a bulk
   `.update()` outside of `registrations/services.py`, which would create a
   status change with no corresponding `RegistrationEvent` audit row, or
   bypass the legal-transition check entirely.
5. **`select_for_update()` used outside an active transaction**, or,
   conversely, capacity/duplicate/expiry checks that read data *without*
   the lock, that should be inside the locked+atomic block in
   `reserve_seat()`.
6. **Permission checks (`require_organizer`, `require_session_access`)
   missing from any mutating view**, or present but checking the wrong
   session/event (e.g. one taken from the URL rather than the one actually
   being acted on) — this was a real bug pattern earlier (e.g. a session
   lookup not scoped to its parent event).

What I'd like from the review

Please give me, in order of severity:

1. **Correctness bugs** — anything where the code doesn't do what it's
   supposed to, especially around the concurrency safety, the transition
   state machine, or permission enforcement.
2. **Security gaps** — places where a determined user (especially a staff
   account) could plausibly access, modify, or infer data they shouldn't,
   via URL tampering, form tampering, or otherwise. Also check CSRF
   coverage, and whether any view leaks another user's data through error
   messages or timing.
3. **Data integrity risks** — anything that could leave the database in an
   inconsistent state (e.g. a `Registration` whose status doesn't match its
   `RegistrationEvent` history, orphaned rows, etc.).
4. **Performance issues** — N+1 queries, missing `select_related`/
   `prefetch_related`, anything that would visibly degrade as data volume
   grows beyond the current small seed-data scale.
5. **Deployment readiness** — anything that would break or behave
   differently once actually running on Render against Supabase rather
   than local Docker Postgres (e.g. connection pooling behavior, SSL
   settings, `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`, static file handling,
   `DEBUG` leaking in production, secret handling).
6. **Test coverage gaps** — is there anything genuinely load-bearing (a
   security check, a business rule) that has no test at all?
7. **Anything else** you'd flag in a real pre-launch review, even if it
   doesn't fit neatly into the above categories.

For each issue: tell me the file and roughly where, explain the actual
impact (not just "this is unusual"), and suggest a fix if it's not obvious.
I'd rather have a shorter list of real, specific issues than a long list of
stylistic nitpicks.

### What you got
I received a detailed analysis of the project codebase that identified major correctness bugs, security vulnerabilities, data integrity risks, and performance issues that could be improved. The report also highlighted critical deployment blockers that could cause significant problems if the application were deployed without addressing them.

### What you corrected
The report helped me identify and fix several correctness bugs, including typos, missing parameters, and forgotten authorization guards. It also highlighted important security gaps that were addressed, such as the lack of role-based scoping in `event_list` and `event_detail`, editing permissions being incorrectly enabled in `RegistrationAdmin`, and transition views accepting GET requests for state-changing operations.

## <What you were trying to achieve>
To unit test each functionality and feature implemented in the project before committing it to version control. The goal was to create functionality-specific tests, including relevant edge cases and failure scenarios, to thoroughly validate each feature.

### Prompt
5. Follow-up test prompts to the master prompt.

### What you got
I received individual, feature-specific and situation-specific test code blocks designed to thoroughly test each implemented functionality. These tests were executed together before deployment to verify that all features were functioning correctly and that the different applications worked together as expected.

### What you corrected
As features were modified and updated throughout the development of the application, the corresponding tests also had to be updated to reflect the latest implementation and expected behavior.

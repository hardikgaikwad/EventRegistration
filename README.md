# EventSync

A server-rendered event registration and check-in system built with Django.
Organizers manage events, sessions, and staff assignments; staff run
check-in for the sessions they're assigned to; both get a live dashboard,
searchable registration history, CSV bulk tools, and automatic capacity
alerts — all enforced server-side, not just hidden in the UI.

Built with Django + PostgreSQL (Supabase), plain Django templates, and
Bootstrap 5 — no separate frontend build, no REST API layer.

**Live demo:** [https://eventsync-oj0g.onrender.com/](https://eventsync-oj0g.onrender.com/)

| Role | Email | Password |
|---|---|---|
| Organizer | `organizer@example.com` | `demopass123` |
| Staff | `staff@example.com` | `demopass123` |

This is a seeded demo instance, not a production system — data may be reset
or re-seeded periodically, and no real attendee information is involved.

---

## Features

### Accounts & roles
- Email + password login (no separate username field)
- Two roles: **Organizer** and **Staff**, enforced on every view server-side
  — never just hidden buttons in a template
- Staff can only act on sessions they're explicitly assigned to; organizers
  can act on anything
- *(Forgot-password intentionally not implemented — there's no self-serve
  signup, so there's no account for a user to independently recover; an
  organizer resets a password directly via the admin site.)*

### Events
- Create, edit, archive, and restore events (name, description, dates, venue)
- Archiving hides an event from the default view without deleting its
  sessions or registrations — it's a flag, never a delete

### Sessions
- Each session belongs to exactly one event: title, start time, duration,
  location, and capacity
- Full CRUD, organizer-only (staff can view but never create/edit/delete)

### Staff assignment
- Any number of staff can be assigned to a session; a staff member can be
  assigned to any number of sessions across any event
- Organizer-only to add or remove assignments
- Each staff member has a dedicated "My Sessions" page

### Registration lifecycle
- **Reserved → Confirmed → Checked-in**, with **Cancelled** reachable from
  Reserved or Confirmed only (never from Checked-in)
- Every legal move is defined in one explicit transition table and enforced
  through a single function — no scattered status-check `if` statements
- **Capacity is enforced safely under concurrent requests** using row-level
  locking (`SELECT ... FOR UPDATE`) inside a database transaction — verified
  against real PostgreSQL with a multithreaded test, since SQLite silently
  ignores row locks
- Stale reservations (default 30-minute hold, configurable) automatically
  expire — both via a scheduled management command and a lazy check applied
  anywhere seat counts are computed, so the app self-corrects even without
  the scheduled job running
- Optional notes can be attached to any status change

### Finding registrations
- One searchable, filterable, paginated list across every registration a
  user is allowed to see (all sessions for organizers, only assigned
  sessions for staff)
- Text search over attendee name and email, filters by event/session/status
- Search, filtering, sorting, and pagination all happen as real database
  queries — nothing is loaded into memory and filtered in Python

### Bulk actions
- **CSV import** of an attendee list into a session, with a per-row report:
  created, duplicate, or rejected (with a reason) — valid rows are created
  even when other rows in the same file fail
- **CSV export** of a session's full roster, available to organizers and to
  staff assigned to that session

### Dashboard
- Role-scoped: organizers see everything, staff see only their sessions
- Sessions happening today, attendees checked in today, registrations
  expired this week, sessions currently at capacity
- Breakdown of registrations by status and by session
- A multi-line chart (reservations / confirmations / check-ins per day)
  with a selectable 7/14/30-day range

### Immutable audit history
- Every status change writes an append-only audit row — who changed it,
  when, old status, new status, and any note
- This history **cannot be edited or deleted through the app, including by
  superusers** — enforced directly in Django admin's permission methods,
  not just left as a convention
- A full timeline view per registration

### At-capacity alerts
- A session that reaches full capacity surfaces as an alert, with a live
  count badge and dropdown preview in the nav
- Organizers can dismiss an alert; if the session later drops below
  capacity and fills back up again, the alert reappears automatically —
  no manual re-triggering required

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Django 5.2 (LTS), Python 3.12+ |
| Database | PostgreSQL (Supabase in production; local Docker Postgres in dev) |
| Frontend | Django templates, Bootstrap 5 (CDN) |
| Charts | Chart.js (CDN) |
| Static files | WhiteNoise |
| Production server | gunicorn |
| Config | django-environ, dj-database-url |

No JavaScript framework, no separate API layer — everything renders
server-side. The handful of places JavaScript appears at all (the dashboard
chart, Bootstrap's own dropdown/collapse behavior) is the minimum needed for
something a static page genuinely can't do.

---

## Project structure

```
eventsync/
├── manage.py
├── requirements.txt
├── .env
├── config/                  # settings, root urls, wsgi/asgi
├── accounts/                # custom User model, login/logout, roles
├── events/                  # Event, Session, StaffAssignment, permissions.py
├── registrations/           # Registration, RegistrationEvent, DismissedAlert,
│                            # services.py (transitions, capacity, CSV, alerts)
├── dashboard/               # role-scoped stats, chart, nav alert badge
└── templates                # shared base.html + per-app templates
```

Each app with real business logic keeps a `services.py` holding the actual
rules, independent of any view or HTTP request — `views.py` stays a thin
layer that checks permissions and calls into it. This is what makes the
core logic (the transition state machine, capacity locking, CSV import,
alert state) directly unit-testable without spinning up a request at all.

---

## Getting started

### 1. Clone and set up a virtual environment

```bash
git clone <your-repo-url>
cd eventsync
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:
- Leave `DATABASE_URL` empty to fall back to a local SQLite database (fastest
  way to try the app), **or**
- Point it at a PostgreSQL instance — a local Docker container for
  development, or your Supabase connection string for anything beyond quick
  local testing (SQLite silently skips the row-locking behavior the
  concurrency-safety guarantees depend on, so it's not representative for
  anything beyond basic smoke-testing)
- Set a real `SECRET_KEY`

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Create an organizer account

```bash
python manage.py createsuperuser
```

### 6. (Optional) Seed realistic demo data

```bash
python manage.py seed_demo_data
```

Creates a demo organizer/staff account (`organizer@example.com` /
`staff@example.com`, password `demopass123`), several events and sessions
with varied capacities, and registrations spread across the last 30 days
and every possible status — including a couple of sessions deliberately
left at capacity, one with a pre-dismissed alert, so every feature has
something real to look at immediately.

### 7. Run the server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` and log in.

---

## Running tests

```bash
python manage.py test
```

The suite covers, among other things: server-side role/assignment
enforcement (a staff member gets a real 403 acting on a session they're
not assigned to), capacity being refused once a session is full, illegal
status transitions being rejected, a genuine multithreaded concurrency test
against PostgreSQL, CSV import partial-success behavior, RegistrationEvent
immutability (including against superusers via Django admin), and the
self-healing alert-dismissal behavior.

---

## Deployment (Render + Supabase)

1. **Supabase** — create a project, grab the pooled Postgres connection
   string (Project Settings → Database → Connection Pooling).
2. **Render** — create a Web Service pointed at this repo.
   - Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Start command: `gunicorn config.wsgi`
   - The included `Procfile`'s `release:` step runs migrations automatically
     before each deploy goes live.
   - Environment variables: `SECRET_KEY`, `DEBUG=False`,
     `ALLOWED_HOSTS=<your-render-domain>`, `DATABASE_URL=<supabase pooled URL>`,
     `DATABASE_SSL_REQUIRED=True`, `RESERVATION_HOLD_MINUTES=30`, plus SMTP
     variables if email delivery is ever added later.

---

## Known limitations

- **Forgot-password is not implemented.** There's no self-serve signup, so
  there's no account a user could independently recover — an organizer
  resets a password through Django admin instead. A deliberate scope
  decision, not an oversight.
- **`RegistrationEvent` cannot be created outside the app's own transition
  logic — not even by an admin.** There's no manual "fix a bad audit row"
  escape hatch; any correction has to happen through a real status
  transition.
- **`StaffAssignment.staff` has no hard database constraint requiring the
  `staff` role** — this is enforced at the application layer, not the
  schema level.
- **No per-event timezone support** — one global `TIME_ZONE` setting
  applies to the whole app.
- **The nav alert badge and dashboard's "at capacity" stat reflect state as
  of the last page load**, not real-time — there's no WebSocket/polling
  layer, consistent with keeping this a plain server-rendered app.
- **The alerts dropdown and nav badge loop over visible sessions in Python**
  rather than a single aggregated query — a reasonable trade-off at the
  scale this app is built for, worth revisiting if session counts grow
  very large.


# Assignment Specs

## Assignment 12 — Event Registration

## The scenario

Picture an organization running multi-day conferences and workshops — a handful of sessions each
with a fixed room capacity, spread across one or more events a year. Right now sign-ups happen over
email, a shared spreadsheet gets updated by whoever answers the message first, and how many seats
are actually left in a popular session is whatever the last person to edit the sheet believes.

The result is predictable. Two people register around the same time for a session with one seat
left, the spreadsheet gets updated twice, and the room ends up with more attendees than chairs. A
seat gets reserved by someone who never follows through, and because nobody frees it, that seat stays
lost to everyone else who wanted it. On the day itself, front-of-house has no reliable way to tell who
has actually walked in versus who merely signed up weeks ago and forgot.

They want one system: organizers set up events and their sessions with a real seat capacity,
check-in staff manage the door on the day, and a reservation nobody confirms in time frees itself
back up automatically instead of sitting on the books forever. Anyone should be able to trust that a
session marked full really is full. That is the system you are building.

## What it must do

Everything below is required. Several of the ten spell out exact rules — what happens on an illegal
move, what a bulk action must report back, when a dismissed alert is allowed to reappear — and those
specifics are the actual ask, not just the bold headline in front of them.

1. **Accounts and roles.** People sign in with an email and password, and there are at least two
roles — an organizer role and a check-in staff role. Organizers create and archive events, create
sessions within an event and set each session's capacity, and can create, confirm, cancel and check
in registrations for any session. Check-in staff can do the same only for sessions they are assigned
to, and cannot create events, create sessions, or change a session's capacity. The difference must be
enforced on the server, not just hidden in the interface.

2. **Events.** Organizers create events with a name, a description, a start date, an end date, and a
venue, and can edit them later. Events can be archived and restored. Archiving hides an event from
the default views without destroying its sessions or registrations.

3. **Sessions inside events.** Every session belongs to exactly one event and carries a title, a
start time, a duration, a location within the venue, and a seat capacity. Sessions can be created,
edited, and deleted by organizers. Opening an event shows its sessions.

4. **A registration lifecycle with rules.** Each registration records an attendee's name and email
address for one session, and moves through *Reserved → Confirmed → Checked In*. Reserving a seat
requires room left in the session's capacity, counted as its Reserved, Confirmed and Checked In
registrations together; once that count reaches capacity, the server refuses any further reservation
rather than overselling the session. A reservation left Reserved for longer than a set holding window
is automatically marked *Expired*, freeing the seat it held. A registration can be marked *Cancelled*
from Reserved or Confirmed, which also frees the seat, but not once it is Checked In. Any other move
must be rejected by the server with a message explaining why.

5. **Assignment.** Any number of check-in staff can be assigned to a session, and a staff member can
be assigned to any number of sessions across any event. Only an organizer can add or remove a staff
assignment. Every check-in staff member can see one list of every session they are assigned to.

6. **Finding registrations.** One list shows registrations across every session the viewer can see,
with a text search over attendee name and email, filters for event, session and status, sorting by
reserved time, status or session, and pagination showing the total number of matches. All of this
must happen on the server — do not load every registration into the browser and filter there.

7. **Acting on many attendees at once.** Organizers can bulk-import an attendee list from a CSV file
into a session's registrations. The result is a per-row report: a row is created as a new
reservation, counted as a duplicate if that email is already registered for the session, or rejected
as invalid with a reason, and valid rows are still created even when others in the same file are
rejected. Separately, export a session's check-in sheet — every registered attendee and their status
— as a CSV file.

8. **A dashboard.** A landing view shows headline numbers — sessions today, attendees checked in
today, registrations expired this week, and sessions currently at capacity. It also breaks
registrations down by status and by session, and charts check-ins per day over the last fourteen
days.

9. **History you cannot rewrite.** Every registration has a timeline showing when it was created,
every status change with the old and new status and who made it, and any notes staff leave about it.
Nothing in this timeline can be edited or deleted after the fact, including by organizers.

10. **At-capacity alerts.** A session that reaches its full seat capacity appears in an alerts area,
with a count badge visible in the navigation. An organizer can dismiss the alert for that session. If
a later cancellation or expiry frees a seat and the session then fills back up to capacity, the alert
returns.

## Stretch ideas (optional)

None of these are required, and none substitute for a goal above. If you finish all ten with time
left over, pick whichever of these sounds most useful and build it:

- QR-code badges for faster check-in.
- A waitlist for sessions at capacity.
- Speaker and topic management per session.
- Automated email confirmations and reminders.
- A multi-track schedule builder with conflict detection.
- A public event page for self-service registration.
- Sponsor or exhibitor booth management.
- Post-session feedback surveys.
- Multiple ticket types with different pricing.


---

## What we are assessing

A working application is table stakes. Almost every serious candidate will produce something that runs, has a login, and roughly does what was asked. That's the floor, not the differentiator.

What actually separates submissions is the record of thinking behind the app: the decisions you made and why, the trade-offs you weighed, what you built first and what you deliberately left out, and whether you can explain any part of your own system when asked. We are hiring for judgement. The app is the evidence for that judgement, not the deliverable in itself.

We also read the code itself for structure and readability, which counts for a small share of the overall score.

## Time budget

Budget about 12 hours total, spent roughly 2 hours a day across a week.

This is not a race. We are not timing you against other candidates, and submitting early scores nothing extra. Twelve hours is a size guide so you know how much to attempt — pace yourself, stop when you're tired, and spend some of that time thinking and documenting, not only typing code.

## Pick any stack you like

Use any language, any framework, any UI library, any ORM, and any database access approach you want. We have no house stack, and no stack scores better than another — this round is not a test of whether you know particular tools.

Use whatever you are fastest and most confident in. Time spent learning something new to impress us is time not spent on the ten goals above, and it will show.

## Using AI is allowed and encouraged

Use AI tools however you want — to scaffold code, debug a stuck problem, write tests, draft documentation, or anything else that helps you move faster. A few things to know about how we treat it:

- We do not penalise AI use, and we make no attempt to detect it.
- We care about whether you understood, directed and verified the output — not about who or what produced the first draft of it.
- `docs/ai-prompts.md` must contain the prompts you actually used, including the ones that produced bad output and what you changed afterwards. If you used no AI at all, say so here and describe how you worked instead — that is assessed the same way.
- Submitting generated code you cannot explain is the single most common way candidates fail this round.

You are accountable for everything in your submission. If a reviewer points at a piece of code and asks why it's there, or why it works the way it does, "the AI wrote it" is not an answer.

## Use git properly

Publish to a public GitHub repository, and commit incrementally as the work actually happens — after each meaningful step, not in one pass at the end.

A repository whose entire history is a single "initial commit" containing a finished app scores zero on git history, and it colours how we read everything else in your submission, however good the app itself is. Your history is how we see the order you built in, where you got stuck, and how the design changed along the way. If it isn't there, we can't assess it, and we won't assume the best.

## What you must commit

Alongside your code, commit these five files under `docs/`. Your zip includes a stub for each with the questions it needs to answer — fill them in as you go, not from memory at the end.

| File | What it must answer |
|------|----------------------|
| `docs/architecture.md` | What the moving pieces are, how they talk to each other, where each one runs, the request path for one representative user action end to end, and what you decided not to build. |
| `docs/schema.md` | Every table's columns and types, which relationships are one-to-many versus many-to-many, which constraints live in the database versus the application, what you deliberately denormalised, and what would break first at 100x the data. |
| `docs/plan.md` | How you split the work into sessions, what order you built in and why, what you estimated versus what it actually took, and what you cut when you ran short. |
| `docs/decisions.md` | At least five real decisions — what you chose, what you rejected, and why — including at least one you later reversed. |
| `docs/ai-prompts.md` | The prompts you actually used, in order, grouped by what you were trying to do, including at least one that produced something wrong and what you did about it. |

## Host it for free

Deploy the whole thing somewhere reachable by URL, using free tiers only.

One combination that works, if you would rather not decide:

- **Database** — a managed service such as Supabase.
- **Server-side code** — Render.
- **Browser-side code** — Vercel.

Deploy in that order: create the database first, give the server its connection details as environment variables, then point the browser-side part at the server's public URL.

This is one option, not a requirement. Any free host is equally acceptable — everything on a single provider, one virtual machine, a container platform, a static host with serverless functions. The choice earns and loses nothing.

Requirements:

- A working live URL.
- Seeded with enough demo data to show the system doing something, not an empty shell.
- Demo credentials for every role recorded in `SUBMISSION.md`.
- Connection strings, keys and passwords kept in environment variables, never in the repository.
- Free tiers often sleep when idle and can take a minute or more to wake. Note it in `SUBMISSION.md` if yours does, so a slow first load is not read as a broken deployment.
- If you cannot get it hosted, submit anyway and record in `SUBMISSION.md` what you tried and where it broke.

## How to submit

Send us:

- The URL of your public GitHub repository.
- The URL of your live, deployed application.
- Your completed `SUBMISSION.md`, committed to the repository.

That's the whole submission. Nothing else to prepare, no separate form.

## What happens next

If your submission clears the bar, we'll set up a short call. We will ask about specific decisions we can see in your repository and its history — why you modelled something a particular way, what a certain commit was fixing, what you'd change if you kept going.

We're telling you this now because it should change how carefully you document as you go. Write `docs/decisions.md` for a version of yourself who has to explain it three weeks from now.

## Scope

The 10 goals stated in this brief are the cutoff. Meet all 10, solidly, and you have a complete submission.

Stretch ideas are optional. They exist for candidates who finish the 10 with time left and want to keep building — they are never required, and they do not make up for a goal you didn't hit. Doing 8 goals well beats doing 10 goals badly. If time is short, finish fewer goals properly rather than leaving all ten half-done.

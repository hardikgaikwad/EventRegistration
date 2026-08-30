# Assignment 12 — Event Registration

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

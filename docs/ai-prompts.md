# AI prompts

The prompts you actually used, in the order you used them, grouped by what you were trying to achieve. For each significant one: what you asked, what you got back, and what you had to correct.

Include at least one prompt that produced something wrong, and what you did about it.

If you did not use AI at all, say so here, and describe your process instead.

## <What you were trying to achieve>
1. To create a comprehensive and reliable implementation plan covering the application's architecture, database schema, implementation details, and technology stack.

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
1. An implementation guide in Markdown format was generated and stored as `implementation_guide.md` in the `docs` directory.

### What you corrected
1. Made multiple code changes throughout the entire coding phase of the project, as mentioned below.

## <What you were trying to achieve>
Build the initial `accounts` app in Django, starting with the creation of different apps such as `accounts`, `dashboard`, `events`, and `registrations`. In the `accounts` app, models such as `UserManager` and `User` were created. The goal was to build a basic application skeleton along with an initial roles and authentication system.

### Prompt
Follow-up prompts based on the initial master prompt.

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
Follow-up prompt to the master prompt to build the CSV bulk import feature under Phase 8 of `implementation_guide.md`.

### What you got
I got a working CSV bulk import and roster export feature. However, the bulk import feature was initially accessible to both staff and organizers for their respective assigned sessions, whereas the requirement was for the bulk import feature to be exclusive to organizers.

### What you corrected
I restricted the CSV bulk import feature to organizers only.

The CSV roster export feature remains available to both staff and organizers, but users can only export the roster of sessions they are assigned to.
# Submission

Fill this in and commit it. This is the first file we open.

## Links

- **GitHub repository:** (https://github.com/hardikgaikwad/EventRegistration)
- **Live application:** (https://eventsync-oj0g.onrender.com/)

## Notes for the reviewer

- Cold Starts: The application is hosted on Render Free Tier. If the site is idle for more than 15 minutes, the server will spin down. Please be aware that the very first page load might take about 60 seconds as the server wakes back up. The application experience in general is slow as well as the database is deployed on Supabase free tier and It fetches the frontend from Bootstrap 5 CDN.
- Time-Travel Demo Data: The database has been pre-seeded using a custom seed_demo_data management command. To ensure the Dashboard's 14 day check-in history and so that chart.js looks realistic. The script intentionally backdates the audit logs upto last 30 days.
- Supabase Free Tier: The PostgreSQL database is hosted on Supabase's Free Tier. If the project is not reviewed for over 7 days, Supabase might automatically pause the database project, which would cause the Render app to return a 500 error until unpaused from the Supabase dashboard.

## Demo credentials

| Role      | Email                     | Password      |
|-----------|---------------------------|---------------|
| Organizer | `organizer@example.com`   | `demopass123` |
| Staff     | `staff@example.com`       | `demopass123` |

## Stack

| Layer | What you used | Why |
|-------|---------------|-----|
| Frontend | Django Templates + Bootstrap 5 | Prioritized simplicity and zero setup friction. Server-rendered templates are fast to build, secure, and perfectly sufficient for this domain without the overhead of a separate React SPA. |
| Backend | Django 5.2 (Python 3.14) | Excellent built-in admin, robust ORM for complex database locking (used for capacity concurrency), and a mature authentication system. |
| Database | PostgreSQL (Supabase) | Required a relational database that supports strong ACID guarantees for the `select_for_update` capacity locking, plus Supabase's transaction pooler works well with serverless hosting. |
| Hosting | Render | Easy Git-push deployments and managed environment variables. |

## Goal checklist

Mark each honestly. Partial is fine — say what is partial.

| # | Goal | Status | Notes |
|---|------|--------|-------|
| 1 | Accounts and roles | Done | Enforced at the view layer via `require_session_access` |
| 2 | Events | Done | Archiving flips a boolean; cascade deletes are blocked if registrations exist |
| 3 | Sessions | Done | Fully nested under events |
| 4 | Registration lifecycle with rules | Done | Handled via a centralized `transition()` state machine and `select_for_update` locking. Stale reservations auto-expire. |
| 5 | Assignment | Done | `StaffAssignment` join table enforcing unique pairs |
| 6 | Finding registrations | Done | DB-level filtering and pagination applied before evaluation |
| 7 | Bulk actions | Done | Valid rows commit independently of invalid rows |
| 8 | Dashboard | Done | N+1 queries optimized using `annotate()` and `Count` |
| 9 | Immutable history | Done | Locked down via Django Admin; no update/delete paths exist in the code |
| 10 | At capacity alerts | Done | Dismissals naturally clear themselves when seats open up |

## How much time did you actually spend?
I have spent around 20-25 hours to build this application, give or take. This includes planning and reviewing the plan, architecture and schema, then comes the programming part and finally deploying and documentation.

## What would you do next, with another 12 hours?
UI/UX Polish: I would move beyond the default Bootstrap components to create a more vibrant, custom user interface. This would include adding micro-animations, improving the dashboard's visual hierarchy, and creating a more engaging experience for the attendees and staff interacting with the platform.
End-to-End Authentication & Communication: I would build out the complete public-facing authentication flow. This includes self-service user registration and integrating a real SMTP backend (like SendGrid or AWS SES) so that password recovery, account confirmations, and ticket status updates are automatically emailed to users.
Performance Profiling & Scalability: I would spend time stress-testing the application to identify bottlenecks under high traffic. Specifically, I would look into caching the dashboard's heavy aggregation queries using Redis, moving the CSV bulk-import parsing to an asynchronous background worker (like Celery), and adding database indexes to handle a massive increase in registration volume without degrading response times.

## What are you least happy with in this codebase, and why?
The Visual Design: The application relies heavily on default Bootstrap 5 styling, which makes it look functional but visually unappealing and generic. For instance, the at-capacity alerts are very plain; investing more time into the UI to make these alerts dynamic and engaging would significantly improve the overall feel of the application.
Rigid Role Management: Currently, role assignments are somewhat rigid. A major enhancement would be building a dedicated administrative interface where superusers can easily invite new users and assign or modify their roles (Organizer vs. Staff) directly from the dashboard, rather than relying on Django's built-in backend admin panel or hardcoded scripts.
Lack of Attendee Profiles: We built a robust state machine for tickets, but we lack a self-service profile area. If an attendee makes a typo in their name or email during registration, they have no way to log in and correct their own information. Staff also lack a safe UI view to edit these details. Building a dedicated user profile system would drastically reduce administrative overhead and improve the attendee experience.
# Architecture

## What are the moving pieces, and how do they talk to each other?

The system is a modular Django application split by domain, backed by a relational database:

1.  **`accounts`**: Manages the custom `User` model, authentication, and the two core roles (Organizer, Staff).
2.  **`events`**: Owns the structural data — `Event`, `Session`, and `StaffAssignment`. It also houses the central permission choke point (`require_session_access`) used across the app.
3.  **`registrations`**: The operational heart of the system. It manages `Registration` lifecycle states, the immutable `RegistrationEvent` audit trail, and `DismissedAlert`s. It exposes safe mutation boundaries (`reserve_seat`, `transition`) to the rest of the application.
4.  **`dashboard`**: A purely read-only aggregation layer. It queries data from `events` and `registrations` to compute statistics, alerts, and charting data, but never mutates state.
5.  **PostgreSQL (Database)**: The single source of truth for all state, enforcing constraints (like `unique_together` on assignments) and handling concurrency locks.

**Communication:** The pieces talk to each other synchronously via direct Python function calls. Views in any app always call the centralized permission helpers in `events` and the safe state-machine services in `registrations`. There are no internal APIs, message queues, or microservices.

## Where does each piece run?

-   **The Web Server**: The entire Django application runs in a single server process managed by Gunicorn, hosted on a **Render Web Service**. It uses WhiteNoise to serve static files (CSS, JS) directly from this same process.
-   **The Database**: The PostgreSQL database is hosted remotely on **Supabase** and is accessed via a connection pooler to efficiently manage database connections in a serverless/PaaS environment.
-   **The Client**: The user's web browser. It renders plain HTML and CSS (using Bootstrap 5 via CDN). The only JavaScript executed on the client is the Chart.js library for rendering the dashboard timeline chart.

## What is the request path for one representative user action, end to end?

**Scenario: A staff member clicks "Reserve" to manually add an attendee to a session.**

1.  **Client Request**: The browser sends an HTTP POST request with the attendee's name and email to `/events/<id>/sessions/<id>/register/`.
2.  **Routing & View**: Django routes the request to `registration_create` in `registrations/views.py`.
3.  **Authentication & Authorization**:
    *   The view checks if the user is authenticated.
    *   It calls `require_session_access(user, session)`. This queries the `events` app to confirm the user is either an Organizer or explicitly assigned to this session via `StaffAssignment`.
4.  **Business Logic (`registrations/services.py`)**:
    *   The view calls `reserve_seat()`, which opens a `transaction.atomic()` block.
    *   It locks the `Session` row in Postgres using `select_for_update()` to prevent concurrent double-booking.
    *   It checks for stale reservations and expires them to ensure an accurate capacity count.
    *   It counts current active seats. If `seats_taken >= capacity`, it rolls back and raises a `CapacityFullError`.
    *   It creates a new `Registration` record in the database.
5.  **State Machine & Audit**:
    *   `reserve_seat()` calls `transition(registration, 'reserved')`.
    *   `transition()` checks the `ALLOWED_TRANSITIONS` rules (validating `None` -> `reserved`).
    *   It creates an immutable `RegistrationEvent` audit row recording who made the change and when.
6.  **Commit & Response**: The transaction commits, releasing the database lock. The view catches success, adds a Django flash message, and returns an HTTP 302 redirect back to the session detail page.
7.  **Client Render**: The browser follows the redirect and renders the updated HTML, showing the new registration and decreasing the available seat count.

## What did you decide *not* to build, and why?

-   **A Single Page Application (SPA) / REST API frontend**: I decided against building a separate React/Vue frontend communicating via Django REST Framework. *Why:* The requirements prioritized simplicity, fast delivery, and zero setup friction. Server-rendered Django templates (enhanced slightly with Bootstrap and Chart.js) perfectly met the UX requirements without the massive overhead of maintaining two separate codebases and an API serialization layer. Everything can be built solely with Django templates with CDNs and my lack of heavy experience in frontend development led me to prioritize feature implementation over UI.
-   **JSON Web Tokens (JWT) for Authentication**: I rejected JWTs in favor of Django's built-in session-backed cookies. *Why:* JWTs are designed for stateless distributed architectures or mobile clients. For a traditional server-rendered web application, session cookies are simpler, more secure out-of-the-box (with HttpOnly and CSRF protections), and easily revocable.
-   **Admin editing for Registration History**: I strictly disabled `has_change_permission` and `has_delete_permission` for `RegistrationEvent` in the Django Admin, even for superusers. *Why:* The audit trail must be mathematically provable and immutable. If an admin can silently edit a status change history, the audit trail loses its integrity. If a manual fix is required, it must be enacted as a *new* forward-moving state transition, not a historical rewrite.
-   **Cascade Deletion for Sessions**: Deleting a session that already has registrations is blocked. *Why:* Cascading deletes would silently wipe out user registration data and the associated audit history. Blocking the deletion forces the organizer to intentionally handle existing attendees (e.g., by cancelling them) before destroying the event structure.

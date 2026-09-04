# Schema

## Table by table: what columns and types does each one have?

**User (`accounts`)**
*   `id`: Primary Key
*   `email`: EmailField (Unique, acts as USERNAME_FIELD)
*   `full_name`: CharField
*   `role`: CharField (Choices: organizer, staff)
*   `password`: CharField (Hashed)
*   `is_active`, `is_staff`, `is_superuser`: BooleanField
*   `date_joined`: DateTimeField

**Event (`events`)**
*   `id`: Primary Key
*   `name`: CharField
*   `description`: TextField
*   `start_date`, `end_date`: DateField
*   `venue`: CharField
*   `is_archived`: BooleanField (Default: False)
*   `created_at`, `updated_at`: DateTimeField

**Session (`events`)**
*   `id`: Primary Key
*   `event_id`: ForeignKey (to Event)
*   `title`: CharField
*   `start_time`: DateTimeField
*   `duration_minutes`: IntegerField
*   `location`: CharField
*   `capacity`: PositiveIntegerField

**StaffAssignment (`events`)**
*   `id`: Primary Key
*   `staff_id`: ForeignKey (to User)
*   `session_id`: ForeignKey (to Session)
*   `created_at`: DateTimeField

**Registration (`registrations`)**
*   `id`: Primary Key
*   `session_id`: ForeignKey (to Session)
*   `attendee_name`: CharField
*   `attendee_email`: EmailField
*   `status`: CharField (Choices: reserved, confirmed, checked_in, expired, cancelled)
*   `reserved_at`: DateTimeField
*   `created_by_id`: ForeignKey (to User, Nullable)
*   `updated_at`: DateTimeField

**RegistrationEvent (`registrations`)** - *Append-only audit table*
*   `id`: Primary Key
*   `registration_id`: ForeignKey (to Registration)
*   `old_status`: CharField (Nullable)
*   `new_status`: CharField
*   `changed_by_id`: ForeignKey (to User, Nullable)
*   `note`: TextField (Nullable)
*   `created_at`: DateTimeField

**DismissedAlert (`registrations`)**
*   `id`: Primary Key
*   `session_id`: ForeignKey (to Session)
*   `dismissed_by_id`: ForeignKey (to User)
*   `dismissed_at`: DateTimeField

---

## Which relationships are one-to-many, and which are many-to-many?

**One-to-Many (1:N):**
*   **Event 1—N Session:** An event contains multiple sessions, but a session belongs to only one event.
*   **Session 1—N Registration:** A session has many attendees, but a registration is tied to a specific session.
*   **Registration 1—N RegistrationEvent:** A registration has a history of multiple status changes.
*   **Session 1—N DismissedAlert:** A session can have alerts dismissed over time.

**Many-to-Many (N:M):**
*   **User N—M Session:** Staff members can be assigned to multiple sessions, and a session can have multiple staff members assigned. This is explicitly managed through the `StaffAssignment` joining table.

---

## Which constraints are enforced by the database, and which by application code — and why did you draw the line there?

**Database Enforced:**
*   `unique=True` on `User.email`: Prevents identical accounts at the lowest level.
*   `unique_together = ("staff", "session")` on `StaffAssignment`: Ensures a staff member cannot be assigned to the same session twice.
The database enforces these absolute uniqueness rules because it is the single source of truth; relying on the application layer for uniqueness under high concurrency is prone to race conditions.

**Application Code Enforced:**
*   **Session Capacity:** Evaluated in application code inside a transaction (`select_for_update`) before inserting a registration.
*   **Event Dates:** Validating that `start_date <= end_date` is handled in form/model clean methods.
*   **Staff Role Check:** Ensuring only users with the `staff` role can be assigned to `StaffAssignment.staff_id`.
The line was drawn here because capacity is a dynamic calculation (summing active seats) rather than a static field check. Date range constraints and role checks are easily handled by Django's form and model validation layers, keeping complex domain logic in Python rather than embedding it as database triggers or custom constraints, which can be harder to version control and debug.

---

## What did you deliberately denormalise?

The `status` field on the `Registration` table is a deliberate denormalization. 

Strictly speaking, the current status of a registration could be dynamically computed by querying the `RegistrationEvent` table for the most recent row associated with that registration. However, `Registration.status` is maintained as a fast-read cache of that latest event. This allows the system to filter, search, and count registrations by status (e.g., "show all confirmed attendees") using a single, simple query, avoiding heavy SQL joins and aggregations on the audit table for every page load.

---

## What would break first if this had 100x the data?

1.  **Dashboard Alert Count Computation:** The context processor that checks for at-capacity alerts is executed on every page load. Currently, it aggregates seat counts across all visible sessions. At 100x scale (e.g., thousands of active sessions), this dynamic aggregation would slow down every request, even with database annotations. It would need to be moved to a background caching layer (e.g., Redis).
2.  **Dashboard 14-Day Timeline Chart:** The query that builds the Chart.js timeline truncates and aggregates raw `RegistrationEvent` rows. If the audit table grows to millions of rows, running this aggregation on the fly will cause dashboard load timeouts. This would require materialized views or pre-computed daily rollups.

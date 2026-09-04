# Plan

## How did you break the work into sessions?

The work was broken down into strict, modular phases defined in an initial `implementation_guide.md` generated with my AI pair-programmer. Each session focused on producing a single, stable, committable layer of the application. 

Instead of jumping between frontend and backend, I worked vertically through specific domains:
- **Session 1:** Project scaffolding, database connection, and custom user authentication (`accounts`).
- **Session 2:** Core structural models and permissions (`events`, `sessions`, and `staff_assignments`).
- **Session 3:** The core business logic — concurrency-safe reservations and the state machine (`registrations`).
- **Session 4:** Bulk operations (CSV import/export) and search/filtering.
- **Session 5:** Read-only aggregations — the immutable timeline, capacity alerts, and the role-scoped dashboard.
- **Session 6 (Final):** Pre-deploy security audit, N+1 query optimization, and Render deployment configuration.

## What order did you build in, and why that order?

I built strictly from the foundation upward, never building a feature until its dependencies were fully stable and tested. 

1. **Auth First (`accounts`)**: Built first because every other entity in the system either belongs to a `User` or relies on role-based access control.
2. **Structure Second (`events`)**: Events and Sessions had to exist before anyone could register for them. 
3. **Permissions Third (`StaffAssignment`)**: The security choke point (`require_session_access`) was built and tested *before* writing any code that mutated data. This ensured security was baked in, not bolted on later.
4. **Core Logic Fourth (`registrations`)**: The `reserve_seat()` concurrency locks and `transition()` state machine were built.
5. **Aggregation Last (`dashboard`)**: The dashboard was built at the very end because it is purely read-only. It relies on the existence of events, registrations, and audit trails to compute its statistics and charts. 

This order prevented the need to mock data or write temporary code. Every phase naturally rested on the verified layer beneath it.

## What did you estimate versus what it actually took?

I initially estimated that ensuring concurrency safety (preventing overbooking) and writing the CSV bulk import logic would be the most time-consuming parts of the project, taking several days of debugging race conditions.

In reality, pairing with the AI significantly accelerated these phases. By designing the `reserve_seat()` function with `select_for_update()` inside an `atomic` block *before* writing the views, the concurrency problem was solved at the database layer immediately. The CSV logic also went faster because I scoped it to handle row-by-row atomic transactions, allowing valid rows to succeed even if the file contained errors, eliminating the need for complex rollback logic.

The pre-deploy audit phase took slightly longer than expected because I found and fixed N+1 query performance issues in the dashboard and timeline views, and had to reconfigure static files for Render using WhiteNoise.

## What did you cut when you ran short?

The core application is feature-complete against the original specification, so no mandatory requirements were cut. However, I made deliberate choices to heavily scope certain features to save time and maintain simplicity:

1. **SPA Frontend**: Cut entirely. There is no React or REST API. Server-rendered Django templates with Bootstrap 5 proved perfectly adequate and significantly faster to build.
2. **Admin Edit Interfaces**: Rather than building safe admin interfaces to correct bad registration data, I completely locked down the Django Admin for `RegistrationEvent` rows. If data needs correcting, it forces the user to move the state machine forward (e.g., cancelling and re-registering) rather than letting us rewrite history.

# Milestone 2 backend usage

Historical milestone notes. See [integrated backend](integration.md) for the current implemented forecasting, workflow and UI behavior.

The foundation UI still uses public reference geometry. Protected backend data
is synthetic and does not imply that forecasting or agents have been implemented.

## Local identity configuration

Set AO02_AUTH_TOKENS in backend/.env to a JSON object of independently generated
bearer secrets and server-owned principals. No default credentials are enabled.
Example shape (replace placeholders with long random secrets):

AO02_AUTH_TOKENS={"<operator-secret>":{"role":"operator"},"<tenant-one-secret>":{"role":"tenant","tenant_id":"T1"}}

Clients send Authorization: Bearer <secret>. An empty configuration denies all
protected access. This local static-token scheme is intended for development;
replace it with your identity provider before shared deployment. Use HTTPS for
remote access. Never put these secrets in VITE_ variables or commit .env.

## Endpoints

- GET /api/telemetry?offset=0&limit=100: tenant-scoped daily readings (limit 1000).
- GET /api/telemetry/events: scoped synthetic scenario events.
- GET /api/telemetry/window?rack_id=R-01&resource_type=STORAGE: persist exact
  authorized source window and return validated summary with SHA-256.
- POST /api/incidents: operator-only HeapIncidentEnvelope. Use the window summary
  as telemetry and matching token scope. Server checks the snapshot and summary;
  fresh tokens must begin at RESOURCE_MONITORING with zero hops and no audit list.
- GET /api/queue: authorized queued tokens, lower priority number first.
- GET /api/incidents/{token_id}: incident, source hash and audit history; inaccessible
  and unknown IDs both return 404.

Public /api/health and /api/bootstrap remain compatible with the existing UI.
Private payloads currently use snake_case domain fields; reference UI DTOs use
camelCase. Frontend domain binding will require an explicit adapter.

## Reproducibility and persistence

Generator defaults: seed 42, 2025-10-28 inclusive to 2026-10-28 exclusive, 365 daily
observations. 26,280 rack/resource records plus 2,190 CRAC readings = 28,470 points.
Six resource classes cover 12 racks assigned cyclically to T1/T2/T3. CRAC readings
include supply/return temperature and RPM. Workloads, units, capacities, 80%
safety thresholds and scenario event timestamps are explicit. Known storage
exhaustion/recovery, workload regime change and transient spike/recovery are
synthetic ground truth for later evaluation, not measured model performance.

This is a new reproducible dataset, not a migration of the archive's inconsistent
scenarios. Archive migration remains a separate pending integration task.

SQLite stores incidents, exact requested snapshots and audit records in
backend/incidents.sqlite3 (ignored by Git). Configure AO02_DATABASE_PATH to use a
new persistent database location; its parent must exist. Queue snapshots are
rebuilt using heapq; atomic SQLite claims prevent concurrent double processing.
Active scope uniqueness survives dequeue and restart. Terminal closure releases
scope for a new incident. Halted incidents retain scope until reviewed.

Database triggers reject update/delete of audit and snapshot records through
normal application SQL. This protects against application mistakes; it is not
protection against an administrator replacing the database file. Backups and
external integrity anchoring are deployment concerns.

Domain models live in app/models.py; enums remain in core/ao02_state_and_graph.py.
Remediation requires stated simulation assumptions and disallows live-control
mutation. No remediation is executed. The internal advance method provides a hop
guard; full ordered LangGraph transitions and human pause/resume arrive in
Milestone 3. Queue dequeue/advance are internal, not exposed as public operations.

## Verification

Run from repository root:

    ./backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v

Checks cover concurrent deduplication/claim, restart recovery, stable priority
ties, scope reopening, loop limits, audit triggers, schema safety, tenant denial,
reproducible telemetry, snapshot-to-incident submission and tampered summaries.

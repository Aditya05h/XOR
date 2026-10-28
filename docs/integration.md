# Integrated backend and frontend

## Configuration

AO02_DATABASE_PATH selects the incident database; its parent directory must exist.
The workflow checkpointer uses the same path with `.checkpoints.sqlite3` appended.
AO02_AUTH_TOKENS maps secrets to server-owned operator/tenant identities.
AO02_DEMO_MODE enables loopback development synthetic preview only; default false.
AO02_ENVIRONMENT accepts development, test or production.
AO02_LLM_PROVIDER accepts deterministic (default), openai or gemini.
AO02_OPENAI_API_KEY/AO02_GEMINI_API_KEY remain backend-only; model overrides are
AO02_OPENAI_MODEL/AO02_GEMINI_MODEL. Provider failure falls back after two attempts.

## API contracts

Public bootstrap retains its original camelCase reference-layout contract.
Authenticated domain endpoints use snake_case and frontend typed service mapping.
The public geometry contains no tenant readings. Credentials establish a session
through POST /api/session; cookie values are random, HttpOnly and expire in eight
hours. Session lookup is in-process; restarting requires sign-in again while
incidents, audit and human-review checkpoints remain durable.

| Endpoint | Behavior |
|---|---|
| GET /api/facility?day=364 | Authorized historical readings and operator-only CRAC data |
| GET /api/forecasts/{rack}/{resource}?day=364 | Traceable statistical forecast using only readings through cursor |
| GET /api/evaluation | Operator-only measured holdout KPIs and evidence rubric |
| POST /api/monitor | Evaluate selected rack/day, persist risk incidents and suppress transients |
| GET /api/queue | Tenant-filtered deterministic pending queue |
| GET/POST /api/incidents | Authorized incident history / operator ingestion of matched source window |
| POST /api/workflow/run-next | Claim highest-priority queued incident and run to review |
| POST /api/incidents/{id}/run | Run/resume the selected incident without automatic human approval |
| GET /api/incidents/{id}/workflow | Authorized status and evidence |
| POST /api/incidents/{id}/decision | Validated approve/reject/defer with notes |
| WS /api/stream | Cookie-authenticated tenant-filtered persisted incident changes |
| POST /api/ingestion/csv | Operator-only validated readings with accepted/rejected counts |
| GET /api/snapshots/{hash}/forecast | Authorized forecast over an imported/frozen window |
| GET /api/archive | Operator inspection of both original dataset variants |
| GET /api/archive/sources | Preserved original source text, including embedded domain descriptions |

Use the generated FastAPI documentation for exact body schemas. Inaccessible
incident IDs return the same 404 as nonexistent IDs. No actuation endpoints exist.

## Forecast and evaluation method

A robust median-pairwise-slope baseline fits a recent daily window. Observed,
confirmed-return spikes can be removed; sustained shifts change the fitting
window. Approximate prediction bands combine residual/leverage uncertainty with
training-only rolling-origin error calibration. Exhaustion estimates are bounded
by the forecast horizon and may be absent. Confidence scores are not fabricated.
Bands may exceed 100% to express demand beyond physical capacity.

Evaluation fits at historical cutoffs and compares the next 28 days, without
passing those future points into the forecasting function. False-alarm negatives
are series/cutoffs whose next 28 observations remain below the 80% safety margin.
Lead time measures warnings before observed hard-capacity exhaustion. Evidence
completeness checks source linkage, audit presence, RCA evidence, assumptions,
risk and model IDs; explanation correctness still requires human assessment.

## Workflow and advisory semantics

Monitoring persists the exact canonical source series and its SHA-256. Incident
reporting, RCA, remediation, risk and human review run as LangGraph nodes. SQLite
checkpoints preserve interrupts; deferred reviews reinterrupt and cannot silently
approve. Replayed nodes avoid duplicate phase effects. Per-incident leases reject
concurrent runs. Internal guards cap transitions and preserve halted evidence.

RCA attributes measured workload scope and compares same-rack/same-tenant snapshot
windows when available. Correlation is explicitly not proof of causation.
Remediation compares hypothetical 10/20 percentage-point demand reductions using
an observed recent slope. It does not assert feasibility or zero downtime. Risk
uses an explicit utilization/uncertainty heuristic, requires human review and
leaves SLA/dependency effects unverified. A completed advisory may still represent
an unresolved real-world capacity risk.

## Archive migration

Both archive dataset families, four AO-02 envelope seeds, all legacy alerts,
resources, settings, server-unit data, 425-point generated curves and source
modules are preserved under backend/app/data. The anchor clock is fixed at
2026-10-28T00:00:00Z and the ZIP hash is recorded. Original authored KPI constants,
invalid example hashes and inconsistent tenant assignments are retained as
source examples rather than trusted operational evidence. Source content is
rendered as escaped text and is never executed by the application.

Original camera, airflow, fan and selection mechanics informed the SVG scene's
pan/zoom, focus, staggered particles, slowed RPM fan illustration and inspection
transitions. The existing three-by-four floor, palette and typography are retained.
Archive WebGL/sidebar/theme markup was not substituted for the visual baseline.
The original nine pages' domain material is accessible through focused workbench
views and the archive evidence browser; source-specific controls are not portrayed
as real hardware operations.

The one-time import helper reads the preserved archive-source.json and rebuilds
serialized data exports with the fixed date; it is not run by the app. Temporary
extraction staging is removed after integration.

## Provider references

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)

Provider explanations are optional, source-labeled hypotheses. Model access and
live response behavior depend on the user's account and credentials. Numerical
results are always computed locally from telemetry.

# XOR engineering ledger

Append entries only. Read before architecture changes; skip updates for purely informational turns.

## 2026-10-28 / Milestone 1 foundation / session 01a18241-1aac-7421-8815-b3dd43112d25

- Summary: inspected pasted requests and supporting references. The latest pasted
  master request explicitly starts with milestone 1. Created `dev/ao02-core` from
  an unborn `master`; there was no main branch or commit history. Preserved the
  pre-existing staged `XOR-Agentic_AI/README.md` without content changes.
- Changed files: root README, ignore rules and this ledger; backend pyproject,
  dependency lock, env example, app/config.py, app/contracts.py,
  app/core/ao02_state_and_graph.py, app/main.py and tests/test_foundation.py;
  frontend Vite/TypeScript/Tailwind configuration, dependency lock, env example,
  index.html, src/App.tsx, CSS, types/ao02.ts, services/api.ts,
  hooks/useFacility.ts, components/digital-twin/FacilityScene.tsx and Playwright
  configuration/tests. Removed unused generated Vite assets.
- Architecture: public reference geometry and health only, no operational or
  tenant data exposed. Pydantic DTOs serialize camelCase; frontend validates the
  bootstrap boundary. Six resource enums match across Python/TypeScript.
  Unknown lead time and facility equipment tenant identity may be null.
  React owns interaction state; scoped Anime.js v4 manages presentation and
  cleanup, including reduced motion. Original SVG floor supports rack selection,
  keyboard access and bounded zoom/reset. LangGraph is installed, not yet wired
  to agents. Provider keys stay private in backend configuration.
- Verification: 5 backend unittest checks passed; pip check passed; frontend
  TypeScript/production build and lint passed; all 3 Playwright tests passed
  against the real API. Browser tests cover reference geometry, selection,
  zoom/reset, keyboard, reduced motion, mobile overflow and failure/retry.
  Desktop/mobile screenshots reviewed. Fixed desktop caption overlap, empty
  Anime.js selection warnings, scope callback typing and Windows test startup.
  npm ci --offline verified the lockfile. Built JS: 264.87 kB / 86.02 kB gzip.
  Python dependency lock dry-run succeeded. Verified on Python 3.14 and Node 24.
- Tooling notes: machine's Python 3.12 launcher points to a missing executable;
  used system Python 3.14 virtualenv. npm package-lock-only hit a remote optional
  package restriction after package rename; retained the resolved lock and
  updated its root package name, then verified offline clean installation.
- Next: milestone 2 domain models, persistent SQLite incident context/audit,
  deterministic priority queue and deduplication, authenticated tenant access,
  and seeded twelve-month telemetry. Then numerical forecasts/KPIs and actual
  checkpointed LangGraph human review. Full pan, exploded rack components,
  timeline scrubbing, charts, WebSockets and decision console remain pending.
  No forecasts, operational health, performance KPIs or agent results are faked.

## 2026-10-28 / Archive integration Step 1 audit

- Summary: inspected the live XOR shell and safely extracted 65 application files
  from Agentic_AI .zip into ignored tmp/archive-audit. Cataloged all 21,933 ZIP
  entries without running archive code, Git hooks or bundled dependencies.
- Touched files: docs/archive-integration-audit.md, docs/archive-inventory.json,
  and this appended ledger entry. Application source and visual tokens unchanged.
- Architectural findings: two inconsistent demo datasets/tenant mappings; four
  seeded AO-02 incidents; nine pages; browser-only queue/shared heap and phase
  simulation; static KPI claims; 365+60 point formula generator; Three.js and
  CSS airflow/fan/camera interactions. No server agents or real isolation in ZIP.
- Visual lock: preserved existing palette, typography, SVG geometry and layout;
  stored source fingerprints. Motion must be adapted to current Anime.js/SVG.
- Live verification: localhost shell loads, but bootstrap returns 404. Port 8000
  serves a different AO-02 v0.3.0 API without /api/bootstrap. Multiple listeners
  exist; no unrelated service was stopped. Current scene cannot render until
  the target service/proxy is reconciled.
- Verification: checked archive containment during extraction; enumerated source
  hashes/exports; inspected source models, generators, state and motion code;
  checked live browser/error and API schema. No code tests needed for audit docs.
- Pending: Step 2 data extraction/adapters with source provenance; Step 3 motion
  integration; Step 4 live UI/type checks and staging cleanup. Fix approval,
  deduplication, tenant security and audit semantics before claiming real agents.

## 2026-10-28 / Fix local API service collision

- Changed frontend/vite.config.ts, frontend/playwright.config.ts and README.md
  to consistently use backend port 8011 instead of the occupied port 8000.
- Started this repository's backend with explicit app-dir and restarted its
  Vite process. Other project processes were preserved.
- Verified all 3 browser tests passed against the running services, including
  real bootstrap, rack rendering, interaction, mobile and error recovery.
- Architecture and visual design unchanged. Archive integration remains pending.

## 2026-10-28 / Milestone 2 domain and telemetry

- Summary: added validated incident/telemetry/forecast/RCA/remediation/risk/audit
  models, SQLite shared context, priority heap snapshots and atomic claims,
  stable ties, active-scope deduplication, restart recovery and internal hop guard.
- Files: backend/app/models.py, storage.py, telemetry.py, auth.py, config.py,
  main.py; backend/tests/test_milestone2.py and foundation route expectation;
  backend/.env.example, docs/milestone2.md, README.md and this ledger.
- Persistence: exact authorized telemetry windows stored canonically with SHA-256;
  incident submission validates matching source summary. Audit/snapshot triggers
  forbid update/delete. Local DB ignored. Protected API requires server-configured
  bearer principals; tenant filtering applies to readings, events, queue and IDs.
- Data: deterministic seed 42, fixed 365-day window, 28,470 readings covering all
  six rack resource classes and CRAC temperature/RPM; five ground-truth scenario
  events. A new synthetic dataset, not imported archive content or measured KPIs.
- Verification: 12 unittest tests pass, including concurrent claims/deduplication,
  restart, priority ties/reopening, loop guard, immutable SQL audit, model safety,
  tenant access denial, deterministic data and snapshot-to-incident/tamper flow.
  pip check passes. Frontend and theme untouched.
- Limits/next: static bearer identity is local development auth, replace for shared
  deployment. Domain API fields are snake_case; use explicit UI adapters later.
  SQLite file administrators can bypass application protections. Milestone 3
  implements numerical forecasts, measured KPIs, ordered LangGraph execution,
  checkpoints, provider adapters and human review. Archive migration remains pending.

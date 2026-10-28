# Acceptance evidence — Milestones 3–5

Verified on 2026-10-28 with Python 3.14, Node 24 and Chromium, on the development
branch. This records a synthetic advisory prototype, not production sensor or
provider validation.

| Check | Result |
|---|---|
| Backend unittest suite | 26 passed |
| Python dependency consistency | pip check passed |
| TypeScript and Vite production build | Passed |
| Frontend oxlint | Passed, no application lint warnings |
| Playwright browser suite | 6 passed |
| Production JavaScript bundle | 295.97 kB / 95.53 kB gzip |
| Production CSS | 18.75 kB / 5.05 kB gzip |
| Desktop/mobile screenshots | Reviewed; no overflow in checked 1440px/390px layouts |
| Source whitespace check | Passed after normalizing scene line endings |

## Verified scenario

The browser connected to the loopback synthetic session, selected R-04, exploded
and reassembled the rack, loaded a historical early-warning cursor, monitored
storage, processed the priority incident, observed a real LangGraph human-review
pause, recorded deferral and then approval, and inspected audit/evaluation/archive
content. WebSocket upgrade and authenticated connection were confirmed through
Vite. A separate backend test restarted the engine at the review pause before
resuming it. No infrastructure mutation was performed.

Other checks cover tenant REST/WebSocket access denial, source snapshot matching,
audit triggers, concurrent claims/deduplication, restart recovery, loop exits,
CSV rejection reasons, recent transient versus persistent breach, controlled
provider fallback, keyboard pan/reset, reference selection, reduced motion,
mobile width and API failure/retry. Archive seeds and 425-point curves were
checked against expected counts. JSON/source details render lazily to avoid
mounting every archived record simultaneously.

## Measured synthetic backtest

| Metric | Measured result |
|---|---:|
| Resource series | 72 |
| Chronological cases | 360 |
| Held-out point predictions | 10,080 |
| MAE | 3.3702 percentage points |
| RMSE | 4.4154 percentage points |
| Interval coverage | 87.02% against nominal 90% |
| False-alarm rate | 1.71% (6 / 351 defined negative cases) |
| Known exhaustion events detected | 1 |
| Mean warning lead time for detected exhaustion | 7.714 weeks |

The false-alarm denominator is series/cutoffs whose next 28 observations stay
below the 80% safety threshold. These results come from the fixed synthetic
fixture and selected cutoffs; they do not establish production performance.
Evidence completeness is calculated separately from current reviewed/review-ready
incidents using the documented six-part rubric. No causal-correctness score is
invented, and no generic accuracy percentage replaces forecasting error.

## Deployment-dependent limits

- Live LLM requests were not tested with user credentials. Both provider wire
  formats, timeouts/fallback and schema/evidence validation were tested using
  mocked transports and checked against official documentation.
- Static development principals and loopback demo access are implemented;
  production identity-provider integration is not supplied by the reference data.
- Data originates from a seeded replay or explicit CSV upload. No real facility
  telemetry connection or control actuation exists.
- Risk scores and mitigation outcomes are explicit heuristics/hypotheticals,
  with feasibility, dependency blast radius and SLA effects left for review.
- SQLite audit/snapshot/forecast triggers protect application writes; replacing
  the database file as an administrator remains outside that protection.
- Archive content is preserved as source examples and inspectable datasets, with
  contradictions retained. The current workbench consolidates that information
  while retaining the existing visual design.

## Milestone outcome

Milestone 3: numerical forecasting, evaluated KPIs, executable persisted agent
workflow and explicit human decisions are integrated.

Milestone 4: the original SVG facility and its visual system now connect to scoped
readings, history, charts, incident evidence, decisions and archive inspection.

Milestone 5: end-to-end, isolation, motion, responsiveness and build checks pass;
documentation and engineering ledger are updated and extraction staging cleared.

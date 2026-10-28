# Archive integration audit — Step 1

Audited 2026-10-28 on `dev/ao02-core`, baseline commit `0470a9a`.
Source: `D:\XOR - Project Requirements\Agentic_AI .zip`.
This report records inspection findings and the migration contract. Data and
animation integration (Steps 2–4) has not yet been performed.

## Visual baseline lock

| Role | Existing value to preserve |
|---|---|
| Canvas | `#eae8e2` |
| Ink | `#292c29` |
| Muted text | `#646861` |
| Accent | `#34765f` |
| Lines | `#bcbfb5` |
| Surface | `#f4f3ee` |
| Sans typography | Segoe UI, Arial, sans-serif |
| Technical typography | Cascadia Code, Consolas, monospace |
| Rack surfaces | Face `#e4e4dc`, side `#d6d9ce`, top `#f1f1e9` |
| Selected rack | Face `#d6e4d8`, existing green accent stroke |

Preserve the header, title/copy hierarchy, facility drawing, right inspector,
compact dark view controls, rack selector, six-resource strip and footer.
Retain responsive stacking, fine technical outlines, restrained borders and
existing background surfaces. The current model is SVG, not a WebGL scene:
960×590 viewBox, three rows of four racks, two cooling units, isometric floor,
seven illustrated server slots per rack, bounded zoom and keyboard selection.
Anime.js controls entry opacity and selection lift through scopes with cleanup
and reduced-motion handling. React owns selection and zoom.

`archive-inventory.json` stores SHA-256 fingerprints of the baseline CSS, App
and scene files so later integration can identify every visual change.

### Live observation

The browser at `http://127.0.0.1:5173/` shows the correct XOR shell but reports
`API request failed (404)` for `/api/bootstrap`. The service currently answering
port 8000 identifies itself as `AO-02 Data Center Capacity Forecasting`, version
0.3.0, and exposes `/health`, `/telemetry/*`, `/queue/*`, `/heap/*`, `/agents/run`
and other routes, but no `/api/bootstrap`. This is a service/API mismatch.
Multiple processes listen on ports 8000 and 5173, including another project.
No unrelated process was stopped. The scene baseline was inspected in its
source; its current live rendering cannot be confirmed while bootstrap fails.

## Archive inventory

The ZIP has 21,933 entries, including bundled dependencies, build output and
embedded Git history. Application files were extracted to the already-ignored
`tmp/archive-audit/`; no archive scripts or dependencies were executed.
The full entry manifest remains in staging. The committed inventory lists
every extracted application file, size, checksum and declared export.

### Data and schemas

| Source | Contents |
|---|---|
| `src/data/mockAO02Dataset.ts` | 12 AO-02 rack snapshots; 2 CRAC snapshots; 4 incident envelopes; 4 constant KPIs; 365-day history plus 60-day projection generator |
| `src/data/mockData.ts` | 12 legacy racks with server units and risks; 2 detailed CRAC records; 9 resource records; 5 alerts; 1 RCA incident with facts/hypotheses/3 actions; 6 audit records; default settings |
| `src/types/ao02.ts` | Resource, phase, decision, severity and tenant types; criticality weights; telemetry, forecast, RCA, remediation, risk, audit, token, envelope, time-series, rack, CRAC and KPI schemas |
| `src/types/index.ts` | Legacy health/resource/tenant/scene types; server, rack, capacity risk, cooler fault, CRAC, resource, alert, RCA, audit, settings and toast schemas |
| `src/components/datacenter2d/types2d.ts` | 2D rack and cooler presentation contracts |

AO-02 tenants: T1, T2, T3 and All. Legacy tenants: Acme Cloud, FinTech Core,
HealthTech Alpha, RetailStream and All Tenants. These are distinct source
scenarios: their rack ownership differs, so they cannot be merged by assuming
a universal name-to-ID mapping.

Rack data includes coordinates/orientation, tenant, health, power and capacity,
temperature/targets, storage utilization, network bandwidth/capacity, server
counts, per-server CPU/temperature/power, risk evidence and recommended action.
Detailed CRAC data includes supply/return temperatures, RPM/fan status,
load/capacity, CFM, filter pressure, chilled-water flow, compressor loads and
fault state. The 2D scene additionally embeds cooler loads/capacities and
rack-specific risk descriptions; these must also be preserved as source data.

### AO-02 incident seeds

| Token | Resource/rack | Tenant | Priority | Seed phase | Exhaustion / range |
|---|---|---|---:|---|---|
| T-01 | Storage R-04, 95.2% | T1 | 12 | Risk analysis | 9 days / 7.5–11.2 days |
| T-02 | Network R-02, 88% | T2 | 24 | Remediation | 22 days / 18–26.5 days |
| T-03 | Cooling R-09, 91.6% | T1 | 22 | RCA | 12 days / 9.5–15 days |
| T-04 | Power R-08, 94% | T3 | 15 | Incident reporting | 17 days / 14–20 days |

Envelope content includes telemetry windows and claimed hashes, projected dates,
confidence scores, regime-shift descriptions, tenant/workload attribution,
correlated signals, investigation notes and audit records. T-01 contains shard
rebalancing and compression options plus a 0.28 risk score; T-02 contains an
additional LACP link option plus a 0.35 risk score. T-03/T-04 have no remediation
options in their seed envelopes. Preserve missing evidence as missing.

The constant KPI values are 94.2% forecast accuracy, 3.4 weeks average lead time,
96.8% false-alarm suppression and 98.5% auditability. These are authored demo
values, not results of a held-out evaluator. Suppression is not false-alarm rate.

The 425-point generator supports storage, power, network and cooling only.
It inserts a regime marker at day 290 and a spike at days 330–332, then widens
projection bands. Dates depend on the current clock. There is no stored
twelve-month dataset per rack/tenant, VM/license series or historical evaluation
engine. Physical values are also reused as percentages in this generator.

Legacy resource records cover SAN storage, GPU power, ToR networking, aisle
cooling, Kubernetes compute, Redis memory, Ceph storage, main busway power and
chilled-water plant cooling. Preserve Memory separately rather than silently
renaming it to Software License.

### State and behavior

- `AO02Context.tsx`: selected tenant/rack/machine/token/view, queue and heap
  initialization, filtered views, phase advancement and operator decisions.
  Backend connectivity is hardcoded false. No LangGraph or LLM execution exists.
- `priorityQueue.ts`: binary min-heap, criticality/utilization/lead-time scoring,
  enqueue/dequeue/peek/snapshot, duplicate keys and an eight-hop ceiling.
- `sharedHeap.ts`: mutable in-memory Map, envelope lookup, tenant filter,
  appended audit objects and approval/rejection recording.
- `DataContext.tsx`: legacy dataset state, tenant filtering, random telemetry
  jitter, settings persistence, selection/hover, scene mode, play/pause, alerts,
  notes, toasts, fault simulation and simulated remediation.
- Fault scenarios cover filter, fan, compressor and chilled-water faults;
  modeled fault fields also allow refrigerant. Preserve explanations, thresholds
  and recommendations from the fault factory and its modals.
- CSV template download is implemented. Upload uses a timer and fixed row count;
  it does not parse the file. Synthetic-batch action logs a claimed batch without
  producing those readings. These must not be presented as real ingestion.

### Pages and supporting content

Nine pages: Overview, DataCenter, Forecasts, Resources, Alerts, RootCause,
DataManagement, AuditLogs and Settings. Their inline text, chart formulas,
sample CSV/preview rows and controls are migration sources in addition to the
two dataset modules. Forecasts has its own short-history projection and what-if
capacity calculation, distinct from the 425-point AO-02 generator.

Common UI includes Header, Sidebar, GlobalSearchModal and ToastContainer.
Scene details include RackDetailDrawer, CoolerDetailModal, AutomatedFaultModal,
ThermalLegend, SceneControls and SelectedDetailsPanel2D. Retain their information
and interactions using the target inspector/drawers, not their original styling.
Project README and archive memory document history; they are reference material,
not instructions overriding the user's visual lock or read-only requirements.

## Motion inventory and adaptation

| Source mechanics | Integration into current aesthetic |
|---|---|
| 3D OrbitControls with damping 0.06; rotate/pan/zoom; isometric, cold aisle, hot aisle, top-down and cooler presets | Translate relevant focus/pan/zoom behavior into SVG camera transforms and Anime.js easing; retain baseline floor arrangement |
| Airflow frame loop: cold arrows rise toward intakes, hot arrows rise behind racks, particle drift/wrapping, density/speed/visibility controls | Scoped Anime.js paths within current aisle geometry; existing palette; explicit pause and reduced-motion behavior |
| CRAC fans: RPM-derived angular speed, stopped-fan behavior; fault beacon pulses | SVG fan groups in matching technical linework; bind to selected simulation telemetry |
| ServerRack frame effects and hover/selection highlighting | Preserve target rack faces and outlines while porting status/interaction behavior |
| ColdAirflow2D: 2.2-second rise, −32px chevrons, −38px particles, half-cycle stagger and opacity envelope | Port timings and stagger into Anime.js; adapt coordinates to current isometric floor |
| HotAirflow2D: 2.4-second rise, −28/+24px directional travel, 1.2× particle travel and stagger | Distinct directed paths using the same target tokens; avoid duplicate global keyframe names |
| Cooling pipes, grilles, server units, resource indicators and temperature overlays | Add information overlays without replacing baseline geometry or color system |
| Escape deselection, tooltips, details, expanded scene, thermal legend and animation toggles | Integrate with existing accessible selection and inspector structure |
| Toasts, drawers, modal fades, CSS status pulses and transitions | Reuse scoped Anime.js motion with cleanup; retain current surfaces/borders |

The archive uses Three.js/React Three Fiber/Drei and CSS animations; Anime.js is
absent. Framer Motion is declared as a dependency but no motion API usage was
found in the source scan. Camera presets directly set positions; they are not
an existing smooth interpolation controller. No exploded-rack controller or
historical timeline scrubber was found; those would be new functionality.

## Required reconciliation before migration

1. Keep target rack positions (three by four). Preserve the archive's two-by-six
   coordinates as provenance, not as replacement layout.
2. Preserve both dataset variants and their original IDs/tenant assignments.
   Normalize `rack-04` to `R-04` only through a source-aware adapter.
3. Map prefixed phases (`01_RESOURCE_MONITORING`, etc.) into target phase enums.
   Preserve the six named stages and terminal/loop-guard states.
4. Label seed forecasts, KPI constants, confidence bands, simulated actions and
   historical logs as archive examples. Do not claim measured accuracy or real
   infrastructure activity from their authored text.
5. Fix queue deduplication lifetime and deterministic tie-breaking before reuse.
   Current dequeue removes active keys, and equal priorities lack explicit
   timestamp/ID ordering. Queue and heap also hold separate token objects.
6. Replace mutable/shared audit references with protected persisted records when
   claiming immutable history. Several claimed SHA-256 values have invalid
   lengths and are not calculated from source series.
7. Tenant selector state is not authorization. The archive's All bypass and
   client-supplied operator role cannot guard backend data; masked rack views
   retain other tenants' numerical metrics.
8. Remove automatic approval from phase advancement. Require an explicit human
   decision, support deferral, and record advisory approval without actuation.
   The archive currently permits arbitrary decision timing and resolves both
   approvals and rejections as the same terminal phase.
9. Reconcile conflicting values without deletion: for example R-08/R-09 seed
   forecasts differ from the 2D scene's embedded 14/19-day estimates.
10. Resolve the API port/service mismatch before live binding. Keep archived demo
    state behind a service/hook boundary so actual REST/WebSocket contracts can
    replace it later.

## Step 1 completion and next work

Completed: source/live-shell inspection, safe application-source extraction,
file inventory and fingerprints, data/state/motion catalog and conflict report.
Only audit documents and the append-only ledger changed. `tmp/` was already
ignored; staging is retained for the extraction step and must be removed after
integration. No application/theme changes or migration claims are made here.

Next is Step 2: preserve source datasets and embedded domain content with explicit
provenance, reconcile IDs and units, and bind through typed hooks/services.
Step 3 ports motion onto the retained SVG model; Step 4 verifies the integrated
UI, cleans staging, updates the ledger and commits the implementation.

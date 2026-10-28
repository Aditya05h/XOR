# XOR Capacity Observatory

AO-02: Seeing trouble before the capacity runs out.

Milestone 1 provides a runnable FastAPI + React foundation for a read-only,
multi-tenant capacity advisory platform. The SVG reference facility contains
twelve selectable racks and two CRAC units. It supports keyboard selection,
zoom/reset, scoped Anime.js v4 motion and reduced-motion preferences.

**Current data is reference geometry only.** No telemetry, forecasts, incident
processing, tenant authentication or LLM calls are implemented yet. The interface
labels these unavailable states explicitly. Only public sample layout and health
endpoints exist; do not add operational data until server authorization is ready.

## Run locally (PowerShell)

Requires Python 3.12+ and Node 22.12+ (verified here with Python 3.14 and Node 24).
Run commands from the repository root, `D:\XOR`.

```powershell
python -m venv backend/.venv
./backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
./backend/.venv/Scripts/python.exe -m pip install -e './backend[dev]'
npm --prefix frontend ci
```

Optional configuration: copy `backend/.env.example` to `backend/.env` and
`frontend/.env.example` to `frontend/.env`. Defaults work without credentials.
Secrets belong only in the backend environment. Provider selection is reserved
configuration for milestone 3; it does not enable provider calls yet.

Start the API in one terminal:

```powershell
./backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload
```

Start the frontend in another:

```powershell
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173. API documentation: http://127.0.0.1:8011/docs.
Vite proxies `/api` to port 8011. Production hosting needs an equivalent reverse
proxy or a configured `VITE_API_BASE_URL` and matching backend CORS origins.
The Vite preview server alone does not proxy API requests.

## Verification

```powershell
./backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v
./backend/.venv/Scripts/python.exe -m pip check
npm --prefix frontend run build
npm --prefix frontend run lint
cd frontend
npx playwright install chromium
npm run test:e2e
```

Playwright starts both services automatically unless they are already running.
Its backend command resolves the platform's virtualenv path automatically.
Screenshots go to ignored `tmp/` in the repo root.

## Structure and contracts

- `backend/app/main.py`: typed health and public reference-layout endpoints.
- `backend/app/config.py`: validated environment configuration and private secrets.
- `backend/app/contracts.py`: Pydantic DTOs with explicit camelCase serialization.
- `backend/app/core/ao02_state_and_graph.py`: resource, phase and decision enums.
- `frontend/src/types/ao02.ts`: matching TypeScript contracts.
- `frontend/src/services/` and `hooks/`: API access, validation and loading state.
- `frontend/src/components/digital-twin/`: SVG geometry and scoped motion.
- `frontend/src/index.css`: semantic color and typography tokens with Tailwind v4.
- `memory.md`: append-only project engineering ledger.

LangGraph is installed and version-locked; executable agent nodes, persistence
and human interruption will be introduced with the real domain logic. React
owns selection and zoom; Anime.js only controls presentation. No global store
is required for the foundation. Nullable forecast lead time and tenant identity
allow unknown exhaustion estimates and facility-level equipment.

## Remaining milestones

2. Validated incident models, persistent priority queue/shared context, server
   authorization and reproducible twelve-month telemetry.
3. Statistical forecasts, held-out KPI evaluation, LangGraph agent execution,
   checkpoint-backed human review, provider integration and immutable evidence.
4. Authenticated APIs/WebSockets, full pan and exploded component inspection,
   historical scrubbing, forecast/attribution charts and decision console.
5. End-to-end scenario, isolation/safety testing and final visual/performance QA.

All mitigation remains offline advisory simulation. Operator approval records
a decision and must never actuate facility controls.

## Reference decisions

The pasted master request controls the implementation. The OpsPilot PDF supplies
architectural context; its Git/CI self-healing actions are outside AO-02 scope.
The handwritten plan supplies the token/queue/shared-context workflow. The
Anime.js images guide original fine-line drawings and a warm neutral palette.
The existing `XOR-Agentic_AI/README.md` is preserved unchanged.

Motion lifecycle follows the [Anime.js React integration guide](https://animejs.com/documentation/getting-started/using-with-react/).
Tailwind uses the [official Vite integration](https://tailwindcss.com/docs/installation/using-vite).

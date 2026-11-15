# TerraMind React frontend

An additive, functional React application for the existing academic prototype. Audited base: `b93d3b98bdd2411046fe0247c48c6a0919ba516e`, branch `feature/grounded-genai-prototype`. No backend, NLP, checkpoints or Streamlit source changes are required. No commit, push, deployment or merge is part of this delivery.

## Architecture and scope

Browser → same-origin `/api` Vite proxy → FastAPI presentation application. Trained NLP → structured query → environmental session → deterministic analytics → optional grounded explanation. The UI renders backend values, never synthesizes environmental measurements or LLM prose. React and Streamlit are independent HTTP clients.

Pages: Overview (connectivity, model and provider configuration, town coverage); AI assistant (English/Hindi/Nepali input, trained or explicitly enabled rule mode, entities and structured query, environmental results, AI explanation and follow-ups); Climate analytics (last assistant results, temperature and water charts, daily table, provenance); Location comparison (two supported town points, variables and dates through trained NLP); Model & data transparency (architecture and limitations).

Supported locations come from `/system`: Gangtok, Namchi, Mangan town points. Comparison deliberately uses `/nlp/analyze`, not browser-authored structured queries; trained checkpoints are required. Statistics are descriptive, not validated climate trends. Rainfall and total precipitation are distinct. Historical reanalysis and recent weather-model estimates are not station observations. TerraMind is not a complete operational Earth System Digital Twin.

### Files and dependencies

```
frontend-react/
  src/
    main.tsx            BrowserRouter entry
    App.tsx             shell, health/system status, overview/transparency/analytics
    Assistant.tsx       NLP → session → explanation and contextual follow-up
    Comparison.tsx      supported comparison workflow
    Results.tsx         metrics, charts, daily tables, source and AI components
    UI.tsx              shared heading
    contracts.ts        typed backend request/response shapes
    api.ts              fetch client, cancellation, timeout and safe errors
    styles.css          responsive design, keyboard focus, reduced-motion support
  tests/
    app.test.tsx        mocked browser API unit tests
    analysis.json       actual rule-demonstration response fixture
    bundle.json         actual backend recorded-data session fixture
    system.json         backend capability fixture
    e2e/workflow.spec.ts genuine HTTP browser integration checks
  vite.config.ts        local proxy and separate chart bundle
  vitest.config.ts      bounded unit test execution
  playwright.config.ts browser tests
  .env.example         public URL/proxy configuration only
  package.json / package-lock.json
  tsconfig.json / index.html / .gitignore
```

React, TypeScript, Vite, React Router, Recharts, Lucide. Plain CSS supplies the small design system; no Tailwind or heavy component framework is needed. Vitest, Testing Library and Playwright are development-only. Lockfile included; use `npm ci`. Node 22.12+ or Node 24 recommended (cloud verified Node 24.22.1/npm 11.9.0). Fonts use installed system fallbacks; no external font service is required.

## API contracts audited against actual OpenAPI

| Endpoint | Purpose |
|---|---|
| GET `/health` | Connectivity and `models_loaded`; degraded is distinct from disconnected |
| GET `/system` | Demo availability, towns, sources, provider configuration, limitations |
| POST `/nlp/analyze` | Original trained inference, `{query,session_id}` |
| POST `/demo/analyze` | Explicitly enabled, visibly labelled rules; never an automatic fallback |
| POST `/environment/session` | `{query,session_id,source_mode,language}` → environment, context_id, explanation |
| POST `/genai/explain` | `{session_id,context_id,question,language}` using server-owned context |

`/environment/query` remains available unchanged; React uses the session endpoint so analytics and follow-ups share the same validated period. Original OpenAPI and request/response contracts are untouched. No CORS change: Vite dev and preview proxy `/api` to FastAPI. A separate production host would need a same-origin reverse proxy, SPA history fallback, and separate operational security work; nothing is deployed here.

Provider `configured` means configuration exists, not successful live availability. Only explanations with backend status `ok` have text rendered. Other statuses remain visible. No browser HTML injection or markdown rendering of provider content; links allow only HTTP(S). Browser state is memory-only; reload clears results and conversation identifiers. Context IDs are opaque session capabilities, not user authentication. No provider keys belong in frontend files, `VITE_*` variables or browser storage. Vite exposes `VITE_*` variables publicly.

Requests have a 100-second client timeout. Assistant requests can be cancelled and abort on leaving the page. Cancelling browser HTTP does not guarantee server/provider cancellation. A new query clears stale UI results; a new conversation creates a fresh UUID. Environmental results survive disabled, unavailable, unsupported or rejected AI responses. `no_context` disables further follow-ups until the query is rerun. Server-side TTL and session binding remain authoritative. No weakening of grounding, numeric validation or source attribution.

## Windows setup and startup

These commands assume the reviewed frontend files are present locally. This implementation has not been committed or pushed; `git pull` alone cannot retrieve it yet. Use the existing working Python environment with verified trained checkpoints. Do not recreate or overwrite those checkpoints.

### Terminal 1: FastAPI

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind'
# Activate your existing working Python virtual environment if needed.
# Keep your existing backend-only Groq configuration in this terminal.
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

Do not substitute `backend.api.app`: that is the NLP-only application. For optional rule demonstration set `$env:TERRAMIND_DEMO='1'` before starting the presentation backend. Trained mode remains the React default. Without checkpoints the backend can run degraded, but trained requests correctly return 503.

### Terminal 2: React

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind\frontend-react'
node --version
npm ci
Copy-Item .env.example .env.local  # First setup only; preserve any existing configuration.
npm run dev
```

Open `http://127.0.0.1:5173`. Defaults: `VITE_API_BASE_URL=/api`, `TERRAMIND_PROXY_TARGET=http://127.0.0.1:8000`. Restart Vite after environment changes. Never copy provider keys into `.env.local`. To use a different backend port, change only the proxy target. Direct cross-origin browser URLs require separately scoped backend CORS; the supplied same-origin proxy avoids this.

### Terminal 3: independent Streamlit backup

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind'
$env:TERRAMIND_API_URL='http://127.0.0.1:8000'
python -m streamlit run streamlit_app/app.py --server.port 8501
```

Open `http://localhost:8501`. Use the same running FastAPI instance; React is not required. Existing dashboard dependencies remain in `requirements-dashboard.txt` if your Python environment needs them.

### Build and tests

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind\frontend-react'
npm test
npm run build
npx vite preview --host 127.0.0.1 --port 4173
```

Preview serves the built application and local API proxy. It is a local verification server, not a production deployment. Run the unchanged backend suite from the repository root with `python -m pytest -q`.

Optional automated browser checks use a demo-enabled backend and no LLM credentials, intentionally checking disabled-provider fallback. For reproducible checks start a separate backend terminal with `TERRAMIND_DEMO=1` and `TERRAMIND_LLM_PROVIDER=disabled`, pointing the Vite proxy at that port; do not change your genuine Groq backend environment. In the frontend terminal:

```powershell
npx playwright install chromium
npm run test:e2e
# For built preview instead:
$env:REACT_TEST_URL='http://127.0.0.1:4173'
npm run test:e2e
Remove-Item Env:REACT_TEST_URL
```

By default Playwright uses its installed Chromium. `CHROMIUM_PATH` can point to an existing executable; cloud uses `/usr/bin/chromium`. No trained model or live LLM is mocked into these genuine HTTP tests.

## Verification evidence (cloud)

- Existing backend suite: **715 passed, 2 pre-existing dependency deprecation warnings**; no tests removed or changed.
- React unit tests: **30 passed**, with mocked fetch/API and recorded backend response fixtures. Successful GenAI and trained comparison rendering in these tests are mocked, not genuine model/provider verification.
- Genuine browser HTTP: **3 passed** against Vite dev proxy and the actual FastAPI application: seven-day recorded-data query via explicit rule demo, environmental charts/table/results retained with disabled AI, contextual request using real server context, mobile navigation/390px layout without document overflow, actual OpenAPI and model-health endpoints. Also checked against built preview.
- Genuine live Open-Meteo request through React's API proxy: **ok**, Gangtok **2025-01-01 to 2025-01-07**, **7 daily rows**, rainfall **11.9 mm** (display rounded from backend floating-point representation), ERA5 attribution, AI **disabled**. No annual expansion.
- Production TypeScript/Vite build passes. Charts use a separate bundle and disable unnecessary chart animation. Desktop/mobile screenshots inspected locally; accessible daily tables accompany charts.
- Streamlit directory and all tracked original files remain byte-for-byte unchanged; existing Streamlit HTTP health on 8501 returns `ok` and its automated tests pass in the 715-test suite.
- Checked ports: existing FastAPI 8000 and Streamlit 8501 were already bound; fresh current-code verification used FastAPI **8004**, React **5173**, built preview **4173**, proxy target 8004. Windows commands above select 8000 by default; they are instructions, not a claim of access to your Windows ports.
- No trained checkpoints or private Groq credentials available in cloud. No new genuine trained-NLP/Groq verification is claimed. User-reported earlier Windows success is distinct from this frontend verification.

## Windows demonstration checklist

1. Start the existing trained/Groq-configured presentation backend, then React. Verify Overview shows connected, trained models loaded and provider configured.
2. On Assistant keep **Trained NLP inference**, choose live retrieval, submit `Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.` Confirm structured dates, exactly seven daily rows, approximate 11.9 mm rainfall and original ERA5 source.
3. Check initial validated AI explanation; ask `What is the mean temperature?` and `What is the total rainfall?`. Ask humidity to verify rejection, not invented data. Repeat with Hindi and Nepali explanation selection/input.
4. Open Climate analytics; confirm retained results, °C/mm, timezone, source, missing-data coverage and table.
5. Compare Gangtok/Namchi, then Gangtok/Mangan, same dates and live source. Confirm both actual returned periods and attribution. Missing checkpoints must produce a visible error, not rule substitution.
6. Switch to Streamlit on 8501 if necessary. For dedicated provider verification run `python scripts/verify_genai.py --mode trained --source live --require-llm --min-interval-seconds 10` from the repo root, using existing backend credentials.

The implemented frontend is suitable for a local academic demonstration after this genuine Windows trained/Groq smoke check. It is not a hardened multiuser deployment: no application authentication, persistent history, multiworker session store, exports, district coverage, causal inference or disaster forecasts.

## Troubleshooting

- **Port in use:** Vite uses strict ports and exits rather than silently switching; free the port or run `npm run dev -- --port 5174` and use that URL. Check Windows ports with `Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 8000,5173,8501`.
- **Disconnected / invalid API:** verify `Invoke-RestMethod http://127.0.0.1:8000/health` and `/system`, backend module and proxy target. Proxy is required for a local browser; opening `dist/index.html` directly does not work.
- **503 trained unavailable:** restore the existing verified checkpoint arrangement, or explicitly enable and select rules for a labelled demonstration. Never imply rules are trained inference.
- **Snapshot unavailable:** recorded files cover only 1–7 January 2025 for supported town points; use those dates or explicitly select live retrieval.
- **422:** check ordered ISO dates and the backend's 366-day/historical limits. The backend remains the authority.
- **AI unavailable/rejected:** environmental results remain available. Inspect safe provider diagnostics documented in `GROQ_PROVIDER_DIAGNOSTICS.md`; no key should be sent to the frontend. Provider configuration is not a successful request guarantee.
- **Expired context:** rerun the environmental query; do not reuse another browser's identifiers. Reload intentionally clears client history.

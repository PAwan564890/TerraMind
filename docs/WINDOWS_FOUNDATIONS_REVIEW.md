# Safe Windows integration and fallback

Target only: `C:\Users\pawan kumar singh\TerraMind-genai-review`. Do not overwrite the original TerraMind directory, recreate the Python environment, change the model junction, or copy Groq credentials into React.

## Availability gate

The foundation changes are currently **uncommitted in a separate cloud worktree** on local branch `feature/geospatial-intelligence-foundations`, based on `01bf4942174dfb2b1fac9fe57e841a07bd4b3716`. They are not on GitHub yet. The Git retrieval commands below are for **after explicit commit/push approval and a verified published branch**, not a claim that `git pull` can retrieve uncommitted files today.

After preservation is approved, use the confirmed branch/commit from that preservation report. If its branch name differs, replace the remote ref below with the exact confirmed ref. No reset, force push, clean, checkpoint copy or secret transfer is required.

## Retrieve into the existing review checkout

Stop the review frontend/backend processes first. Leave your working backend environment and existing Groq configuration available; no API key is requested here.

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind-genai-review'
git status --short
git branch --show-current
git rev-parse HEAD
if (git status --porcelain) { throw 'Preserve local changes before switching. Do not reset or clean this checkout.' }

# Optional inspection only: confirm the existing model directory/junction.
Get-Item .\models | Select-Object Name, LinkType, Target
python scripts/inspect_model_artifacts.py

# AFTER the approved foundation branch has actually been pushed:
git fetch origin
if (-not (git branch --list fallback/terramind-01bf494)) {
    git branch fallback/terramind-01bf494 01bf4942174dfb2b1fac9fe57e841a07bd4b3716
}
git switch --create review/geospatial-foundations --track origin/feature/geospatial-intelligence-foundations
# If that local branch already exists, stop and inspect it; do not overwrite it.
git rev-parse HEAD
git rev-parse origin/feature/geospatial-intelligence-foundations
git status --short
```

Compare both SHAs against the future verified preservation report. The currently proven fallback is `01bf494...`; no new commit SHA exists for the uncommitted implementation yet. Ignored Python environments, the model junction and private configuration must remain intact. Never use `git clean -fdx`.

## Backend terminal

Use the **existing working Python environment**, with the existing trained checkpoint junction and backend-only Groq settings. No new Python dependency is needed.

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind-genai-review'
$env:TERRAMIND_EXTENDED_LOCATIONS='1'
$env:TERRAMIND_ADDITIONAL_MEASUREMENTS='1'
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

The first flag enables ten reviewed town points; the second enables the separate humidity/wind-speed product. With flags absent, the three-point/default behavior remains available. Restart the backend after changing flags. Keep trained mode as the normal workflow; `TERRAMIND_DEMO=1` is optional and only enables explicitly labelled rule demonstration, never an automatic fallback.

Confirm capabilities from another terminal:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health'
Invoke-RestMethod 'http://127.0.0.1:8000/locations' | ConvertTo-Json -Depth 8
Invoke-RestMethod 'http://127.0.0.1:8000/system' | ConvertTo-Json -Depth 8
```

Expect ten locations, supplemental variables HUMIDITY/WIND_SPEED, and genuine checkpoint health. Provider `configured` is not a successful live LLM verification.

## React terminal

Node 22.12+ or Node 24. Use npm only for frontend packages; do not recreate the Python environment.

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind-genai-review\frontend-react'
npm ci
npm test
npm run build
npm run dev
```

Open `http://127.0.0.1:5173/map`. Default proxy target is `http://127.0.0.1:8000`. Preserve any existing `.env.local`; no new browser-side secrets are needed. The real map uses public OpenStreetMap tiles, not an image or a paid map API. If campus networking blocks tiles, use the accessible town selectors and real API retrieval; do not treat a blank basemap as missing environmental data.

## Independent Streamlit backup

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind-genai-review'
$env:TERRAMIND_API_URL='http://127.0.0.1:8000'
python -m streamlit run streamlit_app/app.py --server.port 8501
```

Streamlit remains an independent client. Its town caption now reflects `/system`; existing temperature/rainfall queries, provenance and GenAI workflows remain intact. Supplemental humidity/wind charts and the geographical map are React features; they are not falsely advertised as new Streamlit features.

## Evaluation smoke check

1. Check genuine trained checkpoint health, then the original 1–7 January 2025 Gangtok query and approximate 11.9 mm rainfall benchmark.
2. Inspect the new AI Pipeline Inspector: collapsed initially; actual mode, entities, normalized query, source data, validated claims/status. No private reasoning should appear.
3. Open Environmental Map; verify actual Sikkim tiles, ten markers, zoom/pan and keyboard selection. Select Pelling and Gangtok for 2025-01-01 through 2025-01-07. Retrieve live data; inspect both provenance blocks and coverage.
4. Click the map-to-comparison link. Confirm those same two towns are selected. Submit through the trained Comparison page; this step needs the real trained models.
5. Request humidity and wind speed via map checkboxes with explicit live retrieval. Check %, m/s, coverage and original source URLs; these supplemental values are not in the weather GenAI context.
6. In the Assistant ask a humidity-only or wind-speed-only question with complete ISO dates. Successful routing depends on actual model intent/entities; do not relabel model failure as rule success. Mixed temperature-plus-humidity text queries remain a separate-request limitation; the explicit map form can retrieve both products.
7. Create a Namchi weather session and ask “What was the warmest day?” / “What was the wettest day?”. Check actual Groq status, returned dates, source IDs and strict validation. Repeat the documented native follow-ups if needed.
8. Check a failed provider call leaves retrieved weather available, and a tile failure leaves selectors available. Reject wind direction, pressure, snowfall, cloud cover and hazard timing requests.

Optional original provider verification (with your existing backend credentials):

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind-genai-review'
python -m pytest -q
python scripts/verify_genai.py --mode trained --source live --require-llm --min-interval-seconds 10
```

Do not run backend regression tests with the expansion flags inherited in that test terminal: baseline tests intentionally assert default three-town/unsupported-measurement behavior. Remove those two environment variables in the **test terminal only**, or use a fresh terminal, while leaving the running expanded server unchanged.

## Browser regression modes

The original five browser checks are kept unchanged and use default feature flags, including their intentional unsupported-humidity assertion. Four new checks use the expanded backend. Playwright now has `baseline` and `expanded` projects. To run all nine checks, serve the same frontend against two backend instances:

- Baseline backend on 8007: `TERRAMIND_DEMO=1`, `TERRAMIND_LLM_PROVIDER=disabled`, expansion flags absent.
- Expanded backend on 8006: same explicit rule/disabled-LLM setup plus both expansion flags `1`.
- Vite dev on 5175 with `TERRAMIND_PROXY_TARGET=http://127.0.0.1:8007`.
- Vite dev on 5174 with `TERRAMIND_PROXY_TARGET=http://127.0.0.1:8006`.

Use separate terminals so none of these verification settings overwrite your genuine Groq backend environment. In the frontend test terminal:

```powershell
npx playwright install chromium
$env:REACT_TEST_URL='http://127.0.0.1:5175'
$env:REACT_EXPANDED_TEST_URL='http://127.0.0.1:5174'
npm run test:e2e
```

For production-preview verification, build once, run `npx vite preview --port 4175` with proxy target 8007 and another preview on 4174 with proxy target 8006, then change the two test URLs accordingly. These are local verification servers, not deployment instructions. On Windows Playwright uses its installed Chromium; `CHROMIUM_PATH` is only needed for a custom executable.

## Safe fallback

If an upgraded feature fails during rehearsal, stop the review servers and switch only the review checkout back to the preserved baseline, with a clean tracked working tree:

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind-genai-review'
if (git status --porcelain) { throw 'Preserve review changes before fallback.' }
git switch fallback/terramind-01bf494
Remove-Item Env:TERRAMIND_EXTENDED_LOCATIONS -ErrorAction SilentlyContinue
Remove-Item Env:TERRAMIND_ADDITIONAL_MEASUREMENTS -ErrorAction SilentlyContinue
```

Restart the proven backend and React (run `npm ci` for the baseline lockfile), or use Streamlit on 8501. Do not alter the original TerraMind directory, trained checkpoints, Python environment, model junction or private Groq settings.

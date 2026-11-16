# Safe Git preservation and Windows integration

No commit, push, merge or deployment was performed for this handover. Current foundations branch is `feature/geospatial-intelligence-foundations`; base is `01bf4942174dfb2b1fac9fe57e841a07bd4b3716`. Do not apply changes to protected master or reset the original worktree.

After explicit approval only: inspect branch/HEAD/status, review the complete tracked and untracked source/docs/test inventory, rerun checks, stage an explicit reviewed allowlist (never `git add .`), review `git diff --cached --check` and `git diff --cached`, and scan for secrets/weights/artifacts. Commit once with an approved message. Before first push check whether the new remote branch exists; if unexpected, stop. Push only `HEAD:refs/heads/feature/geospatial-intelligence-foundations`, without force. Verify its remote SHA equals the full local SHA and compare master to the pre-push master SHA. Do not claim preservation before remote confirmation.

The exact changed-file manifest is in the parent verification report; it includes this guide. Generated dependencies/builds, private configuration and checkpoints are excluded. Creating a preservation commit requires a new explicit user approval.

For Windows, follow [the complete existing review instructions](../WINDOWS_FOUNDATIONS_REVIEW.md). They preserve `C:\Users\pawan kumar singh\TerraMind-genai-review`, its working Python environment, checkpoint junction and private Groq configuration. Do not run a future fetch/switch workflow before a preservation commit has actually been pushed. Never use reset/clean or replace the original project directory.

After the approved branch exists remotely, in the review checkout:

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind-genai-review'
git status --short
# Stop if tracked/untracked work needs preservation.
git fetch origin
# Keep a named fallback; stop if an existing name points somewhere unexpected.
git branch fallback/terramind-01bf494 01bf4942174dfb2b1fac9fe57e841a07bd4b3716
git switch --create review/geospatial-foundations --track origin/feature/geospatial-intelligence-foundations
git rev-parse HEAD
git rev-parse origin/feature/geospatial-intelligence-foundations
```

If either branch name already exists, inspect it and use the detailed guide rather than overwriting. Compare both SHAs to the future approved push report.

Backend terminal, using the existing activated Python environment and private provider configuration:

```powershell
$env:TERRAMIND_EXTENDED_LOCATIONS='1'
$env:TERRAMIND_ADDITIONAL_MEASUREMENTS='1'
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind-genai-review\frontend-react'
npm ci
npm test
npm run build
npm run dev
```

Open `http://127.0.0.1:5173/map`. In another terminal at the review root:

```powershell
$env:TERRAMIND_API_URL='http://127.0.0.1:8000'
python -m streamlit run streamlit_app/app.py --server.port 8501
```

Genuine verification (server must actually have checkpoints and backend credentials):

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health'
Invoke-RestMethod 'http://127.0.0.1:8000/system'
python scripts/verify_genai.py --mode trained --source live --require-llm --min-interval-seconds 10
```

Run backend regressions in a separate test terminal with expansion flags removed, not in the running server terminal:

```powershell
Remove-Item Env:TERRAMIND_EXTENDED_LOCATIONS -ErrorAction SilentlyContinue
Remove-Item Env:TERRAMIND_ADDITIONAL_MEASUREMENTS -ErrorAction SilentlyContinue
python -m pytest -q
```

The original verifier does not cover every foundation feature. Also complete the map, supplemental variables, comparison handoff, native-language Inspector and warmest/wettest genuine Groq smoke checks in the parent Windows guide. Browser regression requires both baseline and expanded API/frontend targets; its exact commands are there.

## Exact cloud allowlist procedure — only after explicit approval

First confirm branch/base/status and inspect every path below. Capture remote master before any push. A nonempty existing remote foundation branch requires investigation, not overwrite. Network errors are not proof of absence.

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
git ls-remote origin refs/heads/master refs/heads/feature/geospatial-intelligence-foundations
```

Stage only the reviewed inventory (this command is documentation and has not been executed):

```bash
git add -- \
  backend/environment/provider.py \
  backend/environment/service.py \
  backend/genai/facts.py \
  backend/genai/questions.py \
  backend/genai/schema.py \
  backend/presentation/app.py \
  backend/presentation/routing.py \
  frontend-react/package-lock.json \
  frontend-react/package.json \
  frontend-react/playwright.config.ts \
  frontend-react/src/App.tsx \
  frontend-react/src/Assistant.tsx \
  frontend-react/src/Comparison.tsx \
  frontend-react/src/api.ts \
  frontend-react/src/contracts.ts \
  frontend-react/src/styles.css \
  streamlit_app/app.py \
  backend/environment/insights.py \
  backend/environment/locations.json \
  backend/environment/measurements.py \
  backend/environment/registry.py \
  backend/environment/transport.py \
  docs/FOUNDATIONS_IMPLEMENTATION_MAP.md \
  docs/FOUNDATIONS_REPORT.md \
  docs/FOUNDATIONS_VERIFICATION.md \
  docs/PROJECT_EXPLAINED/01_VISION_SCOPE.md \
  docs/PROJECT_EXPLAINED/02_ARCHITECTURE_LIFECYCLE.md \
  docs/PROJECT_EXPLAINED/03_TRAINED_NLP.md \
  docs/PROJECT_EXPLAINED/04_GROUNDED_GENAI.md \
  docs/PROJECT_EXPLAINED/05_ENVIRONMENTAL_DATA.md \
  docs/PROJECT_EXPLAINED/06_ANALYTICS_FORMULAS.md \
  docs/PROJECT_EXPLAINED/07_REACT_MAP_INSPECTOR.md \
  docs/PROJECT_EXPLAINED/08_FASTAPI_ENDPOINTS.md \
  docs/PROJECT_EXPLAINED/09_STREAMLIT_TECHNOLOGIES.md \
  docs/PROJECT_EXPLAINED/10_TESTING_LIMITATIONS.md \
  docs/PROJECT_EXPLAINED/11_VIVA_QUESTIONS.md \
  docs/PROJECT_EXPLAINED/12_DEMONSTRATION.md \
  docs/PROJECT_EXPLAINED/13_WINDOWS_GIT_HANDOVER.md \
  docs/PROJECT_EXPLAINED/README.md \
  docs/WINDOWS_FOUNDATIONS_REVIEW.md \
  frontend-react/src/Geospatial.tsx \
  frontend-react/src/Insights.tsx \
  frontend-react/src/LeafletMap.tsx \
  frontend-react/src/Measurements.tsx \
  frontend-react/src/PipelineInspector.tsx \
  frontend-react/src/TownMap.tsx \
  frontend-react/tests/e2e/foundations.spec.ts \
  frontend-react/tests/foundations.json \
  frontend-react/tests/foundations.test.tsx \
  frontend-react/tests/inspector.test.tsx \
  tests/environment/test_foundations.py \
  tests/fixtures/geocoding_evidence.json \
  tests/fixtures/supplemental_era5.json \
  tests/fixtures/supplemental_recent.json
git diff --cached --check
git diff --cached --stat
git diff --cached
# Recheck for real credentials and unintended files before the approved commit.
```

After explicit commit/push approval, commit with the agreed message, capture `git rev-parse HEAD`, then push only this new branch without force. Exact push/ref verification commands:

```bash
git push origin HEAD:refs/heads/feature/geospatial-intelligence-foundations
git rev-parse HEAD
git ls-remote origin refs/heads/feature/geospatial-intelligence-foundations refs/heads/master
```

Compare the full remote foundation SHA with local HEAD and remote master against its recorded pre-push SHA. Stop on any mismatch. These instructions do not authorize execution.

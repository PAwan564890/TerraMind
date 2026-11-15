# Preserve the TerraMind prototype and retrieve it on Windows

## Implementation review state — before authorized preservation

At implementation review, work remained in the existing cloud checkout on `master`, based on
`eb483eac04e73009bd7a8a87a0a0093a95f998f1`. The earlier prototype and new GenAI
files were mostly untracked. The only modified **tracked** file was `.gitignore`.
No branch had been created and nothing had been staged or committed at that
review. The user subsequently authorized creation and push of the feature
branch, with staged-diff review, tests and remote confirmation required. The
commands below describe that preservation procedure; use `git log` and the
remote branch to confirm its actual completion. No deployment is authorized.

Preservation feature branch: **`feature/grounded-genai-prototype`**.
This leaves the remote `master` branch unchanged and includes the entire earlier
prototype plus the GenAI continuation, so the earlier work is not lost.

## Audit performed

- No deletion since the start of the GenAI continuation; original NLP source,
  original API implementation, original tests, original requirements and NLP
  configuration remain unchanged.
- No candidate file over 5 MiB. The largest candidate remains the original
  NLP training JSONL, approximately 1.4 MB; no model-weight artifacts were found.
- Credential-pattern scan found no likely OpenAI/GitHub/AWS tokens or private
  keys in tracked or nonignored untracked candidates. This is a heuristic
  review, not a guarantee; manually inspect the staged diff before a commit.
- Test tokens are conspicuously fake `test-token-not-a-secret` values, used only
  with mocked transports; no real provider key is included.
- `.gitignore` retains its existing rules and adds `work/`, environment variants,
  `.venv-*/`, `.streamlit/secrets.toml`, and model-weight extensions. `.env.example`
  stays eligible for tracking. Do not use `git add -f` for ignored files.
- Machine paths were found only in evaluation/verification documentation:
  the supplied laptop location and historical cloud test commands. They are
  intentional explanatory text, not hardcoded application configuration.
  Runtime code resolves repository paths or uses environment configuration.
- Existing `work/` assets, old logs and intermediate transfer ZIPs remain
  untouched and are now ignored. Their earlier contents are not the current
  implementation and should not be used as a current release bundle.

## After explicit approval: cloud preservation

From the existing cloud checkout, with authenticated Git write access:

```bash
cd /workspace/TerraMind
git status --short --branch
git switch -c feature/grounded-genai-prototype
git add .gitignore backend/environment backend/genai backend/presentation streamlit_app tests/environment tests/genai tests/presentation docs/FINAL_ARCHITECTURE.md docs/FINAL_EVALUATION_DEMO.md docs/FINAL_VERIFICATION.md docs/GIT_PRESERVATION.md requirements-dashboard.txt requirements-prototype.txt scripts/inspect_model_artifacts.py scripts/verify_dashboard.py scripts/verify_demo.py scripts/verify_genai.py
git diff --cached --check
git diff --cached --stat
git diff --cached
```

Review the actual staged contents. The explicit staging list includes all
previously untracked prototype files and the new GenAI code/docs/tests but not
scratch, model checkpoints, `.env`, secrets, local Python environments or logs.
No staged content should include credentials. Then, only when commit/push are
approved:

```bash
git commit -m "Add grounded multilingual GenAI to TerraMind academic prototype"
git push -u origin feature/grounded-genai-prototype
```

Public clone access does not grant write access. Authenticate the Git client
using your approved GitHub credential mechanism before pushing; never embed a
token in the remote URL or command text. No force-push or merge is required.
If the target remote branch already exists unexpectedly before the first push,
stop rather than overwrite it or switch to another branch without authorization.

Until the approved commit and push succeed, the cloud changes **are not on
GitHub** and cannot be retrieved there from Windows. Downloading the current
GitHub default branch will still fetch the older NLP-only code.

## Windows: retrieve without changing the current working tree

After the feature branch has actually been pushed, in PowerShell:

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind'
git status --short --branch
git fetch origin feature/grounded-genai-prototype
git worktree add '..\TerraMind-genai-review' -b review/grounded-genai-prototype FETCH_HEAD
Set-Location '..\TerraMind-genai-review'
```

This creates a separate working directory for the **same repository**, leaving
your current checkout, uncommitted changes, original frontend and trained models
in the original folder intact. Use an unused review folder/branch name if either
already exists. No reset, forced checkout, stash or overwrite is needed. Keep
your original folder until you have reviewed and run the feature branch.

Activate your existing Python environment by its full path, or create the
isolated prototype environment documented in `FINAL_EVALUATION_DEMO.md`.
Installing `requirements-dashboard.txt` into an already working NLP environment
adds only presentation requirements. The GenAI HTTP client needs no new package.
Do not copy a Linux virtual environment to Windows.

The new worktree will not contain ignored original checkpoints. For a data-only
presentation select rule demonstration. To inspect the existing model files,
run `scripts/inspect_model_artifacts.py` from the original checkout (once the
helper is available there through your chosen reviewed integration), or point
an ignored local NLP config at the existing absolute model directory using
`TERRAMIND_CONFIG`. Keep matching intent/NER summaries, seed checkpoints,
thresholds, domain index and E5 cache together. Do not move or delete the
original models merely to test the new worktree.

## Start and verify

In backend PowerShell terminal, reviewed worktree, environment active:

```powershell
$env:TERRAMIND_DEMO = '1'
$env:TERRAMIND_LLM_PROVIDER = 'disabled'
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

In a second activated terminal, same reviewed worktree:

```powershell
$env:TERRAMIND_API_URL = 'http://127.0.0.1:8000'
python -m streamlit run streamlit_app/app.py --server.port 8501 --browser.gatherUsageStats false
```

Open http://localhost:8501. Select the historical example and recorded snapshot
for a network-independent data demo. Configure a real LLM privately as described
in `FINAL_EVALUATION_DEMO.md` if desired, restart the backend, then verify:

```powershell
python scripts/verify_genai.py --require-llm
python -m pytest -q
```

Without configured credentials the LLM verification is blocked; the ordinary
`python scripts/verify_genai.py` verifies real HTTP data behavior and explicitly
reports generation as skipped. Mocked tests are never evidence of live model
availability. No deployment is part of this workflow.

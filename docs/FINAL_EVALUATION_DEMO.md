# TerraMind final evaluation demonstration

## Scope and inspection findings

This is an academic environmental query and analytics prototype, not a complete
Earth System Digital Twin. Implementation is additive to GitHub commit
`eb483ea` (`master`, “Complete multilingual NLP subsystem”). No presentation
branch existed. The clone was clean before work. The original NLP engine, API contracts, tests and frontend files remain
unchanged. The GenAI continuation extends the existing presentation API/client
and adds Git ignore rules; previous prototype work is preserved.

The public branch contains **no frontend directory** and **no models directory**.
The laptop folder `C:\Users\pawan kumar singh\TerraMind` is not mounted in this
cloud environment; permission alone does not establish a filesystem connection.
Any frontend or trained artifacts present only on that laptop remain uninspected.
Do not replace the laptop checkout with the cloud clone. Use the separate
worktree retrieval procedure in `GIT_PRESERVATION.md`, preserving local files.
The implementation review preceded the subsequently authorized feature-branch
commit/push; Git history and the preservation report establish its outcome.

The existing NLP corpus is synthetic question/label data, not environmental
measurements. Original documentation and reported model-quality results remain
historical records; they do not describe the new rule demonstration.

## Install only the presentation dependencies in your working laptop environment

PowerShell, from the existing project root:

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind'
# Activate your existing working environment, if this is its path:
.\.venv\Scripts\Activate.ps1
python --version
python scripts/inspect_model_artifacts.py
python -m pip install -r requirements-dashboard.txt
```

Streamlit 1.41.1 supports Python 3.12 and runs as a separate HTTP client. The
additional dependency file does not upgrade PyTorch, Transformers, scikit-learn
or other NLP packages. Do not reinstall the original requirements into a working
model environment merely to run the dashboard.

### Optional isolated environment for a clone without an existing environment

The cloud test environment used Python 3.12.14, torch 2.5.1+cpu, Transformers
4.48.3 and the packages in `requirements-prototype.txt`. These differ from the
original repository pins; the original requirements are preserved. This setup
passed the code tests but has **not** loaded the absent original trained weights.

```powershell
py -3.12 -m venv .venv-demo
.\.venv-demo\Scripts\Activate.ps1
python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-prototype.txt
```

No pretrained downloads or model retraining are required for the rule demo.
The test suite creates tiny random BERTs to test training/checkpoint mechanics;
these are not TerraMind's trained models.

## Start the central FastAPI backend

Terminal 1, project root, with the appropriate environment activated:

```powershell
$env:TERRAMIND_DEMO = '1'
$env:TERRAMIND_LLM_PROVIDER = 'disabled' # data-only demo; optional provider setup below
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

URLs:

- API documentation: http://127.0.0.1:8000/docs
- Original model health: http://127.0.0.1:8000/health
- Presentation capabilities: http://127.0.0.1:8000/system

Run one worker. The original `/nlp/analyze` always attempts the original trained
pipeline; it does **not** fall back. Missing models produce degraded health and
HTTP 503 from that endpoint. Explicitly enabled `/demo/analyze` uses rules and
returns the existing `AnalyzeResponse` schema with conspicuous demo warnings.
Its confidence fields are 0, meaning **unmeasured**, not zero-probability model
predictions. The UI states this.

To disable demo rules, remove the environment flag and restart:

```powershell
Remove-Item Env:TERRAMIND_DEMO -ErrorAction SilentlyContinue
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

## Start Streamlit independently

Terminal 2, project root, same environment:

```powershell
$env:TERRAMIND_API_URL = 'http://127.0.0.1:8000'
python -m streamlit run streamlit_app/app.py --server.port 8501 --browser.gatherUsageStats false
```

Dashboard: http://localhost:8501

If checkpoints load, choose **Trained NLP**. Otherwise choose **Rule demonstration**.
Choose **Live Open-Meteo** for network retrieval. No weather API key is needed.

The original backend can still be run separately with its unchanged command:

```powershell
python -m uvicorn backend.api.app:app --port 8002
```

It offers the original NLP routes only. The dashboard requires the presentation
backend on port 8000 because it also calls `/system`, `/environment/session` and `/genai/explain`.
The original `/environment/query` remains available with its original contract.
There is no original frontend in the public branch, so no verified frontend
startup command can be supplied. If your laptop contains one, retain its own
startup command and API configuration; Streamlit is an independent client.

## Questions and expected behavior

Use a new conversation for an independent example. The example selector updates
the text box. Click **Analyze and retrieve** after selecting a question.

1. Historical English, reliable baseline:
   `Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.`
   Expected: `en`, `WEATHER_QUERY`, `loc:gangtok`, `TEMPERATURE` and
   `PRECIPITATION`, exact date range, seven ERA5 daily rows, charts and summary.
2. Hindi:
   `गंगटोक में 2025-01-01 से 2025-01-07 तक तापमान और बारिश दिखाओ।`
   Expected: `hi`, same canonical query and historical data.
3. Nepali:
   `गान्तोकमा 2025-01-01 देखि 2025-01-07 सम्म तापक्रम र वर्षा देखाउनुहोस्।`
   Expected: `ne`, same canonical query and historical data.
4. Recent Hindi:
   `गंगटोक में पिछले 7 दिनों का तापमान और बारिश दिखाओ।`
   Expected: seven completed local days, weather-model past data, explicitly
   distinguished from station observations and ERA5 reanalysis.
5. Recent Nepali:
   `गान्तोकमा पछिल्ला 7 दिनको तापक्रम र वर्षा देखाउनुहोस्।`
   Expected: `ne`, same recent period and canonical variables.
6. Comparison:
   `Compare temperature and rainfall in Gangtok and Namchi from 2025-01-01 to 2025-01-07.`
   Expected: two town series for the same period and a comparison table.
7. Current:
   `What is the temperature in Mangan today?`
   Expected: current model estimate with timestamp/interval plus one daily row.
   Today's daily values include forecast hours; they are not a completed-day
   observation. A single-day line chart has only one point.
8. Follow-up after a historical lookup: `And rainfall?`
   Expected: location/time inherited by the existing context resolver; inherited
   fields appear in `context_used`.
9. Clarification: `Show temperature in Gangtok.`
   Expected: explicit time requested, no retrieval.
10. Off-topic: `Tell me a joke.`
    Expected: out-of-domain status, no structured query or retrieval.

The live archive/snapshot Gangtok baseline returned mean daily temperature
11.2286 °C, minimum 4.9 °C, maximum 20.0 °C, and rainfall/precipitation 11.9 mm
for this particular point grid and period. These are reanalysis values, not
station measurements; a provider revision could change future live responses.

## Explicit network fallback

Select **Recorded snapshot · 1–7 Jan 2025** and use example 1, 2, 3 or 6 above.
Snapshots are actual Open-Meteo ERA5 responses recorded on 15 November 2026,
with original source URL and retrieval timestamp, in
`backend/environment/snapshots/`. They cover the three supported towns and
exactly 2025-01-01 to 2025-01-07. Other dates fail visibly, rather than being
replaced. Snapshot selection is explicit, never automatic. No fabricated data
is included. The UI distinguishes previously recorded data from live retrieval.

## Verify the whole workflow

With the backend running:

```powershell
python scripts/verify_demo.py --source snapshot
python scripts/verify_demo.py --source live
python scripts/verify_dashboard.py
python scripts/verify_genai.py
python -m pytest -q
```

For restored trained models, add `--mode trained` to the verification script.
Actual model results may differ from the rules; use clarifications honestly.
Do not claim original checkpoint inference passed until that mode is verified.

### Verification performed in cloud

- Original baseline: **412 passed** before integration (15.23 seconds).
- Final test total and UI verification: see `FINAL_VERIFICATION.md`.
- Real FastAPI HTTP: health reported absent language checkpoint; original
  `/nlp/analyze` returned 503; explicit demo endpoint worked.
- English/Hindi/Nepali historical questions each fetched seven live ERA5 rows.
- Current Mangan and recent Gangtok requests returned weather-model results.
- Streamlit health returned 200. Streamlit's AppTest exercised its actual
  script against the running HTTP backend: snapshot lookup, town comparison,
  a live Nepali request, and clearing old results after invalid input.
- Model training quality and original laptop artifacts were not verified.

## Troubleshooting and limitations

- **Missing models:** run the inventory helper on the laptop. Expected artifacts:
  `models/language_detection/hi_ne.joblib`, `models/intent/full/summary.json`,
  `models/intent/full/seed_<best_seed>/` (weights, model config, tokenizer),
  equivalent `models/ner/full/`, `models/decision/thresholds.json`, and
  `models/decision/domain_index.npz`. Each task's best seed comes from its own
  summary. The E5 encoder `intfloat/multilingual-e5-small` resolves through the
  Hugging Face cache; prefix is `query: `, max length 64, normalized mean pooling.
  Preserve matching models, index and thresholds as a set. Do not train XLM-R
  merely to make this demo start. Only load trusted local joblib files.
- **Backend unreachable:** check both terminals, port 8000 and
  `TERRAMIND_API_URL`. Start `backend.presentation.app`, not just the original app.
- **Demo route disabled:** set `TERRAMIND_DEMO=1` in the backend terminal and
  restart; this never makes `/nlp/analyze` a rule endpoint.
- **Provider timeout/429/503:** retry later or explicitly choose the recorded
  snapshot. The first cloud current-weather request timed out; subsequent live
  calls succeeded. No availability guarantee is made.
- **Unsupported geography:** only Gangtok, Namchi and Mangan **town points**.
  District/state/river queries request clarification. Coordinates were checked
  against Open-Meteo's GeoNames geocoder, restricted to India/Sikkim.
- **Time:** local timezone Asia/Kolkata; past N days exclude today. Months/years
  use calendar arithmetic. At most 366 days per query. ERA5 ranges end at least
  six days ago; recent/model ranges start within the last 92 days. Longer
  climate analyses and future-period requests are unsupported.
- **Scientific meaning:** Open-Meteo combines models, not a local gauge network.
  Historical data use explicitly selected ERA5. Grid elevation/resolution can
  poorly represent Himalayan microclimates. No district aggregation is done.
- **Rain versus precipitation:** `PRECIPITATION` maps to precipitation_sum (rain,
  showers and snow water equivalent). Rainfall is archive rain_sum, or forecast
  rain_sum + showers_sum. Both are mm; temperature is °C. Current precipitation
  uses the provider's interval, not a daily sum. Missing entries stay null;
  summaries disclose valid-day counts and partial totals.
- **Intent answer kind:** the original query contract may say `observation` for
  a lookup. The result's `data_kind` and source warnings describe the actual
  evidence (reanalysis/model); the UI never calls it a station observation.
- **Rules:** limited vocabulary, naive native-script language cues, one intent
  and period; no measured accuracy or confidence. Complex, mixed-language,
  romanized, implicit, negated or unknown-location questions may be misread.
  Use the documented small query set for the demonstration. Original model
  limitations and pending fluent-speaker review still apply.
- **No advanced claims:** no disaster prediction, future forecast service,
  validated climate trend significance, RAG or scenario simulation. An optional
  constrained LLM explanation layer is implemented, described below.
- **Operation:** one process, in-memory context, no authentication/rate limiting.
  Run locally for evaluation, not as a public production service.

## Five-to-seven minute presentation script

**0:00–0:45 — Purpose.** “TerraMind is an academic prototype toward an Earth
System Digital Twin for Sikkim. It separates language understanding from
retrieval and calculations so every number has a source.” Show supported
languages, town scope and limitations.

**0:45–1:30 — Architecture and honesty.** Explain original XLM-R intent/NER,
language classifier, E5 domain check, normalization/context/validation. “This
cloud copy has no trained checkpoints, so today I am explicitly demonstrating
rules for the first three steps. The original model endpoint is preserved.”
Show the mode label and model health.

**1:30–2:45 — English to data.** Run the historical English query. Inspect
entities, canonical location/variable IDs and dates. Show seven daily rows,
charts, mean/min/max and rainfall. Explain grid reanalysis versus measurements,
source URL, original retrieval time and CC BY attribution.

**2:45–3:45 — Languages and context.** Enter the Hindi and Nepali historical
questions. Show the same canonical query. Run “And rainfall?” to display
inherited slots, clearly labelled as deterministic context resolution.

**3:45–4:45 — Comparison.** Compare Gangtok and Namchi over the same seven days.
Explain that the statistics are calculated from available provider data;
these short series do not establish a climate trend or predict hazards.

**4:45–5:00 — Failure handling.** Ask a query with no period, then an off-topic
question. Show clarification and no retrieval. Explain null handling and the
explicit recorded-data option if live networking fails.

**5:00–5:30 — Optional GenAI.** Show the separate AI explanation section.
If configured, explain that a real LLM selects facts, which are checked against
server calculations before multilingual rendering. Try a follow-up. If not
configured, show the explicit disabled status; do not claim a live model demo.

**5:30–6:30 — Evidence and roadmap.** Show passing original/new test counts.
State that original trained inference still needs the laptop artifacts. Next
steps: restore and verify checkpoints, fluent-speaker review, additional
validated locations/datasets and scientifically evaluated models. “This is a
working query-to-data academic prototype; the complete digital twin remains
the roadmap.”


## Optional genuine LLM configuration

No API key was available during cloud verification. Provider success/failure,
hallucination rejection and successful UI rendering were tested with mocked
provider responses; real model inference has not been claimed. No extra Python
packages are required for the new client (existing httpx is used).

### OpenAI (PowerShell, backend terminal)

With the project environment activated, configure the model and supply a real
key privately. This reads the key without echoing it or embedding it in shell
history; do not paste credentials into chat or commit them:

```powershell
$env:TERRAMIND_DEMO = '1'
$env:TERRAMIND_LLM_PROVIDER = 'openai'
$env:TERRAMIND_LLM_MODEL = 'gpt-4.1-mini'
$env:TERRAMIND_LLM_BASE_URL = 'https://api.openai.com/v1'
$env:TERRAMIND_LLM_TIMEOUT_SECONDS = '15'
$llmCredential = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $llmCredential).Password
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

Use a model available to your account that supports Chat Completions JSON mode,
`temperature` and `max_tokens`; the example is configurable, not a verified
model/account entitlement. If `TERRAMIND_LLM_API_KEY` was previously set, it takes
precedence; remove a stale value with
`Remove-Item Env:TERRAMIND_LLM_API_KEY -ErrorAction SilentlyContinue`.
Restart the backend after configuration changes. Keys exist only in the current
terminal/process environment; this does not create or edit `.env`.

### Another OpenAI-compatible provider

```powershell
$env:TERRAMIND_LLM_PROVIDER = 'openai_compatible'
$env:TERRAMIND_LLM_MODEL = Read-Host 'Provider model/deployment name'
$env:TERRAMIND_LLM_BASE_URL = Read-Host 'Trusted HTTPS API root, including /v1'
$llmCredential = Read-Host 'Provider API key' -AsSecureString
$env:TERRAMIND_LLM_API_KEY = [System.Net.NetworkCredential]::new('', $llmCredential).Password
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

No provider endpoint or credential is invented automatically. Remote URLs must
use HTTPS; explicit local HTTP is accepted only for localhost development with
a configured token. Redirects are not followed. The chosen provider must be
directly reachable and support the documented Chat Completions JSON protocol.

On Linux/cloud, export the same nonsecret variables, then read the key privately:

```bash
export TERRAMIND_LLM_PROVIDER=openai
export TERRAMIND_LLM_MODEL=gpt-4.1-mini
export TERRAMIND_LLM_BASE_URL=https://api.openai.com/v1
read -r -s -p 'OpenAI API key: ' OPENAI_API_KEY
export OPENAI_API_KEY
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

Run the separate Streamlit command from the earlier section. Select **Explanation
language** (Automatic/English/Hindi/Nepali), submit the historical example, and
inspect **AI-generated explanation** below the environmental evidence. The
explanation includes locations, dates, units, data kind and original source
attribution. The LLM selects a structured explanation plan; validated templates
render it. It does not write unrestricted scientific prose or calculate values.

Use **Follow-up about these results**, e.g. “Explain the rainfall summary”,
“वर्षा का सारांश समझाएँ”, or “वर्षाको सारांश बुझाउनुहोस्”. Only the current
server-stored result is available. The opaque context expires after 15 minutes;
new successful retrieval replaces it. Different places/dates need a new query.
The model judges relevance; every accepted claim must still match the stored
facts exactly. New conversation clears the dashboard's previous result/token.

### Verify without confusing mocks and live inference

Backend running, in a separate terminal:

```powershell
# Real HTTP + recorded environmental data; disabled LLM explicitly reports SKIP.
python scripts/verify_genai.py
# Require an actual successful provider call and contextual follow-up per language.
python scripts/verify_genai.py --require-llm
# Also retrieve weather live rather than using recorded ERA5 evidence.
python scripts/verify_genai.py --source live --require-llm
```

`--require-llm` exits unsuccessfully if configuration/credentials are missing or
provider generation/validation fails. It never substitutes mocked text. The
regular pytest GenAI tests are deliberately mocked, avoid API costs and do not
prove provider/model availability.

For the no-provider demonstration, set
`$env:TERRAMIND_LLM_PROVIDER = 'disabled'` and restart. The dashboard still shows
real environmental data/analytics with an explicit explanation-unavailable
notice; there is no fabricated AI response. Provider timeouts/authentication/
rate limits/failures and rejected hallucinations also leave the data accessible.

### Security and practical limits

The LLM receives the selected question and environmental fact/source catalogue,
not session tokens, credentials or arbitrary prior chat history. Avoid personal
information in follow-ups. No raw provider output or secret is logged/rendered.
Unknown facts, invented numbers, source substitutions and arbitrary prose are
rejected. Units, place, period and source must match exactly. Rendering is plain
text with mandatory server attribution and limitations. This provides grounded
claim selection, not validated causal reasoning, general RAG or open-ended
research. Hindi/Nepali wording still needs fluent-speaker review.

Socket timeouts default to 15 seconds, configurable from 1 to 30; connect is
capped at 5. Provider responses are size-limited, no automatic paid retries are
made, and graceful failure is explicit. This remains a local one-worker demo
without production authentication/rate limits. Do not publish it with a paid
provider key. See `GIT_PRESERVATION.md` for safe branch preservation and Windows
retrieval instructions. Commit/push completion must be checked against GitHub;
no deployment is part of the authorized preservation step.

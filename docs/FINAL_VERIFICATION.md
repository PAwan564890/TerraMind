# Final verification record — environmental prototype plus grounded GenAI

Verified 15 November 2026 in the existing managed Linux cloud checkout,
Python 3.12.14. Original base is `eb483eac04e73009bd7a8a87a0a0093a95f998f1`
on `master` at implementation review. No fresh clone or reset was performed.
The user subsequently authorized feature-branch preservation, subject to tests,
full staged-diff review and remote confirmation. This document records the
implementation verification; Git history and the preservation report establish
the later commit/push outcome. No merge or deployment is authorized.
The earlier prototype work was retained. This is not a Windows verification.

## Automated results

| Suite | Result |
| --- | --- |
| Original baseline, historical run | 412 passed in 15.23 seconds |
| Previous complete prototype suite | 460 passed in 18.14 seconds |
| New GenAI tests in this continuation | 61 passed as part of complete run |
| Complete current suite | **521 passed, 2 warnings in 21.80 seconds** |

Command:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 HF_HUB_OFFLINE=1 \
  /workspace/terramind-env/bin/python -m pytest -q
```

All 412 original tests and 48 earlier prototype tests remain present and pass.
The two warnings are dependency deprecations: Starlette's httpx TestClient
adapter and Streamlit's use of the old Altair theme API. There are no failures.
CPU PyTorch 2.5.1 and alternate compatible package versions recorded in
`requirements-prototype.txt` were used; original dependency pins were preserved.
No additional package was needed for GenAI. Tiny random BERT training inside
the original tests checks mechanics, not TerraMind model quality.

### New mocked-provider coverage

External LLM calls in pytest are **mocked** with `httpx.MockTransport`. No paid
model, real provider credential, or genuine provider inference was used.
Environmental evidence comes from the previously recorded real ERA5 snapshots,
not invented weather values. Coverage includes:

- Valid English/Hindi/Nepali explanation plans, localization and mandatory
  original source, unit, location and period information.
- Numeric hallucinations, wrong units/dates/locations/source IDs, invented facts,
  duplicate claims/JSON keys, wrong language, arbitrary prose and extra fields.
- Prompt-injection isolation: untrusted question text cannot become rendered
  instructions, numbers, HTML or source citations.
- Provider 401/403/429/500/503, read timeouts and malformed/truncated/oversized
  provider output; safe fallback without returning raw provider content.
- Missing/invalid provider configuration and credentials produce disabled
  generation without an outgoing request.
- Deterministic comparison arithmetic and exclusion of incomplete comparisons.
- Context copies, session binding, replacement, capacity limits and TTL expiry;
  client-uploaded fake environmental results are refused.
- FastAPI's original NLP/health/environment contracts plus new session/explain
  routes; existing environmental data remain available when generation fails.
- HTTP client sequencing through FastAPI with mocked transport bridging.
- Streamlit AppTest against FastAPI TestClient, with mocked external model:
  successful Hindi generation and contextual follow-up, rejected hallucination,
  provider failure and disabled provider. All four states retain seven weather
  metrics and both chart elements, with the rule-demo warning visible.

These tests demonstrate implementation behavior and validation. They do not
establish live model availability, quality or follow-up relevance accuracy.

## Real HTTP checks with no configured LLM

A new verification backend was run on localhost:8003 to avoid replacing any
pre-existing servers:

```bash
TERRAMIND_DEMO=1 TERRAMIND_LLM_PROVIDER=disabled HF_HUB_OFFLINE=1 \
  /workspace/terramind-env/bin/python -m uvicorn \
  backend.presentation.app:app --host 127.0.0.1 --port 8003
```

`python scripts/verify_genai.py --api-url http://127.0.0.1:8003` used real HTTP:

```text
Provider configured: False
en environment PASS; GenAI status: disabled
SKIP live LLM: no credentials/provider; real data and analytics verified.
hi environment PASS; GenAI status: disabled
SKIP live LLM: no credentials/provider; real data and analytics verified.
ne environment PASS; GenAI status: disabled
SKIP live LLM: no credentials/provider; real data and analytics verified.
HTTP verification finished. Disabled/skipped generation is not a live LLM pass.
```

This run used actual recorded ERA5 data for 1–7 January 2025. Each language
returned seven daily values, source attribution, a server-issued context token
and no AI response. No model text was fabricated.

`python scripts/verify_demo.py --api-url http://127.0.0.1:8003 --source live`
also passed all English/Hindi/Nepali historical questions through real HTTP and
**live Open-Meteo** retrieval, with disabled generation. Gangtok's seven-day
mean temperature was 11.2285714286 °C for that provider response/grid point.
The NLP mode was explicitly labelled rules, not trained inference.

The original `/nlp/analyze` still returned 503 with missing model artifacts;
health reported `models_loaded=false`. The original `/environment/query` shape
was verified unchanged in the API tests. `/system` adds safe GenAI capability
metadata without credentials. New routes use separate response envelopes.

## Real dashboard script against running HTTP backend

Reproduction:

```bash
TERRAMIND_API_URL=http://127.0.0.1:8003 \
  /workspace/terramind-env/bin/python scripts/verify_dashboard.py
```

Final run:

```text
PASS snapshot dashboard, metrics and two charts
PASS two-town comparison
PASS live Nepali query through Streamlit -> HTTP FastAPI -> Open-Meteo
PASS failed input clears previous data
```

An earlier recent-weather attempt failed on provider/network availability;
an explicit retry succeeded. No live failure was silently replaced by recorded
data. The dashboard's AI section correctly reported the disabled provider.
Successful AI-section rendering/follow-up was tested only with mocked provider
responses in the automated suite. This is scripted interaction verification,
not a human visual review, accessibility audit or Windows/browser load test.

## Genuine LLM verification: blocked, not claimed

No `TERRAMIND_LLM_API_KEY` or `OPENAI_API_KEY` was configured for a live provider.
A real OpenAI-compatible client is implemented, but no real model request has
been verified. The helper deliberately fails in `--require-llm` mode without
credentials; there is no runtime mock provider fallback.

To complete genuine verification, privately set provider/model/API root/key in
the backend environment, restart it, and run:

```powershell
python scripts/verify_genai.py --require-llm
python scripts/verify_genai.py --source live --require-llm
```

This requires successful validated provider responses and contextual follow-ups
in all three languages. Unsupported model JSON protocol, refusals or strict
validation failure will fail this verification while leaving weather data
available. Instructions and security limits are in `FINAL_EVALUATION_DEMO.md`.

## Preservation and Git audit

No files were deleted relative to the start-of-continuation file hash inventory.
Original `backend/nlp/`, `backend/api/`, configs, requirements and tests are
unchanged. Existing prototype changes were extended in place, not replaced.
At implementation review, the only changed originally tracked file was
`.gitignore`; presentation/GenAI implementation and final docs were untracked
from the original base.
Nothing was staged at implementation review. `git diff --check` passed.

The current candidate scan found no likely credential/private-key patterns
and no file over 5 MiB. The largest candidate is the original 1.4 MB NLP training
JSONL. Machine-specific paths occur only in explanatory startup/verification
and Git/Windows documentation, not runtime configuration. `work/`, secret env
variants, local environments, Streamlit secrets and model weights are ignored;
`.env.example` remains eligible for tracking. This is a heuristic audit plus
scope inspection, not a guarantee against every possible secret format.

Authorized preservation branch: `feature/grounded-genai-prototype`. A fresh
pre-preservation test run confirmed **521 passed, 2 warnings in 23.15 seconds**.
Before creating the branch, GitHub advertised only the original `master` head;
the target feature branch was absent. Ignored files were caches/scratch only,
with no model artifacts present. A credential-bearing URL scan matched only
the deliberate `user:password` negative test fixture. Commit and push completion
require separate confirmation against the remote HEAD. `GIT_PRESERVATION.md` contains the explicit staging list, review and
approved commit/push steps, and a separate Windows worktree retrieval procedure
that preserves the existing laptop checkout and local artifacts.

## Remaining limits

- Original fine-tuned language/intent/NER artifacts and matching thresholds,
  domain index/E5 cache are unavailable here. Genuine trained NLP inference
  remains unverified; the rule path is always visibly labelled.
- Live LLM verification requires credentials and a compatible model. Tests
  cannot establish actual provider/model availability or translation quality.
- Generation is constrained LLM fact selection followed by validated localized
  templates, not unrestricted scientific prose or general conversation. Every
  accepted claim is grounded, but follow-up relevance remains model-dependent.
- Context is local, bounded and expiring, with no production authentication or
  public rate limits. It is not a production multi-user deployment.
- No station-observation integration, district/state aggregates, validated
  long-term trend significance, disaster predictions, scenario engine or RAG.
- Windows-only files and any original laptop frontend remain inaccessible and
  untouched. GitHub cannot supply these uncommitted cloud additions until an
  explicitly approved preservation commit/push has succeeded.

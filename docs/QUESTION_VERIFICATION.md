# Question handling verification and delivery

Scope: additive changes on `feature/grounded-genai-prototype`, parent `efccbac823e4d6ac9d1142bd9bef28b15ac2cdd9`. No commits or pushes performed. Full audit, capability matrix, limitations, API contract, examples and Windows startup instructions: `QUESTION_CAPABILITIES.md`.

## Results

- Full backend suite: **771 passed** (original 715 plus 56 new regressions). No existing backend tests removed or changed. Two existing dependency warnings: Starlette/httpx adapter and Streamlit/Altair themes.
- React: **48 passed** (previous 43 plus 5 routing tests). Existing assertions preserved; the original environment-path unit tests explicitly mock the new preflight route as `environment`.
- Real development HTTP/browser integration: **5 passed**.
- Built production-preview HTTP/browser integration: **5 passed**.
- TypeScript and Vite production build: **passed**.
- Original ISO-date, grounded-numeric, provider diagnostics/retries, source attribution, environmental retrieval and Streamlit regression tests remain included in the complete suite.
- No changes to trained checkpoint files, environmental provider, data snapshots, deterministic analytics, numerical fact compiler, LLM requests, provider client, backend GenAI validation or Streamlit source.

Commands used:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 HF_HUB_OFFLINE=1 HF_HOME=/workspace/TerraMind/work/huggingface /workspace/terramind-env/bin/python -m pytest -q
cd frontend-react
npm test
npm run build
CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e
REACT_TEST_URL=http://127.0.0.1:4173 CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e
```

Fresh current-code backend: 127.0.0.1:8005, explicitly enabled rule demo and disabled LLM, Vite proxy target 8005. React development 5173; built preview 4173. Windows guide uses the normal 8000 target; no claim of access to local Windows files or ports.

## Genuine versus mocked evidence

Genuine HTTP browser checks exercise the running FastAPI application and React proxy, recorded ERA5 weather, same-period charts, mobile layout, keyboard access, actual OpenAPI/health and the new curated-reference/unsupported routes. Four browser tests use actual backend responses. One test explicitly intercepts only the AI explanation to verify successful evidence presentation without provider credentials; its environmental retrieval is real recorded data. All five pass on both development and built preview.

A separate genuine live Open-Meteo request through `http://127.0.0.1:5173/api` used the question “How much did it rain in Gangtok during the first week of January 2025?”. Routing selected `environment`; the explicitly labelled rule demonstration produced 2025-01-01 to 2025-01-07. Actual live ERA5 retrieval returned exactly seven daily rows, 11.9 mm rainfall and original Open-Meteo/Copernicus attribution. AI status was `disabled`; no fabricated LLM success was returned. This is live weather verification, not trained-model verification.

Real HTTP knowledge requests returned English ERA5, Hindi climate change and Nepali rainfall-versus-precipitation summaries with their trusted citations. No LLM call or measured result was required. A warmer-town question against a single-town session was correctly `unsupported`.

Original pipeline wiring is tested using explicitly scripted detector/classifier/NER outputs, including the rain synonym; those tests verify preservation of classifier labels, actual normalizer/structurer behavior, original FastAPI contracts and real recorded environmental retrieval. They do not establish live trained-model paraphrase accuracy. Provider integration, timeouts, failures and hallucination rejection are mocked tests. No cloud access to the user's original model checkpoints or private Groq credentials was available.

General-reference pages were actually fetched and inspected. Geocoding searches were actually performed; they are investigation evidence, not an enabled dynamic geocoding feature. Ambiguous results are why coverage was not expanded.

## Coverage of requested cases

| Requested case | Evidence |
|---|---|
| Existing Gangtok query | Original date workflow regressions and real browser/snapshot workflow |
| Hindi and Nepali | Scripted original-pipeline tests with actual calendar normalization and recorded retrieval; native knowledge tests |
| Paraphrases | Named month/year, leap month, first week, last named month, bounded rain/temperature/comparison follow-ups |
| Missing dates | Existing environmental adapter tests; missing-context clarification; no default data synthesized |
| Ambiguous locations | New route regression for Gangtok or Namchi; original unresolved-location validation |
| Unsupported locations/measurements | Route guards and existing strict provider adapter tests |
| General questions | Seven-topic multilingual catalogue tests, full-match/injection exclusions and genuine browser HTTP |
| Session follow-ups/expiry | Valid server-owned context, wrong owner, expiry and missing-metric tests |
| Groq/Open-Meteo failures | Original complete regression suite, unchanged provider implementations; no fabricated fallback |
| Hallucination prevention | Original exact claim/source/numeric validation plus new context-bounded paraphrase rejection |
| Comparison accuracy | Two-town recorded ERA5 values, server-computed left-minus-right difference, source IDs, °C, dates; partial coverage refuses comparison |
| Units and dates | Existing strict upstream unit/date alignment tests plus exact 1–7 January regression |
| React and Streamlit | 48 React tests, 5 checks on each browser mode, existing Streamlit AppTest cases preserved |

## Exact delivery files

Modified:

- `backend/genai/questions.py`
- `backend/nlp/normalization/explicit_dates.py`
- `backend/nlp/normalization/time_parser.py`
- `backend/presentation/app.py`
- `frontend-react/src/Assistant.tsx`
- `frontend-react/src/api.ts`
- `frontend-react/src/contracts.ts`
- `frontend-react/tests/app.test.tsx`
- `frontend-react/tests/e2e/workflow.spec.ts`

Created:

- `backend/nlp/normalization/calendar_periods.py`
- `backend/presentation/knowledge.py`
- `backend/presentation/routing.py`
- `tests/regression/test_question_expansion.py`
- `docs/QUESTION_CAPABILITIES.md`
- `docs/QUESTION_VERIFICATION.md`

New API: only `POST /assistant/route`. Existing NLP/environment/GenAI response shapes unchanged. No new Python/npm dependencies or secrets. Secret-pattern scan found no matches in the delivery files; generated artifacts remain ignored. No master-branch changes.

## Evaluation recommendation

**Conditional GO for the academic prototype after a brief Windows smoke check.** Preserve the currently proven commit as a fallback. Verify the new route after restarting FastAPI, genuine trained month/first-week questions, two-town warmer follow-up and live Groq explanations in all three languages. The cloud verifies the integration and deterministic corrections, not unavailable trained-model accuracy or provider credentials.

**NO-GO for claims of arbitrary-question competence, district/state averages, additional measured variables or towns, causal explanations, hazard prediction, or a production operational digital twin.** Knowledge is a finite curated topic catalogue. Follow-ups are bounded by stored facts and language formulations. Warmer answers show the validated left-minus-right mean-temperature difference; weekly temperature summaries use mean/min/max and do not invent start/end changes or climate significance. Other week conventions require explicit dates. New geocoding and variable adapters were intentionally deferred.

General knowledge is presently routed in React; Streamlit remains an independent backup for the existing environmental workflow. This is a local single-process academic application, not an authenticated multiuser deployment. A new React client needs the new backend route; do not run it against an old already-imported backend. No deployment or Git preservation has been performed.

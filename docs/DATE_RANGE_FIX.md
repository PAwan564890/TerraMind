# Explicit date-range correction

Base: `3523cac0f824768860b6a7a2902098d75adceeaf` on
`feature/grounded-genai-prototype`. This note records the verified correction
reviewed before the subsequently authorized preservation commit/push. Git history
and remote verification establish its preservation status. No model weights
were modified and no retraining occurred.
The earlier final verification documents describe the original base prototype;
this note records the subsequent date-normalization correction.

## Confirmed root cause

Reported question:

```text
Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.
```

Before the correction, the shared deterministic `parse_time()` had year-range,
relative/current and single-year rules, but no explicit calendar-date rule.
`_SINGLE_YEAR` matched `2025` inside `2025-01-01` and constructed January 1 to
December 31. It did not parse the requested January 7 endpoint at all. This
behavior was reproduced directly on the original code in the cloud.

`EntityNormalizer.normalize(..., TIME, ...)` calls `parse_time()` for each
model-predicted span. `build_turn()` then took the first resolved TIME entity;
whole-query time parsing was only a fallback when no TIME entity resolved.
Therefore the same year expansion occurred with no TIME spans, a year-only span,
a first-date span, or two separate date spans. All four paths were reproduced
before the fix. A year inferred from a partial entity could also take precedence
over the more specific explicit dates in the full question.

The query schema and environmental retrieval did not invent December 31. They
accepted and used the already incorrect NLP period. The reported Windows
annual total of 5519.8 mm was not independently reproduced in the cloud; the
wrong annual structured period itself was reproduced exactly.

The Windows model's exact TIME spans are unknown here. The cloud has no original
trained checkpoints, so no claim is made to have rerun those weights. The
classifier's reported `CLIMATE_TREND` prediction is retained in the regression
fixtures. It is not changed to a weather intent to hide the issue.

## Minimal runtime correction

- New `backend/nlp/normalization/explicit_dates.py`: explicit calendar-date
  parser and typed `ExplicitDateError` using the existing input-error contract.
- Modified `backend/nlp/normalization/time_parser.py`: full-query explicit dates
  precede partial TIME spans and generic year rules.
- Modified `backend/nlp/query/structurer.py`: full-query explicit dates precede
  the first resolved TIME entity, **before** NLP context resolution/storage.

The trained detector, classifier, recognizer, their confidence/decision logic,
model-loading code and weights are unchanged. No runtime demo substitution is
introduced. Existing schemas, endpoints and environmental result contracts are
unchanged. New provenance warning: `explicit_time_from_text`.

With the fix the period is:

```json
{"type":"date_range","start":"2025-01-01","end":"2025-01-07"}
```

## Supported formats and validation

Examples:

- `2025-01-01 to 2025-01-07` (also through, until, till, or a spaced dash).
- `between 2025-01-01 and 2025-01-07`.
- `1 January 2025 to 7 January 2025`.
- `January 1, 2025 through January 7, 2025`.
- `1st Jan. 2025 until 7th Jan. 2025`.
- `1–7 January 2025` and `January 1–7, 2025`.
- Hindi/Nepali questions with ISO dates and `से` / `देखि`, including Devanagari
  numerals, normalize to the same canonical period.
- A single explicit date (`on 2025-01-07`) is one day, not an entire year.

Named-month support is English Gregorian month names/abbreviations and does not
depend on Windows/Linux locale. Hindi/Nepali month names, Bikram Sambat dates,
month-only periods and arbitrary natural-language date expressions are not
implemented. Unrecognized phrasing outside the documented date-like guards
remains a parser coverage limitation. Use complete ISO dates for evaluation.

Invalid calendar dates, reversed explicit ranges, multiple periods, incomplete
endpoints and ambiguous slash dates produce the original FastAPI error shape:
HTTP 422, `detail.code = "invalid_time_period"`. They do not silently expand
into a year, silently reorder explicit dates, retrieve data, or replace the
last valid NLP conversation period. Year-only behavior (including its existing
reordering rule) is preserved for compatibility with the original tests.

The environmental layer continues to enforce its existing limits: dates on or
after 1940-01-01, no future ranges, at most 366 inclusive days, and the current
ERA5-delay/recent-model-window restrictions. Over-limit requests ask for
clarification before contacting the provider. No truncation or clamping occurs.

## Verification

Full command:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 HF_HUB_OFFLINE=1 \
  /workspace/terramind-env/bin/python -m pytest -q
```

Result: **597 passed, 2 warnings in 19.93 seconds**.

All 521 prior tests, including the original 412, remain present and pass.
The 76 added cases cover date formats, invalid/ambiguous inputs, chronology,
leap/cross-year/single-day boundaries, partial or absent NER spans, preservation
of trained intent outputs, NLP follow-up context, API error shape, retrieval
bounds (including 366-day inclusivity), sources, summaries, GenAI context and
Streamlit charts/cards.

Tests are in:

- `tests/regression/test_explicit_dates.py`
- `tests/regression/test_explicit_date_workflow.py`

The workflow tests use the **original NlpPipeline** with scripted detector,
intent and NER outputs, not live model checkpoints. They deliberately hold the
intent at `CLIMATE_TREND` and exercise no/missed/year-only/truncated/separate/
full TIME spans. This injection exists only in tests. Weather evidence in the
automated tests is the actual recorded ERA5 snapshot, with seven rows and
11.9 mm rainfall. GenAI responses in those tests are mocked. The Streamlit test
uses the normal trained-endpoint route with an injected test pipeline; it is
not proof of actual trained-model inference.

A separate successful **live Open-Meteo** request was made through FastAPI
TestClient and the original production pipeline with scripted model outputs:

- Retained intent: `CLIMATE_TREND`.
- Corrected dates: 2025-01-01 to 2025-01-07.
- Live ERA5 rows: 7.
- Rainfall: 11.9 mm at the configured Gangtok grid point.
- Provider URL start_date/end_date: exactly the requested dates.
- Stored environmental context and every compiled GenAI fact: the same period.
- LLM disabled in that live check; no live LLM claim is made.

Chart date indices and displayed cards derive from those same validated daily
rows, and are checked with Streamlit AppTest. No chart/UI/business-logic rewrite
was needed. Dependency warnings are the existing Starlette/httpx and
Streamlit/Altair deprecations.

## Revalidate the original checkpoints on Windows after transferring the fix

After the preservation push is confirmed, verify that the fetched feature
branch includes the correction commit before transferring it. Activate the
already working Windows environment and run from its project root:

```powershell
@'
from datetime import date
from backend.core import load_settings
from backend.nlp.pipeline import NlpPipeline
p = NlpPipeline.from_settings(load_settings())
r = p.analyze("Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.")
print(r.model_dump_json(indent=2))
assert r.structured_query is not None
assert r.structured_query.time_period.start == date(2025, 1, 1)
assert r.structured_query.time_period.end == date(2025, 1, 7)
'@ | python -
```

Restart the existing FastAPI process to load the changed Python modules, then
start a **new conversation** in Streamlit to avoid previously stored annual
context. Submit the same question in Trained NLP mode. Verify the structured
query, seven table/chart dates, summary, source request parameters and any
explanation/follow-up period. The parser correction cannot repair results or
contexts already produced by a running old backend. No weights need changing.

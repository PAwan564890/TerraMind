# Stored environmental follow-up correction

Base: `23cd38b9a2fb7e66f35fca950f882c553451411c` on
`feature/grounded-genai-prototype`. This note records the implementation review
before the subsequently authorized preservation commit/push. Git history and
remote verification establish the final preservation status.
No trained checkpoints, NLP inference, weather retrieval, analytics, API schemas,
provider credentials or model-loading configuration were changed.

## Evidence and root cause

Reported live Windows verification:

```text
Provider configured: True
en environment PASS; GenAI status: ok
AssertionError: The stored results cannot answer this question. Submit a new environmental query for different places or dates.
```

The question was `Explain the mean daily temperature in these stored results.`
It is a supported summary request, not a request for new observations or a causal
explanation. The verifier defaults to the recorded 1–7 January 2025 snapshot,
which contains `temperature_mean_c = 11.23 °C` as a compiled canonical fact.

In the inspected service, the exact reported message occurs **only** after:

1. A non-null environmental context was found.
2. A provider was configured and a nonempty fact catalogue was compiled.
3. A provider response arrived and parsed into the strict Plan schema.
4. The response language matched the requested language.
5. The model said `answerable=false` with an empty claims list.

A missing/expired/wrong-session context instead returns `no_context` with a
different message. Missing facts also have a different message. This failure
therefore points to the model's negative answerability decision, not that context
lookup/expiry branch or an HTTP/JSON error. There was no separate follow-up
classifier: that decision was delegated entirely to the LLM. No deterministic
mapping bound the verification question to its available summary metric.

The old behavior was reproduced locally with a valid stored context, the real
recorded snapshot, and a **mocked** provider returning that negative Plan. The
result exactly matched the reported error despite the mean-temperature fact
being present. The private Groq response and original trained checkpoints are
not accessible here. The model's internal reason for declining is unknown;
confusion between descriptive “explain” and causal explanation is plausible,
not established evidence. No live Groq fix verification is claimed.

## Correction and boundaries

`backend/genai/questions.py` introduces a small explicit set/grammar of supported
stored-data follow-ups. It maps complete formulations such as:

- `Explain the mean daily temperature in these stored results.`
- `What was the average daily temperature?`
- `Explain these temperature results`
- `Explain the rainfall summary in these stored results.`
- `What is the total precipitation?`
- `Show the minimum temperature for this period.`
- `वर्षा का सारांश समझाएँ`
- `वर्षाको सारांश बुझाउनुहोस्`
- `औसत दैनिक तापमान समझाएँ`
- `औसत दैनिक तापक्रम बुझाउनुहोस्`

A whole-result summary and the existing supported mean-temperature/rainfall
comparisons remain available. Comparison facts still require complete comparable
coverage. Other follow-up formulations are refused with guidance rather than
left to unrestricted model interpretation. This bounded routing supersedes the
base architecture document's earlier model-only relevance decision.

The route selects **only existing compiled facts** for the requested metric.
If the measurement is null/absent, or a question asks for humidity, a new place,
new dates, a cause, prediction or unsupported instructions, it is refused before
a provider request. A keyword appearing inside an otherwise unsupported question
does not authorize it. This is not a general natural-language question router;
rephrase unsupported formulations using the examples above.

The LLM now receives a `describe_stored_facts` task, requested canonical metric
names, matching facts and an example JSON plan populated from those real facts.
The prompt explicitly distinguishes a descriptive temperature/rainfall summary
from causal explanation. A JSON example is guidance, not a runtime canned answer:
provider output must still be received and validated.

The original strict schema, exact numerical strings, units, location/date/source
matching, duplicate-key rejection, no-prose boundary and server-rendered source
attribution remain intact. Validation is stronger for follow-ups: a correct but
irrelevant metric elsewhere in the context is no longer eligible. If a provider
still says false for a known supported task, the result is `unavailable`, not a
false claim that the measurement is missing. No success is manufactured, no
fallback explanation is inserted, and `--require-llm` still fails. Timeouts,
missing credentials and malformed/hallucinated output retain safe failure paths.

The context store, TTL (900 seconds), session binding, capacity, API handler and
stored environmental measurements are unchanged; their regression checks pass.
Environmental results remain available when optional generation fails.

## Verification and files

Modified:

- `backend/genai/service.py`
- `scripts/verify_genai.py`
- `tests/genai/test_service.py` (injection test strengthened to require refusal
  before an outgoing provider call)

Added:

- `backend/genai/questions.py`
- `tests/genai/test_followups.py`
- `docs/GENAI_FOLLOWUP_FIX.md`

Complete suite: **654 passed, 2 dependency warnings in 19.27 seconds**.
The 57 new regression cases cover supported English/Hindi/Nepali responses,
missing metrics, out-of-scope questions, valid-but-irrelevant claims, unchanged
numeric/unit/source/period validation, provider false negatives, context expiry
and isolation, FastAPI behavior, and verifier success/failure control flow.
Existing trained-NLP/analytics/date-range regression tests remain passing.

All external LLM responses in the new tests are mocked. The recorded ERA5 data
are real previously retrieved data, not fabricated measurements. No Groq/API key
was configured for live inference in this cloud check; no live provider call or
original checkpoint execution is claimed. Passing these tests does not establish
actual Groq behavior or model quality. A real provider can still refuse or return
invalid output, and that must continue to fail verification safely.

## Minimal Windows revalidation

After fetching the confirmed correction commit, stop and restart FastAPI in the same activated Windows environment/terminal that has the
working Groq variables. Keep the configured provider, model, base URL and key;
do not paste credentials into chat or change checkpoints.

```powershell
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

In another activated terminal, from the updated project root:

```powershell
python scripts/verify_genai.py --mode trained --require-llm
```

The explicit `--mode trained` is important: the verifier's backward-compatible
default is `demo`. It now prints the selected NLP mode and source. The first
check uses the reproducible snapshot, isolating LLM behavior from networking.
For each explanation language (en/hi/ne), expect:

```text
en environment PASS; GenAI status: ok
en temperature_mean_c follow-up status: ok
en rainfall_total_mm follow-up status: ok
en LIVE LLM grounded temperature/rainfall follow-ups PASS; absent humidity rejected
```

Repeat using live weather once the recorded-data/provider check succeeds:

```powershell
python scripts/verify_genai.py --mode trained --source live --require-llm
```

The verifier now requires genuine successful temperature AND rainfall provider
responses, the expected metric/language, nonempty claims/sources/text, and
provider/model identity. It also checks rejection of absent humidity. Refusal
messages print the failing metric and status, distinguishing `no_context`,
`unsupported`, `unavailable` and `rejected`. If a provider still refuses a valid
task, the check intentionally fails; do not disable the assertion or grounding
checks. Preservation was subsequently authorized for the feature branch only;
no merge, deployment or repository visibility change is part of that authorization.

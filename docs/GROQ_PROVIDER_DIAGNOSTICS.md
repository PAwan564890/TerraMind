# Intermittent Groq provider failures: diagnostics, retries and verification pacing

Base: `5bd09ec793f698f90f287c4bc7be9a1df73639e8` on
`feature/grounded-genai-prototype`. This note records the implementation review
before the subsequently authorized preservation commit/push. Git history and
remote verification establish its preservation status.
No trained checkpoints, NLP, environmental retrieval/analytics, frontend,
provider model, API key or repository visibility was changed. No dependency
installation, merge or deployment was performed.

## Proven evidence versus hypotheses

The reported Windows tests with Groq `openai/gpt-oss-20b` successfully produced
several grounded explanations before failing with:

```text
LLM provider failed; environmental results remain available.
```

In the inspected client this exact generic message caught **both HTTP errors
and response-parsing errors** (`HTTPError`, `ValueError`, `KeyError`, etc.). It
removed HTTP status and failure details. Ordinary httpx timeouts already used
a separate timed-out message. There were no provider diagnostic logs or retries.
The generic failure is not the stored-context/unsupported-question response.

The verifier makes nine logical LLM requests: three initial explanations plus
six temperature/rainfall follow-ups, with no intentional pacing. Its three
humidity checks are rejected locally and do not call the model. `--source live`
also makes three weather requests; those are not Groq requests.

Groq's public documentation confirms HTTP 429 on rate limiting, `Retry-After`
in seconds, and rate-limit headers. That request/token volume makes 429 plausible.
Provider 5xx, transport failures or JSON generation/response errors are also
possible. No actual failing status/body/headers from Windows are available here.
Neither a rate limit nor a model-specific defect has been proven. No private
Groq credential or original trained checkpoint was accessed, and no live Groq
request was verified in the cloud.

References reviewed through successful public HTTP reads:

- https://console.groq.com/docs/rate-limits
- https://console.groq.com/docs/errors

Groq documents `x-ratelimit-remaining-requests` and reset-requests as **requests
per day**, not requests per minute. Token remaining/reset headers refer to
**tokens per minute**. Do not infer an RPM limit from the request header.
Current account/model limits must be checked using actual response metadata;
this change does not assume a particular free-tier quota.

## Safe diagnostic categories

The provider client and service now report static categories and a locally
created correlation reference. Typical sanitized log fields:

```text
llm_failure ref=<local-id> category=rate_limit http_status=429 attempt=1 retry=True delay_seconds=2.0 retry_after_seconds=2.0 remaining_requests=100 remaining_tokens=0
```

Values above are illustrative, not evidence of a live provider response.

| Category | Meaning |
| --- | --- |
| `rate_limit` | HTTP 429 |
| `authentication` | HTTP 401/403; authentication or authorization failure |
| `timeout` | HTTP 408 or httpx connect/read/write timeout |
| `transport` | Connection/protocol/read transport failure |
| `http_server_error` | Provider HTTP 5xx (status retained, e.g. gateway 504) |
| `provider_rejection` | Nontransient rejected request, explicit refusal/filter/tool-call finish, or a negative answerability plan |
| `malformed_response` | Invalid outer JSON/shape, invalid content-field type, decoding failure or size-limit violation |
| `structured_output` | Known provider JSON-generation error such as HTTP 400 `json_validate_failed`, or invalid completion JSON/Plan schema |
| `incomplete_response` | Provider `finish_reason=length`; no partial explanation accepted |
| `grounding_validation` | Wrong numbers/units/places/period/sources/language, duplicate or otherwise inconsistent claims |
| `internal_error` | Unexpected exception caught by the optional-generation API isolation boundary |

Provider failures return `unavailable`; invalid generated plans still return
`rejected`. Public messages include static category, numeric HTTP status where
available, attempt count, and reference (and numeric retry delay if supplied).
No raw provider body, error message, `failed_generation`, completion, prompt,
Authorization header, key, URL or environment value is included in our logs.
Remote request IDs are not echoed. Only parsed numeric quota/retry metadata is
retained. Exception tracebacks are not logged.

Dependency httpx/httpcore URL/header debug logs are suppressed **only in the
current provider call's context**, including HTTPX's otherwise automatic URL
logging. Other requests retain their normal logging. Tests verify simulated
secrets in headers, bodies, malformed output and exception messages are absent
from diagnostics and public failure messages.

## Bounded transient retries

Default: **two total attempts**, meaning at most one retry.

Retry candidates:

- HTTP 429, 500, 502, 503, 504.
- ConnectError/ConnectTimeout, where connection establishment failed.

Do not retry:

- HTTP 401/403 and other nontransient request/authentication failures.
- HTTP 408 and ambiguous read/write timeouts or post-connect transport failures;
  a provider may already have processed/billed those requests.
- Provider refusal, truncation, malformed output, JSON-generation failure,
  Plan/schema/grounding validation failure, or unsupported environmental questions.

`Retry-After` is parsed as nonnegative seconds or an HTTP date. It takes
precedence. If absent/invalid, exhausted Groq request/token quota reset durations
(e.g. `2m59.56s`, `7.66s`) are considered. Nonexhausted quotas are not mistaken for
retry instructions. Otherwise use exponential backoff (0.5 seconds, then 1)
plus up to 0.25 seconds jitter.

If provider guidance exceeds the configured wait cap, the client **stops** and
reports the suggested delay. It never clamps the wait and retries too early.
Wait at least that reported interval before a manual retry. A long daily quota
reset is not hidden by repeated immediate requests.

Environment configuration, read on backend startup:

| Variable | Default | Allowed |
| --- | --- | --- |
| `TERRAMIND_LLM_MAX_ATTEMPTS` | 2 | 1–3 total attempts; 1 disables retries |
| `TERRAMIND_LLM_RETRY_MAX_WAIT_SECONDS` | 5 | 0–15 seconds per retry wait |
| `TERRAMIND_LLM_TIMEOUT_SECONDS` | 15 | Existing 1–30-second component timeouts; connect capped at 5 |

Invalid values revert to defaults. A 35-second **retry-admission budget** bounds
starting another attempt plus its wait; it does not claim hard cancellation of
an in-flight synchronous HTTP operation. Attempt timeouts are reduced to the
remaining budget. Response size limits (64 KiB outer body/16,000-character
completion) are preserved. Additional attempts can incur additional provider
usage; no retry is triggered by validation failures to manufacture a success.
Success on a later attempt logs `llm_recovered` with only reference and attempt.

Environmental data remain in the response if all attempts fail. The existing
independent environmental endpoint is unchanged. No fallback measurement or AI
explanation is fabricated, and all existing grounded-claim checks are retained.

## Optional verifier pacing

New flag:

```powershell
--min-interval-seconds 10
```

Allowed interval: 0–60 seconds, default 0. It spaces the starts of the nine
potential LLM calls, subtracting time already spent processing the prior call.
It does not delay the first request, unsupported humidity checks or ordinary
application requests. Disabled providers do not incur verification pacing.
Backend retries remain independently bounded and obey provider guidance.

Pacing is not a promise that a particular account's quotas will be sufficient.
If 429 persists, honor the logged retry interval and use a larger interval,
e.g. 20 or 30 seconds, up to the 60-second bound. Run verifications sequentially;
parallel runs/app activity also consume the provider's limits.

## Tests and verification limits

Full suite: **715 passed, 2 dependency warnings in 24.51 seconds**. The 61 added
cases cover failure categories, safe metadata, retry/backoff limits, Retry-After
seconds/dates, Groq reset guidance, budget admission, ambiguous timeout no-replay,
malformed/oversized/truncated responses, JSON-generation errors, grounding and
refusal logs, environment preservation, and script-only pacing. Existing NLP,
date-range, context, analytics, frontend and follow-up tests still pass.

All provider failures/successes in these regression tests are simulated with
httpx MockTransport. Sleep/clock injection makes retry tests deterministic.
This is not evidence of genuine Groq model availability or a successful live
Windows verification. The cloud has no configured live LLM credentials.

## Exact Windows revalidation

After fetching the confirmed correction commit, stop the old FastAPI process
with Ctrl+C. In the same activated backend terminal/project root,
retain the existing Groq provider/model/base-URL/key variables. Do not print or
paste keys, change checkpoints, or reinstall dependencies.

```powershell
$env:TERRAMIND_LOG_LEVEL = 'INFO'
$env:TERRAMIND_LLM_MAX_ATTEMPTS = '2'
$env:TERRAMIND_LLM_RETRY_MAX_WAIT_SECONDS = '10'
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

In a separate activated terminal, updated project root:

```powershell
python scripts/verify_genai.py --mode trained --require-llm --min-interval-seconds 10
```

After snapshot verification succeeds, test live weather sequentially:

```powershell
python scripts/verify_genai.py --mode trained --source live --require-llm --min-interval-seconds 10
```

Keep the backend console visible. If a check fails, record only its sanitized
category, HTTP status, attempt, retry metadata and reference. These now establish
which path failed without collecting keys or private payloads.

- `rate_limit`/429: observe quota/reset information, wait at least Retry-After,
  and reduce request cadence. Do not assume language or grounding is the cause.
- `authentication`/401/403: fix credentials/permissions privately; repeated
  retries will not help.
- `structured_output`/400: the provider rejected JSON generation; do not disable
  validation. Investigate model/output compatibility separately using the safe
  category/status, not raw failed_generation contents.
- `incomplete_response`: token-limit truncation is distinct from transport errors;
  do not accept partial output. Token-budget/model tuning would need a separately
  tested change, not a silent grounding relaxation.
- `timeout`: component timeout may be increased up to 30 seconds only if needed;
  restart the backend after environment changes. Read timeouts are not replayed.
- `grounding_validation`/`rejected`: model claims were discarded as intended.

Preservation was subsequently authorized for the existing feature branch only.
No merge, deployment, model-weight modification or visibility change is authorized.

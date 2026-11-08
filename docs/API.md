# TerraMind NLP API

One service, two endpoints. It turns an English, Hindi or Nepali question into
a structured query. It does not answer the question: there is no environmental
data behind it yet.

## Run it

Train the models and select thresholds first (see the README), then:

```powershell
uvicorn backend.api.app:app --port 8000
```

Interactive documentation is generated at `http://127.0.0.1:8000/docs`.

## POST /nlp/analyze

Request:

```json
{
  "query": "गंगटोक में बारिश का रुझान क्या है?",
  "session_id": "optional-conversation-id"
}
```

| Field | Type | Rules |
| --- | --- | --- |
| `query` | string | Required. 1 to 4,000 raw characters; at most 500 after normalisation |
| `session_id` | string | Optional. 1 to 64 characters from `A-Z a-z 0-9 _ -`. Queries with the same id form one conversation |

Response, HTTP 200:

```json
{
  "language": {"code": "hi", "confidence": 1.0},
  "intent": {"label": "CLIMATE_TREND", "confidence": 0.99},
  "entities": [
    {"text": "गंगटोक", "type": "LOCATION", "start": 0, "end": 6,
     "normalized": "loc:gangtok", "confidence": 0.97},
    {"text": "बारिश", "type": "ENV_VARIABLE", "start": 11, "end": 16,
     "normalized": "PRECIPITATION", "confidence": 0.95}
  ],
  "structured_query": {
    "schema_version": "1.0",
    "intent": "CLIMATE_TREND",
    "operation": "TREND",
    "answer_kind": "analysis",
    "locations": [{"id": "loc:gangtok", "name": "Gangtok", "type": "TOWN",
                   "parent": "loc:gangtok_district"}],
    "variables": ["PRECIPITATION"],
    "disasters": [],
    "time_period": {"type": "relative_past", "value": 10, "unit": "year",
                    "start": null, "end": null},
    "scenario": null,
    "target": null,
    "context_used": []
  },
  "status": "ok",
  "clarification": null,
  "warnings": ["time_period_defaulted"],
  "needs_clarification": false
}
```

The confidence values above are illustrative.

### Fields

| Field | Meaning |
| --- | --- |
| `language.code` | `en`, `hi` or `ne` |
| `intent.label` | One of nine intents. If a follow-up inherited its intent from the conversation, this is the inherited one |
| `intent.confidence` | Calibrated probability the classifier gave to that label |
| `entities[]` | Spans found in the normalised query. `start`/`end` are character offsets. `normalized` is `null` if the span could not be resolved |
| `structured_query` | The language-independent query; `null` when out of domain |
| `status` | `ok`, `needs_clarification` or `out_of_domain` |
| `needs_clarification` | `true` exactly when `status` is `needs_clarification` |
| `clarification` | Present only with `needs_clarification` |
| `warnings` | Non-fatal notes; see below |

### structured_query

| Field | Values |
| --- | --- |
| `intent` | `WEATHER_QUERY`, `CLIMATE_TREND`, `VEGETATION_ANALYSIS`, `DISASTER_RISK`, `GEOLOCATION_QUERY`, `COMPARISON`, `SCENARIO_ANALYSIS`, `GENERAL_ENVIRONMENT` |
| `operation` | `LOOKUP`, `TREND`, `COMPARE`, `EXPLAIN`, `RANK`, `FORECAST`, `SCENARIO` |
| `answer_kind` | `observation`, `analysis`, `prediction`, `scenario`: the scientific status the answer will have |
| `locations[]` | `id` (stable key, shared with the future database), `name`, `type`, `parent` |
| `variables[]` | `TEMPERATURE`, `PRECIPITATION`, `HUMIDITY`, `WIND_SPEED`, `AIR_QUALITY`, `NDVI`, `SOIL_MOISTURE`, `LAND_COVER`, `LAND_SURFACE_TEMPERATURE`, `ELEVATION`, `SLOPE` |
| `disasters[]` | `FLOOD`, `LANDSLIDE`, `WILDFIRE`, `EARTHQUAKE`, `GLOF`, `CLOUDBURST` |
| `time_period` | `type` is `current`, `relative_past`, `relative_future` (with `value` and `unit`) or `date_range` (with `start` and `end`) |
| `scenario` | `variable`, `change`, `unit` (`percent` or `absolute`), `direction` (`increase` or `decrease`) |
| `target` | A risk (`FLOOD_RISK`, `LANDSLIDE_RISK`, `WILDFIRE_RISK`) or a variable |
| `context_used[]` | Names of fields inherited from earlier turns, including `intent` |

### status and clarification

| `status` | `structured_query` | What the caller should do |
| --- | --- | --- |
| `ok` | Complete | Act on it |
| `needs_clarification` | Partial, or `null` | Ask the user; do not act |
| `out_of_domain` | `null` | Tell the user the question is outside TerraMind's scope |

`clarification` has `reason`, `message_key`, `missing_fields` and `options`.
`message_key` is a stable key for the interface to translate; the API returns
no user-facing sentences.

| `reason` | `message_key` | Extra |
| --- | --- | --- |
| `missing_required_field` | `missing_locations`, `missing_variables`, `missing_disasters`, `missing_scenario` | `missing_fields`; `a\|b` means either satisfies it |
| `unknown_location` | `unknown_location` | `options` holds the place text that was not recognised |
| `comparison_needs_two` | `missing_comparison_target` | |
| `implausible_change` | `confirm_change_amount` | |
| `low_confidence` | `unclear_request` | `options` holds the two most likely intents |
| `signals_disagree` | `unclear_request` | The classifier says off-topic but the query closely resembles in-domain ones. `structured_query` is `null` |

### warnings

| Warning | Meaning |
| --- | --- |
| `time_period_defaulted` | A trend had no time span; the last 10 years were assumed |
| `time_from_rules`, `change_from_rules` | Found by rules after the NER model missed it |
| `ambiguous_time` | Hindi कल or परसों with no tense cue; the future was assumed |
| `multiple_time_expressions` | More than one found; the first was used |
| `unresolved_<type>:<text>` | An entity span could not be mapped to a known value |
| `incomplete_scenario:<parts>` | A scenario lacked a variable, change or direction |
| `language_from_context` | Too little text to detect; the conversation's language was used |
| `mixed_script` | Latin and Devanagari in one query |
| `low_domain_similarity` | Rejected by the embedding-similarity check |
| `signals_disagree` | The two off-topic signals disagreed; the user is asked |

## Errors

| Code | When | Body |
| --- | --- | --- |
| 422 | Missing or mistyped field, unknown field, bad `session_id`, body not JSON | FastAPI's standard validation detail |
| 422 | Query unusable after normalisation | `{"detail": {"code": "empty" \| "too_long" \| "no_content", "message": "..."}}` |
| 503 | Models not loaded | `{"detail": {"code": "models_not_loaded", "message": "..."}}` |

An out-of-domain or unclear question is **not** an error and returns 200.

## GET /health

```json
{"status": "ok", "models_loaded": true, "detail": null}
```

If the models could not be loaded, the service still starts, `status` is
`degraded`, and `detail` names what is missing.

## Conversations

Send the same `session_id` with each turn. The service remembers the last
places, variables, hazards and time span, and fills them into follow-ups such
as "और बारिश?". Without a `session_id` every query stands alone.

State lives in memory: it is lost on restart, expires after 30 minutes of
inactivity, and is not shared between server processes.

## Operational notes

- **Latency.** About 71 ms median and 85 ms at the 95th percentile per query
  for the pipeline with the final models on an RTX 2050, one query at a time.
  The small development models took about 40 ms on a laptop CPU. Neither
  figure includes a network.
- **Concurrency.** Requests are analysed one at a time behind a lock. Run a
  single worker; several workers would each hold their own conversation state.
- **Logging.** Language, intent, status and timing are logged. The query text
  is logged only at DEBUG level.
- **Not included yet.** Authentication, rate limiting and CORS. Add them
  before exposing the service beyond your own machine.

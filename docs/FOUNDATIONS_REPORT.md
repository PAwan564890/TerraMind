# TerraMind environmental/geospatial foundations — implementation report

## Repository and preservation

Starting commit: `01bf4942174dfb2b1fac9fe57e841a07bd4b3716`. The question-handling expansion was already committed/pushed, not absent or uncommitted. Starting tests were verified, not assumed: **771 backend / 48 React**. The original clean `/workspace/TerraMind` checkout remains on `feature/grounded-genai-prototype` at that commit. Protected master remains `eb483eac04e73009bd7a8a87a0a0093a95f998f1`.

Implementation is uncommitted in `/workspace/TerraMind-foundations`, separate local branch `feature/geospatial-intelligence-foundations`. No reset, cleanup, stash deletion, checkpoint copy, retraining, commit, push, merge or deployment was performed. The existing fallback remains recoverable. No Windows folder was accessed.

See `FOUNDATIONS_IMPLEMENTATION_MAP.md` for the audit and `WINDOWS_FOUNDATIONS_REVIEW.md` for exact safe integration/fallback commands.

## Capability status

| Capability | Status and verification |
|---|---|
| Original NLP, calendar and question router | Preserved; original regression assertions retained |
| Ten reviewed town points | Implemented, opt-in; coordinates traced to real GeoNames/Open-Meteo responses; weather and supplemental retrieval live-verified for every point |
| Ambiguous geocoding | Pakyong/Singtam excluded; Chungthang/Chungtang unresolved and excluded; no unrestricted runtime geocoding |
| Backend deterministic insights | Implemented: extrema/ties, ranges, adjacent-day changes, monthly portions, coverage, comparable temperature/rainfall differences |
| Real Environmental Map | Implemented with React Leaflet/Leaflet/OSM; real geography, 10 markers, zoom/pan, automatic bounds, actual retrieval, comparison handoff, keyboard/fallback controls verified |
| AI Pipeline Inspector | Implemented, collapsed by default; actual returned NLP, environmental and grounded-AI outputs only |
| Humidity and scalar wind speed | Implemented, opt-in, separate validated daily-data endpoint and React charts/tables; historical and recent products verified |
| Humidity/wind GenAI facts | Deliberately deferred; supplemental values are not in the existing weather context and cannot be invented by its LLM |
| Day-event grounded follow-ups | Implemented with server-owned dates and numeric facts; English/Hindi/Nepali successful provider integration tested with mocks, not live Groq |
| Open-Meteo reliability | Implemented sanitized timeout/transport/rate-limit/provider/invalid-response handling and bounded appropriate GET retries |
| Streamlit | Independent backup preserved; only the supported-town caption now reads actual backend towns |
| Pressure/snow/clouds/wind direction/gusts | Unsupported; explicit refusal prevents substitution |
| Multi-year climate significance/causality/hazards | Unsupported; monthly portions are descriptive, not attribution, forecasts or established climate trends |
| Full operational Earth System Digital Twin | Not claimed; these are environmental/geospatial foundations |

Backend flags are explicit:

- `TERRAMIND_EXTENDED_LOCATIONS=1`: activates the full ten-point registry; absent means original three points.
- `TERRAMIND_ADDITIONAL_MEASUREMENTS=1`: exposes humidity/wind-speed retrieval; absent preserves default unsupported-measurement behavior.

## Reviewed geographical coverage

Registry: `backend/environment/locations.json`, validated by `registry.py`. The existing three IDs and coordinates are unchanged. All coordinates are populated-place town points in Sikkim, India, obtained from GeoNames via the public Open-Meteo geocoding service. They are not district boundaries, district means or station locations.

| Town | Latitude | Longitude | GeoNames ID | English aliases already in ontology | Live 1–7 Jan 2025 retrieval |
|---|---:|---:|---:|---|---|
| Gangtok | 27.32574 | 88.61216 | 1271631 | Gangtok, Gantok | Weather + humidity/wind OK |
| Namchi | 27.16494 | 88.3638 | 1262029 | Namchi | Weather + humidity/wind OK |
| Mangan | 27.50965 | 88.52206 | 1263776 | Mangan | Weather + humidity/wind OK |
| Gyalshing | 27.28952 | 88.25764 | 1270577 | Gyalshing, Geyzing, Gyalzing | Weather + humidity/wind OK |
| Rangpo | 27.17733 | 88.53358 | 1258484 | Rangpo | Weather + humidity/wind OK |
| Jorethang | 27.10696 | 88.32332 | 7279751 | Jorethang | Weather + humidity/wind OK |
| Ravangla | 27.30589 | 88.36355 | 10630194 | Ravangla, Rabongla, Ravongla | Weather + humidity/wind OK |
| Pelling | 27.30158 | 88.23266 | 7114402 | Pelling | Weather + humidity/wind OK |
| Soreng | 27.16902 | 88.20263 | 1255707 | Soreng | Weather + humidity/wind OK |
| Lachung | 27.6934 | 88.74429 | 1265346 | Lachung | Weather + humidity/wind OK |

Every entry includes source URL, verification timestamp, country, administrative names, feature code, aliases and attribution. Independent recorded geocoding evidence is in `tests/fixtures/geocoding_evidence.json`; coordinate tests compare registry entries against that evidence. The API `/locations` is authoritative for UI selectors. English/Hindi/Nepali aliases are inherited from the original ontology; some native spellings were originally marked draft and are not newly certified native-speaker translations. Existing deterministic normalization can resolve them when extracted; trained NER accuracy for new town phrasings remains a Windows verification item.

Pakyong returned two populated-place candidates; Singtam returned multiple Sikkim candidates (and another state). No arbitrary result was chosen. Chungthang and the alternate search Chungtang returned no usable candidate. Lachung was a single verified Sikkim populated-place result and brings the accepted total to ten. No invented coordinates or dynamic client-coordinate upload was introduced.

Several towns share the same coarse ERA5 grid cell, so identical estimates are scientifically expected. The response retains requested point and actual provider-grid coordinates separately. Registry policy is deliberately Sikkim-scoped; future regions require reviewed entries and a policy change, not a new query architecture.

## Environmental definitions and missing data

Calculations live in `backend/environment/insights.py`, never in React:

- Warmest/coolest available day: maximum/minimum **daily mean air temperature** among non-null rows; not the daily maximum/minimum temperature fields.
- Wettest/driest available day: maximum/minimum daily **rainfall**; zero is a valid dry day. Missing rainfall is not dry weather.
- Ties: earliest chronological date is primary; all tied dates remain available through the insight API and expandable UI. GenAI receives only the primary date to keep prompts bounded.
- Daily temperature variation: daily maximum minus daily minimum, unavailable if either is missing.
- Available period range: highest available daily maximum minus lowest available daily minimum. Coverage is explicit; missing extremes can make it an incomplete description.
- Day-to-day change: consecutive-calendar-day mean difference only, right minus left. Missing values produce null; missing dates are never bridged or interpolated.
- Monthly aggregation: arithmetic mean of valid daily mean temperatures and sum of valid daily rainfall for the **retrieved part** of a month. Period boundaries and valid/retrieved counts are included; a seven-day subset is not presented as a full month.
- Rainfall distribution: original daily rainfall values by date, including nulls, not synthesized percentages or an invented trend.
- Coverage: valid, missing and expected counts per field, expected from the selected date span.
- Cross-location differences: left mean minus right mean, left rainfall total minus right rainfall total; ranks follow the sign, exact equality is a tie. Calculations use full precision before display rounding. No statistical significance is inferred.
- Comparison requires matching period/timezone/data kind, aligned full date coverage and non-null values for the compared metric. Incomplete comparisons remain unavailable and show warnings; other available records remain inspectable.

Original `summarize()` statistics are unchanged. Historical weather remains explicit ERA5, recent weather remains the existing weather-model product, and the 366-day/non-future/1940+ limits remain. There is no validated long-term climate trend, causal attribution or multi-year analysis added.

## Real map and application state

Route: `/map`, labelled Environmental Map, in addition to the original five pages. React Leaflet 5 / Leaflet 1.9.4 renders real OpenStreetMap tiles at `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. No static/generated map image, heatmap or sparse-point interpolation is used.

Viewport fits the active registry automatically; normal pan/zoom controls work. Green/larger markers are selected, gray/smaller markers unselected. Markers show actual names, coordinates, retrieved period/temperature/rainfall, timestamps/source or explicit absence of measurements. Enter/Space selects markers; native checkboxes offer the same actions. A selected pair is passed through validated `town` query parameters to the original trained Comparison page. That trained request still requires actual checkpoints. The map's own explicit-selection endpoint can retrieve/compare actual data without claiming trained inference; this is a separate user-selected workflow, never an automatic fallback from model failure.

Tile errors or map initialization errors leave textual selectors, dates and real API retrieval usable. The OSM attribution control is retained. No bulk/offline tile prefetch was added; normal browser tile caching/referrers are used. Data: OpenStreetMap contributors, ODbL; public tile usage policy applies. Leaflet license: BSD-2-Clause. React Leaflet/@react-leaflet/core license: Hippocratic-2.1; this academic environmental use must retain its applicable package/license terms. Geocoding/meteorological data retain the returned Open-Meteo/GeoNames/Copernicus attribution.

Actual Chromium verification loaded OSM PNG tiles with HTTP 200 and ten markers. In this managed cloud, external Chromium traffic needed the environment proxy and explicit public-CA SPKI trust for its installed proxy roots. That trust adjustment was confined to the verification browser; no application TLS bypass or browser-side credential was added. Ordinary Windows browser access is a separate network environment. Tile-blocking behavior was deliberately tested.

## Supplemental variables and source products

| Variable | Provider daily field | Unit | Definition |
|---|---|---|---|
| Relative humidity | `relative_humidity_2m_mean` | % | Daily mean relative humidity at 2 m; values must be finite and between 0 and 100 |
| Scalar wind speed | `wind_speed_10m_mean` | m/s | Daily mean scalar wind speed at 10 m, requested with `wind_speed_unit=ms`; nonnegative, not gust or vector direction |

Both fields were genuinely retrieved from historical ERA5 and recent forecast/past-data products. All ten points were live-verified for 1–7 January 2025. The recent-product fixture was genuinely retrieved for 14 November 2026 at Gangtok. ERA5 historical availability is documented from 1940; not every historical date at every point has been individually probed. Upstream missing values remain null/unavailable, never fabricated.

Supplemental queries require explicit start/end dates, live mode, supported query intents/operations, one or two distinct active towns and 1–366 non-future days. Recent-product ranges must stay in its 92-day past-data window; historical periods use ERA5 when the end is at least six days old. Additional measurements have no recorded-snapshot fallback. Today can include forecast hours.

Period mean is the arithmetic mean of valid daily means; minimum/maximum are extrema of daily means, with valid/missing/expected counts. No aggregation over missing values as zeros. Malformed units, dates, lengths, coordinates, numbers, negative wind, or out-of-range humidity are rejected. All-null responses are unavailable. Weather and supplemental products retain separate source metadata and separate failure states.

Natural-language humidity/wind-only queries use the original trained response and the new service when complete supported fields are returned. Mixed weather-plus-supplemental text queries are not silently split; use separate questions or the explicit map checkboxes. Supplemental responses are available in Assistant/Analytics and the map. They deliberately do not create weather GenAI context or permit humidity/wind numerical follow-ups through the old weather fact schema.

## NLP, grounded facts and AI Pipeline Inspector

No original NLP/ontology/checkpoint files were changed. Trained confidence, entities, intent and structured query stay as returned. Missing checkpoints still produce 503, not a rule success. Existing multilingual dates and question categories remain. The router recognizes enabled registry towns rather than rejecting every newly connected town; unsupported variable/hazard timing restrictions remain.

Day-event follow-ups use server-compiled `warmest_day`, `coolest_day`, `wettest_day`, `driest_day` facts. Period start/end remain the full selected range, preserving prior date invariants. New optional Fact metadata `event_dates` is server-owned (one primary date); it is **not** a Claim field the LLM may author. Existing strict numeric/unit/location/period/source equality checks and untrusted-output rejection remain intact. Model attempts to submit event dates as extra claim fields are rejected. Templates render dates from server metadata. Default summaries continue to select the original compact weather/comparison facts; event facts are sent only for explicit day-event requests.

The AI Pipeline Inspector is collapsed by default and shows:

1. **NLP:** actual language, intent, entity text/type/offsets/canonical normalization and backend confidence, selected trained/rule mode, query and warnings. Rule confidence is labelled unmeasured; combined normalization confidence is not misrepresented as raw logits.
2. **Environmental:** actual provider, selected dates/locations, status/errors, returned observations/statistics/coverage, units, grid/requested coordinates and original source attribution. Supplemental data are clearly separate.
3. **Grounded AI:** exposed configured provider, actual response status/provider/model, validated facts and evidence, context availability/expiry rules. Missing fields explicitly say not exposed. No prompts, secret configuration or private chain-of-thought are exposed.

General knowledge/unsupported/clarification routing does not show a prior query's measurements as if they were newly retrieved; the Inspector explicitly states which stages were not invoked.

## APIs and compatibility

Existing route bodies/responses remain usable by original consumers. Additions:

- `GET /locations`: active verified registry metadata, feature-gate status and available supplemental variables.
- `POST /environment/selected`: explicit location IDs (1–2), ISO start/end, session ID, source mode and language; returns the ordinary environment/context/explanation bundle plus server insights and an explicit no-trained-inference label.
- `POST /environment/insights`: session ID + context token; returns derived insights over that server-owned retrieval, or `no_context` for expired/wrong-owner contexts. No client observation upload.
- `POST /environment/measurements`: existing StructuredQuery + live source mode; separate typed response for humidity/wind; no new API keys.
- `/system` adds optional capability metadata; its towns come from the same registry. GenAI Facts add optional `event_dates`; existing strict claim fields are unchanged.

React still uses the existing trained/environment/GenAI routes, preserves dates/units/formatting, and retains weather if supplementary insight/measurement or Groq requests fail. Streamlit is independently runnable with the same backend; only its town caption was made registry-driven. No new Python dependency. Frontend lockfile adds Leaflet, React Leaflet/core and type declarations.

## Reliability

Open-Meteo error messages/logs distinguish `timeout`, `transport`, `rate_limit`, `provider_error`, `provider_rejection`, and `invalid_response`; partial retrieval, date/coverage limitations, context expiry and Groq errors remain separate existing states. No raw response body, Authorization header or API key is logged by the new transport helper.

Only idempotent GET requests retry, at most twice. Appropriate 429/500/502/503/504 and transport/timeout failures may retry; other client errors, malformed responses and nontransient statuses do not. Retry-After seconds/HTTP dates are respected; advice over the two-second wait cap stops instead of retrying too early. A 20-second retry-admission budget reduces later per-phase timeouts; it is not a hard whole-operation cancellation deadline. The first request retains the original 20-second read/8-second connect settings. Browser cancellation cannot guarantee cancellation of server work. No automatic switch to recorded data was introduced.

## Verification and remaining limitations

See `FOUNDATIONS_VERIFICATION.md` for final exact test counts, genuine versus mocked evidence and file list. Live weather/supplemental retrieval and real map tiles were verified; genuine trained checkpoints and private Groq credentials were unavailable in cloud. New trained-location recognition and live day-event Groq explanations must be smoke-tested on Windows before evaluation. Tests use explicit scripted models/provider mocks where stated.

**CONDITIONAL GO for the 17 November 2026 academic demonstration after Windows smoke verification.** The current `01bf494...` application remains the fallback. No claim of an operational digital twin, arbitrary-question competence, district averages, climate causality, hazard forecasting, global geocoding, extra unimplemented measurements, or statistically established trends is justified.

## Demonstration question set

Legend: **Live-verified** means genuine API/provider execution in this cloud, explicitly rule-mode where NLP was needed; it does not mean genuine trained checkpoints or Groq. **Fixture-tested** means recorded inputs/scripted models/provider mocks or deterministic unit tests. **Not yet verified** means that exact natural-language/model combination needs the Windows smoke test. Each accepted town's raw weather/humidity/wind data were separately live-verified for 1–7 January 2025, even when a wording below is not yet verified.

| # | Question / action | Verification |
|---|---|---|
| 1 | Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07. | Fixture-tested original pipeline; benchmark data live-verified (11.9 mm) |
| 2 | Show temperature and rainfall in Pelling from 2025-01-01 to 2025-01-07. | Live-verified HTTP, explicit rule mode; Pelling weather OK |
| 3 | Compare temperature and rainfall in Gangtok and Namchi from 2025-01-01 to 2025-01-07. | Fixture-tested NLP/demo contract; real browser explicit-selection comparison verified |
| 4 | Compare rainfall in Gangtok and Ravangla during January 2025. | Not yet verified as a trained query; both points' seven-day data live-verified |
| 5 | Show temperature in Gyalshing from 2025-01-01 to 2025-01-07. | Not yet verified as a trained query; point/provider live-verified |
| 6 | Show rainfall in Rangpo during January 2025. | Not yet verified as a trained monthly query; point/provider live-verified |
| 7 | Show temperature in Lachung from 2025-01-01 to 2025-01-07. | Not yet verified as a trained query; point/provider live-verified |
| 8 | What was the warmest day? (after a Gangtok weather session) | Fixture-tested successful grounded provider mock; Jan 6, 13.00 °C daily mean |
| 9 | What was the wettest day? (same session) | Fixture-tested fact selection; Jan 7, 9.20 mm rainfall |
| 10 | Which town was warmer? (same-period two-town session) | Fixture-tested complete/missing coverage and left-minus-right math; no invented rank |
| 11 | Which town received more rainfall? | Not yet verified with genuine Groq; bounded metric routing implemented |
| 12 | Show humidity in Gangtok from 2025-01-01 to 2025-01-07. | Daily humidity data live-verified; genuine trained wording pending |
| 13 | गंगटोक में 2025-01-01 से 2025-01-07 तक आर्द्रता दिखाएं। | Live-verified HTTP in explicit rule mode, HUMIDITY |
| 14 | गान्तोकमा 2025-01-01 देखि 2025-01-07 सम्म हावाको गति देखाउनुहोस्। | Live-verified HTTP in explicit rule mode, WIND_SPEED |
| 15 | गंगटोक में जनवरी 2025 के पहले सप्ताह में तापमान दिखाएं। | Fixture-tested calendar family; exact trained wording pending |
| 16 | गान्तोकमा जनवरी २०२५ मा कति वर्षा भयो? | Not yet verified as an exact trained query; native month grammar preserved |
| 17 | सबसे गर्म दिन कौन सा था? | Fixture-tested successful Hindi grounded event follow-up with mocked provider |
| 18 | सबैभन्दा न्यानो दिन कुन थियो? | Fixture-tested successful Nepali grounded event follow-up with mocked provider |
| 19 | What does ERA5 reanalysis mean? | Genuine browser HTTP verified, curated knowledge only; no measurements or LLM call |
| 20 | Show wind direction in Gangtok during January 2025. | Fixture-tested unsupported refusal, no wind-speed substitution |
| 21 | Predict tomorrow's earthquake. | Fixture-tested unsupported hazard-timing refusal |
| 22 | Explicit map selection: Gangtok + Pelling, 1–7 Jan 2025, live weather + humidity/wind. | Genuine browser/API data displayed; separately verified actual OSM tiles |

Do not present unverified trained phrasings as guaranteed successes. Missing place/date/variable should lead to clarification, not a guessed measurement. Snapshot source is restricted to the three original towns and seven recorded January days; new towns/supplemental products need explicit live retrieval.

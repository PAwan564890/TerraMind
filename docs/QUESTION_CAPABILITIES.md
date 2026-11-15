# TerraMind question handling and capability audit

Base: `efccbac823e4d6ac9d1142bd9bef28b15ac2cdd9`, existing feature branch. This is an additive academic prototype enhancement; no models retrained, no checkpoint changes, no provider/analytics/grounding relaxation, no Streamlit changes. No commit, push or deployment authorized.

## Evidence-based capability matrix

Supported means implemented with deterministic tests, not proof that the unavailable cloud trained checkpoints predict every paraphrase correctly. Live trained NLP/Groq was reported working by the user on Windows; this cloud work does not reverify it. Model accuracy remains limited by existing training and confidence thresholds.

| Capability | Before | After / limit | Code evidence |
|---|---|---|---|
| English, Hindi, Nepali trained language/intent/NER | Supported with checkpoints | Preserved; model confidence and entity outputs never fabricated | `backend/nlp/pipeline/pipeline.py`, predictors and ontology |
| NLP intents | 9 recognized labels | WEATHER_QUERY, CLIMATE_TREND, VEGETATION_ANALYSIS, DISASTER_RISK, GEOLOCATION_QUERY, COMPARISON, SCENARIO_ANALYSIS, GENERAL_ENVIRONMENT, OUT_OF_DOMAIN; recognition does not imply retrieval support | `backend/nlp/query/enums.py`, `intents.py` |
| Entity types | LOCATION, ENV_VARIABLE, DISASTER, TIME, CHANGE | Preserved, deterministic normalization remains separate from model inference | ontology, `normalizer.py`, `structurer.py` |
| Structured queries | Schema version 1.0; LOOKUP/TREND/COMPARE etc | Existing shapes and original endpoints unchanged | `backend/nlp/query/schema.py` |
| Explicit ISO and named full dates | Supported, including ordered ranges and Devanagari digits | Preserved; invalid/mixed/reversed dates rejected | `explicit_dates.py`, `time_parser.py` |
| Month/year, leap months | January 2025 could fail or fall through to year logic | Added Gregorian full-month normalization, full/abbreviated English and common Hindi/Nepali Gregorian month names | `calendar_periods.py` |
| First week of a month | Not explicit | First week means days 1–7, not ISO week numbers; English and documented Hindi/Nepali forms | same |
| Last January / गत जनवरी | Not reliably anchored | Most recent completed occurrence of the named month, anchored to Asia/Kolkata calendar date; in Nov 2026 last January is Jan 2026, in Jan 2026 it is Jan 2025 | same |
| Other calendar subdivisions | Partial | No guessing of second/last weeks or early/late/mid-month; request explicit dates | same; explicit-date errors remain HTTP 422 |
| Relative periods/current/year ranges | Supported original rules | Today, yesterday, last N days/weeks/months/years etc unchanged; future retrieval refused | `time_parser.py`, `environment/service.py` |
| Missing period/location/variable | Clarification or environmental adapter refusal | Preserved; router also asks for a fresh query when stored context is absent/expired; no guessed dates/places | validator, service, routing |
| Town points | Gangtok, Namchi, Mangan | Same three verified configured points; no district/state aggregates | `environment/provider.py` LOCATIONS |
| Extra Sikkim towns | Some are already in NLP ontology, not adapter | Investigated, not activated. Geocoding is not trained entity recognition or verified retrieval coverage | geocoding audit below |
| Temperature | Supported | Daily mean/min/max °C; original current support preserved | provider, schema, analytics |
| Rainfall vs total precipitation | Supported distinct actual quantities | Rainfall mm versus total precipitation water-equivalent mm; no silent substitution | provider field/unit validation |
| Humidity, wind, pressure, snow, clouds | Recognizable partly; provider fields exist | Not connected. Explicit unsupported reply for bounded known measurement terms; original adapter rejects all unconnected variables. No fake data | routing and service |
| Vegetation, air quality, slope, elevation, soil moisture | NLP entities/intent partly available | No measurement adapter. Unsupported/clarification, not evidence of measured capability | ontology and service |
| Hazards, scenarios, causal environmental analysis | NLP can classify | No earthquake/landslide timing prediction, disaster forecasting or causal attribution | router, service |
| Natural environmental wording | Trained NLP + normalization | Open-ended trained inference preserved, named-calendar additions; recognition errors still possible, never silently replaced with rules | pipeline |
| Contextual rainfall/temperature paraphrases | Strict metric-bound follow-ups | Added “How much did it rain?”, warmer-town difference questions and native equivalents; new places/dates/measurements still rejected | `genai/questions.py` |
| Which town was warmer | Complete comparable sessions only | Selects server-computed left-minus-right mean-temperature difference; sign and left/right order are in original validated text, not a generated ranking | facts, questions |
| Temperature variation summary | Existing summary facts | Mean/min/max over stored week; no invented start-to-end change, trend significance or causal explanation | questions, facts |
| General environmental knowledge | GENERAL_ENVIRONMENT NLP label but no knowledge adapter | Added 7 reviewed, cited reference topics, visibly separate from NLP/measurements/LLM generation | knowledge catalogue and route |
| Arbitrary scientific conversation | Unsupported | Finite topic grammar, not unrestricted chat/RAG. Unknown questions continue to trained NLP and its limits | knowledge full-match boundary |
| LLM numerical grounding | Strict validated claims; no free prose | Unchanged. No retry changes, no new model/provider requests for knowledge | `backend/genai/` |
| Provider/retrieval failures, missing values | Explicit unavailable, no fabricated fallback | Preserved by existing tests; environmental results stay accessible after AI failure | service and presentation API |
| React | Five real pages, polished evidence/charts | Assistant adds clear category panels and main-input contextual routing; measured results remain available in analytics across a general answer | `frontend-react/src/Assistant.tsx` |
| Streamlit backup | Independent HTTP client | Unchanged; receives calendar/follow-up normalization improvements through existing routes. General-knowledge router UI is React-only | `streamlit_app/` unchanged |

Original variables in the NLP vocabulary are TEMPERATURE, PRECIPITATION, HUMIDITY, WIND_SPEED, AIR_QUALITY, NDVI, SOIL_MOISTURE, LAND_COVER, LAND_SURFACE_TEMPERATURE, ELEVATION, SLOPE. Original hazard vocabulary is FLOOD, LANDSLIDE, WILDFIRE, EARTHQUAKE, GLOF, CLOUDBURST. Only temperature/precipitation retrieval is connected; displayed rainfall is a separate provider-derived daily field.

Historical retrieval is ERA5 via Open-Meteo for periods ending at least six days ago. Recent data use weather-model output; today's daily estimates can include forecast hours. Retrieval is limited to non-future periods, dates from 1940, at most 366 inclusive days, and the existing recent-data window. Missing numbers remain null; partial totals and coverage remain visible. Snapshots only cover 1–7 Jan 2025 and are never a silent live-data fallback.

## Audit of additional locations and variables

The original ontology already has canonical town entries for the eight proposed names. That does not establish correct trained NER predictions or a data-provider mapping. A live public Open-Meteo geocoding search (`/v1/search`, count 5, countryCode IN) returned Sikkim candidates for Gyalshing, Pakyong, Rangpo, Singtam, Ravangla, Pelling, Jorethang and Soreng. Pakyong returned two candidates and Singtam four Sikkim candidates plus another state. Administrative matching alone cannot safely select the intended town point. No coordinates have been invented or added; no geocoding endpoint is exposed. The three existing configured town points remain the verified retrieval coverage. An explicit user-reviewed map selection and point validation are future work.

Open-Meteo historical documentation confirms hourly relative_humidity_2m (%), wind fields, surface pressure, snowfall and cloud cover are available upstream. This application currently requests a fixed daily temperature/water contract and validates aligned arrays and units. Adding those variables would require new aggregation conventions (especially circular wind direction), missing-value handling, response schema, fact units/templates, UI and cross-source tests. That expansion is intentionally deferred for the evaluation. No browser-only chart or LLM answer is used to simulate it.

## General knowledge: references and trust boundary

Seven topics: ERA5 reanalysis; rainfall versus precipitation; precipitation; weather versus climate; climate change; greenhouse effect; air temperature at 2 metres. English topic grammar accepts polite/explain/describe/what-is/what-does-mean variations. Hindi and Nepali use documented reviewed formulations, not arbitrary machine translation. Language selection is explicit or follows a recognized native formulation; this is routing, not trained language detection.

Reference pages were retrieved successfully over HTTPS and their relevant text inspected during implementation:

- Open-Meteo historical weather documentation: https://open-meteo.com/en/docs/historical-weather-api
- NASA climate change: https://science.nasa.gov/climate-change/what-is-climate-change/
- NASA greenhouse effect: https://science.nasa.gov/climate-change/faq/what-is-the-greenhouse-effect/
- WMO Climate: https://wmo.int/themes/climate

Answers are short application-maintained reference summaries, not live retrieval from those pages and not Groq-generated prose. No measurements, model confidence or NLP entities are fabricated. Exact whole-question topic matching prevents a measured request such as “What is precipitation in Namchi today?” from being answered as generic science. Source links and scientific limitations remain visible. Input that mixes unsupported requests with a known topic is not stripped down into a knowledge answer. The unavailable ECMWF dataset page (HTTP 401 in cloud) is not used as a catalogue reference.

## Additive endpoint and routing

`POST /assistant/route`

Request: `{question: string (1..4000), session_id: bounded opaque ID, context_id?: bounded server context token|null, language: auto|en|hi|ne (default auto)}`. Extra fields forbidden; clients cannot upload environmental values.

Response: `{category: environment|general_knowledge|contextual|unsupported|clarification, message: string, knowledge: null|{topic,title,text,language,label,sources:[{name,url}]}}`.

The route makes no LLM call and performs no trained prediction. `environment` proceeds to the explicitly selected original `/nlp/analyze` or rule-only `/demo/analyze`. There is no automatic rule fallback after missing models, low confidence or model failure. `contextual` is permitted only for a recognized metric formulation with valid session-bound server context and eligible stored facts; React then calls the original `/genai/explain`. General knowledge never creates charts. Unsupported answers provide a supported alternative without numbers. Unknown formulations fall through to the original trained path; routing is not an exhaustive hazard/location detector.

React preserves the original environmental result and context in memory across a general explanation, hides it from that knowledge panel to prevent misattribution, and retains it on Climate Analytics. New environmental submissions clear stale query results. Existing follow-up form remains strict and bound to the same context. Expired context requires a new environmental query. Streamlit continues to use the original routes and has no dependency on React or the new route.

All existing response contracts remain unchanged. The only new API contract is `/assistant/route` and the corresponding React type. Model/entity confidence stays unmodified; date normalization continues to report `explicit_time_from_text`/rule provenance warnings through existing fields.

## Examples

English:
- Show rainfall in Gangtok during January 2025.
- What was the average temperature in Namchi last January?
- How much did it rain in Gangtok during the first week of January 2025?
- Compare rainfall in Gangtok and Namchi from 2025-01-01 to 2025-01-07.
- Which of the two locations was warmer during the selected period? (Requires a complete two-town session.)
- Summarize the temperature changes during the retrieved week. (Descriptive mean/min/max only.)
- What does ERA5 reanalysis mean?
- Explain the difference between rainfall and precipitation.

Hindi:
- गंगटोक में जनवरी 2025 के पहले सप्ताह में तापमान और बारिश दिखाएं।
- नामची में जनवरी 2025 का तापमान दिखाएं।
- कुल बारिश कितनी हुई? (stored follow-up)
- दोनों स्थानों में कौन सा अधिक गर्म था? (stored comparison)
- जलवायु परिवर्तन क्या है?
- बारिश और वर्षण में क्या अंतर है?

Nepali:
- गान्तोकमा जनवरी २०२५ को पहिलो हप्ता तापक्रम र वर्षा देखाउनुहोस्।
- नाम्चीमा जनवरी २०२५ को तापक्रम देखाउनुहोस्।
- कुल वर्षा कति भयो? (stored follow-up)
- दुई स्थानमध्ये कुन बढी न्यानो थियो? (stored comparison)
- ERA5 पुनर्विश्लेषण भनेको के हो?
- वर्षा र वर्षणमा के फरक छ?

Environmental examples still depend on trained model intent/entity predictions. Native Gregorian months do not imply support for the Bikram Sambat calendar. “First week” is days 1–7; for other week interpretations use explicit dates. “Compare rainfall in Gangtok and Namchi” with no previous usable period must ask for dates; it must not invent one.

## Windows integration and evaluation

These changes are not committed/pushed yet. After approved preservation and retrieval, keep your existing trained checkpoints and Python environment. No new dependencies or credentials are required. Stop/restart FastAPI so the new route is registered; the old running backend will return 404 to the new React client.

Backend terminal (existing Groq environment stays backend-only):

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind'
python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000
```

Check the additive route from another PowerShell terminal:

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/assistant/route' -ContentType 'application/json' -Body (@{question='What does ERA5 reanalysis mean?';session_id='windows-check';language='en'} | ConvertTo-Json)
```

Expected category: `general_knowledge`, with cited knowledge and no measurements. HTTP 404 means the presentation backend has not been updated/restarted.

React terminal (Node 22.12+ or 24):

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind\frontend-react'
npm ci
npm test
npm run build
npm run dev
```

Open http://127.0.0.1:5173. Default Vite proxy targets 8000; no CORS change. Do not put provider keys in browser environment variables.

Python verification / backup terminal:

```powershell
Set-Location 'C:\Users\pawan kumar singh\TerraMind'
python -m pytest -q
python scripts/verify_genai.py --mode trained --source live --require-llm --min-interval-seconds 10
# Streamlit backup, independently:
$env:TERRAMIND_API_URL='http://127.0.0.1:8000'
python -m streamlit run streamlit_app/app.py --server.port 8501
```

Smoke-check the exact ISO seven-day example, month/year and first-week examples in all three languages, a same-period two-town comparison and warmer follow-up, reference knowledge (no charts), a missing-date query, humidity, unknown town, and earthquake prediction. Verify model outputs stay labelled trained and original provenance/coverage/units remain accessible. A Groq failure must not remove weather results. Do not deploy or replace the established Windows version until this smoke check passes; the current reviewed commit remains the fallback.

Detailed test results and final recommendation are in `docs/QUESTION_VERIFICATION.md`.

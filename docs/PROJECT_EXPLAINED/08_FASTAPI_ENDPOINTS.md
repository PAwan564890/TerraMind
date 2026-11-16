# FastAPI endpoints and compatibility

Run `python -m uvicorn backend.presentation.app:app --host 127.0.0.1 --port 8000`. Runtime `/docs` and `/openapi.json` are authoritative for complete schemas. Existing endpoints and the original NLP engine remain intact; additions use separate products rather than silently redefining original weather units.

| Endpoint | Purpose |
|---|---|
| GET `/health` | Original service/checkpoint health; configuration alone is not inference proof |
| GET `/system` | Modes, active towns, provider configuration and optional capability metadata |
| POST `/nlp/analyze` | Original trained text → validated structured query |
| POST `/demo/analyze` | Explicit opt-in labelled rules; disabled unless `TERRAMIND_DEMO=1` |
| POST `/assistant/route` | Environmental/follow-up/general/unsupported/clarification routing |
| POST `/environment/query` | Validated structured query + source mode → original weather response |
| POST `/environment/session` | Weather retrieval + bounded stored context + optional explanation |
| POST `/genai/explain` | Matching session/context + question/language → validated explanation |
| GET `/locations` | Active registry, supplemental capability and point-data limitations |
| POST `/environment/selected` | One/two registered IDs, start/end, session ID, source mode/language → weather, insights and explicit-selection label |
| POST `/environment/insights` | Session/context IDs → server-owned temporal insights and comparisons |
| POST `/environment/measurements` | Structured query/source mode → typed separate humidity/wind response |

Example explicit-selection JSON (no NLP claim):

```json
{"location_ids":["loc:gangtok","loc:pelling"],"start":"2025-01-01","end":"2025-01-07","session_id":"presentation_check","source_mode":"live","language":"en"}
```

Use IDs returned by `/locations`, not user-invented values. Context requests bind session and context IDs. Requests reject unsupported dates/variables, unknown locations and unexpected fields where specified. New insights do not let clients supply environmental facts. The Vite `/api` proxy strips `/api` and forwards to FastAPI; API secrets stay server-side. This local prototype is not production multi-user authentication or persistent storage.

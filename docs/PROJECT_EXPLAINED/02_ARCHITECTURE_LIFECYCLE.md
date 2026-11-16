# Architecture and complete request lifecycle

```text
React or Streamlit → FastAPI presentation API
  → routing / original trained NLP (explicit demo endpoint is separate)
  → validated StructuredQuery
  → environmental provider → validated daily rows + provenance
  → deterministic summaries / temporal insights / aligned comparisons
  → bounded server-side environmental context
  → optional LLM fact selection → strict validation → fixed-language rendering
  → client metrics, charts, evidence and Inspector
```

`backend/presentation/app.py` extends the original `backend/api/app.py`; original NLP contracts remain in place. `backend/presentation/routing.py` distinguishes supported retrieval, stored-context follow-up, clarification, unsupported requests and general knowledge. NLP labels alone do not prove data support.

A typical request asks for Gangtok temperature and rainfall for 2025-01-01 through 2025-01-07. The original pipeline detects language and predicts intent/entities, resolves the registered point and explicit inclusive dates, then validates the structured query. The environmental service chooses live or explicitly selected snapshot data. Provider output must have supported units, aligned dates and valid numbers before statistics are computed. Missing values remain null. Provenance accompanies the actual period and grid coordinates.

A session retains validated weather facts. Follow-up requests must use the matching session/context IDs and stay within stored variables, places and dates. A provider error returns an unavailable explanation while leaving environmental results available. Context expiry requires a fresh environmental query. NLP conversation slots and environmental fact context are separate mechanisms: NLP idle expiry is 1800 seconds with five-turn slot age; environmental context defaults to 900 seconds and 128 entries.

The map route is deliberately different: explicit registered IDs and dates go through `/environment/selected`, bypassing trained NLP with a visible selection-mode label. Supplemental humidity/wind use `/environment/measurements`, not a fabricated extension of the original weather bundle. Browser code never receives the provider API key.

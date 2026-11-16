# Grounded generative explanations

Evidence: `backend/genai/client.py`, `service.py`, `context.py`, `facts.py`, `questions.py` and `schema.py`. The original provider client and core validation service are unchanged by foundations.

Generation occurs after retrieval and deterministic computation. A validated server context supplies facts with values, units, locations, time period and source IDs. The provider selects a structured claim list; free prose is not accepted as authoritative evidence. Claim fields are strictly constrained: fact ID, value, unit, location IDs, start, end and source IDs. Numerical/source/location/date mismatches and unexpected fields fail validation. Rendering uses fixed English, Hindi or Nepali wording and server facts.

New warmest/coolest/wettest/driest facts are computed from validated rows. The full query interval remains the claim interval; a primary event date is server-owned metadata, never an extra provider claim field. All tied dates remain available in the insights product. Default summaries exclude these additional day facts unless relevant, keeping prompts compact.

Follow-ups require matching session/context IDs and supported stored metrics. A rainfall session cannot answer absent humidity, another place or another period. Provider errors, missing credentials, expired context and unsupported questions do not turn into invented successful explanations. Supplemental humidity/wind currently have separate deterministic displays and are not eligible weather GenAI facts.

## Configuration

Use backend-only environment variables; never put keys in React variables, repository files, screenshots or chat:

- `TERRAMIND_LLM_PROVIDER`: `disabled` by default; `openai` or an OpenAI-compatible provider identifier with a configured URL.
- `TERRAMIND_LLM_BASE_URL`: for Groq, `https://api.groq.com/openai/v1`.
- `TERRAMIND_LLM_MODEL`: existing Windows configuration may use `openai/gpt-oss-20b`.
- `TERRAMIND_LLM_API_KEY`: obtain through your existing private environment, not this guide.
- `TERRAMIND_LLM_TIMEOUT_SECONDS`: default 15, clamped 1–30.
- `TERRAMIND_LLM_MAX_ATTEMPTS`: bounded attempts; default 2.
- `TERRAMIND_LLM_RETRY_MAX_WAIT_SECONDS`: default 5, clamped 0–15.

Safe diagnostics classify rate limiting, authentication, timeout, transport, invalid response, rejection and grounding failures without logging credentials or sensitive full payloads. Transient retries are bounded and respect supported Retry-After guidance; authentication and unsupported questions are not retried. No credentials means real data and analytics still work without a generated response. Provider-configured status is not proof of a successful provider call.

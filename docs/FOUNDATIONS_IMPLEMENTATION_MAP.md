# Preservation and implementation map

Actual starting commit: `01bf4942174dfb2b1fac9fe57e841a07bd4b3716`, already committed and pushed on `feature/grounded-genai-prototype`. The master prompt's description of the question expansion as uncommitted was stale. Repository identity: `https://github.com/PAwan564890/TerraMind.git`. Protected master remains `eb483eac04e73009bd7a8a87a0a0093a95f998f1`.

The source checkout `/workspace/TerraMind` was clean and has been preserved. Development uses `/workspace/TerraMind-foundations`, a separate worktree on local branch `feature/geospatial-intelligence-foundations`, based on the same commit. No changes have been committed, pushed, merged or deployed for this task. No model checkpoint or Windows directory was accessed or overwritten.

Audited baseline: original NLP schemas/enums/ontology/normalizer, presentation routes, environmental provider/service/analytics, grounded fact compiler/schema/service/questions, React pages/API client, Streamlit client/UI, and prior regression suites/docs. Actual baseline checks passed: **771 backend tests and 48 React tests**.

| Area | Starting state | Implementation |
|---|---|---|
| Original multilingual trained NLP | Present | Preserved; no checkpoint/NER/intent changes |
| Question expansion/calendar understanding | Present and committed | Reused; router now respects optional active registry/measurements |
| Three-point environmental adapter | Working | Stable IDs/coordinates and calculations preserved; registry opt-in expands to ten |
| Extra town coordinates | Missing validated adapter registry | Reviewed GeoNames/Open-Meteo candidates, central schema/data, API and live verification |
| Geocoding ambiguity | Pakyong/Singtam known ambiguous | Excluded; Chungthang unresolved; no runtime global geocoding |
| Descriptive insights | Basic summaries only | Backend extrema, ties, changes, ranges, monthly portions, coverage and comparable differences |
| Scientific GenAI | Strict facts/validation | Added server-owned event-date metadata and bounded day-event follow-ups; no authoritative LLM arithmetic |
| Geographical map | Missing | React Leaflet/Leaflet + real OSM tiles, automatic bounds, keyboard selection, real API retrieval and comparison handoff |
| AI Pipeline Inspector (added requirement) | Missing | Native expandable three-stage view over actual returned responses; collapsed by default |
| Humidity/wind speed | NLP enum/ontology existed; retrieval unconnected | Opt-in separate validated daily-measurement endpoint and React view; deliberately excluded from weather GenAI context |
| Wind direction/pressure/snow/clouds | Unconnected | Remain unsupported; no substitution |
| Reliability | Generic Open-Meteo errors, no retries | Sanitized categories, bounded idempotent GET retry, retry guidance and partial-result preservation |
| Streamlit | Working independent backup | Preserved; only supported-town caption reads actual backend registry instead of a hardcoded list |

The opt-in flags keep the proven three-town/default behavior recoverable. Both `TERRAMIND_EXTENDED_LOCATIONS=1` and `TERRAMIND_ADDITIONAL_MEASUREMENTS=1` are explicit backend flags. No Python dependencies were added. New frontend dependencies are Leaflet, React Leaflet and Leaflet type declarations.

The new explicit-selection API is not a trained NLP substitute: its response explicitly labels user-selected registry points/dates and no trained prediction. Existing trained endpoints still return 503 when checkpoints are unavailable. A map-selected pair can be handed to the existing trained Comparison page, whose model execution still requires real checkpoints.

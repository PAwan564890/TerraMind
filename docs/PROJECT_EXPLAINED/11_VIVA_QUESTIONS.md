# Technical viva: 60 questions with answers

Answers refer to actual implementation, not proposed features.

## 1. What is TerraMind?

An academic multilingual environmental-query prototype combining trained NLP, validated data, deterministic analytics and optional grounded explanations.

## 2. Which languages are supported?

English, Hindi and Nepali; actual trained performance on new queries still needs local verification.

## 3. Does the map use trained NLP?

No. Explicit selected locations and dates are labelled as manual selection and go through validated environmental retrieval.

## 4. What is the original intent encoder?

The historical model card describes XLM-RoBERTa-based intent classification; no new training was performed here.

## 5. What does NER produce?

Entity spans/types that are normalized into canonical locations, variables and time expressions before query validation.

## 6. Does every NLP intent imply a supported API measurement?

No. Capability validation rejects unsupported measurements even when an intent label is recognized.

## 7. How is rule demonstration separated?

It uses the explicitly enabled demo endpoint and visible labels; the trained endpoint never silently substitutes rules.

## 8. Were checkpoints modified?

No. Foundations preserve the original checkpoint path and inference code.

## 9. Can cloud tests prove Windows trained inference?

No. Missing cloud checkpoints require an explicit Windows revalidation.

## 10. Is new model accuracy claimed?

No. Historical model-card metrics are not a fresh evaluation of this implementation.

## 11. Why validate dates after NLP?

An explicit interval must retain its exact dates, valid chronology and supported inclusive span.

## 12. Is 2025-01-01 to 2025-01-07 seven days?

Yes, inclusive length is (end minus start).days plus one; it must not become a full year.

## 13. Are Nepali calendar dates converted?

No general Bikram Sambat conversion is implemented; use supported Gregorian dates.

## 14. What is the structured query?

A validated contract containing intent, operation, locations, variables and normalized time information.

## 15. How are low-confidence requests handled?

The original confidence/domain checks may request clarification or reject out-of-domain content.

## 16. What is the environmental source?

Open-Meteo serves historical ERA5 and recent weather-model data with explicit source metadata.

## 17. Are values station observations?

Not generally. They are gridded estimates and must be labelled accordingly.

## 18. Why show requested and returned coordinates?

The requested town point and provider model-cell point can differ.

## 19. Why can two towns have identical values?

Nearby points may use the same coarse model grid cell.

## 20. How many registry points are available?

Ten with the extended-location flag, otherwise the original three.

## 21. Why exclude ambiguous geocoding results?

Choosing an unverified candidate could attach measurements to the wrong place.

## 22. What does rainfall mean?

A daily rainfall amount in mm; it is not automatically identical to total precipitation.

## 23. What does humidity measure?

Daily mean relative humidity at 2 metres, in percent, in the separate supplemental product.

## 24. What does wind speed measure?

Daily mean scalar speed at 10 metres in m/s, not direction or gusts.

## 25. What limits humidity values?

Finite numeric validation and the physical relative-humidity interval 0 to 100 percent.

## 26. Is missing rainfall zero?

No. Null means unavailable; zero is a valid measured/modelled dry day.

## 27. How is mean temperature calculated?

Arithmetic mean of available validated daily means, with coverage shown.

## 28. How is rainfall total calculated?

Sum of available daily amounts; all-missing data remain unavailable.

## 29. What is the warmest day?

The date of the highest valid daily mean temperature, not the highest instantaneous reading.

## 30. How are ties represented?

Earliest date is primary and all tied dates remain available in insights.

## 31. What is daily temperature range?

Daily maximum minus daily minimum when both values exist.

## 32. What is day-to-day temperature change?

Difference between daily means on adjacent calendar dates; missing dates are not bridged.

## 33. Is a partial monthly total a full-month estimate?

No. It is explicitly labelled as the retrieved portion of that calendar month.

## 34. When can towns be compared?

Matching periods, timezone, data kind and complete aligned coverage are required per compared metric.

## 35. Which subtraction direction is used?

Left location minus right location, using unrounded numeric values.

## 36. Does display rounding affect validation?

No. Formatting is a presentation operation; calculations and validation retain precision.

## 37. Do short-term insights establish climate change?

No. Descriptive short-term variation is not a long-term trend or causal attribution.

## 38. What does the LLM calculate?

It must not authoritatively calculate measurements; it selects server-computed facts for validated rendering.

## 39. How are hallucinated numbers rejected?

Claims must exactly match known fact values, units, source IDs, locations and dates.

## 40. Can provider prose bypass grounding?

No. Arbitrary prose is not accepted as a validated environmental explanation.

## 41. How is a day event grounded?

The server computes the event value/date; the claim retains the query interval and event-date metadata is server-owned.

## 42. Can humidity be explained by the current weather LLM context?

No. Supplemental humidity/wind facts have not been integrated into that context.

## 43. What makes a follow-up contextual?

It uses matching stored session/context IDs and requests only supported metrics, places and dates already present.

## 44. What happens when context expires?

The user must submit a fresh environmental query; unavailable context cannot be reconstructed by guessing.

## 45. What if credentials are absent?

Real environmental retrieval and deterministic analytics remain available without a generated explanation.

## 46. What if Groq returns 429?

Safe diagnostics identify rate limiting and eligible bounded retries respect supported provider guidance.

## 47. Are authentication failures retried?

No. Credentials must be corrected privately; retrying does not solve authentication.

## 48. Where are API keys stored?

In the existing private backend environment/configuration, never browser code or committed source.

## 49. Is configured provider status live verification?

No. A genuine successful validated provider response is required.

## 50. What map library is used?

React Leaflet wraps Leaflet and loads actual OpenStreetMap raster tiles.

## 51. How does comparison handoff work?

Selected registered IDs are encoded into the Comparison route and populate its town selectors.

## 52. What if map tiles fail?

A visible notice appears while accessible town selection and environmental retrieval remain usable.

## 53. How can keyboard users select a marker?

Focusable marker buttons support Enter/Space; equivalent town checkboxes also remain available.

## 54. What does the Inspector expose?

Actual returned inference labels/entities/query, environmental evidence and validated GenAI status/claims.

## 55. Does the Inspector expose chain-of-thought?

No. It shows public execution evidence, not private reasoning, raw prompts or secrets.

## 56. Is Streamlit dependent on React?

No. It is an independently runnable API client and backup UI.

## 57. What proves missing-data behavior?

Regression tests exercise nulls, coverage, incomplete comparison and unavailable source responses.

## 58. What does the production build verify?

TypeScript build checks and Vite bundling, supplemented by separate preview browser tests.

## 59. Which tests are mocked?

Injected provider/model fixtures verify contracts and grounding; they do not prove real model/provider behavior.

## 60. What is the deployment recommendation?

Conditional GO for a supervised demonstration after Windows trained/Groq verification, not production deployment approval.

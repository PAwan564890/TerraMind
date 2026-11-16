# Vision and scope

TerraMind helps users ask environmental questions in English, Hindi and Nepali, inspect real gridded weather estimates, compare registered Sikkim town points, and obtain optional grounded explanations. It is an academic prototype, not an operational hazard warning service or a station observation network.

The original trained NLP route is preserved. Deterministic normalization, capability checks and server-side statistics surround that route. An optional OpenAI-compatible provider selects validated facts rather than creating environmental measurements. React is the primary presentation; Streamlit remains a separate backup client.

Foundations add ten opt-in locations, daily humidity and wind-speed retrieval, descriptive temporal insights, a real OpenStreetMap view, selection-to-comparison handoff and an Inspector. The default three-location behavior remains available. Neither newly registered aliases nor explicit map selections are trained-model predictions.

Implementation boundaries: no retraining, changed weights, new model-accuracy claim, RAG, autonomous agents, climate forecasting, causality or statistical significance inference. Mixed temperature/rainfall plus humidity/wind natural-language requests are not automatically split into products. The map form can request these products explicitly. Supplemental measurements are not added to the weather GenAI fact context.

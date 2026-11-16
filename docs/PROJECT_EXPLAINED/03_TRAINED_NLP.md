# Original trained NLP

Code evidence: `backend/nlp/`, `backend/api/app.py`, `docs/MODEL_CARD.md` and the repository's training scripts. Foundations do not alter these files or checkpoint weights.

The existing model card describes XLM-RoBERTa-based intent and token classification, a character n-gram TF-IDF/logistic-regression Hindi/Nepali language detector with an English script shortcut, and multilingual E5 embeddings for domain support. Those are distinct components: using a pretrained encoder is different from training every component from scratch. Historical training/evaluation descriptions should be consulted directly in the model card; no accuracy or new evaluation metric is asserted here.

The pipeline preprocesses text, detects language, obtains trained intent and NER predictions, normalizes ontology slots and time expressions, applies domain/confidence checks, resolves eligible conversation slots, structures the query and validates it. Entity types and BIO token labels are internal model outputs; the public response exposes spans, offsets, types, canonical IDs, confidence/mode and structured query. It does not expose private reasoning.

Intent labels cover weather, climate trend, vegetation, disaster risk, geolocation, comparison, scenario analysis, general environment and out-of-domain. These labels are broader than available environmental measurements; unsupported retrieval must still be rejected. Low confidence and missing necessary information can require clarification.

Deterministic explicit-date handling protects full ISO ranges from year-only expansion, validates dates/order and preserves the inclusive requested interval. Gregorian dates and reviewed natural-language rules are supported; this is not a Bikram Sambat conversion engine.

The explicitly enabled `/demo/analyze` route is rule demonstration. `/nlp/analyze` does not silently fall back to rules when checkpoints are missing. Cloud tests with injected pipelines or demo rules are not genuine trained-model verification. Native-language aliases inherited from the ontology are not a new native-speaker certification or evidence of expanded NER accuracy.

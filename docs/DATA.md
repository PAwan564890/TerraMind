# TerraMind query dataset

Dataset card for the NLP training and evaluation data. Environmental data
sources (weather, satellite, terrain) are a later phase and are not covered
here.

## What it is

Natural-language environmental questions in English, Hindi and Nepali. Each
row is labelled for intent classification and for named-entity recognition.

| File | Rows | Made by | Used for |
| --- | --- | --- | --- |
| `backend/nlp/data/train.jsonl` | 2,572 | Template generator | Training |
| `backend/nlp/data/val.jsonl` | 647 | Template generator | Early stopping, threshold selection |
| `backend/nlp/data/test/test.jsonl` | 648 | Template generator | Held-out template test |
| `backend/nlp/data/test/gold.yaml` | 51 | Hand-written | Development set: inspected many times, no longer a clean test |
| `backend/nlp/data/test/gold_v2.yaml` | 51 | Hand-written | Development set: two fixes were designed from its errors |
| `backend/nlp/data/test/realistic.yaml` | 58 (54 scored) | Hand-written, real-user style, one language per query | The end-to-end figure to quote. Not real user data |
| `backend/nlp/data/test/dialogues.yaml` | 18 dialogues, 43 turns | Hand-written | Conversation context |
| `backend/nlp/data/test/synonyms.yaml` | 78 words | Hand-written | Embedding fallback test |

Regenerate the first three with `python scripts/generate_dataset.py`. The
output is deterministic for a given config and seed, and a test fails if the
files on disk differ from what the generator produces.

## How it is made

1. **Template families** (`backend/nlp/dataset/templates.yaml`). A family is
   one meaning phrased independently in each language, not translated word
   for word. There are 100 families across 9 intents. Nine of them were added to fix
   observed failures (five in Phase 12, four after the final evaluation) and
   are pinned to the training split.
2. **Slot filling.** Slots such as `{loc}` and `{cvar}` are filled from the
   ontology and from `lexicon.yaml` (time and change expressions). The
   character span of each filled slot becomes an entity label, so NER labels
   cost nothing extra.
3. **Light noise.** 15% of English rows are lowercased and 20% of rows lose
   their final punctuation mark.

## Record format

```json
{"id": "trend.how_changed.ne.001",
 "text": "पछिल्ला तीन महिनामा सोरेङको वर्षामा कस्तो परिवर्तन आएको छ?",
 "language": "ne", "intent": "CLIMATE_TREND", "operation": "TREND", "direction": null,
 "entities": [{"start": 0, "end": 17, "type": "TIME", "text": "पछिल्ला तीन महिना",
               "normalized": {"type": "relative_past", "value": 3, "unit": "month"}},
              {"start": 20, "end": 25, "type": "LOCATION", "text": "सोरेङ",
               "normalized": "loc:soreng"}, "..."],
 "group_id": "trend.how_changed", "source": "template", "split": "val",
 "heldout_location": false}
```

Offsets are character positions, start inclusive and end exclusive.

## Split design

- **By family, not by row.** Each family goes wholly into one split (per
  intent: 2 validation, 2 test, the rest train). This blocks template leakage
  (same sentence frame, different town) and translation leakage (the Hindi
  version of a training sentence in test).
- **Held-out locations.** Lachen, Ravangla, Jorethang, Singtam and Yuksom never
  appear in train or validation. 274 of 648 test rows contain one.
- **Out-of-domain topics differ by split**, because each topic is its own
  family. Test OOD topics are unseen in training.
- **Hard negatives.** One OOD family uses environmental words in another sense
  ("a landslide election victory").

## Balance

Languages are within a few rows of each other for every intent. Intents are
not balanced in train: `WEATHER_QUERY` has 450 rows, `GENERAL_ENVIRONMENT`
441 and `OUT_OF_DOMAIN` 355, against 210 to 252 for the others. Class
weighting is implemented but off; see docs/EVALUATION.md for the effect.

## Known limitations

- **Unreviewed Hindi and Nepali.** All non-English text was drafted by an AI
  assistant and has not been checked by a fluent speaker. Treat every score on
  this data as provisional until it is.
- **Synthetic and repetitive.** 3,867 rows come from 100 families. Real users
  phrase things in ways no template covers, so scores on `test.jsonl` will
  overstate real-world accuracy. The gold set exists to measure that gap.
- **The gold set is small.** 51 queries, against a design target of about 450.
  It is enough to catch gross failures, not to report a precise accuracy.
- **Some fills are grammatically rough.** A slot can receive a form that does
  not fit perfectly ("events of floods", "बादल फटना का खतरा"), and Hindi
  templates avoid gender agreement by using constructions like "का स्तर",
  which is correct but more formal than everyday speech.
- **Some fills are semantically odd,** such as a scenario that raises air
  quality by 25%. They are valid for language understanding, not for science.
- **Time expressions are a small closed list.** Years are read as Common Era;
  Bikram Sambat dates are not handled.
- **No romanised or code-mixed text.**
- **No unseen variable-and-intent combinations are held out.** The design
  document proposed this; only held-out locations are implemented.

## Provenance

Authored for this project. No external dataset or scraped text is included.
Place names and the district structure come from the gazetteer in
`backend/nlp/ontology/data/locations.yaml`, which cites its source.

# Model card: TerraMind NLP models

Four models are involved. Two are fine-tuned by this project, one is trained
from scratch, one is used as published.

**Read this first.** No fluent Hindi or Nepali speaker has reviewed the
training or test data, and no real user queries were used. All of it was
drafted by an AI assistant. Results describe behaviour on that data.

## Overview

| Model | Task | Base | Trained by this project | Size on disk |
| --- | --- | --- | --- | --- |
| Intent classifier | 9-way query classification | `xlm-roberta-base` | Fine-tuned, 3 seeds | about 1.1 GB per seed |
| NER | BIO tagging, 5 entity types | `xlm-roberta-base` | Fine-tuned, 3 seeds | about 1.1 GB per seed |
| Language detector | Hindi versus Nepali | none | Trained from scratch (TF-IDF + logistic regression) | under 100 KB |
| Sentence embeddings | Similarity for the out-of-domain check | `intfloat/multilingual-e5-small` | Used as published | about 470 MB |

A small development configuration (`intfloat/multilingual-e5-small` for intent
and NER) is kept for CPU-only work; select it with `active_run: dev`.

Trained artefacts are not in the repository. They are reproduced by the
scripts in `scripts/`; see the README.

## Intended use

Turning questions about Sikkim's weather, climate, vegetation, geography and
natural hazards, written in English, Hindi (Devanagari) or Nepali
(Devanagari), into a structured query for a downstream system.

**Out of scope:** any other region; romanised Hindi or Nepali; other
languages; answering questions; operational warnings or any decision that
affects safety. The models classify and extract. They know nothing about the
environment itself.

## Training data

Generated from 100 hand-written template families (see [DATA.md](DATA.md)):
2,572 training rows, 647 validation, 648 test. A family is one meaning phrased
separately in each language, and a family never spans two splits. Five towns
appear only in test.

| Intent | Training rows |
| --- | --- |
| `WEATHER_QUERY` | 450 |
| `GENERAL_ENVIRONMENT` | 441 |
| `OUT_OF_DOMAIN` | 355 |
| `COMPARISON` | 252 |
| `CLIMATE_TREND`, `VEGETATION_ANALYSIS`, `DISASTER_RISK`, `SCENARIO_ANALYSIS` | 216 each |
| `GEOLOCATION_QUERY` | 210 |

Properties of this data that shape the models:

- Synthetic and repetitive: about 26 rows per sentence frame.
- Not balanced across intents. Class weighting is implemented and off.
- Hindi templates avoid gender agreement by using formal constructions.
- A small closed list of time expressions.

## Training run (recorded)

Run on 8 October 2026 on a laptop with an NVIDIA GeForce RTX 2050 (4 GB),
PyTorch 2.14.1+cu126, Transformers 5.18.0, mixed precision. GPU memory use was
3.9 of 4.0 GB. Each epoch took about 5 minutes.

| Setting | Intent | NER |
| --- | --- | --- |
| Base model | `xlm-roberta-base` | `xlm-roberta-base` |
| Optimiser | AdamW, weight decay 0.01 | same |
| Learning rate | 2e-5 | 3e-5 |
| Schedule | 10% warm-up, linear decay over 10 epochs | same |
| Batch size, max length | 16, 64 tokens | same |
| Gradient clipping | 1.0 | 1.0 |
| Loss | Cross-entropy, no class weighting | Cross-entropy over tokens, special tokens ignored |
| Early stopping | 2 epochs without better validation macro-F1 | 2 epochs without better validation entity F1 |

| Task | Seed | Best epoch | Epochs run | Validation score |
| --- | --- | --- | --- | --- |
| Intent | 42 | 2 | 4 | 0.9752 macro-F1 |
| Intent | 43 | 3 | 5 | **0.9798** (used by the pipeline) |
| Intent | 44 | 6 | 8 | 0.9658 |
| NER | 42 | 3 | 5 | **0.9185** entity F1 (used by the pipeline) |
| NER | 43 | 6 | 8 | 0.9109 |
| NER | 44 | 2 | 4 | 0.9093 |

These settings are starting values and were not tuned. The exact
configuration, library versions and per-epoch history of every run are saved
in `models/<task>/full/seed_<n>/metrics.json`.

The wall-clock times recorded in those files are not training times: the
laptop entered standby during the run and the timer kept counting.

After training, on validation data: temperature 1.151 for the intent
probabilities; confidence threshold 0.30; similarity below 0.864 is
off-topic; similarity at or above 0.895 is firmly in-domain. These are stored
in `models/decision/thresholds.json` and belong to these specific models.

Language detector: character 1 to 3-grams within word boundaries, TF-IDF with
sublinear term frequency, logistic regression. Trained on the Hindi and Nepali
training rows plus two random short fragments per row, 5,088 texts. Digits and
Latin text are removed first.

## Results

Full tables, method and caveats are in [EVALUATION.md](EVALUATION.md).

| Measure | All | English | Hindi | Nepali |
| --- | --- | --- | --- | --- |
| Intent accuracy, template test, 3 seeds | 91.6% ± 3.3 | 89.0% ± 3.0 | 90.3% ± 4.0 | 95.5% ± 3.4 |
| Intent accuracy, gold, 3 seeds | 92.8% ± 1.1 | 96.1% ± 3.4 | 90.2% ± 3.4 | 92.2% ± 3.4 |
| NER entity F1, exact span, template test, 3 seeds | 0.923 ± 0.005 | 0.970 ± 0.001 | 0.947 ± 0.009 | 0.853 ± 0.021 |
| NER + normalisation, value-level F1, template test | 0.976 | 0.986 | 0.969 | 0.972 |
| Whole pipeline, complete query, realistic set (54) | 61.1% | 70.6% | 63.2% | 50.0% |
| Whole pipeline, complete query, gold_v2 (51) | 74.5% | 64.7% | 76.5% | 82.4% |
| Whole pipeline, complete query, template test (648) | 89.7% | 92.1% | 86.1% | 90.7% |

Language detector: 99.4% on the template test set, 100% on gold, 84.7% on
one- and two-word Hindi and Nepali fragments.

Embedding model, chosen over
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`: mean
cross-language Recall@1 of 0.81 against 0.47 on 150 generated parallel
triples. As an off-topic signal on the test set: AUROC 0.993.

### Compared with the development models

| | Development (`e5-small`, 1 seed) | Final (`xlm-roberta-base`) |
| --- | --- | --- |
| Intent accuracy, gold | 84.3% | 92.8% ± 1.1 |
| NER entity F1, template test | 0.929 | 0.923 ± 0.005 |
| Real Hindi/Nepali test queries rejected as off-topic, before the data fix | 23 | 0 |

The larger model clearly helps intent and does not help NER.

## Known failure modes

- **Words that imply a variable** and are not in the ontology: "rainier",
  "wetter", loanwords such as टेम्परेचर, Nepali पानी पर्नु for rain. On the
  realistic set such queries are right 1 time in 10. This is the largest
  source of error on realistic text and is worst in Nepali.
- **Intent flips on unseen sentence frames.** A trend asked as "wetter or
  drier?" is read as a comparison; "how likely is a flood?" as a general
  question.
- **NER tags "sea level"** (समुद्र तल, समुद्र सतह) as an entity in Hindi and
  Nepali, and sometimes merges adjacent place names. The second is repaired
  after NER; the first is not.
- **Nepali entity boundaries.** Exact-span F1 is capped near 0.91 by the
  tokenizer. Normalisation removes the endings.
- **Short Devanagari text** often cannot be assigned to Hindi or Nepali.
- **Romanised Hindi and Nepali** are detected as English and rejected as
  off-topic.
- **Confidence on hand-written text** is over-stated (calibration error 0.09
  on gold against 0.03 on template test).
- **Seed variance.** Intent accuracy on the test set varies by 3 to 4 points
  between seeds.

## Ethical and practical considerations

- **Unequal quality across languages** is measured and reported per language.
  It is not solved: Nepali is 20 points behind English on realistic input.
- **No personal data** is used in training or needed at run time. Query text
  is not logged by default.
- **Not for safety decisions.** Classifying a question about flood risk is
  not assessing flood risk.
- **Base model licences.** `xlm-roberta-base` and
  `intfloat/multilingual-e5-small` are third-party models. This project has
  not reviewed their licences or model cards; do so before redistributing
  anything built from them.

## How to reproduce

```powershell
python scripts/generate_dataset.py
python scripts/train_language_detector.py
python scripts/train_intent.py --model full
python scripts/train_ner.py --model full
python scripts/select_thresholds.py
python scripts/evaluate_end_to_end.py --tag reproduce
```

Seeds are fixed, but GPU training is not bit-for-bit deterministic. Expect
figures within the seed spread shown above, not identical ones.

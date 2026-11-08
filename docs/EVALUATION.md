# TerraMind NLP: evaluation

**What these numbers are.** Final models: `xlm-roberta-base` fine-tuned for
intent and for NER on an RTX 2050, three seeds each (42, 43, 44). The pipeline
uses the seed with the best validation score for each task (intent 43, NER 42).

**What they are not.** No fluent Hindi or Nepali speaker has reviewed any of
the data, and no real user has typed a query. Every dataset here was written
by the same AI assistant that wrote the system. Treat every figure as
provisional until both of those change.

Reproduce with:

```powershell
python scripts/evaluate_end_to_end.py --tag my_run
```

## 1. Evaluation sets

| Set | Size | What it is | How clean |
| --- | --- | --- | --- |
| realistic | 58 (54 scored) | Real-user-STYLE queries: typos, keywords, loanwords, chatty openings, unknown places. Written per language, not translated | Written before any final-model result; its errors have now been read once |
| gold_v2 | 51 | Clean hand-written questions, one meaning in three languages | Development set: two fixes were designed from its errors |
| gold | 51 | As gold_v2 | Development set: inspected since Phase 5 |
| test | 648 | Generated from 18 template families unseen in training | Development set: its errors drove the root-cause work below |
| dialogues | 18 dialogues, 43 turns | Hand-written conversations | Development set |

The headline metric is **complete-query exact match**: the status (`ok`,
`needs_clarification`, `out_of_domain`) is right AND intent, operation,
locations, variables, disasters, time period, scenario and target all match.
One wrong field fails the query. An off-topic query is right if it is rejected.

**The realistic set is the number to quote.** It is the only set not used to
design a fix. It is still author-written, so it is a stand-in for real user
data, not a substitute.

## 2. Headline results

Complete-query exact match, final models:

| Set | All | English | Hindi | Nepali |
| --- | --- | --- | --- | --- |
| realistic (54) | 61.1% | 70.6% | 63.2% | 50.0% |
| gold_v2 (51) | 74.5% | 64.7% | 76.5% | 82.4% |
| gold (51) | 82.4% | 82.4% | 82.4% | 82.4% |
| test (648) | 89.7% | 92.1% | 86.1% | 90.7% |

Dialogue turns right: 41 of 43; whole dialogues right: 17 of 18.

Per language each hand-written set has 17 to 19 queries, so one query is 5 to
6 points. Differences of one or two queries are noise.

**The gap between rows is the main finding.** The same system scores 90% on
template-style text, 74 to 82% on clean hand-written questions, and 61% on
messy realistic ones. Nepali falls furthest, to 50%.

## 3. Results by component and language

### Language detection

Script check plus a Hindi/Nepali character n-gram classifier.

| Measure | English | Hindi | Nepali |
| --- | --- | --- | --- |
| Within the pipeline, test set (648) | 100% | 100% | 98.1% |
| Within the pipeline, gold, gold_v2, realistic | 100% | 100% | 100% |
| One- and two-word Hindi/Nepali fragments (432) | n/a | 84.7% overall | |

Short fragments remain the weak point: a single word is often spelled the same
in both languages. The pipeline falls back to the conversation's language.
The off-the-shelf `langdetect` baseline scores 95.8% on the test set.

### Intent classification

Accuracy of the classifier alone, mean and spread over three seeds:

| Set | All | English | Hindi | Nepali |
| --- | --- | --- | --- | --- |
| Validation (647) | 97.4% ± 0.7 | 99.7% ± 0.5 | 95.5% ± 4.8 | 96.9% ± 2.3 |
| Test (648) | 91.6% ± 3.3 | 89.0% ± 3.0 | 90.3% ± 4.0 | 95.5% ± 3.4 |
| gold (51) | 92.8% ± 1.1 | 96.1% ± 3.4 | 90.2% ± 3.4 | 92.2% ± 3.4 |

The spread across seeds on the test set is 3 to 4 points. A single-seed number
on this data is not reliable to better than that.

Intent as it comes out of the whole pipeline (best seed, queries expected in
domain):

| Set | All | English | Hindi | Nepali |
| --- | --- | --- | --- | --- |
| realistic | 91.7% | 93.3% | 100% | 81.2% |
| gold_v2 | 89.6% | 75.0% | 93.8% | 100% |
| gold | 89.6% | 87.5% | 93.8% | 87.5% |
| test | 93.6% | 91.1% | 93.2% | 96.4% |

### NER

Entity-level F1, exact span and type, mean and spread over three seeds:

| Set | All | English | Hindi | Nepali |
| --- | --- | --- | --- | --- |
| Validation | 0.913 ± 0.005 | 0.974 ± 0.010 | 0.984 ± 0.002 | 0.783 ± 0.003 |
| Test | 0.923 ± 0.005 | 0.970 ± 0.001 | 0.947 ± 0.009 | 0.853 ± 0.021 |
| Best possible with this tokenizer, test | 0.970 | 1.000 | 1.000 | 0.910 |

Held-out towns never seen in training: 284 of 296 mentions found exactly.

The larger model did not improve NER over the small development model (0.929
on test). Nepali is capped by the tokenizer, which does not always split a
name from its attached case ending.

### Entity normalisation

Values recovered from NER-predicted spans on the test set (right type and
canonical value, whatever the exact boundary):

| | All | English | Hindi | Nepali |
| --- | --- | --- | --- | --- |
| Value-level F1 | 0.976 | 0.986 | 0.969 | 0.972 |

Normalisation removes the attached endings, so Nepali goes from 0.853 on exact
spans to 0.972 on values.

Normalising a correctly found span scores 100% on generated data. That figure
is circular (the generator and normaliser read the same lists) and is not a
result.

Field accuracy inside the pipeline:

| Field | realistic | gold_v2 | gold | test |
| --- | --- | --- | --- | --- |
| Locations | 97.9% | 97.9% | 95.8% | 99.5% |
| Variables | 77.1% | 85.4% | 83.3% | 95.8% |
| Disasters | 95.8% | 97.9% | 100% | 100% |
| Time period | 95.8% | 100% | 100% | 99.1% |
| Scenario | 91.7% | 100% | 100% | 100% (amount and direction) |

Variables are the weakest field by a wide margin, and worst in Nepali on the
realistic set (68.8%). See section 5.

### Operation

| Set | All | English | Hindi | Nepali |
| --- | --- | --- | --- | --- |
| realistic | 89.6% | 86.7% | 100% | 81.2% |
| gold_v2 | 89.6% | 75.0% | 93.8% | 100% |
| gold | 91.7% | 93.8% | 93.8% | 87.5% |
| test | 97.2% | 97.9% | 97.4% | 96.4% |

Operation errors almost always follow an intent error.

### Context

41 of 43 turns, 17 of 18 dialogues. The one failing dialogue fails on intent:
"Show the NDVI trend in Namchi district" is classed as a climate trend, and
the follow-up inherits that. The context rules themselves resolve all 43 turns
when given a perfect parse.

### Out-of-domain detection

| Set | Off-topic queries | Rejected | Answered by mistake | Real queries wrongly rejected |
| --- | --- | --- | --- | --- |
| test, English | 24 | 100% | 0% | 0 of 192 |
| test, Hindi | 24 | 100% | 0% | 0 of 192 |
| test, Nepali | 24 | 95.8% | 0% | 0 of 192 |
| realistic | 6 | 5 of 6 | 0 | 0 of 48 |
| gold_v2 | 3 | 2 of 3 | 0 | 1 of 48 |
| gold | 3 | 3 of 3 | 0 | 2 of 48 |

No off-topic query was answered in any set. The ones not rejected were turned
into a clarifying question. The three wrongly rejected real queries are all
caused by the embedding-similarity check ("What altitude does Lachung sit
at?", "How steep is the terrain around Lachen?", and a Hindi question about
forests).

The hand-written sets hold only 12 off-topic queries between them. That is far
too few to state a detection rate.

### Confidence behaviour

| Set | Calibration error before | After temperature scaling |
| --- | --- | --- |
| Validation | 0.012 | 0.006 |
| Test | 0.038 | 0.027 |
| gold | 0.098 | 0.093 |

The final model is close to calibrated already (temperature 1.151). It is
well calibrated on template data and over-confident on hand-written data.

The confidence threshold is **0.30, the bottom of the search range**, so in
practice no query is questioned for low confidence. Section 4 explains why
this is now a measured outcome and not the earlier defect.

Among queries the pipeline answered, the share with the wrong intent:

| Set | All | English | Hindi | Nepali |
| --- | --- | --- | --- | --- |
| test | 1.3% | 3.3% | 0.6% | 0.0% |
| realistic | 3.2% | 9.1% | 0.0% | 0.0% |
| gold | 4.9% | 7.1% | 0.0% | 7.7% |
| gold_v2 | 5.6% | 18.2% | 0.0% | 0.0% |

Overall each set is near or under the 5% target. English on gold_v2 is not
(2 of 11 answered queries).

### Latency

71 ms median and 85 ms at the 95th percentile per query, one at a time, with
both `xlm-roberta-base` models on the RTX 2050. The final models were not
timed on the CPU. The small development models took about 40 ms on the CPU.
Not load-tested.

## 4. Root-cause investigations

### Why the confidence threshold rejected nothing

**Symptom.** The selection rule ("lowest threshold with at most 5% wrong among
answered validation queries") returned its minimum.

**Root cause.** Validation rows are not independent. They come from 18
template families, and a family is right or wrong almost as a block: with the
development model, all validation errors sat in 3 of 18 families and all test
errors in 9 of 18. So 647 rows carry about 18 independent pieces of evidence.
The row-level error rate looked precise (3.7%), was not, and happened to fall
under the target; on test it was 8.8%.

**Fix.** The target is now applied to an upper bound: resample whole families
with replacement 1,000 times and take the 90th percentile of the error rate.

**Result with the final model.** The bound is 3.9% at every threshold up to
0.50, already under 5%, so the rule again returns 0.30. This time that is a
finding, not a bug: the final classifier is 98% accurate on validation and the
target is met without rejecting anything. The validation trade-off, for anyone
who wants a stricter target:

| Threshold | Answered | Wrong among answered | Upper bound |
| --- | --- | --- | --- |
| 0.30 | 100% | 2.0% | 3.9% |
| 0.70 | 98.9% | 1.7% | 3.5% |
| 0.80 | 98.1% | 1.4% | 2.9% |
| 0.90 | 97.1% | 1.0% | 2.0% |

On the test set, predictions with confidence between 0.5 and 0.9 are right
only about 60% of the time (61 queries), so a threshold near 0.9 would remove
real errors. That observation comes from the test set and was not used to set
anything. Tightening `target_answered_error` to 2% in the config would select
0.90 from validation data alone; that is a product decision.

### Why 23 Hindi and Nepali queries were rejected, against 1 English

**Symptom.** After Phase 12, 24 real test queries were refused as off-topic.

**What I first wrote was wrong.** I attributed it to the model over-applying
"a sentence with a place can be off-topic". The rejected queries contain no
place.

**Root cause.** 22 of the 24 are one test family, "How can {hazard} be
prevented?". Probing showed Hindi and Nepali general questions about hazards
were classed off-topic at 0.98 to 1.00 confidence even when reworded, while
English ones were fine. Two things compounded:

- Phase 12 grew off-topic training rows from 71 to 118 per language, while
  `GENERAL_ENVIRONMENT`, the in-domain class nearest to off-topic, stayed at
  63 rows from 6 families.
- The Hindi and Nepali words for "how" (कैसे, कसरी) appeared in 4 off-topic
  training families and 1 in-domain family.

**Fix.** Four in-domain "how" and advice families were added for general
questions (252 rows), bringing that class to 147 rows per language.

**Evidence, by ablation** (intent classifier, seed 42, real test queries
wrongly rejected):

| Model | Without the four families | With them |
| --- | --- | --- |
| Small development model | 23 (Hindi 10, Nepali 13, English 0) | 1 |
| `xlm-roberta-base` | 0 | 0 |

The ablation reproduces the defect exactly and shows the fix removes it in the
small model. It also shows the final model never had the defect. The fix is
kept because it corrects a real imbalance in the data, but its benefit for the
final model is not demonstrated.

A confident error like this cannot be caught by a confidence threshold. That
is why the pipeline now also asks, instead of rejecting, when the classifier
says off-topic but the similarity check says firmly in-domain.

## 5. Error analysis

First cause of each failed query, final models:

| First cause | realistic | gold_v2 | gold | test |
| --- | --- | --- | --- | --- |
| Unknown or unresolved entity (ontology, NER boundary) | 10 | 4 | 3 | 27 |
| Intent confusion | 4 | 4 | 3 | 37 |
| Scenario not built | 3 | 0 | 0 | 0 |
| Entity missed by NER | 2 | 2 | 1 | 0 |
| Real query rejected (similarity check) | 0 | 1 | 2 | 0 |
| Off-topic query questioned, not rejected | 1 | 1 | 0 | 1 |
| Time | 1 | 0 | 0 | 0 |
| Validation, operation | 0 | 1 | 0 | 2 |

### Ontology: the largest cause on realistic text

On the realistic set, queries that imply a variable without naming it are
right **1 time in 10**. The ontology knows nouns and a short list of
descriptors; people say:

| Query | Missing |
| --- | --- |
| which is rainier gangtok or mangan | "rainier" |
| गंगटोक का टेम्परेचर क्या है अभी | the loanword टेम्परेचर |
| पर्सि मङ्गनमा पानी पर्ला? | पानी पर्नु, the ordinary Nepali way to say "rain" |
| पिछले 2 साल में गंगटोक जिले में हवा कितनी खराब हुई है | "the air got worse" for air quality |
| लाचुङमा रुखबिरुवा किन घट्दै छन् | रुखबिरुवा (plants) for vegetation |
| हिमताल फुट्दा के हुन्छ | a verbal paraphrase of a glacial lake outburst |

This is a vocabulary gap, not a model failure, and it is worst in Nepali. It
is the single most valuable thing a fluent speaker could fix. These words were
seen on the realistic set and have deliberately not been added, to keep that
set usable.

### Intent

- A trend phrased as a choice is read as a comparison: "has Mangan been
  getting wetter or drier?", "better or worse?".
- Likelihood questions about a hazard are read as general knowledge: "How
  likely is a flood in Singtam?".
- On the test set, 21 of 37 intent errors are one family ("What is causing the
  loss of vegetation?" read as a disaster question).

Errors cluster by sentence frame. That is the signature of training on 100
template families: the model learns frames, and an unseen frame can flip the
intent.

### NER

- The final NER model tags "समुद्र तल" / "समुद्र सतह" (sea level) as an entity
  in one unseen test family. That accounts for most of the 27 unresolved-entity
  failures on test, all of them Hindi or Nepali. The pipeline then asks about an
  "unknown place".
- It sometimes draws one span around two adjacent names ("मंगन नामची") or a
  name and its neighbour ("लाचेन वरपर"). This is now repaired after NER: a
  span that does not resolve whole is split, and accepted only if every word
  is a known place or a connecting word. It moved gold_v2 from 68.6% to 74.5%.

### Scenario

Number words for fractions ("आधी", "आधा" = half) are not parsed, and "2
degrees colder" has no direction verb the cue list knows.

### Confidence and OOD

- Three real queries are rejected by the similarity check alone.
- Two Nepali off-topic queries about food in Gangtok are questioned instead of
  rejected, because they sit close to in-domain text.

### Ambiguity and unsupported input

Run and reported, not scored:

| Input | What the pipeline did |
| --- | --- |
| "What's the temperature in Gangtok and is there any landslide risk?" | Answered the second question only (`DISASTER_RISK`, ok). One intent per query is a design limit |
| "Is it safe to travel to Lachung this week?" | Rejected as off-topic. Arguably should ask |
| "gangtok mein barish kab hogi" (romanised Hindi) | Detected as English, rejected as off-topic |
| "gantok ma pani parcha ki pardaina" (romanised Nepali) | Same |

Romanised input is not supported, and it fails quietly: the user is told the
question is off-topic, not that the script is unsupported.

## 6. Fixes made in this round, each with a regression test

| Defect | Root cause | Fix |
| --- | --- | --- |
| Threshold inert | Row-level error rate on family-clustered data | Family-level bootstrap bound |
| Hindi/Nepali general questions rejected | Class imbalance and a "how"-word shortcut | Four in-domain families |
| Confident wrong rejection has no safety net | A threshold cannot catch a confident error | Disagreement between classifier and similarity produces a question |
| "हाल" read as "currently" in Hindi | Nepali keyword applied to Hindi text | Keyword is Nepali-only |
| "हाल" matched inside "हालत" | Devanagari keywords had no right-hand word boundary | Keyword must end at a word end or case ending |
| "What explains…" not an explanation | Cue list written from template wording only | Added "explain", "how come", "behind", "due to" |
| Two places in one NER span unresolved | NER boundary error with no recovery | Split and accept only if every word is explained |
| Training stalled for hours | Modern Standby on screen-off | Training holds the display on |

The two bugs intentionally left unfixed after Phase 12 ("हाल" and
"explains") are the fifth to seventh rows. They were deferred to keep gold_v2
clean; once the realistic set existed to take that role, they were fixed.

## 7. Fairness across languages

- **Nepali is the weakest language on realistic input** (50% against 71% for
  English), driven by vocabulary the ontology lacks.
- **Hindi and Nepali carry all of the "sea level" NER failures** on the test
  set.
- **English is the weakest on gold_v2** (65%), from intent confusion. No
  language is uniformly worst.
- **Nepali NER** is capped at 0.91 by the tokenizer; normalisation recovers
  most of it.
- **Nepali off-topic detection** is the only one below 100% on the test set.
- These comparisons rest on 17 to 19 queries per language per hand-written
  set.

## 8. Limits of this evaluation

- **No human review, no real users.** Stated at the top; it bounds everything.
- **Small sets.** One query is 2 points overall on a hand-written set.
- **Every set has now been looked at.** realistic was read once, for the error
  tables above. A further round of fixes needs fresh data, ideally real.
- **The pipeline is evaluated with one seed per task** (the best by
  validation). Component tables give the spread over three.
- **Twelve off-topic queries** across the hand-written sets.
- **Thresholds come from 18 validation families.**
- **The earlier before-and-after comparison in this document's history** mixed
  five fixes and is superseded by the ablation in section 4.

## 9. Collecting real queries

The realistic set is a stand-in. To replace it:

1. Ask 10 to 20 people who use Hindi or Nepali daily, ideally from Sikkim, to
   type 10 questions each about local weather, hazards and environment, in
   whatever script and style they would use on a phone. Do not show them
   examples from this project.
2. Store only the text and the language they say it is in. No names.
3. Label each with the expected result in the format of
   `backend/nlp/data/test/realistic.yaml`. Have a second person check a
   sample.
4. Keep the file out of training and out of any fix. Evaluate once per model
   version.

Even 100 such queries would be worth more than every set in this document.

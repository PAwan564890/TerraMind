# How the NLP subsystem works

One function does everything: `NlpPipeline.analyze(query, session_id)` in
`backend/nlp/pipeline/pipeline.py`. This page walks through its steps in
order, with one example carried through:

> गान्तोकमा पछिल्ला पाँच वर्षको वर्षाको प्रवृत्ति कस्तो रहेको छ?
> (What has the rainfall trend been in Gangtok over the last five years?)

For measured results see [EVALUATION.md](EVALUATION.md); for what the models
are, [MODEL_CARD.md](MODEL_CARD.md).

## 1. Prepare

`preprocessing/normalizer.py`. Makes text that looks the same be the same:
Unicode NFC, one form for quote and dash variants, every kind of space to a
plain space, invisible characters dropped. Then rejects input that is empty,
longer than 500 characters, or has no letters or digits.

It does **not** remove stopwords, lowercase, or stem. The models were
pretrained on natural sentences and read meaning from function words and word
order. In Hindi and Nepali the postpositions (में, का, मा, को) are exactly
what marks where a place name ends.

## 2. Language detection

`language_detection/detector.py`. Two stages:

1. **Script.** Latin letters mean English; no model needed.
2. **Hindi versus Nepali.** Both use Devanagari, so a character n-gram
   classifier (TF-IDF plus logistic regression) separates them by endings and
   function words: है / में / का against छ / मा / को.

Digits are stripped first, so the classifier cannot learn a typing habit as a
language. A one-word follow-up often cannot be decided from text; then the
conversation's previous language is used.

Example: Devanagari, classified `ne`.

A wrong language changes only the reply language. Intent and NER do not
depend on it.

## 3. Intent classification

`intent/`. A pretrained multilingual encoder is fine-tuned with one new linear
layer on top. The text is split into subword tokens, the encoder produces a
vector per token, and the first token's vector is mapped to nine scores:

`WEATHER_QUERY`, `CLIMATE_TREND`, `VEGETATION_ANALYSIS`, `DISASTER_RISK`,
`GEOLOCATION_QUERY`, `COMPARISON`, `SCENARIO_ANALYSIS`,
`GENERAL_ENVIRONMENT`, `OUT_OF_DOMAIN`.

When two apply, `SCENARIO_ANALYSIS` beats `COMPARISON` beats the topic intent.

Example: `CLIMATE_TREND`.

## 4. Named-entity recognition

`ner/`. The same kind of encoder with one output per token. Each token gets a
BIO tag: `B-LOCATION` starts a location, `I-LOCATION` continues it, `O` is
nothing. Five entity types give 11 tags.

| Type | Examples |
| --- | --- |
| `LOCATION` | Gangtok, North Sikkim, तीस्ता |
| `ENV_VARIABLE` | rainfall, तापमान, cold |
| `DISASTER` | flood, पहिरो |
| `TIME` | last five years, भोलि, 2015 to 2020 |
| `CHANGE` | 20%, 2 डिग्री |

**Label alignment.** Labels are character ranges; the model sees subwords. The
tokenizer reports which characters each token covers, and a token takes an
entity's tag if the ranges overlap. Special tokens and padding get `-100`,
which the loss ignores.

Every subword is tagged, not just the first of each word, because the Nepali
ending is attached: `गान्तोकमा` is Gangtok plus "in", and the entity must be
able to end mid-word.

Example: `गान्तोक` LOCATION, `पछिल्ला पाँच वर्षको` TIME, `वर्षा` ENV_VARIABLE.

## 5. Entity normalisation

`normalization/`. This is where three languages become one.

Places, variables and hazards go through a cascade, most certain first:

1. **Exact** alias match in the ontology.
2. **Ending removed** (Nepali attached endings, Hindi postposition words),
   accepted only if what remains matches exactly.
3. **Fuzzy** match for typos, at similarity 0.85 or more, and only if clearly
   ahead of the runner-up.
4. Otherwise **unresolved**. Nothing is guessed.

The ontology holds two kinds of word for a variable: `aliases`, nouns that
name it ("temperature"), and `descriptors`, words that imply it ("cold").

If NER draws one span around two places ("मंगन नामची") or a place and the
word beside it ("लाचेन वरपर"), the span is split, but only if every word in it
is a known place or a connecting word. One unexplained word leaves it
unresolved.

Time and change expressions are parsed by rules that handle digits in both
scripts and number words in all three languages. Hindi कल means both yesterday
and tomorrow; the verb tense of the whole query decides. Some keywords are
language-specific: "हाल" is "currently" in Nepali but part of "क्या हाल है"
("how is it") in Hindi, so it counts as a time only in Nepali.

Example: `गान्तोक` → `loc:gangtok`; `पछिल्ला पाँच वर्षको` → past 5 years;
`वर्षा` → `PRECIPITATION`.

## 6. Out-of-domain check

`pipeline/decision.py`. A second opinion, independent of the classifier. The
query is embedded and compared with in-domain training queries; if it is far
from all of them it is rejected.

Place names are removed before embedding, from both sides. What makes a query
environmental is what it asks, not where; without this step real questions
about unfamiliar towns were rejected.

Entity-only fragments ("Gangtok", "20%") skip this check.

The same score has a second use. If it is high enough that almost no
off-topic query reaches it, and the classifier still says off-topic, the two
signals disagree and the user is asked.

## 7. Conversation context

`context/`. A small state per `session_id`: last language, intent, places,
variables, hazards and time span, with the turn each was last stated.

| Rule | |
| --- | --- |
| A slot stated now always wins | |
| An empty slot is inherited if the intent requires it or the turn is a follow-up | |
| A follow-up also inherits the intent, unless what it names cannot belong to it | "And landslides?" after a weather question |
| Nothing older than 5 turns is inherited | |
| Inherited fields are listed in `context_used` | |
| Off-topic and scenario turns are not stored | |

A follow-up is a query with entities and nothing else but filler ("और बारिश?",
"नाम्चीमा नि?"), or one that adds only a place or time while the classifier is
unsure.

## 8. Query structuring

`query/structurer.py`, `query/cues.py`. Slots become a `StructuredQuery`.

- **Operation** starts from the intent's default and is changed by cue words:
  "why" makes an explanation, "which areas" a ranking, a future time a
  forecast. A cue never yields an operation the intent does not allow.
- **Scenario.** The amount comes from the CHANGE entity, the direction from
  the verb nearest to it, the changed variable from the variable nearest to
  it. A named hazard sets the target (`FLOOD_RISK`).
- **Answer kind** follows from intent and operation.

Example: operation `TREND`, answer kind `analysis`.

## 9. Decision

`intent/calibration.py`, `query/validator.py`.

1. **Calibrate.** The classifier's raw probabilities are rescaled by one
   fitted number (temperature) so that "0.9" means right about 90% of the time.
2. **Reject** if the similarity check failed, or the classifier confidently
   says out of domain and the similarity check does not contradict it.
   If they contradict each other, **ask**.
3. **Ask** if the intent is below the confidence threshold and was not
   supplied by the conversation.
4. **Validate.** Unknown place, missing required field, a comparison with one
   place, an implausible scenario amount: each produces a clarification with a
   `message_key`. A trend with no time span gets the last 10 years, reported
   in `warnings`. That is the only default.

Example result, identical for the English and Hindi versions of the question
except for `language`:

```json
{"intent": "CLIMATE_TREND", "operation": "TREND", "answer_kind": "analysis",
 "locations": [{"id": "loc:gangtok", "name": "Gangtok", "type": "TOWN"}],
 "variables": ["PRECIPITATION"],
 "time_period": {"type": "relative_past", "value": 5, "unit": "year"}}
```

## Training and selecting, in order

```text
generate_dataset.py          templates -> train / val / test
train_language_detector.py
train_intent.py              --model full (xlm-roberta-base, GPU) or dev (CPU)
train_ner.py                 same
select_thresholds.py         calibration, confidence and similarity thresholds
evaluate_end_to_end.py       the whole pipeline on every evaluation set
```

Thresholds are chosen on validation data only. The confidence threshold is
the lowest value whose error, among answered queries, stays under the target
even at an upper bound computed by resampling whole template families; rows
from one family are near-copies and cannot be counted as independent.

Fine-tuning settings (starting values, not tuned): AdamW, learning rate 2e-5
for intent and 3e-5 for NER, weight decay 0.01, 10% warm-up then linear decay,
batch 16, maximum length 64, gradient clipping at 1.0, early stopping after 2
epochs without a better validation score, best epoch saved with its tokenizer
and label map.

## Questions a reviewer is likely to ask

**Why NLP if an LLM comes later?** This path is deterministic, runs on a
laptop CPU in tens of milliseconds, and each step is measured on its own. The
LLM will receive typed data and only has to explain it.

**How do Hindi and Nepali become the same query?** The models only pick an
intent and mark spans. Every value in the output is a canonical ID looked up
from those spans. A test asserts that the three versions of a question produce
equal queries.

**Why one multilingual model and not three?** Shared training signal across
languages, and one system to evaluate.

**How are place names normalised?** A gazetteer gives each place an ID, type
and parent, with spellings in three languages. Endings are stripped, typos are
matched by character similarity with a threshold chosen from a sweep, and
unknown places are never forced onto a known one.

**How are ambiguous questions handled?** If the conversation supplies the
missing piece it is inherited and reported. Otherwise the user is asked.

**How are unsupported questions detected?** A trained out-of-domain class
plus embedding distance from known in-domain queries.

**How is hallucination reduced?** By construction at this layer: the output
is a closed vocabulary of IDs, numbers and dates. Downstream, the LLM will be
given data and asked to explain it, not to recall facts.

**What if Nepali is worse?** It is measured separately at every step. See the
fairness section of EVALUATION.md.

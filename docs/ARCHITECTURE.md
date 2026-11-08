# TerraMind architecture

TerraMind is planned as a question-answering and analysis system over the
environmental state of Sikkim. **Only the first layer, multilingual NLP, is
built.** Everything else on this page is design.

## The idea in one paragraph

A plain chatbot answers environmental questions fluently and invents the
numbers. TerraMind separates the two jobs. The NLP layer turns a question in
English, Hindi or Nepali into a typed, language-independent **structured
query**. Later layers fetch real data for that query, run models where a
labelled outcome exists, retrieve documents, and only then hand everything to
a language model whose job is to explain what it was given.

```text
User (en / hi / ne)
  |
  v
NLP  ............................  BUILT
  language, intent, entities, normalisation, context, validation
  |
  v
Structured query (typed JSON)  ...  BUILT (the contract)
  |
  v
Query orchestrator  ..............  planned: a routing table, intent -> tools
  |
  v
Climate / geospatial / disaster tools  planned
  |
  v
Environmental data store  ........  planned: PostgreSQL + PostGIS
  |                 |
  v                 v
ML and analytics   RAG  ..........  planned
  |                 |
  +--------+--------+
           v
GenAI / LLM  .....................  planned: explains tool results only
           |
           v
Frontend  ........................  planned: map, charts, assistant, scenarios
```

## What "digital twin" means here

A stored, queryable, regularly refreshed state of a real region, plus models
that can be run against that state. Not a physics simulation of the Earth.

Until the data layer exists, TerraMind is not a twin. It is the language front
end of one, and the README says so.

Every answer the finished system gives will be one of four kinds, and the
structured query already records which in `answer_kind`:

| Kind | Example | Where the answer will come from |
| --- | --- | --- |
| observation | What was the rainfall? | Stored measurements |
| analysis | How has rainfall changed? | Statistics over measurements |
| prediction | What is the flood risk? | A validated model |
| scenario | What if rainfall rises 20%? | A model run on modified inputs, labelled hypothetical |

## The NLP layer as built

```text
query text
  -> prepare        Unicode NFC, whitespace, punctuation; reject unusable input
  -> language       script check, then a Hindi/Nepali n-gram classifier
  -> intent  }      fine-tuned xlm-roberta-base, 9 classes
  -> NER     }      fine-tuned xlm-roberta-base, BIO tags over 5 entity types
  -> normalise      alias lookup -> strip endings -> fuzzy match; rules for time and change
  -> domain check   embedding similarity to in-domain queries, place names removed
  -> context        deterministic slot inheritance from the conversation
  -> structure      operation and scenario direction from cue words
  -> decide         calibrate confidence, validate, then ok / needs_clarification / out_of_domain
  -> AnalyzeResponse
```

Intent and NER read the same normalised text and do not depend on each other.
Learned models do three steps (language, intent, entities). Everything else is
rules, so that each decision can be read, tested and explained.

See [NLP.md](NLP.md) for how each step works and [API.md](API.md) for the
contract.

### Design decisions and why

| Decision | Reason |
| --- | --- |
| One multilingual model per task, not one per language | Hindi and Nepali benefit from English examples; one system to train and evaluate |
| `intent` and `operation` are separate fields | "Compare landslide risk in two districts" is a hazard topic and a comparison; one label cannot hold both |
| NER has one `LOCATION` label; the gazetteer decides town, district or river | "Gangtok" is a town and a district; the sentence cannot tell, the dictionary can |
| Canonical IDs come from dictionaries, never from the model | The same question in any language yields the same query by construction |
| Context, validation, cue words and time parsing are rules | Small closed problems; rules are exact and fail visibly |
| Out-of-domain uses two signals | A classifier can be confidently wrong on text unlike its training data; embedding distance is independent of it |
| Thresholds are selected from validation data and stored with the models | A threshold belongs to one trained model, not to the code |
| The confidence target is applied to a family-level upper bound | Rows from one template family are near-copies; counting them as independent made the threshold meaningless |
| When the two out-of-domain signals disagree, the user is asked | A confident wrong rejection cannot be caught by a confidence threshold |
| Unknown or missing values produce a question, never a default | The only default is a trend's time span, and it is reported |

### Deviations from the original design

- NER tags every subword, not only the first subword of each word, because
  Nepali case endings attach to names and an entity can end mid-word.
- The development model is `multilingual-e5-small`, not DistilBERT: same
  tokenizer family as XLM-R and reused for embeddings.
- Year ranges are stored as date ranges; there is no separate year-range type.
- Embeddings are computed with `transformers` directly; the
  `sentence-transformers` package is not a dependency.
- Place names are removed before the out-of-domain similarity check. Without
  this, real questions about unfamiliar towns were rejected.
- The embedding fallback for unknown words is implemented but switched off; it
  recovered about 30% of synonyms and mapped 4% wrongly. A `descriptors` list
  in the ontology does the job deterministically.
- A scenario requires a location.
- The ontology has `descriptors` (words that imply a variable, such as
  "cold") alongside aliases. The design had only aliases.
- Final training ran locally on an RTX 2050, not on Colab.
- Evaluation sets are much smaller than designed: two gold sets of 51 and a
  real-user-style set of 58, against a planned 450; 18 dialogues against 40.
- The low-confidence follow-up rule is narrower than designed: it applies
  only when a query adds a place or time and names no topic of its own.
- An unresolved location span is split into its parts when every word in it
  is a known place or a connecting word.
- Train and validation data are single files carrying both intent and entity
  labels, not separate `intent/` and `ner/` folders.

## Code layout

One Python process, a modular monolith. Each package exposes a few functions
and imports nothing from its siblings except shared types.

```text
backend/api/        FastAPI app
backend/core/       config, logging, seeding
backend/nlp/
  preprocessing/    normaliser and input validation
  language_detection/
  intent/           data, training, predictor, calibration
  ner/              tags, alignment, training, predictor
  training/         the fine-tuning loop shared by intent and NER
  normalization/    entity -> canonical value; time and change parsers
  embeddings/       encoder, neighbour index, parallel test triples
  context/          state, follow-up detection, resolver, store
  query/            enums, intent spec, schema, cues, structurer, validator
  pipeline/         NlpPipeline, decision thresholds, domain scorer
  ontology/         YAML data and loader
  dataset/          template families, lexicon, generator, validator
  data/             generated splits and hand-written test sets
  evaluation/       metrics
configs/nlp.yaml    every tunable setting
scripts/            generate, train, select thresholds, evaluate, demo
models/             trained artefacts (git-ignored)
```

## Planned layers

None of this exists. No dataset or API is named because none has been
researched; that happens when each phase starts, with source, licence, date
accessed, coverage and resolution recorded for each.

**Environmental data.** ETL into PostgreSQL with PostGIS: ingest raw files
unmodified, validate, clean with a log, transform to ontology variable names
and common units, normalise in space and time to the gazetteer's location IDs,
load, serve. The link to NLP is the gazetteer: `locations[].id` in a
structured query is the key of the location table. The ontology and gazetteer
YAML files are the seed data for those tables.

| Planned table | Holds |
| --- | --- |
| `locations`, `location_aliases` | Gazetteer with geometry and multilingual names |
| `variables` | Ontology variables and units |
| `observations` | Time series per location and variable |
| `raster_layers` | Catalogue of satellite and terrain layers |
| `disaster_events` | Historical events |
| `risk_scores` | Model outputs with model version |
| `data_sources` | Provenance and licence |

**ML and analytics.** Added only where a labelled outcome exists; otherwise
the feature is descriptive statistics and is called that. No model is called
valid without a documented dataset, a split that holds out areas or years,
metrics, a feature list and written limitations. Scarcity of labelled disaster
events in one small state is the largest risk to this layer.

**RAG.** Reports and papers, chunked with source metadata, embedded with the
same model the NLP layer already uses. `variables` and `locations` from the
structured query become filters; `GENERAL_ENVIRONMENT` queries route here.

**GenAI.** Receives the structured query and tool results and writes an
explanation in the user's language. Every number must come from the results it
was given; a scenario is labelled a model-based estimate; missing data is
stated as missing.

**Orchestration.** First a plain routing table from intent and operation to
tool calls. An agent framework only if that table becomes unmanageable.

**Scenario engine.** Load current values for the location, apply the change
from `scenario`, run the model on original and modified inputs, report the
difference. Changes outside the range the model was trained on are refused or
flagged.

**Frontend.** React dashboard: map with layers, indicator cards, charts, an
assistant panel with a source panel, and scenario sliders.

## Security posture of what is built

- Input is length-limited twice and validated by Pydantic.
- No secrets are needed or stored. `.env` is git-ignored.
- Query text is not logged above DEBUG level.
- After NLP, no free text reaches a downstream tool: a structured query holds
  only enum values, IDs, numbers and dates. That is what will let later tools
  build parameterised queries safely.
- Model checkpoints load only from the project's `models/` folder or named
  Hugging Face repositories, in safetensors format. The language detector is
  a joblib file written by this project's own script; do not load one from
  elsewhere.
- Not built: authentication, rate limiting, CORS.

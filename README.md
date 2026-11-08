# TerraMind

A planned AI-powered environmental digital twin for Sikkim. **What exists
today is its first layer: multilingual NLP** that turns a question in English,
Hindi or Nepali into a typed, language-independent structured query.

```text
"गान्तोकमा पछिल्ला पाँच वर्षको वर्षाको प्रवृत्ति कस्तो रहेको छ?"
                              |
                              v
{ "intent": "CLIMATE_TREND", "operation": "TREND", "answer_kind": "analysis",
  "locations": [{"id": "loc:gangtok", "name": "Gangtok", "type": "TOWN"}],
  "variables": ["PRECIPITATION"],
  "time_period": {"type": "relative_past", "value": 5, "unit": "year"} }
```

The English and Hindi versions of that question produce the same query.

## Status

| | |
| --- | --- |
| Built | Language detection, intent classification, NER, entity normalisation, embeddings, conversation context, validation, out-of-domain detection, HTTP API |
| Not built | Environmental data, ML models, retrieval, LLM, orchestration, scenario engine, frontend |
| Result | 61% of real-user-style queries exactly right end to end (54 queries): English 71%, Hindi 63%, Nepali 50%. 90% on template-style text |
| Models | `xlm-roberta-base` fine-tuned for intent and NER, three seeds each, on an RTX 2050 |
| Data | Hindi and Nepali text drafted by an AI assistant. Fluent-speaker review is **pending**; a review pack is prepared, nothing has been reviewed |
| Not | Not production-ready. No real user queries have been collected |

TerraMind cannot answer a question yet. It can only structure one. Read
[docs/LIMITATIONS.md](docs/LIMITATIONS.md) before quoting any number.

## Documentation

| Document | Contents |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The whole planned system, what is built, design decisions |
| [docs/NLP.md](docs/NLP.md) | How each NLP step works, with a worked example |
| [docs/API.md](docs/API.md) | The HTTP contract |
| [docs/DATA.md](docs/DATA.md) | Dataset card |
| [docs/MODEL_CARD.md](docs/MODEL_CARD.md) | The models, how they were trained, where they fail |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Results per language, error analysis |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | What it cannot do and what was not checked |
| [docs/REVIEW_GUIDE.md](docs/REVIEW_GUIDE.md) | How a fluent Hindi or Nepali speaker can review the data (pending) |

## Setup (Windows PowerShell, Python 3.12)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
# PyTorch first, CPU build (small download; enough for the tests and the dev models):
python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
python -m pytest
```

The tests need no trained model and no download. Expected: `412 passed`.

**For the final models you need an NVIDIA GPU build of PyTorch.** Install it
after the steps above; pip must be told to replace the CPU build, because it
considers the version already satisfied:

```powershell
python -m pip install "torch==2.14.1+cu126" --force-reinstall --no-deps --index-url https://download.pytorch.org/whl/cu126
python -c "import torch; print(torch.cuda.is_available())"
```

`cu126` is the build used here (CUDA 12.6, driver 555.97). The download is
2.6 GB; pip checks it against a published checksum and refuses a corrupted
file, in which case run the command again.

## Reproduce everything from scratch

Trained models are not in the repository. Run these in order from the project
root.

```powershell
python scripts/generate_dataset.py                    # 1. templates -> train / val / test
python scripts/train_language_detector.py             # 2. seconds
python scripts/train_intent.py --model full           # 3. xlm-roberta-base, seeds 42 43 44
python scripts/train_ner.py --model full              # 4. same
python scripts/select_thresholds.py                   # 5. calibration and thresholds
python scripts/evaluate_end_to_end.py --tag my_run    # 6. the numbers in docs/EVALUATION.md
```

Steps 3 and 4 need the GPU build above. On an RTX 2050 (4 GB) each epoch took
about 5 minutes and each task about 1.5 hours for three seeds. The first run
downloads the 1.1 GB base model. Each seed's checkpoint is about 1.1 GB.

Step 1 is optional: the generated data is committed, and a test fails if it
differs from what the generator produces.

Results will fall within the seed spread documented in
[docs/EVALUATION.md](docs/EVALUATION.md), not match exactly: GPU training is
not bit-for-bit reproducible.

**Keep the laptop awake.** The training scripts ask Windows not to idle-sleep
and to keep the display on while they run. Closing the lid or pressing the
power button still pauses training.

### Without a GPU

`configs/nlp.yaml` has `active_run: full` under `intent` and `ner`. To work on
a CPU, set both to `dev` and drop `--model full` from steps 3 and 4. That
trains `intfloat/multilingual-e5-small` (470 MB download, about 15 to 20
minutes per task per seed on a laptop CPU) and scores lower.

[notebooks/train_models_colab.ipynb](notebooks/train_models_colab.ipynb) is an
alternative for a free GPU. It has been written but never run.

## Use it

Command line:

```powershell
python scripts/analyze.py "Compare rainfall in North Sikkim and South Sikkim."
python scripts/analyze.py "What is the temperature in Gangtok?" "और बारिश?"   # one conversation
python scripts/analyze.py "What is the temperature?" --json                   # full response
```

HTTP:

```powershell
uvicorn backend.api.app:app --port 8000
```

Then open http://127.0.0.1:8000/docs.

Python:

```python
from backend.core import load_settings
from backend.nlp.pipeline import NlpPipeline

pipeline = NlpPipeline.from_settings(load_settings())
response = pipeline.analyze("गंगटोक में तापमान कितना है?", session_id="demo")
print(response.status, response.structured_query)
```

## Other scripts

| Script | Purpose |
| --- | --- |
| `scripts/evaluate_normalization.py` | Normalisation accuracy and the fuzzy-threshold sweep |
| `scripts/evaluate_embeddings.py` | Compares embedding models on cross-language retrieval |
| `scripts/evaluate_context.py` | Runs the test dialogues through the context rules alone |
| `scripts/ablate_families.py` | Retrains intent with chosen template families removed, to measure what they contribute |
| `scripts/export_review_pack.py` | Exports every Hindi and Nepali string for fluent-speaker review |

## Layout

```text
backend/api/        FastAPI app: POST /nlp/analyze, GET /health
backend/core/       config loading, logging, seeding
backend/nlp/        the NLP subsystem (see docs/ARCHITECTURE.md)
configs/nlp.yaml    every tunable setting
scripts/            generate, train, select thresholds, evaluate, demo
tests/              mirrors backend/
docs/               the documents listed above
review/             Hindi and Nepali review pack (all rows pending)
notebooks/          Colab notebook for GPU training
models/             trained artefacts, created by the scripts (git-ignored)
```

## Technologies actually used

Python, PyTorch, Hugging Face Transformers, scikit-learn, Pydantic, FastAPI,
pytest.

Planned and **not** used yet: PostgreSQL/PostGIS, any RAG or vector store, any
LLM, React, any GIS library.

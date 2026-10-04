# TerraMind

AI-powered Earth system digital twin for Sikkim. Work in progress.

**Status:** Phase 1 (NLP specification) complete: taxonomy enums, ontology and gazetteer, structured-query schema. No models are trained yet.

## Setup (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the tests

```powershell
python -m pytest
```

## Layout

```text
backend/core/   config loading and logging, shared by every layer
backend/nlp/    multilingual NLP subsystem (built phase by phase)
  ontology/     variables, disasters and Sikkim gazetteer (YAML) + loader
  query/        enums, per-intent spec, Pydantic structured-query schema
configs/        nlp.yaml: all tunable settings
tests/          mirrors backend/
```

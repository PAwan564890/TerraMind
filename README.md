# TerraMind

AI-powered Earth system digital twin for Sikkim. Work in progress.

**Status:** Phase 0 (project setup) complete. No NLP components are implemented yet.

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
configs/        nlp.yaml: all tunable settings
tests/          mirrors backend/
```

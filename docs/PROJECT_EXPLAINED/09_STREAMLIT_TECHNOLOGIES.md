# Streamlit backup and technologies

Streamlit is independently runnable: set `TERRAMIND_API_URL=http://127.0.0.1:8000`, then `python -m streamlit run streamlit_app/app.py --server.port 8501`. It uses the same API, not React. Its only foundations modification is a supported-town caption derived from `/system` instead of three hardcoded names. Existing temperature/rainfall, source evidence and GenAI workflows remain. The new map and supplemental-variable UI are React features, not new Streamlit capabilities.

| Layer | Actual technologies |
|---|---|
| API and validation | Python, FastAPI, Pydantic, Uvicorn, httpx |
| Trained NLP | PyTorch, Transformers, scikit-learn components and existing ontology/normalizers |
| Environmental data | Open-Meteo archive/recent APIs, GeoNames-backed registry, original JSON snapshots |
| Analytics | Deterministic Python arithmetic/statistics; validated typed rows |
| Optional explanation | OpenAI-compatible HTTP client; strict structured facts; backend-only credentials |
| React | React 19, TypeScript 5.7, React Router, Vite, Recharts, lucide-react |
| Map | Leaflet 1.9, React Leaflet 5, OpenStreetMap tiles |
| Backup UI | Streamlit and its existing chart stack |
| Tests | pytest, Vitest, Testing Library, Playwright/Chromium |

Use repository requirements and `frontend-react/package-lock.json` for exact dependencies; do not substitute this overview for the lockfile. Node engine range is `^22.12.0 || ^24.0.0 || >=26.0.0`. `npm ci` installs the lock; `npm run build` runs TypeScript build checks followed by Vite production build. Existing Python environment and trained checkpoint junction must be preserved on Windows; do not recreate them merely to update frontend packages.

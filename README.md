# FabricFlow Suite

A local-first rebuild of FabricFlow for bag-production planning. The Python backend owns calculations; a Streamlit prototype provides the catalog, calculator, tutorial and conversational assistant UI.

## Features

- Fabric consumption, cutting yield, material cost and hardware cost calculations
- Scrap-reuse scenarios and alternative comparisons
- Streamlit pages for rolls, bag models, hardware, calculations, history and the assistant
- English and Brazilian Portuguese interface
- Local JSON catalog; no database required for the prototype

## Run locally

Use two PowerShell terminals from the repository root.

Install dependencies:

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -r frontend/requirements.txt
```

Configure the conversational assistant by copying `backend/.env.example` to `backend/.env` and setting `OPENAI_API_KEY` there. Keep `.env` local; Git ignores it.

Start the API:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Start the Streamlit app in the second terminal:

```powershell
python -m streamlit run frontend/streamlit_app.py --server.port 8502
```

Open <http://localhost:8502>. The API and interactive Swagger documentation are at <http://127.0.0.1:8000> and <http://127.0.0.1:8000/docs>.

## Tests

```powershell
python -m unittest discover -s backend/tests -v
python -m unittest discover -s frontend/tests -v
```

## Project layout

- `backend/app/calculations.py` contains framework-independent calculation logic.
- `backend/app/agent/` contains the LangChain conversational assistant and calculation tools.
- `backend/app/main.py` exposes the calculation and chat API.
- `frontend/` contains the Streamlit pages, API client and local catalog.

The local catalog at `frontend/data/catalog.json` is ignored by Git. The assistant's in-memory conversation sessions reset when the API restarts. This is a prototype and does not include authentication.

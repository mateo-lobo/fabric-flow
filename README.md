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

## Deploy

The Streamlit interface and FastAPI backend are separate services. The Render Blueprint can create and deploy both from this repository in one flow.

### Render Blueprint

1. Authorize Render's GitHub app to access `mateo-lobo/fabric-flow` if you have not already.
2. In the Render Dashboard, choose **New > Blueprint** and select this repository on the `main` branch.
3. Review the two services from `render.yaml`: `fabricflow-api` (FastAPI) and `fabricflow-ui` (Streamlit). Both use the Oregon region so they can communicate over Render's private network.
4. Enter `OPENAI_API_KEY` when prompted for the API service. Never add the key to `render.yaml` or GitHub.
5. Deploy the Blueprint and open the `fabricflow-ui` URL when both services are live. The Blueprint connects the UI to the API through its internal host and port; no API URL needs to be copied into Streamlit Secrets.

The free plan may spin down while idle, so the first calculation after inactivity can take up to two minutes. The catalog is stored on the UI service's local filesystem and is not durable across service replacement; use persistent storage before relying on it in production.

### Streamlit Community Cloud

Community Cloud runs only the UI. Create the app from this repository and set **Main file path** to `frontend/streamlit_app.py`. It uses the root `requirements.txt`.

Deploy the FastAPI backend separately, then set the backend's public URL in **App settings > Secrets**:

```toml
FABRICFLOW_API_URL = "https://your-fabricflow-api.example.com"
```

Do not use `127.0.0.1` here: that would point to the Streamlit container itself.

### FastAPI backend

For a separate backend deployment, install `backend/requirements.txt` and start it with:

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

Set `OPENAI_API_KEY` and, optionally, `FABRICFLOW_LLM_MODEL` in the backend host's environment/secrets. Its `/health` endpoint should respond before you set `FABRICFLOW_API_URL` in Streamlit Cloud.

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

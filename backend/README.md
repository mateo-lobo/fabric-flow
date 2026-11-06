# FabricFlow Python Backend

This backend ports the calculation routines recovered from the FabricFlow Suite desktop bundle. The calculation functions are independent of FastAPI so they can also be called directly by a future webapp.

## Run locally

From this directory, install the dependencies and start the API:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API is available at `http://127.0.0.1:8000`; interactive request documentation is at `http://127.0.0.1:8000/docs`.

## Endpoints

- `GET /health` reports whether the service is running.
- `POST /api/calculate` accepts a model, rolls, optional hardware definitions, and `batchSize`. It returns the calculation result and waste-optimization scenarios.
- `POST /api/calculate/apply-optimization` accepts the prior calculation request, result, and selected scenario, then returns the adjusted result.

Requests use the legacy camelCase field names (`widthCm`, `lengthM`, `pricePerMeter`, `materialId`, and so on). Inputs are validated against the legacy form constraints where they were recoverable. Calculations retain full floating-point precision; display rounding belongs in the future webapp.

## AI assistant

`POST /api/agent/chat` takes `{"sessionId": "...", "message": "..."}` and returns the reply, the collected draft, and the latest calculation. The LLM only gathers inputs and calls tools that wrap the calculation functions, so every number comes from the Python code. Sessions are kept in memory and lost on restart.

Set the key before starting the API (see `.env.example`); without it the endpoint returns 503:

```powershell
$env:OPENAI_API_KEY = "sk-..."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Try it in Swagger with, for example: `Quero calcular uma bolsa tote com tecido canvas de 140 cm de largura, rolo de 50 m a R$ 20 o metro.`

## Streamlit prototype

The `frontend/` folder holds a Streamlit prototype of the old interface (dashboard, consumption calculator, assistant, bag models, fabric rolls, hardware, history). It calls this API, so start the API first, then from the workspace root:

```powershell
python -m pip install -r frontend/requirements.txt
python -m streamlit run frontend/streamlit_app.py --server.port 8502
```

Open `http://localhost:8502`. Rolls, hardware, models and saved calculations are stored in `frontend/data/catalog.json` (override with `FABRICFLOW_DATA`). Set `FABRICFLOW_API_URL` if the API is not on `http://127.0.0.1:8000`. Tests: `python -m unittest discover -s frontend/tests`.

## Verification

Run the calculation regression suite from the workspace root:

```powershell
python -m unittest discover -s backend/tests -v
```

The desktop bundle's waste-cost conversion mixed square meters and square centimeters and could make an applied optimization produce a negative total. The Python backend corrects this by deriving cost per square centimeter from the price of one linear meter and the roll width; optimization savings and waste reduction are based on the area actually reused. Confirm this corrected business rule with the business owner before relying on scrap valuations for quotes.
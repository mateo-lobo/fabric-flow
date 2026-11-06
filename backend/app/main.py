from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .agent import agent as agent_module
from .calculations import apply_optimization, calculate_model, optimize_waste
from .models import ApplyOptimizationRequest, CalculationRequest

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


app = FastAPI(
    title="FabricFlow Calculation API",
    description="Local Python implementation of FabricFlow material and cutting calculations.",
    version="0.1.0",
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "sessionId": "maria-tote-001",
                    "message": "Quero calcular uma bolsa tote. Tecido canvas de 140 cm de largura, "
                    "rolo de 50 m a R$ 20 o metro, permite rotação.",
                }
            ]
        }
    )

    session_id: str = Field(alias="sessionId", min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent/chat")
def agent_chat(request: ChatRequest) -> dict[str, object]:
    try:
        return agent_module.run_chat(request.session_id, request.message)
    except agent_module.AgentUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except agent_module.UpstreamError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/calculate")
def calculate(request: CalculationRequest) -> dict[str, object]:
    try:
        result = calculate_model(
            request.model,
            request.rolls,
            request.batch_size,
            request.hardware,
        )
        optimization = optimize_waste(
            request.model,
            result["cutResults"],
            request.rolls,
            request.batch_size,
        )
        return {"result": result, "optimization": optimization}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/calculate/apply-optimization")
def post_apply_optimization(request: ApplyOptimizationRequest) -> dict[str, object]:
    return apply_optimization(
        request.result,
        request.scenario.model_dump(by_alias=True),
        request.calculation.model,
        request.calculation.rolls,
    )
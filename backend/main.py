from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    import mock_analyzer
except ImportError:  # support `from backend.main import app` from project root
    from backend import mock_analyzer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "null"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    message: str = Field(..., max_length=2000)


class AnalyzeResponse(BaseModel):
    risk_level: str
    risk_score: float
    signals: list[str]
    recommended_action: str
    analyzed_by: str
    summary: str = ""
    explanation: list[str] = []
    actions: list[str] = []


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_message(request: AnalyzeRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")
    return mock_analyzer.analyze(request.message)


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True),
    name="frontend",
)

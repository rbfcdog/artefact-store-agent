
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from emporio import Agent


app = FastAPI(title="Empório da Música - atendimento")
agent = Agent()

_INDEX = Path(__file__).resolve().parents[2] / "interface" / "index.html"

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    reply: str

class ResetRequest(BaseModel):
    session_id: str

@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    return ChatResponse(reply=agent.chat(payload.session_id, payload.message))

@app.post("/api/reset")
def reset(payload: ResetRequest) -> dict[str, bool]:
    agent.reset(payload.session_id)
    return {"ok": True}

@app.get("/")
def index() -> FileResponse:
    return FileResponse(_INDEX)

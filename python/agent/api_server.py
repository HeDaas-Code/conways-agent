"""
FastAPI HTTP Server for Conway's Agent

Provides REST API endpoints for the Node.js Body layer:
- POST /api/dialogue  — Send a message and get Agent response
- GET  /api/status    — Get Agent's current state
- GET  /health        — Health check

Run with: python -m agent.api_server
Or:      uvicorn agent.api_server:app --reload --port 8000
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load .env file
load_dotenv()

# Ensure vault path is set
from agent.core.vault import ensure_vault_dirs, get_vault_path
from agent import (
    initialize_agent,
    log_event,
    DialogueSession,
    ProcessingPipeline,
)
from agent.core.llm import LLMClient
from agent.core.state import AgentState


# ==========================================
# Application Lifespan
# ==========================================

_agent_state: Optional[AgentState] = None
_dialogue_session: Optional[DialogueSession] = None
_llm_client: Optional[LLMClient] = None
_pipeline: Optional[ProcessingPipeline] = None
_startup_time: Optional[datetime] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Agent on startup, cleanup on shutdown."""
    global _agent_state, _dialogue_session, _llm_client, _pipeline, _startup_time
    
    try:
        vault_path = get_vault_path()
    except ValueError:
        print("错误: OBSIDIAN_VAULT_PATH 未设置。请先配置环境变量。")
        print("参考 .env.example 文件。")
        sys.exit(1)
    
    ensure_vault_dirs()
    _startup_time = datetime.now()
    _agent_state = initialize_agent()
    _llm_client = LLMClient()
    _pipeline = ProcessingPipeline(llm_client=_llm_client)
    _dialogue_session = DialogueSession(
        llm_client=_llm_client,
        state=_agent_state,
        pipeline=_pipeline
    )
    
    print(f"[Agent] 启动于 {_startup_time.isoformat()}")
    print(f"[Agent] Vault: {vault_path}")
    print(f"[Agent] 状态: {_agent_state.sleep_state}")
    
    log_event("api_server_startup", f"Agent started via API server")
    
    yield
    
    print("[Agent] 正在关闭...")
    log_event("api_server_shutdown", "Agent shutting down via API server")


# ==========================================
# FastAPI App
# ==========================================

app = FastAPI(
    title="Conway's Agent — Brain API",
    description="HTTP API for the Obsidian Agent's cognitive core",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Obsidian plugin to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# Request/Response Models
# ==========================================

class DialogueRequest(BaseModel):
    message: str


class DialogueResponse(BaseModel):
    response: str


class StatusResponse(BaseModel):
    sleep_state: str
    personality_name: str
    total_cycles: int
    uptime_seconds: float
    world_fragment_count: int
    active_goal_count: int


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    vault_path: str


# ==========================================
# Endpoints
# ==========================================

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    if _startup_time is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    vault_path = str(get_vault_path())
    world_dir = Path(vault_path) / "agent" / "world"
    fragment_count = len(list(world_dir.glob("*.md"))) if world_dir.exists() else 0
    
    return HealthResponse(
        status="ok",
        uptime_seconds=(datetime.now() - _startup_time).total_seconds(),
        vault_path=vault_path,
    )


@app.post("/api/dialogue", response_model=DialogueResponse)
async def dialogue(req: DialogueRequest):
    """
    Send a dialogue message to the Agent.
    
    The message is processed through the perception pipeline
    and generates a response in the Agent's voice.
    """
    if _dialogue_session is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        response = _dialogue_session.user_speak(req.message.strip())
        return DialogueResponse(response=response)
    except Exception as e:
        log_event("api_dialogue_error", str(e), {"message": req.message[:100]})
        raise HTTPException(status_code=500, detail=f"Dialogue processing failed: {e}")


@app.get("/api/status", response_model=StatusResponse)
async def status():
    """Get the Agent's current state."""
    if _agent_state is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    vault_path = str(get_vault_path())
    world_dir = Path(vault_path) / "agent" / "world"
    fragment_count = len(list(world_dir.glob("*.md"))) if world_dir.exists() else 0
    
    active_goals = 0
    goals_dir = Path(vault_path) / "agent" / "goals"
    if goals_dir.exists():
        active_goals = len([f for f in goals_dir.glob("*.md")
                          if "status: completed" not in f.read_text()[:500]
                          and "status: failed" not in f.read_text()[:500]])
    
    return StatusResponse(
        sleep_state=_agent_state.sleep_state,
        personality_name=_agent_state.personality.get("name", "图书馆居者"),
        total_cycles=getattr(_agent_state, "total_cycles", 0),
        uptime_seconds=(datetime.now() - _startup_time).total_seconds() if _startup_time else 0,
        world_fragment_count=fragment_count,
        active_goal_count=active_goals,
    )


@app.get("/api/history")
async def history():
    """Get dialogue history."""
    if _dialogue_session is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    turns = _dialogue_session.get_history()
    return {
        "turns": [
            {
                "role": t.role,
                "content": t.content,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in turns
        ],
        "count": len(turns),
    }


@app.post("/api/history/clear")
async def clear_history():
    """Clear dialogue history."""
    if _dialogue_session is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    count = len(_dialogue_session.history)
    _dialogue_session.clear_history()
    return {"cleared": count}


# ==========================================
# Entry Point
# ==========================================

def run():
    """Run the API server."""
    port = int(os.getenv("SERVER_PORT", "8000"))
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    
    print(f"启动 Conway's Agent Brain API...")
    print(f"监听: http://{host}:{port}")
    print(f"端点:")
    print(f"  GET  /health        — 健康检查")
    print(f"  POST /api/dialogue  — 发送对话消息")
    print(f"  GET  /api/status    — 获取 Agent 状态")
    print(f"  GET  /api/history   — 获取对话历史")
    print(f"  POST /api/history/clear — 清空对话历史")
    print()
    
    uvicorn.run(
        "agent.api_server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()

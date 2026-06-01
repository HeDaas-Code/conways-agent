"""
FastAPI HTTP/WebSocket Server for Conway's Agent

Provides:
- GET /health — Health check endpoint (retained)
- WS /ws — WebSocket for mode control

WS message format: {"type": str, "payload": Any}
- activate: Agent switches to INTERACTION mode
- deactivate: Agent switches to SELF mode
- ping/pong: Heartbeat messages

Run with: python -m agent.api_server
Or:      uvicorn agent.api_server:app --reload --port 5588
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
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load .env file
load_dotenv()

# Ensure vault path is set
from agent.core.vault import ensure_vault_dirs, get_vault_path
from agent.core.ws_server import WSServer, ws_endpoint, WSMessage, MessageType, get_server
from agent.core.mode_machine import ModeMachine, Mode
from agent import log_event


# ==========================================
# Application Lifespan
# ==========================================

_startup_time: Optional[datetime] = None
_ws_server: Optional[WSServer] = None
_mode_machine: Optional[ModeMachine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Agent on startup, cleanup on shutdown."""
    global _startup_time, _ws_server, _mode_machine
    
    try:
        vault_path = get_vault_path()
    except ValueError:
        print("错误: OBSIDIAN_VAULT_PATH 未设置。请先配置环境变量。")
        print("参考 .env.example 文件。")
        sys.exit(1)
    
    ensure_vault_dirs()
    _startup_time = datetime.now()
    _mode_machine = ModeMachine()
    _ws_server = WSServer()
    get_server(override=_ws_server)  # inject so ws_endpoint uses the same instance
    _ws_server.mode_controller.mode_machine = _mode_machine
    
    print(f"[Agent] 启动于 {_startup_time.isoformat()}")
    print(f"[Agent] Vault: {vault_path}")
    print(f"[Agent] 模式: {_mode_machine.state.mode.value}")
    
    log_event("api_server_startup", f"Agent started via API server")
    
    yield
    
    print("[Agent] 正在关闭...")
    log_event("api_server_shutdown", "Agent shutting down via API server")


# ==========================================
# FastAPI App
# ==========================================

app = FastAPI(
    title="Conway's Agent — Brain API",
    description="WebSocket API for the Obsidian Agent's cognitive core",
    version="0.2.0",
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

# Add WebSocket endpoint
app.add_api_websocket_route("/ws", ws_endpoint)


# ==========================================
# Request/Response Models
# ==========================================

class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    vault_path: str
    mode: str


class ModeResponse(BaseModel):
    mode: str
    ws_connected: bool


# ==========================================
# Endpoints
# ==========================================

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    if _startup_time is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    vault_path = str(get_vault_path())

    server = get_server()
    mode = server.mode_controller.get_current_mode().value if server else "unknown"

    return HealthResponse(
        status="ok",
        uptime_seconds=(datetime.now() - _startup_time).total_seconds(),
        vault_path=vault_path,
        mode=mode,
    )


@app.get("/mode", response_model=ModeResponse)
async def get_mode():
    """Get current agent mode."""
    if _mode_machine is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    server = get_server()
    return ModeResponse(
        mode=server.mode_controller.get_current_mode().value,
        ws_connected=server.mode_controller.mode_machine.state.ws_connected.value == "connected",
    )


# ==========================================
# Entry Point
# ==========================================

def run():
    """Run the API server."""
    port = int(os.getenv("SERVER_PORT", "5588"))
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    
    print(f"启动 Conway's Agent WebSocket API...")
    print(f"监听: ws://{host}:{port}/ws")
    print(f"端点:")
    print(f"  GET  /health  — 健康检查")
    print(f"  GET  /mode    — 获取当前模式")
    print(f"  WS   /ws      — WebSocket 连接")
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

"""
WebSocket Server for Agent Communication

Handles WebSocket connections on ws://localhost:5588/ws
- Activates INTERACTION mode on connect
- Deactivates to SELF mode on disconnect
- Sends heartbeat pings to detect client disconnection
- Manages mode transitions via ModeMachine
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from agent.core.mode_machine import ModeMachine, Mode, WSConnectionState
from agent.core.streaming_pipeline import StreamingPipeline, StreamMessage
from agent.core.interest_model import InterestModel


# Heartbeat configuration
HEARTBEAT_INTERVAL = 30  # Send ping every 30 seconds
HEARTBEAT_TIMEOUT = 60   # Disconnect after 60 seconds of no response


class MessageType(str, Enum):
    """WebSocket message types."""
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    PING = "ping"
    PONG = "pong"
    MODE_CHANGE = "mode_change"
    ERROR = "error"
    PROCESS = "process"  # Two-stage streaming request


@dataclass
class WSMessage:
    """WebSocket message structure."""
    type: MessageType
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.type.value,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WSMessage":
        """Deserialize from dictionary."""
        msg_type = MessageType(data["type"])
        payload = data.get("payload", {})
        return cls(type=msg_type, payload=payload)


class HeartbeatMonitor:
    """Monitors heartbeat/ping for connection health."""

    def __init__(self) -> None:
        self._last_pong: datetime = datetime.now()
        self._active: bool = True

    def is_active(self) -> bool:
        """Check if heartbeat is active."""
        return self._active

    def get_last_pong(self) -> datetime:
        """Get timestamp of last pong received."""
        return self._last_pong

    def record_pong(self) -> None:
        """Record that a pong was received."""
        self._last_pong = datetime.now()

    def deactivate(self) -> None:
        """Deactivate heartbeat monitoring."""
        self._active = False


class WSModeController:
    """
    Controls mode transitions based on WebSocket events.
    
    Integrates with ModeMachine to manage agent mode lifecycle.
    """

    def __init__(self, mode_machine: Optional[ModeMachine] = None) -> None:
        self.mode_machine = mode_machine or ModeMachine()
        self._interest_model: Optional["InterestModel"] = None

    def set_interest_model(self, interest_model: "InterestModel") -> None:
        """Set the interest model for integration."""
        self._interest_model = interest_model
        self.mode_machine.set_interest_model(interest_model)

    async def on_connect(self) -> None:
        """Handle WebSocket connect event."""
        self.mode_machine.dispatch("ws_connect")
        self.mode_machine.set_ws_connected(True)

    async def on_disconnect(self) -> None:
        """Handle WebSocket disconnect event."""
        self.mode_machine.dispatch("ws_disconnect")
        self.mode_machine.set_ws_connected(False)

    async def on_activity(self) -> None:
        """Handle user activity in INTERACTION mode."""
        self.mode_machine.record_activity()

    def get_current_mode(self) -> Mode:
        """Get current agent mode."""
        return self.mode_machine.state.mode


class WSServer:
    """
    WebSocket server for agent communication.
    
    Manages connections, heartbeats, and mode transitions.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5588,
        heartbeat_interval: int = HEARTBEAT_INTERVAL,
        heartbeat_timeout: int = HEARTBEAT_TIMEOUT,
    ) -> None:
        self.host = host
        self.port = port
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        
        self.mode_controller = WSModeController()
        self.heartbeat_monitor = HeartbeatMonitor()
        
        self._websocket: Optional[WebSocket] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        self._interest_model: Optional["InterestModel"] = None

    def set_interest_model(self, interest_model: "InterestModel") -> None:
        """
        Set the interest model for integration.

        Args:
            interest_model: The InterestModel instance to integrate
        """
        self._interest_model = interest_model
        self.mode_controller.set_interest_model(interest_model)

    async def _send_message(self, message: WSMessage) -> bool:
        """Send a message to the connected client."""
        if self._websocket is None or self._websocket.client_state != WebSocketState.CONNECTED:
            return False
        
        try:
            await self._websocket.send_json(message.to_dict())
            return True
        except Exception:
            return False

    async def _send_heartbeat(self) -> None:
        """Send heartbeat ping to client."""
        message = WSMessage(
            type=MessageType.PING,
            payload={"timestamp": datetime.now().isoformat()}
        )
        await self._send_message(message)

    async def _start_heartbeat(self) -> None:
        """Start sending periodic heartbeat pings."""
        while self._running and self._websocket:
            await asyncio.sleep(self.heartbeat_interval)
            
            if not self._running:
                break
                
            # Check if connection is still alive
            elapsed = (datetime.now() - self.heartbeat_monitor.get_last_pong()).total_seconds()
            if elapsed > self.heartbeat_timeout:
                # Connection timed out
                await self._handle_timeout()
                break
            
            await self._send_heartbeat()

    async def _handle_timeout(self) -> None:
        """Handle heartbeat timeout."""
        await self.mode_controller.on_disconnect()
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception:
                pass

    async def _handle_connect(self) -> None:
        """Handle new connection."""
        await self.mode_controller.on_connect()
        self.heartbeat_monitor = HeartbeatMonitor()

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle incoming message."""
        try:
            message = WSMessage.from_dict(data)
        except (KeyError, ValueError):
            return
        
        if message.type == MessageType.PONG:
            self.heartbeat_monitor.record_pong()
        elif message.type == MessageType.ACTIVATE:
            await self.mode_controller.on_activity()
        elif message.type == MessageType.DEACTIVATE:
            pass  # Client-initiated, handled by disconnect
        elif message.type == MessageType.PROCESS:
            # Two-stage streaming response
            user_message = message.payload.get("message", "")
            await self._process_streaming_message(user_message)

    async def _process_streaming_message(self, message: str) -> None:
        """Process message with two-stage streaming."""
        if self._websocket is None:
            return

        # Accumulate interest for dialogue
        if self._interest_model is not None:
            self._interest_model.accumulate("dialogue", {"message": message})

        pipeline = StreamingPipeline()

        try:
            async for stream_msg in pipeline.process_message(message):
                # Convert StreamMessage to WSMessage and send
                await self._websocket.send_json({
                    "type": stream_msg.type,
                    "payload": stream_msg.payload,
                })
        except Exception as e:
            # Send error message
            await self._websocket.send_json({
                "type": "error",
                "payload": {"message": str(e)},
            })

    async def handle_connection(self, websocket: WebSocket) -> None:
        """
        Handle a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
        """
        self._websocket = websocket
        self._running = True
        
        await websocket.accept()
        await self._handle_connect()
        
        # Start heartbeat task
        self._heartbeat_task = asyncio.create_task(self._start_heartbeat())
        
        try:
            while self._running:
                # Wait for messages
                data = await websocket.receive_json()
                await self._handle_message(data)
                
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            self._running = False
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            await self.mode_controller.on_disconnect()
            self.heartbeat_monitor.deactivate()


# Global server instance
_server: Optional[WSServer] = None


def get_server() -> WSServer:
    """Get or create the global WebSocket server instance."""
    global _server
    if _server is None:
        _server = WSServer()
    return _server


async def ws_endpoint(websocket: WebSocket) -> None:
    """
    FastAPI WebSocket endpoint.
    
    Connect: ws://localhost:5588/ws
    """
    server = get_server()
    await server.handle_connection(websocket)


def create_ws_app() -> FastAPI:
    """
    Create a FastAPI app with WebSocket endpoint.
    
    Returns:
        FastAPI app configured with WS endpoint at /ws
    """
    app = FastAPI(title="Agent WebSocket Server")
    app.add_api_websocket_route("/ws", ws_endpoint)
    return app


async def run_server(host: str = "localhost", port: int = 5588) -> None:
    """
    Run the WebSocket server.
    
    Args:
        host: Server host
        port: Server port
    """
    import uvicorn
    
    app = create_ws_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

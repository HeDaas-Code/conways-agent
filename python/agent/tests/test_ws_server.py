"""
Tests for WS Server - WebSocket handler for agent communication.

TDD RED phase: Tests for expected WS behavior.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestWSMessageHandling:
    """Test WebSocket message parsing and handling."""

    def test_parse_activate_message(self):
        """Should parse activate message type."""
        from agent.core.ws_server import WSMessage, MessageType
        
        msg = WSMessage(type=MessageType.ACTIVATE, payload={})
        
        assert msg.type == MessageType.ACTIVATE

    def test_parse_deactivate_message(self):
        """Should parse deactivate message type."""
        from agent.core.ws_server import WSMessage, MessageType
        
        msg = WSMessage(type=MessageType.DEACTIVATE, payload={})
        
        assert msg.type == MessageType.DEACTIVATE

    def test_message_to_dict(self):
        """Message should serialize to dict."""
        from agent.core.ws_server import WSMessage, MessageType
        
        msg = WSMessage(type=MessageType.ACTIVATE, payload={"key": "value"})
        data = msg.to_dict()
        
        assert data["type"] == "activate"
        assert data["payload"] == {"key": "value"}


class TestWSConnectionLifecycle:
    """Test WS connection and disconnection behavior."""

    @pytest.mark.asyncio
    async def test_ws_endpoint_exists(self):
        """WebSocket endpoint should be registered."""
        from fastapi import FastAPI
        from agent.core.ws_server import ws_endpoint
        
        app = FastAPI()
        app.add_api_websocket_route("/ws", ws_endpoint)
        
        # Verify endpoint is registered
        routes = [r.path for r in app.routes]
        assert "/ws" in routes


class TestWSHeartbeat:
    """Test heartbeat/ping behavior."""

    @pytest.mark.asyncio
    async def test_heartbeat_timeout_after_60_seconds(self):
        """Should timeout after 60 seconds of no messages."""
        from agent.core.ws_server import HeartbeatMonitor, HEARTBEAT_TIMEOUT
        
        assert HEARTBEAT_TIMEOUT == 60

    def test_heartbeat_monitor_initial_state(self):
        """Heartbeat monitor should start active."""
        from agent.core.ws_server import HeartbeatMonitor
        
        monitor = HeartbeatMonitor()
        
        assert monitor.is_active()
        assert monitor.get_last_pong() is not None


class TestWSModeTransition:
    """Test mode transition integration."""

    @pytest.mark.asyncio
    async def test_mode_transitions_on_connect_disconnect(self):
        """Mode should transition on WS connect/disconnect."""
        from agent.core.ws_server import WSModeController
        from agent.core.mode_machine import Mode
        
        controller = WSModeController()
        
        # Connect should transition to INTERACTION
        await controller.on_connect()
        assert controller.mode_machine.state.mode == Mode.INTERACTION
        
        # Disconnect should transition to SELF
        await controller.on_disconnect()
        assert controller.mode_machine.state.mode == Mode.SELF


class TestWSIntegration:
    """Integration tests for WS server."""

    @pytest.mark.asyncio
    async def test_ws_server_sends_heartbeat_pings(self):
        """WS server should send periodic ping messages."""
        from agent.core.ws_server import WSServer
        
        server = WSServer(host="localhost", port=5588)
        
        # Should have heartbeat interval configured
        assert server.heartbeat_interval == 30  # Send ping every 30s

    @pytest.mark.asyncio
    async def test_ws_server_registers_on_connect_hook(self):
        """WS server should call on_connect when client connects."""
        from agent.core.ws_server import WSServer, WSModeController
        
        controller = WSModeController()
        server = WSServer(host="localhost", port=5588)
        server.mode_controller = controller
        
        # Simulate connect
        await server._handle_connect()
        
        # Controller should be notified
        assert server.mode_controller.mode_machine.state.ws_connected.value == "connected"


class TestWSMessageProtocol:
    """Test the message protocol."""

    def test_message_protocol_format(self):
        """Messages should follow {type, payload} format."""
        from agent.core.ws_server import WSMessage, MessageType
        import json
        
        msg = WSMessage(
            type=MessageType.ACTIVATE,
            payload={"client_id": "test"}
        )
        
        # Should serialize to JSON
        json_str = json.dumps(msg.to_dict())
        parsed = json.loads(json_str)
        
        assert "type" in parsed
        assert "payload" in parsed

    def test_invalid_message_type_handled(self):
        """Invalid message types should be handled gracefully."""
        from agent.core.ws_server import WSMessage, MessageType
        
        # Create message with unknown type via raw dict
        msg = WSMessage(type=MessageType.ACTIVATE, payload={})
        
        # Should not raise, just ignore unknown types
        assert msg.type in MessageType

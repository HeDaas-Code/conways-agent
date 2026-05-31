"""
Tests for ModeMachine - the agent mode state machine.

TDD RED phase: Tests for expected behavior.
"""

import pytest
from datetime import datetime, timedelta


class TestModeMachineBasicTransitions:
    """Test basic mode transitions based on WS events."""

    def test_initial_state_is_idle(self):
        """Agent starts in IDLE mode."""
        from agent.core.mode_machine import ModeMachine, Mode
        
        machine = ModeMachine()
        assert machine.state.mode == Mode.IDLE

    def test_ws_connect_from_idle_transitions_to_interaction(self):
        """WS connect from IDLE should transition to INTERACTION."""
        from agent.core.mode_machine import ModeMachine, Mode
        
        machine = ModeMachine()
        new_mode, actions = machine.dispatch("ws_connect")
        
        assert new_mode == Mode.INTERACTION
        assert machine.state.mode == Mode.INTERACTION

    def test_ws_disconnect_from_interaction_transitions_to_self(self):
        """WS disconnect from INTERACTION should transition to SELF."""
        from agent.core.mode_machine import ModeMachine, Mode
        
        machine = ModeMachine()
        machine.dispatch("ws_connect")  # Enter INTERACTION first
        
        new_mode, actions = machine.dispatch("ws_disconnect")
        
        assert new_mode == Mode.SELF
        assert machine.state.mode == Mode.SELF

    def test_ws_connect_from_self_transitions_to_interaction(self):
        """WS connect from SELF should transition back to INTERACTION."""
        from agent.core.mode_machine import ModeMachine, Mode
        
        machine = ModeMachine()
        machine.dispatch("ws_connect")
        machine.dispatch("ws_disconnect")  # Go to SELF
        
        new_mode, actions = machine.dispatch("ws_connect")
        
        assert new_mode == Mode.INTERACTION
        assert machine.state.mode == Mode.INTERACTION

    def test_ws_disconnect_from_self_stays_in_self(self):
        """WS disconnect from SELF is a no-op."""
        from agent.core.mode_machine import ModeMachine, Mode
        
        machine = ModeMachine()
        machine.dispatch("ws_connect")
        machine.dispatch("ws_disconnect")  # Now in SELF
        initial_mode = machine.state.mode
        
        new_mode, actions = machine.dispatch("ws_disconnect")
        
        assert new_mode == Mode.SELF
        assert machine.state.mode == Mode.SELF
        assert actions == []


class TestModeMachineIdleTimeout:
    """Test idle timeout behavior in INTERACTION mode."""

    def test_idle_timeout_transitions_to_self(self):
        """Idle timeout in INTERACTION should transition to SELF."""
        from agent.core.mode_machine import ModeMachine, Mode
        
        machine = ModeMachine()
        machine.dispatch("ws_connect")  # Enter INTERACTION
        
        new_mode, actions = machine.dispatch("idle_timeout")
        
        assert new_mode == Mode.SELF
        assert machine.state.mode == Mode.SELF

    def test_tick_without_timeout_keeps_interaction(self):
        """Tick without reaching idle timeout keeps INTERACTION."""
        from agent.core.mode_machine import ModeMachine, Mode
        
        machine = ModeMachine()
        machine.state.idle_timeout_seconds = 60
        machine.dispatch("ws_connect")
        
        # Simulate a tick
        actions = machine.tick()
        
        assert machine.state.mode == Mode.INTERACTION
        assert actions == []

    def test_tick_with_timeout_triggers_transition(self):
        """Tick with elapsed timeout should trigger idle_timeout."""
        from agent.core.mode_machine import ModeMachine, Mode
        
        machine = ModeMachine()
        machine.state.idle_timeout_seconds = 60
        machine.dispatch("ws_connect")
        
        # Manually set last_activity to 61 seconds ago
        machine.state.last_activity_at = datetime.now() - timedelta(seconds=61)
        
        actions = machine.tick()
        
        assert machine.state.mode == Mode.SELF
        assert "idle_timeout" in [e[0] for e in machine.get_event_history()]

    def test_record_activity_resets_idle_timer(self):
        """record_activity should reset the idle timer."""
        from agent.core.mode_machine import ModeMachine
        
        machine = ModeMachine()
        machine.dispatch("ws_connect")
        original_last_activity = machine.state.last_activity_at
        
        # Advance time
        machine.state.last_activity_at = datetime.now() - timedelta(seconds=30)
        
        # Record activity
        machine.record_activity()
        
        # Should be reset to now (within 1 second)
        assert (datetime.now() - machine.state.last_activity_at).total_seconds() < 1


class TestModeMachineEventHistory:
    """Test that event history is properly recorded."""

    def test_event_history_records_transitions(self):
        """Event history should record all valid transitions."""
        from agent.core.mode_machine import ModeMachine
        
        machine = ModeMachine()
        machine.dispatch("ws_connect")
        machine.dispatch("ws_disconnect")
        
        history = machine.get_event_history()
        
        assert len(history) == 2
        assert history[0][0] == "ws_connect"
        assert history[1][0] == "ws_disconnect"

    def test_invalid_event_not_recorded(self):
        """Invalid events should not change state or be recorded."""
        from agent.core.mode_machine import ModeMachine, Mode
        
        machine = ModeMachine()
        initial_mode = machine.state.mode
        
        machine.dispatch("invalid_event")
        
        assert machine.state.mode == initial_mode
        assert len(machine.get_event_history()) == 0


class TestModeMachineWSConnectionState:
    """Test WS connection state tracking."""

    def test_set_ws_connected_updates_state(self):
        """set_ws_connected should update the ws_connected field."""
        from agent.core.mode_machine import ModeMachine, WSConnectionState
        
        machine = ModeMachine()
        
        machine.set_ws_connected(True)
        assert machine.state.ws_connected == WSConnectionState.CONNECTED
        
        machine.set_ws_connected(False)
        assert machine.state.ws_connected == WSConnectionState.DISCONNECTED

    def test_ws_connected_initially_disconnected(self):
        """WS should start in disconnected state."""
        from agent.core.mode_machine import ModeMachine, WSConnectionState
        
        machine = ModeMachine()
        assert machine.state.ws_connected == WSConnectionState.DISCONNECTED

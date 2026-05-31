"""
Tests for Evolution System

Tests the parameter self-modification capabilities including:
- Protected parameters
- Gradual modifications
- Modification history
- Rollback functionality
"""

import json
import tempfile
from pathlib import Path

import pytest

from agent.core.evolution import (
    EvolutionSystem,
    ProtectedParameters,
    ParameterModification,
)


class TestProtectedParameters:
    """Tests for ProtectedParameters class."""
    
    def test_seed_is_protected(self):
        """The seed parameter should be protected."""
        assert not ProtectedParameters.can_modify("seed")
    
    def test_core_identity_is_protected(self):
        """The core_identity parameter should be protected."""
        assert not ProtectedParameters.can_modify("core_identity")
    
    def test_curiosity_is_modifiable(self):
        """The curiosity_level parameter should be modifiable."""
        assert ProtectedParameters.can_modify("curiosity_level")
    
    def test_fit_threshold_is_modifiable(self):
        """The fit_threshold parameter should be modifiable."""
        assert ProtectedParameters.can_modify("fit_threshold")
    
    def test_attention_window_is_modifiable(self):
        """The attention_window_size parameter should be modifiable."""
        assert ProtectedParameters.can_modify("attention_window_size")


class TestParameterModification:
    """Tests for ParameterModification dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        mod = ParameterModification(
            modified_at="2026-05-31T14:00:00",
            parameter="curiosity_level",
            old_value=0.5,
            new_value=0.6,
            reason="Test reason",
            review_id="test-review",
        )
        
        result = mod.to_dict()
        
        assert result["modified_at"] == "2026-05-31T14:00:00"
        assert result["parameter"] == "curiosity_level"
        assert result["old_value"] == 0.5
        assert result["new_value"] == 0.6
        assert result["reason"] == "Test reason"
        assert result["review_id"] == "test-review"
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "modified_at": "2026-05-31T14:00:00",
            "parameter": "fit_threshold",
            "old_value": 0.5,
            "new_value": 0.55,
            "reason": "Test",
            "review_id": None,
        }
        
        mod = ParameterModification.from_dict(data)
        
        assert mod.modified_at == "2026-05-31T14:00:00"
        assert mod.parameter == "fit_threshold"
        assert mod.old_value == 0.5
        assert mod.new_value == 0.55


class TestEvolutionSystem:
    """Tests for EvolutionSystem class."""
    
    @pytest.fixture
    def temp_state_dir(self):
        """Create a temporary directory for state files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def mock_state_file(self, temp_state_dir):
        """Create a mock state file."""
        state = {
            "seed": "Test seed",
            "personality": {
                "name": "TestAgent",
                "traits": {"curious": 0.5},
                "description": "Test personality"
            },
            "curiosity_level": 0.5,
            "fit_threshold": 0.5,
            "attention_window_size": 3,
            "sleep_state": "awake",
            "wake_duration_seconds": 300,
            "sleep_duration_seconds": 3600,
            "total_cycles": 0,
        }
        
        state_path = temp_state_dir / "state.json"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        return state_path
    
    def test_init_creates_system(self, mock_state_file):
        """Test EvolutionSystem initialization."""
        system = EvolutionSystem(state_path=mock_state_file)
        assert system._state_path == mock_state_file
    
    def test_modify_parameter_success(self, mock_state_file):
        """Test successful parameter modification."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        result = system.modify_parameter(
            "curiosity_level",
            0.6,
            "Test modification",
            "test-review-1"
        )
        
        assert result is True
        assert system.get_current_value("curiosity_level") == 0.6
    
    def test_modify_parameter_protected_fails(self, mock_state_file):
        """Test that protected parameters cannot be modified."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        result = system.modify_parameter(
            "seed",
            "modified seed",
            "Should not work",
        )
        
        assert result is False
    
    def test_modify_parameter_logs_history(self, mock_state_file):
        """Test that modifications are logged to history."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        system.modify_parameter("curiosity_level", 0.7, "Test", "review-1")
        
        history = system.get_modification_history()
        assert len(history) == 1
        assert history[0]["parameter"] == "curiosity_level"
        assert history[0]["old_value"] == 0.5
        assert history[0]["new_value"] == 0.7
        assert history[0]["reason"] == "Test"
    
    def test_rollback_parameter(self, mock_state_file):
        """Test rollback functionality."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        # Make a modification
        system.modify_parameter("curiosity_level", 0.7, "Test", "review-1")
        assert system.get_current_value("curiosity_level") == 0.7
        
        # Rollback
        result = system.rollback_parameter("curiosity_level")
        assert result is True
        assert system.get_current_value("curiosity_level") == 0.5
    
    def test_gradual_change_limits(self, mock_state_file):
        """Test that changes are limited to max 20%."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        # Try to make a 50% change (should be limited)
        new_value = system._calculate_gradual_change(0.5, 0.75, "curiosity_level")
        
        # Should be limited to max 20% increase: 0.5 * 1.2 = 0.6
        assert new_value <= 0.6
        assert new_value >= 0.5
    
    def test_gradual_change_respects_bounds(self, mock_state_file):
        """Test that changes respect parameter bounds."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        # Test curiosity_level bounds (0.0-1.0)
        new_value = system._calculate_gradual_change(0.95, 1.5, "curiosity_level")
        assert new_value <= 1.0
        
        # Test attention_window_size bounds (1-20)
        new_value = system._calculate_gradual_change(3, 30, "attention_window_size")
        assert new_value <= 20
    
    def test_apply_review_insights_curiosity_high(self, mock_state_file):
        """Test applying review insights for high curiosity."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        review = {
            "curiosity_assessment": "too_high",
            "review_id": "test-review",
        }
        
        modified = system.apply_review_insights(review)
        
        assert "curiosity_level" in modified
        # Should be decreased (by ~15%)
        assert system.get_current_value("curiosity_level") < 0.5
    
    def test_apply_review_insights_fit_strict(self, mock_state_file):
        """Test applying review insights for strict fit threshold."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        review = {
            "fit_threshold_assessment": "too_strict",
            "review_id": "test-review",
        }
        
        modified = system.apply_review_insights(review)
        
        assert "fit_threshold" in modified
        # Should be increased (more accepting)
        assert system.get_current_value("fit_threshold") > 0.5
    
    def test_apply_review_insights_attention_small(self, mock_state_file):
        """Test applying review insights for small attention window."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        review = {
            "attention_assessment": "too_small",
            "review_id": "test-review",
        }
        
        modified = system.apply_review_insights(review)
        
        assert "attention_window_size" in modified
        # Should be increased
        assert system.get_current_value("attention_window_size") > 3
    
    def test_suggest_modifications(self, mock_state_file):
        """Test suggestion generation without applying changes."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        review = {
            "curiosity_assessment": "too_high",
            "review_id": "test-review",
        }
        
        suggestions = system.suggest_modifications(review)
        
        assert len(suggestions) >= 1
        curiosity_suggestion = next(
            (s for s in suggestions if s["parameter"] == "curiosity_level"),
            None
        )
        assert curiosity_suggestion is not None
        assert curiosity_suggestion["current"] == 0.5
        assert curiosity_suggestion["direction"] == "decrease"
    
    def test_get_recent_modifications(self, mock_state_file):
        """Test getting recent modifications with limit."""
        system = EvolutionSystem(state_path=mock_state_file)
        
        # Make multiple modifications
        for i in range(5):
            system.modify_parameter("curiosity_level", 0.5 + i * 0.1, f"Test {i}", f"review-{i}")
        
        recent = system.get_recent_modifications(limit=3)
        assert len(recent) == 3
    
    def test_history_persists_across_instances(self, temp_state_dir):
        """Test that history persists when creating new system instances."""
        state = {
            "seed": "Test seed",
            "personality": {"name": "Test", "description": "Test"},
            "curiosity_level": 0.5,
            "fit_threshold": 0.5,
            "attention_window_size": 3,
            "sleep_state": "awake",
            "wake_duration_seconds": 300,
            "sleep_duration_seconds": 3600,
            "total_cycles": 0,
        }
        
        state_path = temp_state_dir / "state.json"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        
        # First instance makes a modification
        system1 = EvolutionSystem(state_path=state_path)
        system1.modify_parameter("curiosity_level", 0.6, "First", "review-1")
        
        # Second instance should see the history
        system2 = EvolutionSystem(state_path=state_path)
        history = system2.get_modification_history()
        
        assert len(history) == 1
        assert history[0]["new_value"] == 0.6


class TestEvolutionSystemIntegration:
    """Integration tests for evolution system."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def state_file(self, temp_dir):
        """Create a state file."""
        state = {
            "seed": "Original seed content",
            "personality": {
                "name": "LibraryDweller",
                "traits": {"curious": 0.5},
                "description": "A dweller of the endless library"
            },
            "curiosity_level": 0.7,
            "fit_threshold": 0.5,
            "attention_window_size": 3,
            "sleep_state": "awake",
            "wake_duration_seconds": 300,
            "sleep_duration_seconds": 3600,
            "total_cycles": 0,
        }
        
        path = temp_dir / "state.json"
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        return path
    
    def test_full_review_cycle(self, state_file):
        """Test a complete review and adjustment cycle."""
        system = EvolutionSystem(state_path=state_file)
        
        # Simulate a review finding curiosity too high
        review = {
            "curiosity_assessment": "too_high",
            "fit_threshold_assessment": "balanced",
            "attention_assessment": "balanced",
            "review_id": "2026-05-31-review",
            "overall_notes": "Agent showing signs of scattered attention"
        }
        
        # Get suggestions first
        suggestions = system.suggest_modifications(review)
        assert any(s["parameter"] == "curiosity_level" for s in suggestions)
        
        # Apply the changes
        modified = system.apply_review_insights(review)
        assert "curiosity_level" in modified
        
        # Verify the change was gradual
        new_value = system.get_current_value("curiosity_level")
        assert new_value < 0.7  # Should be decreased
        assert new_value >= 0.7 * 0.8  # But not more than 20%
        
        # Check history
        history = system.get_modification_history()
        assert len(history) == 1
        assert history[0]["review_id"] == "2026-05-31-review"
    
    def test_protected_parameters_never_change(self, state_file):
        """Test that protected parameters cannot be modified through any path."""
        system = EvolutionSystem(state_path=state_file)
        
        # Try all possible paths
        assert system.modify_parameter("seed", "hacked", "attempt") is False
        assert system.modify_parameter("core_identity", "changed", "attempt") is False
        
        review = {"review_id": "hack-attempt"}
        system.apply_review_insights(review)
        
        # Verify seed is unchanged
        system2 = EvolutionSystem(state_path=state_file)
        assert system2.get_current_value("seed") == "Original seed content"

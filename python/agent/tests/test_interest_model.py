"""
Tests for InterestModel - interest accumulation with keyword extraction.

Issue #38: Interest accumulation system with:
- 5 event types: dialogue, vault_create, vault_edit, tag_use, link_establish
- Interest vector (topic frequency map)
- Behavior triggering at thresholds
- Cooldown after behavior execution
- Decay in INTERACTION mode, no decay in SELF mode
"""

import pytest
from agent.core.interest_model import (
    InterestModel,
    InterestVector,
    POINTS_CONFIG,
    DECAY_RATE_PER_TICK,
    Mode,
    Behavior,
)


class TestInterestVector:
    """Tests for InterestVector data structure."""

    def test_empty_vector_has_zero_topics(self):
        """Empty vector should have no topics."""
        vec = InterestVector()
        assert len(vec) == 0
        assert vec.get("编程") == 0

    def test_add_single_topic(self):
        """Adding a topic should increment its count."""
        vec = InterestVector()
        vec.add("编程")
        assert vec.get("编程") == 1

    def test_add_topic_with_weight(self):
        """Adding with weight should increment by weight."""
        vec = InterestVector()
        vec.add("AI", weight=3)
        assert vec.get("AI") == 3

    def test_add_many_topics(self):
        """Adding multiple topics."""
        vec = InterestVector()
        vec.add_many(["编程", "AI", "编程"])
        assert vec.get("编程") == 2
        assert vec.get("AI") == 1

    def test_top_n_returns_sorted(self):
        """top_n should return topics sorted by frequency."""
        vec = InterestVector()
        vec.add_many(["编程", "AI", "Python", "编程", "AI", "AI"])
        top = vec.top_n(2)
        assert top[0][0] == "AI"
        assert top[0][1] == 3

    def test_decay_reduces_frequencies(self):
        """Decay should multiply all frequencies by rate."""
        vec = InterestVector()
        vec.add("测试", weight=10)
        vec.decay(rate=0.5)
        assert vec.get("测试") == 5

    def test_decay_removes_zero_topics(self):
        """Topics with zero frequency should be removed."""
        vec = InterestVector()
        vec.add("测试", weight=1)
        vec.decay(rate=0.5)
        assert len(vec) == 0

    def test_points_never_negative(self):
        """Decay should not produce negative frequencies."""
        vec = InterestVector()
        vec.add("测试", weight=1)
        vec.decay(rate=0.1)
        assert vec.get("测试") >= 0


class TestInterestModelAccumulation:
    """Test InterestModel.accumulate() with 5 event types."""

    def test_initial_points_is_zero(self):
        """Points should start at 0."""
        model = InterestModel()
        assert model.points == 0

    def test_accumulate_dialogue_with_keywords(self):
        """Dialogue should add 5 + keywords*2 points."""
        model = InterestModel()
        # "Python编程" contains both "Python" and "编程" keywords
        behaviors = model.accumulate("dialogue", {"message": "我想学习Python编程"})
        
        # Base 5 + 2 keywords (Python, 编程) * 2 = 9 points
        assert model.points >= 5
        assert model.points == 5 + 2 * 2  # Exactly 9 for "Python" + "编程"

    def test_accumulate_dialogue_updates_interest_vector(self):
        """Dialogue should update interest vector with keywords."""
        model = InterestModel()
        model.accumulate("dialogue", {"message": "学习Python和AI"})
        
        # Should have extracted Python and AI
        assert model.state.interest_vector.get("Python") >= 1
        assert model.state.interest_vector.get("AI") >= 1

    def test_accumulate_vault_create(self):
        """Vault create should add 3 points."""
        model = InterestModel()
        model.accumulate("vault_create")
        assert model.points == POINTS_CONFIG["vault_create"]
        assert model.points == 3

    def test_accumulate_vault_edit(self):
        """Vault edit should add 2 points."""
        model = InterestModel()
        model.accumulate("vault_edit")
        assert model.points == POINTS_CONFIG["vault_edit"]
        assert model.points == 2

    def test_accumulate_tag_use(self):
        """Tag use should add 4 points."""
        model = InterestModel()
        model.accumulate("tag_use", {"tag": "AI"})
        assert model.points == POINTS_CONFIG["tag_use"]
        assert model.points == 4

    def test_accumulate_tag_use_updates_vector(self):
        """Tag use should update interest vector."""
        model = InterestModel()
        model.accumulate("tag_use", {"tag": "Python"})
        assert model.state.interest_vector.get("Python") >= 1

    def test_accumulate_link_establish(self):
        """Link establish should add 3 points."""
        model = InterestModel()
        model.accumulate("link_establish", {"target": "some-note"})
        assert model.points == POINTS_CONFIG["link_establish"]
        assert model.points == 3

    def test_accumulate_link_establish_updates_vector(self):
        """Link establish should update interest vector."""
        model = InterestModel()
        model.accumulate("link_establish", {"target": "AI相关笔记"})
        assert model.state.interest_vector.get("AI") >= 1

    def test_accumulate_unknown_source_adds_zero(self):
        """Unknown source should add 0 points."""
        model = InterestModel()
        model.accumulate("unknown_source")
        assert model.points == 0


class TestExtractKeywords:
    """Test keyword extraction from messages."""

    def test_extract_chinese_keywords(self):
        """Should extract Chinese multi-character keywords."""
        model = InterestModel()
        keywords = model.extract_topic("我想学习Python和机器学习")
        
        assert "Python" in keywords or "AI" in keywords or "编程" in keywords

    def test_extract_english_keywords(self):
        """Should extract English keywords."""
        model = InterestModel()
        keywords = model.extract_topic("I love coding in Python")
        
        assert "Python" in keywords or "编程" in keywords

    def test_extract_empty_message(self):
        """Empty message should return empty list."""
        model = InterestModel()
        keywords = model.extract_topic("")
        assert keywords == []

    def test_extract_mixed_content(self):
        """Should handle mixed Chinese/English content."""
        model = InterestModel()
        keywords = model.extract_topic("Python编程真的很棒，AI也很有趣")
        
        assert len(keywords) >= 2


class TestBehaviorTriggering:
    """Test behavior triggering at thresholds."""

    def test_quick_association_triggered_at_threshold(self):
        """QUICK_ASSOCIATION should trigger at 10 points."""
        model = InterestModel()
        model.state.points = 9
        
        # Accumulate to reach threshold
        model.accumulate("vault_create")  # +3 = 12
        
        pending = model.get_pending_behaviors()
        behavior_names = [b.name for b in pending]
        
        assert "QUICK_ASSOCIATION" in behavior_names

    def test_world_fragment_triggered_at_threshold(self):
        """WORLD_FRAGMENT should trigger at 20 points."""
        model = InterestModel()
        # Multiple events to reach threshold (need 20+ points for WORLD_FRAGMENT)
        model.accumulate("vault_create")  # +3
        model.accumulate("vault_create")  # +3 = 6
        model.accumulate("vault_create")  # +3 = 9
        model.accumulate("vault_edit")    # +2 = 11
        model.accumulate("dialogue", {"message": "Python AI 编程 JavaScript 设计 系统"})  # +5+10=15 = 26
        
        pending = model.get_pending_behaviors()
        behavior_names = [b.name for b in pending]
        
        # WORLD_FRAGMENT (threshold 20) should be present
        assert "WORLD_FRAGMENT" in behavior_names

    def test_no_behavior_triggered_before_threshold(self):
        """No behavior should trigger below threshold."""
        model = InterestModel()
        model.accumulate("vault_edit")  # +2 only
        
        pending = model.get_pending_behaviors()
        assert len(pending) == 0

    def test_get_pending_behaviors_returns_behavior_objects(self):
        """get_pending_behaviors should return Behavior objects."""
        model = InterestModel()
        model.state.points = 15  # Above QUICK_ASSOCIATION threshold
        
        model.accumulate("dialogue", {"message": "test"})
        
        pending = model.get_pending_behaviors()
        assert all(isinstance(b, Behavior) for b in pending)


class TestCooldown:
    """Test cooldown mechanism after behavior execution."""

    def test_execute_behavior_deducts_cost(self):
        """Executing behavior should deduct its cost from points."""
        model = InterestModel()
        model.state.points = 30  # Well above all thresholds
        
        model.accumulate("dialogue", {"message": "test"})  # Trigger something
        initial_points = model.points
        
        # Execute a behavior
        success = model.execute_behavior("QUICK_ASSOCIATION")
        
        if success:
            assert model.points < initial_points
            assert model.points == initial_points - 5  # QUICK_ASSOCIATION cost

    def test_execute_behavior_sets_cooldown(self):
        """Executing behavior should set cooldown."""
        model = InterestModel()
        model.state.points = 30
        
        model.accumulate("dialogue", {"message": "test"})
        model.execute_behavior("QUICK_ASSOCIATION")
        
        assert model.state.cooldown_tracker.get("QUICK_ASSOCIATION", 0) > 0

    def test_behavior_not_retriggered_during_cooldown(self):
        """Behavior should not re-trigger during cooldown."""
        model = InterestModel()
        model.state.points = 30
        
        # First accumulation triggers QUICK_ASSOCIATION
        model.accumulate("dialogue", {"message": "test"})
        assert "QUICK_ASSOCIATION" in [b.name for b in model.get_pending_behaviors()]
        
        # Execute it
        model.execute_behavior("QUICK_ASSOCIATION")
        
        # Points still high, but should not re-trigger
        model.state.points = 30
        model._check_and_queue_behaviors()
        
        pending = model.get_pending_behaviors()
        names = [b.name for b in pending]
        assert "QUICK_ASSOCIATION" not in names

    def test_cooldown_decrements_on_tick(self):
        """Cooldown should decrement each tick in INTERACTION mode."""
        model = InterestModel()
        model.state.cooldown_tracker["QUICK_ASSOCIATION"] = 3
        
        model.tick()
        
        assert model.state.cooldown_tracker["QUICK_ASSOCIATION"] == 2

    def test_execute_nonexistent_behavior_returns_false(self):
        """Executing non-pending behavior should return False."""
        model = InterestModel()
        
        success = model.execute_behavior("NONEXISTENT")
        
        assert success is False


class TestTickDecay:
    """Test tick() behavior in different modes."""

    def test_tick_increments_tick_count(self):
        """tick() should increment tick_count."""
        model = InterestModel()
        initial = model.tick_count
        
        model.tick()
        
        assert model.tick_count == initial + 1

    def test_interaction_mode_tick_decays_points(self):
        """tick() in INTERACTION mode should decay points by 5."""
        model = InterestModel(initial_mode=Mode.INTERACTION)
        model.state.points = 20
        
        model.tick()
        
        assert model.points == 15  # 20 - 5 = 15

    def test_interaction_mode_tick_decays_interest_vector(self):
        """tick() in INTERACTION mode should decay interest vector."""
        model = InterestModel(initial_mode=Mode.INTERACTION)
        model.state.interest_vector.add("AI", weight=10)
        
        model.tick()
        
        # 10 * 0.95 = 9.5 -> 9
        assert model.state.interest_vector.get("AI") < 10
        assert model.state.interest_vector.get("AI") == 9

    def test_self_mode_tick_does_not_decay_points(self):
        """tick() in SELF mode should NOT decay points."""
        model = InterestModel(initial_mode=Mode.SELF)
        model.state.points = 20
        
        model.tick()
        
        assert model.points == 20

    def test_self_mode_tick_does_not_decay_interest_vector(self):
        """tick() in SELF mode should NOT decay interest vector."""
        model = InterestModel(initial_mode=Mode.SELF)
        model.state.interest_vector.add("AI", weight=10)
        
        model.tick()
        
        # Should still be 10 (no decay)
        assert model.state.interest_vector.get("AI") == 10

    def test_points_never_go_below_zero(self):
        """Points should never go below 0 after decay."""
        model = InterestModel(initial_mode=Mode.INTERACTION)
        model.state.points = 3  # Less than decay rate
        
        model.tick()
        
        assert model.points >= 0

    def test_multiple_ticks_accumulate_decay(self):
        """Multiple ticks should accumulate decay."""
        model = InterestModel(initial_mode=Mode.INTERACTION)
        model.state.points = 25
        
        model.tick()  # -5 = 20
        model.tick()  # -5 = 15
        model.tick()  # -5 = 10
        
        assert model.points == 10


class TestModeTransitions:
    """Test mode setting and transitions."""

    def test_initial_mode_can_be_set(self):
        """Initial mode should be configurable."""
        model = InterestModel(initial_mode=Mode.SELF)
        assert model.mode == Mode.SELF

    def test_set_mode_changes_mode(self):
        """set_mode should change the mode."""
        model = InterestModel(initial_mode=Mode.INTERACTION)
        
        model.set_mode(Mode.SELF)
        
        assert model.mode == Mode.SELF

    def test_set_mode_by_name_valid(self):
        """set_mode_by_name should accept valid names."""
        model = InterestModel()
        
        result = model.set_mode_by_name("self")
        
        assert result is True
        assert model.mode == Mode.SELF

    def test_set_mode_by_name_invalid_returns_false(self):
        """set_mode_by_name should return False for invalid names."""
        model = InterestModel()
        
        result = model.set_mode_by_name("invalid")
        
        assert result is False

    def test_mode_change_logged(self):
        """Mode changes should be logged to history."""
        model = InterestModel()
        model.set_mode(Mode.SELF)
        
        history = model.state.history
        mode_changes = [h for h in history if h["type"] == "mode_change"]
        
        assert len(mode_changes) >= 1


class TestInterestSummary:
    """Test display and summary methods."""

    def test_get_interest_summary_returns_dict(self):
        """get_interest_summary should return a summary dict."""
        model = InterestModel()
        model.accumulate("dialogue", {"message": "Python编程"})
        
        summary = model.get_interest_summary()
        
        assert "points" in summary
        assert "mode" in summary
        assert "tick" in summary
        assert "top_topics" in summary
        assert "pending_behaviors" in summary

    def test_format_display_returns_string(self):
        """format_display should return a formatted string."""
        model = InterestModel()
        
        display = model.format_display()
        
        assert isinstance(display, str)
        assert "Points" in display or "points" in display.lower()


class TestPointsMapping:
    """Verify point mapping constants."""

    def test_dialogue_base_points(self):
        """Dialogue base points should be 5."""
        assert POINTS_CONFIG["dialogue"] == 5

    def test_dialogue_per_keyword_points(self):
        """Dialogue per keyword should be 2."""
        assert POINTS_CONFIG["dialogue_per_keyword"] == 2

    def test_vault_create_points(self):
        """Vault create should be 3 points."""
        assert POINTS_CONFIG["vault_create"] == 3

    def test_vault_edit_points(self):
        """Vault edit should be 2 points."""
        assert POINTS_CONFIG["vault_edit"] == 2

    def test_tag_use_points(self):
        """Tag use should be 4 points."""
        assert POINTS_CONFIG["tag_use"] == 4

    def test_link_establish_points(self):
        """Link establish should be 3 points."""
        assert POINTS_CONFIG["link_establish"] == 3

    def test_decay_rate(self):
        """Decay rate should be 5 per tick."""
        assert DECAY_RATE_PER_TICK == 5

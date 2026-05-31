"""
Tests for perception isolation components.

Tests the debouncing mechanism and activity tracking.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.core.watcher import WriteDebouncer, VaultWatcher, FileEvent
from agent.core.activity import FileActivityTracker, FileActivity


class TestWriteDebouncer:
    """Tests for WriteDebouncer class."""
    
    def test_initial_state(self):
        """Test debouncer starts with empty state."""
        debouncer = WriteDebouncer(debounce_seconds=1.0)
        
        assert len(debouncer.pending_writes) == 0
        assert len(debouncer.settled) == 0
    
    def test_mark_modified(self):
        """Test marking a file as modified."""
        debouncer = WriteDebouncer(debounce_seconds=0.1)
        path = "test.md"
        
        debouncer.mark_modified(path)
        
        assert path in debouncer.pending_writes
        assert path not in debouncer.settled
    
    def test_check_settled_immediately(self):
        """Test that file is not settled immediately after modification."""
        debouncer = WriteDebouncer(debounce_seconds=1.0)
        path = "test.md"
        
        debouncer.mark_modified(path)
        
        assert debouncer.check_settled(path) is False
    
    def test_check_settled_after_wait(self):
        """Test that file settles after debounce period."""
        debouncer = WriteDebouncer(debounce_seconds=0.05)
        path = "test.md"
        
        debouncer.mark_modified(path)
        time.sleep(0.1)
        
        assert debouncer.check_settled(path) is True
    
    def test_get_settled_returns_settled_files(self):
        """Test get_settled returns files that have settled."""
        debouncer = WriteDebouncer(debounce_seconds=0.05)
        
        debouncer.mark_modified("test1.md")
        debouncer.mark_modified("test2.md")
        
        time.sleep(0.1)
        settled = debouncer.get_settled()
        
        assert "test1.md" in settled
        assert "test2.md" in settled
    
    def test_get_settled_clears_pending(self):
        """Test get_settled clears pending entries."""
        debouncer = WriteDebouncer(debounce_seconds=0.05)
        
        debouncer.mark_modified("test.md")
        time.sleep(0.1)
        debouncer.get_settled()
        
        assert "test.md" not in debouncer.pending_writes
    
    def test_is_pending(self):
        """Test is_pending check."""
        debouncer = WriteDebouncer(debounce_seconds=1.0)
        
        assert debouncer.is_pending("test.md") is False
        
        debouncer.mark_modified("test.md")
        
        assert debouncer.is_pending("test.md") is True
    
    def test_clear(self):
        """Test clear removes all state."""
        debouncer = WriteDebouncer(debounce_seconds=1.0)
        
        debouncer.mark_modified("test1.md")
        debouncer.mark_modified("test2.md")
        debouncer.clear()
        
        assert len(debouncer.pending_writes) == 0
        assert len(debouncer.settled) == 0


class TestFileActivityTracker:
    """Tests for FileActivityTracker class."""
    
    def test_initial_state(self):
        """Test tracker starts with empty state."""
        tracker = FileActivityTracker()
        
        assert len(tracker._modification_times) == 0
        assert tracker.get_focus_file() is None
    
    def test_record_modification(self):
        """Test recording file modifications."""
        tracker = FileActivityTracker()
        
        tracker.record_modification("test.md")
        
        assert "test.md" in tracker._modification_times
    
    def test_get_active_files_during_activity(self):
        """Test detecting active file during rapid edits."""
        tracker = FileActivityTracker(active_threshold_seconds=1.0)
        
        tracker.record_modification("test.md")
        
        active = tracker.get_active_files()
        
        assert len(active) == 1
        assert active[0].path == "test.md"
        assert active[0].is_being_edited is True
    
    def test_get_active_files_after_inactivity(self):
        """Test that files become inactive after threshold."""
        tracker = FileActivityTracker(active_threshold_seconds=0.1)
        
        tracker.record_modification("test.md")
        time.sleep(0.2)
        
        active = tracker.get_active_files()
        
        assert len(active) == 0
    
    def test_get_focus_file(self):
        """Test getting the focus file."""
        tracker = FileActivityTracker(active_threshold_seconds=1.0)
        
        tracker.record_modification("test1.md")
        time.sleep(0.05)
        tracker.record_modification("test2.md")
        
        focus = tracker.get_focus_file()
        
        assert focus == "test2.md"
    
    def test_get_focus_file_none_when_inactive(self):
        """Test get_focus_file returns None when no active files."""
        tracker = FileActivityTracker(active_threshold_seconds=0.1)
        
        tracker.record_modification("test.md")
        time.sleep(0.2)
        
        focus = tracker.get_focus_file()
        
        assert focus is None
    
    def test_cleanup_stale_entries(self):
        """Test cleaning up stale entries."""
        tracker = FileActivityTracker()
        
        tracker.record_modification("test.md")
        # Wait for stale threshold to pass
        time.sleep(0.15)
        tracker.cleanup_stale_entries(stale_seconds=0.1)
        
        assert "test.md" not in tracker._modification_times


class TestFileActivity:
    """Tests for FileActivity dataclass."""
    
    def test_default_values(self):
        """Test default values for FileActivity."""
        activity = FileActivity(
            path="test.md",
            is_being_edited=True,
            last_edited=datetime.now()
        )
        
        assert activity.region_hint == "unknown"
    
    def test_all_fields(self):
        """Test all fields can be set."""
        now = datetime.now()
        activity = FileActivity(
            path="test.md",
            is_being_edited=True,
            last_edited=now,
            region_hint="middle"
        )
        
        assert activity.path == "test.md"
        assert activity.is_being_edited is True
        assert activity.last_edited == now
        assert activity.region_hint == "middle"


class TestVaultWatcher:
    """Tests for VaultWatcher class."""
    
    def test_initialization(self):
        """Test watcher initialization."""
        with patch("agent.core.vault.get_vault_path") as mock_get_vault:
            mock_get_vault.return_value = Path("/tmp/test_vault")
            watcher = VaultWatcher(debounce_seconds=2.0)
            
            assert watcher.poll_interval == 2.0
    
    def test_debouncer_integration(self):
        """Test watcher has debouncer for save event detection."""
        with patch("agent.core.vault.get_vault_path") as mock_get_vault:
            mock_get_vault.return_value = Path("/tmp/test_vault")
            watcher = VaultWatcher(debounce_seconds=1.0)
            
            assert hasattr(watcher, 'debouncer')
            assert watcher.debouncer.debounce_seconds == 1.0
    
    def test_debouncer_mark_modified(self):
        """Test marking a file as modified through watcher."""
        with patch("agent.core.vault.get_vault_path") as mock_get_vault:
            mock_get_vault.return_value = Path("/tmp/test_vault")
            watcher = VaultWatcher(debounce_seconds=1.0)
            
            assert watcher.debouncer.is_pending("test.md") is False
            
            watcher.debouncer.mark_modified("test.md")
            
            assert watcher.debouncer.is_pending("test.md") is True
    
    def test_debouncer_settled_after_wait(self):
        """Test file settles after debounce period."""
        with patch("agent.core.vault.get_vault_path") as mock_get_vault:
            mock_get_vault.return_value = Path("/tmp/test_vault")
            watcher = VaultWatcher(debounce_seconds=0.05)
            
            watcher.debouncer.mark_modified("test.md")
            time.sleep(0.1)
            
            assert watcher.debouncer.check_settled("test.md") is True


class TestFileEvent:
    """Tests for FileEvent dataclass."""
    
    def test_default_timestamp(self):
        """Test FileEvent sets timestamp if not provided."""
        event = FileEvent(path="test.md", event_type="modified")
        
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)
    
    def test_explicit_timestamp(self):
        """Test FileEvent uses provided timestamp."""
        now = datetime.now()
        event = FileEvent(path="test.md", event_type="modified", timestamp=now)
        
        assert event.timestamp == now
    
    def test_event_types(self):
        """Test various event types."""
        for event_type in ["created", "modified", "deleted", "moved", "saved"]:
            event = FileEvent(path="test.md", event_type=event_type)
            assert event.event_type == event_type

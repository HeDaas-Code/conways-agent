"""
Tests for the Vault Vitality Monitor
"""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestVitalityState:
    """Tests for VitalityState enum."""

    def test_vitality_states_exist(self):
        """All expected vitality states exist."""
        from agent.core.vitality import VitalityState
        
        assert VitalityState.ALIVE.value == "alive"
        assert VitalityState.DYING.value == "dying"
        assert VitalityState.DEAD.value == "dead"
        assert VitalityState.POLLUTED.value == "polluted"
        assert VitalityState.BORN.value == "born"


class TestVitalityReport:
    """Tests for VitalityReport dataclass."""

    def test_vitality_report_creation(self):
        """VitalityReport can be created with all fields."""
        from agent.core.vitality import VitalityReport, VitalityState
        
        report = VitalityReport(
            state=VitalityState.ALIVE,
            vault_exists=True,
            vault_polluted=False,
            checked_at=datetime.now(),
            message="Test message",
            fork_detected=False,
            original_vault_path=None,
        )
        
        assert report.state == VitalityState.ALIVE
        assert report.vault_exists is True
        assert report.vault_polluted is False
        assert report.message == "Test message"
        assert report.fork_detected is False
        assert report.original_vault_path is None


class TestVaultVitalityMonitor:
    """Tests for VaultVitalityMonitor class."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        agent_dir = vault_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        world_dir = agent_dir / "world"
        world_dir.mkdir(parents=True, exist_ok=True)
        goals_dir = agent_dir / "goals"
        goals_dir.mkdir(parents=True, exist_ok=True)
        logs_dir = agent_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        yield vault_path
        
        if vault_path.exists():
            shutil.rmtree(vault_path)

    @pytest.fixture
    def mock_env(self, temp_vault):
        """Patch the vault path environment variable."""
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(temp_vault)}):
            yield temp_vault

    def test_is_vault_alive_exists(self, mock_env):
        """Vault alive check returns True when vault exists."""
        from agent.core.vitality import VaultVitalityMonitor
        
        monitor = VaultVitalityMonitor(mock_env)
        assert monitor.is_vault_alive() is True

    def test_is_vault_alive_deleted(self, mock_env):
        """Vault alive check returns False when vault is deleted."""
        from agent.core.vitality import VaultVitalityMonitor
        
        shutil.rmtree(mock_env)
        monitor = VaultVitalityMonitor(mock_env)
        assert monitor.is_vault_alive() is False

    def test_is_vault_alive_not_directory(self, mock_env):
        """Vault alive check returns False when path is not a directory."""
        from agent.core.vitality import VaultVitalityMonitor
        
        test_file = mock_env / "test_file.txt"
        test_file.write_text("test")
        
        monitor = VaultVitalityMonitor(test_file)
        assert monitor.is_vault_alive() is False

    def test_check_born_vault_no_git(self, mock_env):
        """Check returns BORN for vault without git (forked/cloned)."""
        from agent.core.vitality import VaultVitalityMonitor, VitalityState
        
        monitor = VaultVitalityMonitor(mock_env)
        report = monitor.check()
        
        assert report.state == VitalityState.BORN
        assert report.vault_exists is True
        assert report.vault_polluted is False
        assert report.fork_detected is True

    def test_check_dead_vault(self, mock_env):
        """Check returns DEAD when vault is deleted."""
        from agent.core.vitality import VaultVitalityMonitor, VitalityState
        
        shutil.rmtree(mock_env)
        monitor = VaultVitalityMonitor(mock_env)
        report = monitor.check()
        
        assert report.state == VitalityState.DEAD
        assert report.vault_exists is False
        assert "消失" in report.message

    def test_handle_death_writes_log(self, mock_env):
        """Handle death writes death log file."""
        from agent.core.vitality import VaultVitalityMonitor
        
        monitor = VaultVitalityMonitor(mock_env)
        monitor.set_last_thought("最后的思考...")
        monitor.handle_death()
        
        death_log_path = mock_env / "agent" / "death-log.json"
        assert death_log_path.exists()
        
        death_data = json.loads(death_log_path.read_text(encoding="utf-8"))
        assert "died_at" in death_data
        assert death_data["reason"] == "vault_deleted"
        assert death_data["last_thought"] == "最后的思考..."

    def test_detect_pollution_clean_vault(self, mock_env):
        """Detect pollution returns False for clean vault."""
        from agent.core.vitality import VaultVitalityMonitor
        
        clean_file = mock_env / "test.md"
        clean_file.write_text("# Test\n\nThis is a clean file.")
        
        monitor = VaultVitalityMonitor(mock_env)
        assert monitor.detect_pollution() is False

    def test_detect_pollution_with_corruption_markers(self, mock_env):
        """Detect pollution returns True when corruption markers found."""
        from agent.core.vitality import VaultVitalityMonitor
        
        corrupted_file = mock_env / "test.md"
        corrupted_file.write_text("# Test\n\n████ 替换我\n████ 替换我\n████ 替换我\n████ 替换我\n████ 替换我\n")
        
        monitor = VaultVitalityMonitor(mock_env)
        assert monitor.detect_pollution() is True

    def test_detect_pollution_with_invalid_frontmatter(self, mock_env):
        """Detect pollution returns True for invalid YAML frontmatter."""
        from agent.core.vitality import VaultVitalityMonitor
        
        invalid_fm_file = mock_env / "test.md"
        invalid_fm_file.write_text("---\ntitle: Test\n::\n---\n\n████\n████\nContent")
        
        monitor = VaultVitalityMonitor(mock_env)
        assert monitor.detect_pollution() is True

    def test_handle_pollution_marks_vault(self, mock_env):
        """Handle pollution creates polluted marker file."""
        from agent.core.vitality import VaultVitalityMonitor
        
        monitor = VaultVitalityMonitor(mock_env)
        monitor._pollution_count = 5
        monitor.handle_pollution()
        
        polluted_marker = mock_env / "agent" / "polluted.marker"
        assert polluted_marker.exists()
        
        marker_data = json.loads(polluted_marker.read_text(encoding="utf-8"))
        assert "marked_at" in marker_data
        assert marker_data["pollution_count"] == 5

    def test_on_fork_creates_born_marker(self, mock_env):
        """On fork creates born marker file."""
        from agent.core.vitality import VaultVitalityMonitor, VitalityState
        
        original_path = Path("/original/vault")
        monitor = VaultVitalityMonitor(mock_env)
        report = monitor.on_fork(original_path)
        
        born_marker = mock_env / "agent" / "born.marker"
        assert born_marker.exists()
        
        born_data = json.loads(born_marker.read_text(encoding="utf-8"))
        assert born_data["state"] == "born_from_fork"
        assert born_data["original_vault"] == str(original_path)
        
        assert report.state == VitalityState.BORN
        assert report.fork_detected is True
        assert report.original_vault_path == original_path

    def test_pollution_count_accumulates(self, mock_env):
        """Pollution count accumulates across checks."""
        from agent.core.vitality import VaultVitalityMonitor
        
        monitor = VaultVitalityMonitor(mock_env)
        assert monitor._pollution_count == 0
        
        monitor._pollution_count = 3
        assert monitor.get_pollution_status()["pollution_count"] == 3
        
        monitor.reset_pollution_count()
        assert monitor._pollution_count == 0

    def test_check_dying_state(self, mock_env):
        """Check returns DYING state when pollution is accumulating."""
        from agent.core.vitality import VaultVitalityMonitor, VitalityState
        
        for i in range(10):
            corrupted_file = mock_env / f"test{i}.md"
            corrupted_file.write_text("# Test\n\n████\n████\n████\n████\n████\n")
        
        monitor = VaultVitalityMonitor(mock_env)
        monitor._pollution_count = 3
        
        report = monitor.check()
        
        assert report.state == VitalityState.DYING
        assert report.vault_polluted is True


class TestGetVitalityMonitor:
    """Tests for get_vitality_monitor factory function."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        agent_dir = vault_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        
        yield vault_path
        
        if vault_path.exists():
            shutil.rmtree(vault_path)

    @pytest.fixture
    def mock_env(self, temp_vault):
        """Patch the vault path environment variable."""
        with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(temp_vault)}):
            yield temp_vault

    def test_get_vitality_monitor_default(self, mock_env):
        """Get monitor with default vault path."""
        from agent.core.vitality import get_vitality_monitor, VaultVitalityMonitor
        
        monitor = get_vitality_monitor()
        
        assert isinstance(monitor, VaultVitalityMonitor)
        assert monitor.vault_path == mock_env

    def test_get_vitality_monitor_custom_path(self, mock_env):
        """Get monitor with custom vault path."""
        from agent.core.vitality import get_vitality_monitor, VaultVitalityMonitor
        
        custom_path = mock_env / "custom"
        monitor = get_vitality_monitor(custom_path)
        
        assert isinstance(monitor, VaultVitalityMonitor)
        assert monitor.vault_path == custom_path


class TestYAMLFrontmatterValidation:
    """Tests for YAML frontmatter validation."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_valid_frontmatter(self, temp_vault):
        """Valid frontmatter does not trigger pollution."""
        from agent.core.vitality import VaultVitalityMonitor
        
        valid_file = temp_vault / "valid.md"
        valid_file.write_text("""---
title: Test Document
created: 2024-01-01
tags:
  - test
  - example
---

# Content
""")
        
        monitor = VaultVitalityMonitor(temp_vault)
        assert monitor._check_yaml_frontmatter_errors(valid_file.read_text()) is False

    def test_invalid_frontmatter_trailing_colon(self, temp_vault):
        """Double colon in frontmatter triggers pollution detection."""
        from agent.core.vitality import VaultVitalityMonitor
        
        invalid_file = temp_vault / "invalid.md"
        invalid_file.write_text("""---
title: Test
::
---

Content
""")
        
        monitor = VaultVitalityMonitor(temp_vault)
        assert monitor._check_yaml_frontmatter_errors(invalid_file.read_text()) is True

    def test_invalid_frontmatter_value_tag(self, temp_vault):
        """Invalid YAML tag value triggers pollution detection."""
        from agent.core.vitality import VaultVitalityMonitor
        
        invalid_file = temp_vault / "invalid.md"
        invalid_file.write_text("""---
title: Test
tags:
---

Content
""")
        
        monitor = VaultVitalityMonitor(temp_vault)
        assert monitor._check_yaml_frontmatter_errors(invalid_file.read_text()) is False


class TestBinaryContentDetection:
    """Tests for binary content detection."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_clean_text_file(self, temp_vault):
        """Clean text file does not trigger binary detection."""
        from agent.core.vitality import VaultVitalityMonitor
        
        clean_file = temp_vault / "clean.md"
        clean_file.write_text("# Title\n\nThis is plain text content.")
        
        monitor = VaultVitalityMonitor(temp_vault)
        assert monitor._check_binary_content(clean_file.read_text()) is False

    def test_pdf_header_detection(self, temp_vault):
        """PDF header triggers binary detection."""
        from agent.core.vitality import VaultVitalityMonitor
        
        binary_file = temp_vault / "binary.md"
        binary_file.write_text("# Title\n\n%PDF-1.4\nBinary content here")
        
        monitor = VaultVitalityMonitor(temp_vault)
        assert monitor._check_binary_content(binary_file.read_text()) is True


class TestAgentIdRetrieval:
    """Tests for agent ID retrieval from state."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        agent_dir = vault_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        
        yield vault_path
        
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_get_agent_id_from_state(self, temp_vault):
        """Agent ID is retrieved from state.json."""
        from agent.core.vitality import VaultVitalityMonitor
        
        state_file = temp_vault / "agent" / "state.json"
        state_data = {
            "personality": {
                "name": "TestAgent"
            }
        }
        state_file.write_text(json.dumps(state_data), encoding="utf-8")
        
        monitor = VaultVitalityMonitor(temp_vault)
        agent_id = monitor._get_agent_id()
        
        assert agent_id == "TestAgent"

    def test_get_agent_id_no_state(self, temp_vault):
        """Agent ID returns 'unknown' when state.json doesn't exist."""
        from agent.core.vitality import VaultVitalityMonitor
        
        monitor = VaultVitalityMonitor(temp_vault)
        agent_id = monitor._get_agent_id()
        
        assert agent_id == "unknown"

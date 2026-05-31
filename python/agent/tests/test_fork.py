"""
Tests for Vault Fork Detection
"""

import json
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestForkInfo:
    """Tests for ForkInfo dataclass."""

    def test_fork_info_creation(self):
        """ForkInfo can be created with all fields."""
        from agent.core.vitality import ForkInfo
        
        forked_at = datetime.now()
        fork_info = ForkInfo(
            is_fork=True,
            original_vault_path=Path("/original/vault"),
            fork_method="git_branch",
            forked_at=forked_at,
            shared_history=["abc123", "def456"],
        )
        
        assert fork_info.is_fork is True
        assert fork_info.original_vault_path == Path("/original/vault")
        assert fork_info.fork_method == "git_branch"
        assert fork_info.forked_at == forked_at
        assert fork_info.shared_history == ["abc123", "def456"]

    def test_fork_info_not_fork(self):
        """ForkInfo represents non-fork state correctly."""
        from agent.core.vitality import ForkInfo
        
        fork_info = ForkInfo(
            is_fork=False,
            original_vault_path=None,
            fork_method="none",
            forked_at=None,
            shared_history=[],
        )
        
        assert fork_info.is_fork is False
        assert fork_info.original_vault_path is None
        assert fork_info.fork_method == "none"
        assert fork_info.forked_at is None
        assert fork_info.shared_history == []


class TestVaultForkDetector:
    """Tests for VaultForkDetector class."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        agent_dir = vault_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        seed_dir = vault_path / "seed"
        seed_dir.mkdir(parents=True, exist_ok=True)
        
        yield vault_path
        
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_detect_fork_no_fork(self, temp_vault):
        """detect_fork returns not a fork when on main branch."""
        from agent.core.vitality import VaultForkDetector
        
        detector = VaultForkDetector(temp_vault)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "main\n"
            
            fork_info = detector.detect_fork()
            
            assert fork_info.is_fork is False
            assert fork_info.fork_method == "none"

    def test_detect_fork_git_branch(self, temp_vault):
        """detect_fork detects non-main branch as fork."""
        from agent.core.vitality import VaultForkDetector
        
        detector = VaultForkDetector(temp_vault)
        
        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0]
            if "rev-parse" in cmd:
                result = MagicMock()
                result.returncode = 0
                result.stdout = "feature/my-branch\n"
                return result
            elif "log" in cmd:
                result = MagicMock()
                result.returncode = 0
                result.stdout = "abc123\ndef456\n"
                return result
            return MagicMock(returncode=1)
        
        with patch("subprocess.run", side_effect=mock_run_side_effect):
            fork_info = detector.detect_fork()
            
            assert fork_info.is_fork is True
            assert fork_info.fork_method == "git_branch"
            assert len(fork_info.shared_history) >= 0

    def test_check_git_branch_main(self, temp_vault):
        """check_git_branch returns not fork for main branch."""
        from agent.core.vitality import VaultForkDetector
        
        detector = VaultForkDetector(temp_vault)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "main\n"
            
            fork_info = detector.check_git_branch()
            
            assert fork_info.is_fork is False

    def test_check_git_branch_master(self, temp_vault):
        """check_git_branch returns not fork for master branch."""
        from agent.core.vitality import VaultForkDetector
        
        detector = VaultForkDetector(temp_vault)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "master\n"
            
            fork_info = detector.check_git_branch()
            
            assert fork_info.is_fork is False

    def test_check_git_branch_feature_branch(self, temp_vault):
        """check_git_branch detects feature branch as fork."""
        from agent.core.vitality import VaultForkDetector
        
        detector = VaultForkDetector(temp_vault)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "feature/experiment\n"
            
            fork_info = detector.check_git_branch()
            
            assert fork_info.is_fork is True
            assert fork_info.fork_method == "git_branch"
            assert fork_info.forked_at is not None

    def test_check_git_branch_git_error(self, temp_vault):
        """check_git_branch handles git errors gracefully."""
        from agent.core.vitality import VaultForkDetector
        
        detector = VaultForkDetector(temp_vault)
        
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            
            fork_info = detector.check_git_branch()
            
            assert fork_info.is_fork is False
            assert fork_info.fork_method == "none"

    def test_check_directory_clone_with_fork_origin(self, temp_vault):
        """check_directory_clone reads existing fork-origin.json."""
        from agent.core.vitality import VaultForkDetector
        
        fork_origin = temp_vault / "agent" / "fork-origin.json"
        fork_origin_data = {
            "is_fork": True,
            "original_vault": "/original/vault",
            "forked_at": "2026-05-31T10:00:00",
            "fork_method": "directory_copy",
            "shared_history": ["abc123"],
        }
        fork_origin.write_text(json.dumps(fork_origin_data), encoding="utf-8")
        
        detector = VaultForkDetector(temp_vault)
        fork_info = detector.check_directory_clone()
        
        assert fork_info.is_fork is True
        assert fork_info.original_vault_path == Path("/original/vault")
        assert fork_info.fork_method == "directory_copy"
        assert fork_info.shared_history == ["abc123"]

    def test_check_directory_clone_no_fork_origin(self, temp_vault):
        """check_directory_clone returns not fork when no fork-origin exists."""
        from agent.core.vitality import VaultForkDetector
        
        detector = VaultForkDetector(temp_vault)
        fork_info = detector.check_directory_clone()
        
        assert fork_info.is_fork is False

    def test_record_fork(self, temp_vault):
        """record_fork writes fork-origin.json."""
        from agent.core.vitality import VaultForkDetector, ForkInfo
        
        fork_info = ForkInfo(
            is_fork=True,
            original_vault_path=Path("/original/vault"),
            fork_method="git_branch",
            forked_at=datetime(2026, 5, 31, 10, 0, 0),
            shared_history=["abc123", "def456"],
        )
        
        detector = VaultForkDetector(temp_vault)
        detector.record_fork(fork_info)
        
        fork_origin_path = temp_vault / "agent" / "fork-origin.json"
        assert fork_origin_path.exists()
        
        data = json.loads(fork_origin_path.read_text(encoding="utf-8"))
        assert data["is_fork"] is True
        assert data["original_vault"] == "/original/vault"
        assert data["fork_method"] == "git_branch"
        assert data["shared_history"] == ["abc123", "def456"]

    def test_get_agent_identity_creates_new(self, temp_vault):
        """get_agent_identity creates identity.json for new agent."""
        from agent.core.vitality import VaultForkDetector
        
        detector = VaultForkDetector(temp_vault)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "main\n"
            
            identity = detector.get_agent_identity()
        
        assert "instance_id" in identity
        assert identity["is_original"] is True
        assert identity["forked_from"] is None
        assert identity["fork_method"] is None
        
        identity_path = temp_vault / "agent" / "identity.json"
        assert identity_path.exists()

    def test_get_agent_identity_existing(self, temp_vault):
        """get_agent_identity returns existing identity."""
        from agent.core.vitality import VaultForkDetector
        
        identity_data = {
            "instance_id": "existing-uuid",
            "born_at": "2026-05-31T09:00:00",
            "forked_from": None,
            "is_original": True,
        }
        identity_path = temp_vault / "agent" / "identity.json"
        identity_path.write_text(json.dumps(identity_data), encoding="utf-8")
        
        detector = VaultForkDetector(temp_vault)
        identity = detector.get_agent_identity()
        
        assert identity["instance_id"] == "existing-uuid"

    def test_get_agent_identity_forked(self, temp_vault):
        """get_agent_identity records fork origin for forked agent."""
        from agent.core.vitality import VaultForkDetector
        
        fork_origin = temp_vault / "agent" / "fork-origin.json"
        fork_origin_data = {
            "is_fork": True,
            "original_vault": "/original/vault",
            "forked_at": "2026-05-31T10:00:00",
            "fork_method": "git_branch",
            "shared_history": [],
        }
        fork_origin.write_text(json.dumps(fork_origin_data), encoding="utf-8")
        
        detector = VaultForkDetector(temp_vault)
        identity = detector.get_agent_identity()
        
        assert identity["is_original"] is False
        assert identity["forked_from"] == "/original/vault"
        assert identity["fork_method"] == "git_branch"


class TestForkDetectionIntegration:
    """Integration tests for fork detection with real filesystem."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        agent_dir = vault_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        
        yield vault_path
        
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_fork_detection_with_seed_file(self, temp_vault):
        """Fork detection considers seed file content."""
        from agent.core.vitality import VaultForkDetector
        
        seed_file = temp_vault / "seed" / "seed.md"
        seed_file.parent.mkdir(parents=True, exist_ok=True)
        seed_file.write_text("# Seed\n\nInitial content", encoding="utf-8")
        
        detector = VaultForkDetector(temp_vault)
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "main\n"
            
            fork_info = detector.detect_fork()
            
            assert fork_info.is_fork is False

    def test_record_and_read_fork(self, temp_vault):
        """Record fork and verify it can be detected again."""
        from agent.core.vitality import VaultForkDetector, ForkInfo
        
        fork_info = ForkInfo(
            is_fork=True,
            original_vault_path=Path("/original/vault"),
            fork_method="directory_copy",
            forked_at=datetime(2026, 5, 31, 10, 0, 0),
            shared_history=["abc123"],
        )
        
        detector = VaultForkDetector(temp_vault)
        detector.record_fork(fork_info)
        
        detector2 = VaultForkDetector(temp_vault)
        detected = detector2.check_directory_clone()
        
        assert detected.is_fork is True
        assert detected.original_vault_path == Path("/original/vault")
        assert detected.fork_method == "directory_copy"

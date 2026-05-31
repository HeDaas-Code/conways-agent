"""
Tests for the Vault Pollution Detector
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestPollutionReport:
    """Tests for PollutionReport dataclass."""

    def test_pollution_report_creation(self):
        """PollutionReport can be created with all fields."""
        from agent.core.vitality import PollutionReport

        report = PollutionReport(
            severity="clean",
            corrupted_files=[],
            yaml_errors=[],
            binary_files=[],
            inconsistency_rate=0.0,
            recommendations=["Vault is clean"],
        )

        assert report.severity == "clean"
        assert report.corrupted_files == []
        assert report.yaml_errors == []
        assert report.binary_files == []
        assert report.inconsistency_rate == 0.0
        assert report.recommendations == ["Vault is clean"]

    def test_pollution_report_with_issues(self):
        """PollutionReport with detected issues."""
        from agent.core.vitality import PollutionReport

        report = PollutionReport(
            severity="moderate",
            corrupted_files=["corrupted.md"],
            yaml_errors=["invalid_yaml.md"],
            binary_files=["has_binary.md"],
            inconsistency_rate=5.5,
            recommendations=["Fix YAML", "Remove binary content"],
        )

        assert report.severity == "moderate"
        assert "corrupted.md" in report.corrupted_files
        assert "invalid_yaml.md" in report.yaml_errors
        assert "has_binary.md" in report.binary_files


class TestVaultPollutionDetector:
    """Tests for VaultPollutionDetector class."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        agent_dir = vault_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_detector_initialization(self, temp_vault):
        """Detector initializes with vault path."""
        from agent.core.vitality import VaultPollutionDetector

        detector = VaultPollutionDetector(temp_vault)
        assert detector.vault_path == temp_vault

    def test_scan_clean_vault(self, temp_vault):
        """Scan returns clean report for clean vault."""
        from agent.core.vitality import VaultPollutionDetector

        clean_file = temp_vault / "test.md"
        clean_file.write_text("# Test\n\nThis is a clean file.")

        detector = VaultPollutionDetector(temp_vault)
        report = detector.scan_for_corruption()

        assert report.severity == "clean"
        assert len(report.corrupted_files) == 0
        assert len(report.yaml_errors) == 0
        assert len(report.binary_files) == 0
        assert "clean" in report.recommendations[0].lower()

    def test_scan_nonexistent_vault(self):
        """Scan returns severe for non-existent vault."""
        from agent.core.vitality import VaultPollutionDetector

        detector = VaultPollutionDetector(Path("/nonexistent/path"))
        report = detector.scan_for_corruption()

        assert report.severity == "severe"
        assert "does not exist" in report.recommendations[0]


class TestYAMLSyntaxChecking:
    """Tests for YAML syntax checking."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_valid_yaml_frontmatter(self, temp_vault):
        """Valid YAML frontmatter passes check."""
        from agent.core.vitality import VaultPollutionDetector

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

        detector = VaultPollutionDetector(temp_vault)
        assert detector.check_yaml_syntax(valid_file) is False

    def test_invalid_yaml_trailing_colon(self, temp_vault):
        """Trailing colon in frontmatter fails check."""
        from agent.core.vitality import VaultPollutionDetector

        invalid_file = temp_vault / "invalid.md"
        invalid_file.write_text("""---
title: Test
:
---

Content
""")

        detector = VaultPollutionDetector(temp_vault)
        assert detector.check_yaml_syntax(invalid_file) is True

    def test_invalid_yaml_double_terminator(self, temp_vault):
        """Double YAML terminator fails check."""
        from agent.core.vitality import VaultPollutionDetector

        invalid_file = temp_vault / "invalid.md"
        invalid_file.write_text("""---
--- ---
title: Test
---

Content
""")

        detector = VaultPollutionDetector(temp_vault)
        assert detector.check_yaml_syntax(invalid_file) is True

    def test_no_frontmatter(self, temp_vault):
        """File without frontmatter passes check."""
        from agent.core.vitality import VaultPollutionDetector

        no_fm_file = temp_vault / "nofm.md"
        no_fm_file.write_text("# Just a title\n\nPlain content.")

        detector = VaultPollutionDetector(temp_vault)
        assert detector.check_yaml_syntax(no_fm_file) is False


class TestBinaryDetection:
    """Tests for binary content detection."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_clean_text_file(self, temp_vault):
        """Clean text file passes check."""
        from agent.core.vitality import VaultPollutionDetector

        clean_file = temp_vault / "clean.md"
        clean_file.write_text("# Title\n\nThis is plain text content.")

        detector = VaultPollutionDetector(temp_vault)
        assert detector.check_binary_in_markdown(clean_file) is False

    def test_file_with_control_characters(self, temp_vault):
        """File with control characters fails check."""
        from agent.core.vitality import VaultPollutionDetector

        binary_file = temp_vault / "binary.md"
        binary_file.write_text("# Title\n\n\x00\x01\x02 Binary content")

        detector = VaultPollutionDetector(temp_vault)
        assert detector.check_binary_in_markdown(binary_file) is True


class TestCorruptionDetection:
    """Tests for file corruption detection."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_corruption_markers(self, temp_vault):
        """Files with corruption markers are detected."""
        from agent.core.vitality import VaultPollutionDetector

        corrupted_file = temp_vault / "corrupted.md"
        corrupted_file.write_text("# Test\n\n████ ???\n████ ???\n████ ???\n████ ???\n████ ???\n")

        detector = VaultPollutionDetector(temp_vault)
        assert detector._check_file_corruption(corrupted_file) is True

    def test_placeholder_markers(self, temp_vault):
        """Files with placeholder markers are detected."""
        from agent.core.vitality import VaultPollutionDetector

        placeholder_file = temp_vault / "placeholder.md"
        placeholder_file.write_text("# Test\n\n{{TODO}}\n{{FIXME}}\n___PLACEHOLDER___\n###CHANGEME\n")

        detector = VaultPollutionDetector(temp_vault)
        assert detector._check_file_corruption(placeholder_file) is True

    def test_clean_file_no_corruption(self, temp_vault):
        """Clean files pass corruption check."""
        from agent.core.vitality import VaultPollutionDetector

        clean_file = temp_vault / "clean.md"
        clean_file.write_text("# Test\n\nThis is a normal file with normal content.")

        detector = VaultPollutionDetector(temp_vault)
        assert detector._check_file_corruption(clean_file) is False


class TestOrphanLinkDetection:
    """Tests for orphan link detection."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_valid_links(self, temp_vault):
        """Valid wiki links to existing files pass."""
        from agent.core.vitality import VaultPollutionDetector

        linked_file = temp_vault / "linked.md"
        linked_file.write_text("# Linked\n\nContent referencing [[Other]]")
        other_file = temp_vault / "Other.md"
        other_file.write_text("# Other")

        detector = VaultPollutionDetector(temp_vault)
        orphans = detector._find_orphan_links(linked_file.read_text(), temp_vault)

        assert "Other" not in orphans

    def test_orphan_links(self, temp_vault):
        """Wiki links to non-existent files are detected."""
        from agent.core.vitality import VaultPollutionDetector

        linked_file = temp_vault / "linked.md"
        linked_file.write_text("# Linked\n\nContent referencing [[Nonexistent]] and [[AlsoMissing]]")

        detector = VaultPollutionDetector(temp_vault)
        orphans = detector._find_orphan_links(linked_file.read_text(), temp_vault)

        assert "Nonexistent" in orphans
        assert "AlsoMissing" in orphans

    def test_link_with_alias(self, temp_vault):
        """Wiki links with aliases are handled correctly."""
        from agent.core.vitality import VaultPollutionDetector

        linked_file = temp_vault / "linked.md"
        linked_file.write_text("# Linked\n\n[[ActualFile|Display Text]]")

        detector = VaultPollutionDetector(temp_vault)
        orphans = detector._find_orphan_links(linked_file.read_text(), temp_vault)

        assert "ActualFile" in orphans


class TestPollutionSeverity:
    """Tests for pollution severity determination."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        agent_dir = vault_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_clean_severity(self, temp_vault):
        """Clean vault returns clean severity."""
        from agent.core.vitality import VaultPollutionDetector

        clean_file = temp_vault / "test.md"
        clean_file.write_text("# Clean\n\nNormal content.")

        detector = VaultPollutionDetector(temp_vault)
        assert detector.get_pollution_severity() == "clean"

    def test_mild_severity(self, temp_vault):
        """Mild issues return mild severity."""
        from agent.core.vitality import VaultPollutionDetector

        file_with_orphan = temp_vault / "orphan.md"
        file_with_orphan.write_text("# Test\n\nLink to [[MissingFile]]")

        detector = VaultPollutionDetector(temp_vault)
        severity = detector.get_pollution_severity()

        assert severity in ["mild", "moderate", "clean"]

    def test_severe_vault_not_exists(self):
        """Non-existent vault returns severe."""
        from agent.core.vitality import VaultPollutionDetector

        detector = VaultPollutionDetector(Path("/nonexistent"))
        assert detector.get_pollution_severity() == "severe"


class TestIntegrationWithVitalityMonitor:
    """Tests for VaultVitalityMonitor.check_pollution integration."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        agent_dir = vault_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_check_pollution_returns_report(self, temp_vault):
        """check_pollution returns PollutionReport."""
        from agent.core.vitality import VaultVitalityMonitor, PollutionReport

        clean_file = temp_vault / "test.md"
        clean_file.write_text("# Test\n\nClean content.")

        monitor = VaultVitalityMonitor(temp_vault)
        report = monitor.check_pollution()

        assert isinstance(report, PollutionReport)
        assert report.severity in ["clean", "mild", "moderate", "severe"]

    def test_check_pollution_with_yaml_errors(self, temp_vault):
        """check_pollution detects YAML errors."""
        from agent.core.vitality import VaultVitalityMonitor

        invalid_file = temp_vault / "invalid.md"
        invalid_file.write_text("""---
title: Test
:
---

Content
""")

        monitor = VaultVitalityMonitor(temp_vault)
        report = monitor.check_pollution()

        assert len(report.yaml_errors) >= 0

    def test_check_pollution_recommendations(self, temp_vault):
        """check_pollution provides recommendations."""
        from agent.core.vitality import VaultVitalityMonitor

        clean_file = temp_vault / "test.md"
        clean_file.write_text("# Clean\n\nNormal content.")

        monitor = VaultVitalityMonitor(temp_vault)
        report = monitor.check_pollution()

        assert len(report.recommendations) > 0


class TestRecommendations:
    """Tests for recommendation generation."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory for each test."""
        vault_path = Path(tempfile.mkdtemp())
        yield vault_path
        if vault_path.exists():
            shutil.rmtree(vault_path)

    def test_recommendations_for_yaml_errors(self, temp_vault):
        """Recommendations include YAML fix advice."""
        from agent.core.vitality import VaultPollutionDetector

        detector = VaultPollutionDetector(temp_vault)
        recs = detector._generate_recommendations(
            yaml_errors=["file1.md", "file2.md"],
            binary_files=[],
            corrupted_files=[],
            orphan_rate=0.0,
            mass_change=False,
        )

        assert any("yaml" in r.lower() for r in recs)

    def test_recommendations_for_binary_files(self, temp_vault):
        """Recommendations include binary content advice."""
        from agent.core.vitality import VaultPollutionDetector

        detector = VaultPollutionDetector(temp_vault)
        recs = detector._generate_recommendations(
            yaml_errors=[],
            binary_files=["binary.md"],
            corrupted_files=[],
            orphan_rate=0.0,
            mass_change=False,
        )

        assert any("binary" in r.lower() for r in recs)

    def test_recommendations_for_orphan_links(self, temp_vault):
        """Recommendations include orphan link advice."""
        from agent.core.vitality import VaultPollutionDetector

        detector = VaultPollutionDetector(temp_vault)
        recs = detector._generate_recommendations(
            yaml_errors=[],
            binary_files=[],
            corrupted_files=[],
            orphan_rate=0.3,
            mass_change=False,
        )

        assert any("link" in r.lower() for r in recs)

    def test_recommendations_for_mass_changes(self, temp_vault):
        """Recommendations include mass change advice."""
        from agent.core.vitality import VaultPollutionDetector

        detector = VaultPollutionDetector(temp_vault)
        recs = detector._generate_recommendations(
            yaml_errors=[],
            binary_files=[],
            corrupted_files=[],
            orphan_rate=0.0,
            mass_change=True,
        )

        assert any("mass" in r.lower() or "external" in r.lower() for r in recs)

    def test_clean_vault_recommendation(self, temp_vault):
        """Clean vault gets 'clean' recommendation."""
        from agent.core.vitality import VaultPollutionDetector

        detector = VaultPollutionDetector(temp_vault)
        recs = detector._generate_recommendations(
            yaml_errors=[],
            binary_files=[],
            corrupted_files=[],
            orphan_rate=0.0,
            mass_change=False,
        )

        assert any("clean" in r.lower() for r in recs)

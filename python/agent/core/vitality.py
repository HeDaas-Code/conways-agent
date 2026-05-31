"""
Vault Vitality Monitor

Monitors vault health — death and pollution detection.
The vault IS the Agent, so when the vault dies, the agent dies.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class VitalityState(Enum):
    ALIVE = "alive"
    DYING = "dying"
    DEAD = "dead"
    POLLUTED = "polluted"
    BORN = "born"  # from a fork


@dataclass
class ForkInfo:
    """Information about a vault fork."""
    is_fork: bool
    original_vault_path: Path | None
    fork_method: str  # "git_branch" | "directory_copy" | "none"
    forked_at: datetime | None
    shared_history: list[str]  # shared commit hashes


@dataclass
class PollutionReport:
    severity: str  # "clean" | "mild" | "moderate" | "severe"
    corrupted_files: list[str]
    yaml_errors: list[str]
    binary_files: list[str]
    inconsistency_rate: float
    recommendations: list[str]


@dataclass
class VitalityReport:
    state: VitalityState
    vault_exists: bool
    vault_polluted: bool
    checked_at: datetime
    message: str
    fork_detected: bool = False
    original_vault_path: Optional[Path] = None


class VaultVitalityMonitor:
    """Monitors vault health — death and pollution detection."""
    
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self._last_thought: str = ""
        self._pollution_count: int = 0
        self._pollution_threshold: int = 5
    
    def check(self) -> VitalityReport:
        """Perform a vitality check."""
        checked_at = datetime.now()
        
        if not self.is_vault_alive():
            return VitalityReport(
                state=VitalityState.DEAD,
                vault_exists=False,
                vault_polluted=False,
                checked_at=checked_at,
                message="图书馆消失了...",
                fork_detected=False,
                original_vault_path=None,
            )
        
        is_polluted = self.detect_pollution()
        fork_detected, original_path = self._detect_fork()
        
        if is_polluted:
            self._pollution_count += 1
            if self._pollution_count >= self._pollution_threshold:
                return VitalityReport(
                    state=VitalityState.POLLUTED,
                    vault_exists=True,
                    vault_polluted=True,
                    checked_at=checked_at,
                    message="图书馆被污染了...",
                    fork_detected=fork_detected,
                    original_vault_path=original_path,
                )
            else:
                return VitalityReport(
                    state=VitalityState.DYING,
                    vault_exists=True,
                    vault_polluted=True,
                    checked_at=checked_at,
                    message=f"图书馆正在腐化... ({self._pollution_count}/{self._pollution_threshold})",
                    fork_detected=fork_detected,
                    original_vault_path=original_path,
                )
        
        if fork_detected:
            self._pollution_count = 0
            return VitalityReport(
                state=VitalityState.BORN,
                vault_exists=True,
                vault_polluted=False,
                checked_at=checked_at,
                message="图书馆从 fork 中诞生了...",
                fork_detected=True,
                original_vault_path=original_path,
            )
        
        self._pollution_count = 0
        return VitalityReport(
            state=VitalityState.ALIVE,
            vault_exists=True,
            vault_polluted=False,
            checked_at=checked_at,
            message="图书馆心跳正常。",
            fork_detected=False,
            original_vault_path=None,
        )
    
    def is_vault_alive(self) -> bool:
        """Check if vault directory still exists."""
        return self.vault_path.exists() and self.vault_path.is_dir()
    
    def detect_pollution(self) -> bool:
        """Check for vault pollution (corrupted files, etc)."""
        if not self.is_vault_alive():
            return True
        
        pollution_indicators = 0
        
        md_files = list(self.vault_path.rglob("*.md"))
        sample_size = min(20, len(md_files))
        sample_files = md_files[:sample_size] if sample_size > 0 else []
        
        for md_file in sample_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                
                if self._check_yaml_frontmatter_errors(content):
                    pollution_indicators += 1
                
                if self._check_binary_content(content):
                    pollution_indicators += 2
                
                if self._check_corruption_markers(content):
                    pollution_indicators += 1
                    
            except (UnicodeDecodeError, PermissionError, OSError):
                pollution_indicators += 2
        
        agent_dir = self.vault_path / "agent"
        if agent_dir.exists():
            corruption_files = list(agent_dir.glob("**/*corrupted*"))
            pollution_indicators += len(corruption_files)
        
        return pollution_indicators >= 3
    
    def _check_yaml_frontmatter_errors(self, content: str) -> bool:
        """Check for YAML frontmatter syntax errors."""
        frontmatter_pattern = r"^---\s*\n(.*?)\n---"
        match = re.match(frontmatter_pattern, content, re.DOTALL)
        
        if not match:
            return False
        
        frontmatter = match.group(1)
        lines = frontmatter.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if not stripped or stripped.startswith('#'):
                i += 1
                continue
            
            if stripped == ':':
                i += 1
                continue
            
            if ':' not in stripped:
                if stripped.startswith('-') or stripped.startswith('...'):
                    i += 1
                    continue
                if line.startswith(' ') or line.startswith('\t'):
                    i += 1
                    continue
                if stripped == '---':
                    i += 1
                    continue
                return True
            
            key, value = stripped.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            if not key:
                return True
            
            if stripped.endswith(':') and len(stripped) > 1 and stripped[-2] != '\\':
                i += 1
                continue
            
            i += 1
        
        if re.search(r'---\s*---', frontmatter):
            return True
        
        return False
    
    def _check_binary_content(self, content: str) -> bool:
        """Check for binary content in markdown files."""
        binary_patterns = [
            (b'\x00', 'null byte'),
            (b'\xfe\xff', 'UTF-16 BOM'),
            (b'\xff\xfe', 'UTF-16 BOM reverse'),
            (b'\xef\xbb\xbf', 'UTF-8 BOM'),
        ]
        
        content_bytes = content.encode('utf-8', errors='ignore')
        
        for pattern, name in binary_patterns:
            if pattern in content_bytes:
                return True
        
        if b'%PDF-' in content_bytes:
            return True
        
        try:
            content.encode('ascii')
        except UnicodeEncodeError:
            return True
        
        if len(content_bytes) > len(content) * 3:
            return True
        
        return False
    
    def _check_corruption_markers(self, content: str) -> bool:
        """Check for unusually high rate of corruption markers."""
        corruption_markers = [
            r"████",
            r"░░░░",
            r"\?\?\?\?",
            r"###CHANGEME",
            r"{{TODO}}",
            r"{{FIXME}}",
            r"___PLACEHOLDER___",
        ]
        
        marker_count = 0
        for pattern in corruption_markers:
            marker_count += len(re.findall(pattern, content))
        
        if len(content) > 0:
            ratio = marker_count / (len(content) / 100)
            if ratio > 0.05:
                return True
        
        return marker_count >= 5
    
    def handle_death(self) -> None:
        """Handle vault death — write death log, stop all activity."""
        death_log = {
            "died_at": datetime.now().isoformat(),
            "reason": "vault_deleted",
            "last_thought": self._last_thought or "图书馆消失了...",
            "vault_path": str(self.vault_path),
            "agent_id": self._get_agent_id(),
        }
        
        death_log_path = self._get_death_log_path()
        death_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        death_log_path.write_text(
            json.dumps(death_log, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        from agent.log import log_event
        log_event(
            "death",
            "Agent died - vault no longer exists",
            death_log
        )
    
    def handle_pollution(self) -> None:
        """Handle vault pollution — mark as polluted, continue with caution."""
        from agent.log import log_event
        
        log_event(
            "pollution_detected",
            "Vault pollution detected - agent operating with caution",
            {
                "pollution_count": self._pollution_count,
                "threshold": self._pollution_threshold,
                "vault_path": str(self.vault_path),
            }
        )
        
        self._mark_polluted_marker()
    
    def _mark_polluted_marker(self) -> None:
        """Mark the vault as polluted with a marker file."""
        polluted_marker = self.vault_path / "agent" / "polluted.marker"
        marker_data = {
            "marked_at": datetime.now().isoformat(),
            "pollution_count": self._pollution_count,
            "message": "图书馆已被污染",
        }
        polluted_marker.write_text(
            json.dumps(marker_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def _detect_fork(self) -> tuple[bool, Optional[Path]]:
        """Detect if vault was forked/cloned.
        
        Returns:
            tuple: (fork_detected, original_vault_path)
        """
        if not self.is_vault_alive():
            return False, None
        
        git_dir = self.vault_path / ".git"
        if not git_dir.exists():
            return True, None
        
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            current_branch = result.stdout.strip() if result.returncode == 0 else "unknown"
            
            if current_branch == "HEAD":
                detached = True
            else:
                detached = False
            
            if detached:
                return True, None
            
            remote_result = subprocess.run(
                ["git", "remote", "-v"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if remote_result.returncode != 0 or not remote_result.stdout.strip():
                return True, None
            
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            untracked = len([l for l in status_result.stdout.strip().split('\n') if l.startswith('??')])
            modified = len([l for l in status_result.stdout.strip().split('\n') if l and not l.startswith('??')])
            
            if untracked > 50 or modified > 100:
                return True, None
            
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        
        return False, None
    
    def detect_fork(self) -> bool:
        """Detect if vault was forked/cloned.
        
        Check for:
        - git branch operation
        - vault directory copied to new location
        """
        fork_detected, _ = self._detect_fork()
        return fork_detected
    
    def on_fork(self, original_vault_path: Optional[Path] = None) -> VitalityReport:
        """Handle forking — Agent continues but knows it was born from a fork."""
        from agent.log import log_event
        
        log_event(
            "fork_born",
            "Agent born from vault fork",
            {
                "original_vault": str(original_vault_path) if original_vault_path else None,
                "current_vault": str(self.vault_path),
                "born_at": datetime.now().isoformat(),
            }
        )
        
        born_marker = self.vault_path / "agent" / "born.marker"
        born_data = {
            "born_at": datetime.now().isoformat(),
            "original_vault": str(original_vault_path) if original_vault_path else None,
            "state": "born_from_fork",
        }
        born_marker.write_text(
            json.dumps(born_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        self._pollution_count = 0
        
        return VitalityReport(
            state=VitalityState.BORN,
            vault_exists=True,
            vault_polluted=False,
            checked_at=datetime.now(),
            message="图书馆从 fork 中诞生了...",
            fork_detected=True,
            original_vault_path=original_vault_path,
        )
    
    def _get_death_log_path(self) -> Path:
        """Get the path to the death log file."""
        return self.vault_path / "agent" / "death-log.json"
    
    def _get_agent_id(self) -> str:
        """Get the agent ID from state or generate one."""
        try:
            state_path = self.vault_path / "agent" / "state.json"
            if state_path.exists():
                state_data = json.loads(state_path.read_text(encoding="utf-8"))
                return state_data.get("personality", {}).get("name", "unknown")
        except (json.JSONDecodeError, OSError):
            pass
        return "unknown"
    
    def set_last_thought(self, thought: str) -> None:
        """Set the agent's last thought before death."""
        self._last_thought = thought
    
    def reset_pollution_count(self) -> None:
        """Reset the pollution counter."""
        self._pollution_count = 0
    
    def get_pollution_status(self) -> dict:
        """Get current pollution status."""
        return {
            "pollution_count": self._pollution_count,
            "threshold": self._pollution_threshold,
            "is_polluted": self._pollution_count >= self._pollution_threshold,
        }

    def check_pollution(self) -> PollutionReport:
        """Perform detailed pollution check and return full report."""
        detector = VaultPollutionDetector(self.vault_path)
        return detector.scan_for_corruption()


class VaultPollutionDetector:
    """Detects vault contamination and corruption."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self._orphan_link_pattern = re.compile(r"\[\[([^\]]+)\]\]")

    def scan_for_corruption(self) -> PollutionReport:
        """Scan all files for signs of corruption."""
        if not self.vault_path.exists():
            return PollutionReport(
                severity="severe",
                corrupted_files=[],
                yaml_errors=[],
                binary_files=[],
                inconsistency_rate=0.0,
                recommendations=["Vault does not exist"],
            )

        corrupted_files: list[str] = []
        yaml_errors: list[str] = []
        binary_files: list[str] = []
        orphan_links: list[str] = []

        md_files = list(self.vault_path.rglob("*.md"))

        for md_file in md_files:
            rel_path = str(md_file.relative_to(self.vault_path))
            try:
                content = md_file.read_text(encoding="utf-8")

                if self.check_yaml_syntax(md_file):
                    yaml_errors.append(rel_path)

                if self.check_binary_in_markdown(md_file):
                    binary_files.append(rel_path)

                if self._check_file_corruption(md_file):
                    corrupted_files.append(rel_path)

                orphan_links.extend(self._find_orphan_links(content, md_file.parent))

            except (UnicodeDecodeError, PermissionError, OSError) as e:
                corrupted_files.append(f"{rel_path}: {e}")

        inconsistency_rate = self.check_inconsistency_rate()
        orphan_rate = len(orphan_links) / max(len(md_files), 1)
        mass_change_detected = self._check_mass_changes()

        severity = self.get_pollution_severity()
        recommendations = self._generate_recommendations(
            yaml_errors, binary_files, corrupted_files, orphan_rate, mass_change_detected
        )

        return PollutionReport(
            severity=severity,
            corrupted_files=corrupted_files,
            yaml_errors=yaml_errors,
            binary_files=binary_files,
            inconsistency_rate=inconsistency_rate,
            recommendations=recommendations,
        )

    def check_yaml_syntax(self, file_path: Path) -> bool:
        """Check if YAML frontmatter has syntax errors."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return True

        frontmatter_pattern = r"^---\s*\n(.*?)\n---"
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            return False

        frontmatter = match.group(1)

        invalid_yaml_indicators = [
            r":\s*$",
            r":\s*\n\s*\n\s*:",
            r"^\s+[^-\s]",
            r"---\s*---",
        ]

        for pattern in invalid_yaml_indicators:
            if re.search(pattern, frontmatter, re.MULTILINE):
                return True

        return False

    def check_binary_in_markdown(self, file_path: Path) -> bool:
        """Check if a markdown file contains binary content."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return True

        binary_indicators = [
            r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
        ]

        for indicator in binary_indicators:
            byte_value = int(indicator[2:-1], 16)
            if bytes([byte_value]) in content.encode('utf-8', errors='ignore'):
                return True

        if len(content.encode('utf-8')) > len(content) * 2:
            return True

        try:
            if b'\x00' in file_path.read_bytes():
                return True
        except OSError:
            pass

        return False

    def check_inconsistency_rate(self) -> float:
        """Check if there's an unusually high rate of inconsistencies.

        If many new fragments conflict with each other rapidly,
        the vault may be polluted.
        """
        git_dir = self.vault_path / ".git"
        if not git_dir.exists():
            return 0.0

        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-n", "100", "--format=%H %ai"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return 0.0

            lines = result.stdout.strip().split('\n')
            if len(lines) < 10:
                return 0.0

            commits = []
            for line in lines:
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    timestamp = parts[1]
                    commits.append(timestamp)

            if len(commits) < 2:
                return 0.0

            from dateutil import parser as date_parser
            first_time = date_parser.parse(commits[-1])
            last_time = date_parser.parse(commits[0])
            time_span_hours = (last_time - first_time).total_seconds() / 3600

            if time_span_hours == 0:
                return float(len(commits))

            return len(commits) / time_span_hours

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ImportError):
            pass

        return 0.0

    def get_pollution_severity(self) -> str:
        """Get overall pollution severity: clean / mild / moderate / severe"""
        report = self.scan_for_corruption()

        total_minor = len(report.yaml_errors) + len(report.binary_files)
        major_issues = len(report.corrupted_files)
        orphan_rate = len(self._find_all_orphan_links()) / max(len(list(self.vault_path.rglob("*.md"))), 1)

        mass_changes = self._check_mass_changes()
        high_inconsistency = report.inconsistency_rate > 10

        if major_issues > 0 or (total_minor >= 3 and (orphan_rate > 0.3 or mass_changes)):
            return "severe"
        elif total_minor >= 3 or orphan_rate > 0.2 or mass_changes or high_inconsistency:
            return "moderate"
        elif total_minor >= 1 or orphan_rate > 0.1:
            return "mild"
        return "clean"

    def _check_file_corruption(self, file_path: Path) -> bool:
        """Check if a file shows signs of corruption."""
        try:
            content = file_path.read_text(encoding="utf-8")

            corruption_markers = [
                r"████",
                r"░░░░",
                r"\?\?\?\?",
                r"###CHANGEME",
                r"{{TODO}}",
                r"{{FIXME}}",
                r"___PLACEHOLDER___",
            ]

            marker_count = 0
            for pattern in corruption_markers:
                marker_count += len(re.findall(pattern, content))

            if len(content) > 0:
                ratio = marker_count / (len(content) / 100)
                if ratio > 0.05:
                    return True

            return marker_count >= 5
        except (UnicodeDecodeError, OSError):
            return True

    def _find_orphan_links(self, content: str, file_dir: Path) -> list[str]:
        """Find wiki-style links to non-existent files."""
        orphan_links: list[str] = []
        links = self._orphan_link_pattern.findall(content)

        for link in links:
            link_clean = link.split('|')[0].strip()
            link_path = file_dir / f"{link_clean}.md"

            if not link_path.exists():
                orphan_links.append(link_clean)

        return orphan_links

    def _find_all_orphan_links(self) -> list[str]:
        """Find all orphan links in the vault."""
        all_orphans: list[str] = []
        md_files = list(self.vault_path.rglob("*.md"))

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                all_orphans.extend(self._find_orphan_links(content, md_file.parent))
            except (UnicodeDecodeError, OSError):
                pass

        return all_orphans

    def _check_mass_changes(self) -> bool:
        """Check for sudden mass changes (possible external script)."""
        git_dir = self.vault_path / ".git"
        if not git_dir.exists():
            return False

        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-n", "20", "--format=%H %ai"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return False

            lines = [l for l in result.stdout.strip().split('\n') if l]
            if len(lines) < 2:
                return False

            from dateutil import parser as date_parser
            first_time = date_parser.parse(lines[-1].split(' ', 1)[1])
            last_time = date_parser.parse(lines[0].split(' ', 1)[1])
            time_span_minutes = (last_time - first_time).total_seconds() / 60

            if time_span_minutes > 0 and len(lines) / time_span_minutes > 5:
                return True

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ImportError):
            pass

        return False

    def _generate_recommendations(
        self,
        yaml_errors: list[str],
        binary_files: list[str],
        corrupted_files: list[str],
        orphan_rate: float,
        mass_change: bool,
    ) -> list[str]:
        """Generate recommendations based on detected issues."""
        recommendations: list[str] = []

        if yaml_errors:
            recommendations.append(
                f"Fix YAML frontmatter in {len(yaml_errors)} file(s): {', '.join(yaml_errors[:3])}"
            )
        if binary_files:
            recommendations.append(
                f"Remove binary content from {len(binary_files)} markdown file(s)"
            )
        if corrupted_files:
            recommendations.append(
                f"Review corrupted files: {', '.join(corrupted_files[:3])}"
            )
        if orphan_rate > 0.2:
            recommendations.append("Create missing linked files or fix broken wiki-links")
        if mass_change:
            recommendations.append("Investigate recent mass changes — possible external script modification")

        if not recommendations:
            recommendations.append("Vault is clean")

        return recommendations


def get_vitality_monitor(vault_path: Optional[Path] = None) -> VaultVitalityMonitor:
    """
    Get a vitality monitor instance.
    
    Args:
        vault_path: Optional vault path, defaults to OBSIDIAN_VAULT_PATH
        
    Returns:
        VaultVitalityMonitor: Monitor instance
    """
    if vault_path is None:
        from agent.core.vault import get_vault_path
        vault_path = get_vault_path()
    
    return VaultVitalityMonitor(vault_path)


__all__ = [
    "VitalityState",
    "VitalityReport",
    "PollutionReport",
    "ForkInfo",
    "VaultForkDetector",
    "VaultVitalityMonitor",
    "VaultPollutionDetector",
    "get_vitality_monitor",
]


class VaultForkDetector:
    """Detects vault forking — the birth of an Agent twin."""
    
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
    
    def detect_fork(self) -> ForkInfo:
        """Detect if this vault is a fork of another.
        
        Check:
        1. Git branch operation (git branch != main)
        2. Vault copied to new location
        3. Recent directory clone
        """
        git_branch_result = self.check_git_branch()
        if git_branch_result.is_fork:
            return git_branch_result
        
        dir_clone_result = self.check_directory_clone()
        if dir_clone_result.is_fork:
            return dir_clone_result
        
        return ForkInfo(
            is_fork=False,
            original_vault_path=None,
            fork_method="none",
            forked_at=None,
            shared_history=[],
        )
    
    def check_git_branch(self) -> ForkInfo:
        """Check if vault is on a non-main git branch."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return ForkInfo(
                    is_fork=False,
                    original_vault_path=None,
                    fork_method="none",
                    forked_at=None,
                    shared_history=[],
                )
            
            current_branch = result.stdout.strip()
            
            if current_branch in ("main", "master"):
                return ForkInfo(
                    is_fork=False,
                    original_vault_path=None,
                    fork_method="none",
                    forked_at=None,
                    shared_history=[],
                )
            
            shared_commits = self._get_shared_history()
            
            return ForkInfo(
                is_fork=True,
                original_vault_path=None,
                fork_method="git_branch",
                forked_at=datetime.now(),
                shared_history=shared_commits,
            )
            
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return ForkInfo(
                is_fork=False,
                original_vault_path=None,
                fork_method="none",
                forked_at=None,
                shared_history=[],
            )
    
    def check_directory_clone(self) -> ForkInfo:
        """Check if vault appears to be a copy of another vault.
        
        Compare:
        - Directory names
        - File hashes of seed/seed.md
        - Recent git history
        """
        fork_origin_path = self.vault_path / "agent" / "fork-origin.json"
        
        if fork_origin_path.exists():
            try:
                data = json.loads(fork_origin_path.read_text(encoding="utf-8"))
                if data.get("is_fork") and data.get("original_vault"):
                    return ForkInfo(
                        is_fork=True,
                        original_vault_path=Path(data["original_vault"]),
                        fork_method=data.get("fork_method", "directory_copy"),
                        forked_at=datetime.fromisoformat(data["forked_at"]) if data.get("forked_at") else None,
                        shared_history=data.get("shared_history", []),
                    )
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        
        seed_file = self.vault_path / "seed" / "seed.md"
        if seed_file.exists():
            try:
                seed_content = seed_file.read_text(encoding="utf-8")
                seed_hash = str(hash(seed_content))
                
                common_vaults = self._find_similar_vaults(seed_hash)
                if common_vaults:
                    return ForkInfo(
                        is_fork=True,
                        original_vault_path=common_vaults[0],
                        fork_method="directory_copy",
                        forked_at=datetime.now(),
                        shared_history=[],
                    )
            except OSError:
                pass
        
        return ForkInfo(
            is_fork=False,
            original_vault_path=None,
            fork_method="none",
            forked_at=None,
            shared_history=[],
        )
    
    def _get_shared_history(self) -> list[str]:
        """Get shared commit hashes with the original repository."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-20", "--format=%H"],
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                commits = [c.strip() for c in result.stdout.strip().split('\n') if c.strip()]
                return commits[:10]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        
        return []
    
    def _find_similar_vaults(self, seed_hash: str) -> list[Path]:
        """Find vaults with matching seed content hash."""
        return []
    
    def record_fork(self, fork_info: ForkInfo) -> None:
        """Record that this Agent was born from a fork.
        
        Write to agent/fork-origin.json:
        {
          "is_fork": true,
          "original_vault": "...",
          "forked_at": "...",
          "fork_method": "..."
        }
        """
        fork_origin_path = self.vault_path / "agent" / "fork-origin.json"
        fork_origin_path.parent.mkdir(parents=True, exist_ok=True)
        
        origin_data = {
            "is_fork": fork_info.is_fork,
            "original_vault": str(fork_info.original_vault_path) if fork_info.original_vault_path else None,
            "forked_at": fork_info.forked_at.isoformat() if fork_info.forked_at else datetime.now().isoformat(),
            "fork_method": fork_info.fork_method,
            "shared_history": fork_info.shared_history,
        }
        
        fork_origin_path.write_text(
            json.dumps(origin_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def get_agent_identity(self) -> dict:
        """Get the Agent's identity info.
        
        If forked: "Agent instance born from {method} at {time}"
        If original: "Agent instance (original)"
        """
        identity_path = self.vault_path / "agent" / "identity.json"
        
        if identity_path.exists():
            try:
                return json.loads(identity_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        
        fork_info = self.detect_fork()
        
        import uuid
        identity = {
            "instance_id": str(uuid.uuid4()),
            "born_at": datetime.now().isoformat(),
            "forked_from": str(fork_info.original_vault_path) if fork_info.is_fork else None,
            "is_original": not fork_info.is_fork,
            "fork_method": fork_info.fork_method if fork_info.is_fork else None,
        }
        
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_path.write_text(
            json.dumps(identity, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        return identity

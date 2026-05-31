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
    
    def _check_binary_content(self, content: str) -> bool:
        """Check for binary content in markdown files."""
        binary_indicators = [
            r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
            r"\x00",
            r"\xfe\xff",
            r"ffd8ffe0",
            r"%PDF-",
        ]
        
        for indicator in binary_indicators:
            if indicator.startswith("\\x"):
                byte_value = int(indicator[2:], 16)
                if bytes([byte_value]) in content.encode('utf-8', errors='ignore'):
                    return True
            elif indicator in content:
                return True
        
        if len(content.encode('utf-8')) > len(content) * 2:
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
            
            if untracked > 10 or modified > 20:
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
    "VaultVitalityMonitor",
    "get_vitality_monitor",
]

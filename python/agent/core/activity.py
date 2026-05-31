"""
File Activity Tracker

Tracks which files are being actively edited based on file modification patterns.
Provides awareness of user activity without reading file content.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class FileActivity:
    """
    Awareness of file activity without reading content.
    
    Attributes:
        path: Path to the file (relative to vault)
        is_being_edited: Whether the file is currently open and being typed in
        last_edited: Timestamp of last edit
        region_hint: Which part of the file is active ("top" | "middle" | "bottom")
    """
    path: str
    is_being_edited: bool
    last_edited: datetime
    region_hint: str = "unknown"


class FileActivityTracker:
    """
    Tracks which files are being actively edited.
    
    Infers activity from rapid consecutive file modifications.
    Files modified within 0.5 seconds are considered "actively being edited".
    """
    
    def __init__(self, active_threshold_seconds: float = 0.5):
        """
        Initialize the activity tracker.
        
        Args:
            active_threshold_seconds: Time window for considering edits as active typing.
                                      Files modified within this window are "active".
        """
        self.active_threshold = timedelta(seconds=active_threshold_seconds)
        self._modification_times: dict[str, datetime] = {}
        self._edit_history: dict[str, list[datetime]] = {}
        self._last_check: datetime = datetime.now()
    
    def record_modification(self, path: str) -> None:
        """
        Record a file modification event.
        
        Args:
            path: Path to the modified file
        """
        now = datetime.now()
        
        if path not in self._edit_history:
            self._edit_history[path] = []
        
        self._edit_history[path].append(now)
        self._modification_times[path] = now
        
        if len(self._edit_history[path]) > 20:
            self._edit_history[path] = self._edit_history[path][-20:]
    
    def get_active_files(self) -> list[FileActivity]:
        """
        Get list of files currently being actively edited.
        
        Returns:
            list[FileActivity]: Files with recent rapid modifications
        """
        now = datetime.now()
        active: list[FileActivity] = []
        
        for path, last_time in list(self._modification_times.items()):
            time_since = now - last_time
            
            if time_since <= self.active_threshold:
                region = self._infer_region(path)
                active.append(FileActivity(
                    path=path,
                    is_being_edited=True,
                    last_edited=last_time,
                    region_hint=region
                ))
        
        return active
    
    def get_focus_file(self) -> str | None:
        """
        Get the file the user is most likely focused on.
        
        Returns:
            str | None: Path to the most recently active file, or None
        """
        active = self.get_active_files()
        if not active:
            return None
        
        return max(active, key=lambda a: a.last_edited).path
    
    def _infer_region(self, path: str) -> str:
        """
        Infer which region of the file is being edited.
        
        Based on modification frequency patterns:
        - Consistent intervals suggest systematic editing (might be top/middle)
        - Bursts suggest focused editing (could be anywhere)
        
        Args:
            path: Path to check
            
        Returns:
            str: Region hint ("top" | "middle" | "bottom" | "unknown")
        """
        history = self._edit_history.get(path, [])
        
        if len(history) < 3:
            return "unknown"
        
        intervals = []
        for i in range(1, min(len(history), 6)):
            delta = (history[-i] - history[-i-1]).total_seconds()
            intervals.append(delta)
        
        avg_interval = sum(intervals) / len(intervals)
        
        if avg_interval < 0.8:
            return "unknown"
        elif avg_interval < 2.0:
            return "middle"
        else:
            return "unknown"
    
    def cleanup_stale_entries(self, stale_seconds: float = 60.0) -> None:
        """
        Remove entries for files that haven't been modified recently.
        
        Args:
            stale_seconds: Time after which an entry is considered stale
        """
        now = datetime.now()
        stale_threshold = timedelta(seconds=stale_seconds)
        
        stale_paths = [
            path for path, last_time in self._modification_times.items()
            if now - last_time > stale_threshold
        ]
        
        for path in stale_paths:
            del self._modification_times[path]
            if path in self._edit_history:
                del self._edit_history[path]


__all__ = ["FileActivity", "FileActivityTracker"]

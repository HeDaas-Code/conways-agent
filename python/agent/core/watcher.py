"""
Vault File Watcher

Monitors the Obsidian vault for file save events using debouncing.
Ensures the Agent perceives only saved file states, not in-progress edits.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from notify import NOTE_CREATE, NOTE_MODIFY, NOTE_DELETE, NOTE_MOVE, Event
from notify import Observer

from ..log import log_event
from .vault import get_vault_path


@dataclass
class FileEvent:
    """
    Represents a file save event.
    
    Attributes:
        path: Path to the file (relative to vault)
        event_type: Type of event ("created" | "modified" | "deleted" | "moved")
        timestamp: When the event was detected
    """
    path: str
    event_type: str
    timestamp: datetime = None
    
    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now()


class WriteDebouncer:
    """
    Debounces file write events to detect when a file is truly saved.
    
    In Obsidian, "save" means the file is written to disk.
    This class waits until a file hasn't changed for N seconds before emitting.
    """
    
    def __init__(self, debounce_seconds: float = 1.0):
        """
        Initialize the debouncer.
        
        Args:
            debounce_seconds: Wait time after last modification before emitting
        """
        self.debounce_seconds = debounce_seconds
        self.pending_writes: dict[str, datetime] = {}
        self.settled: set[str] = set()
        self._last_check: datetime = datetime.now()
    
    def mark_modified(self, path: str) -> None:
        """
        Mark that a file was modified.
        
        Args:
            path: Path to the modified file
        """
        self.pending_writes[path] = datetime.now()
        self.settled.discard(path)
    
    def check_settled(self, path: str) -> bool:
        """
        Check if a file has settled (no more modifications for debounce period).
        
        Args:
            path: Path to check
            
        Returns:
            bool: True if file has settled
        """
        if path not in self.pending_writes:
            return False
        
        elapsed = (datetime.now() - self.pending_writes[path]).total_seconds()
        return elapsed >= self.debounce_seconds
    
    def get_settled(self) -> list[str]:
        """
        Get all files that have settled since last check.
        
        Returns:
            list[str]: Paths of files ready to emit
        """
        settled_files: list[str] = []
        now = datetime.now()
        
        for path, modified_time in list(self.pending_writes.items()):
            elapsed = (now - modified_time).total_seconds()
            if elapsed >= self.debounce_seconds:
                settled_files.append(path)
                del self.pending_writes[path]
                self.settled.add(path)
        
        return settled_files
    
    def is_pending(self, path: str) -> bool:
        """
        Check if a file has pending (unsettled) modifications.
        
        Args:
            path: Path to check
            
        Returns:
            bool: True if file has pending modifications
        """
        return path in self.pending_writes
    
    def clear(self) -> None:
        """Clear all pending writes."""
        self.pending_writes.clear()
        self.settled.clear()


class VaultWatcher:
    """
    Watches the vault for file save events.
    
    Uses debouncing to only emit events when files have stopped being modified.
    This ensures the Agent sees "file finished editing" not "every keystroke".
    """
    
    def __init__(
        self,
        debounce_seconds: float = 1.0,
        on_file_save: Optional[Callable[[FileEvent], None]] = None
    ):
        """
        Initialize the vault watcher.
        
        Args:
            debounce_seconds: Time to wait after last modification before emitting
            on_file_save: Optional callback for file save events
        """
        self.debouncer = WriteDebouncer(debounce_seconds=debounce_seconds)
        self.on_file_save = on_file_save
        self._observer: Optional[Observer] = None
        self._vault_path: Optional[Path] = None
        self._event_buffer: list[FileEvent] = []
        self._ignore_agent = True
    
    def start(self) -> None:
        """Start watching the vault for file events."""
        if self._observer is not None:
            return
        
        self._vault_path = get_vault_path()
        
        self._observer = Observer()
        
        self._observer.schedule(
            VaultEventHandler(watcher=self),
            str(self._vault_path),
            recursive=True
        )
        self._observer.start()
        
        log_event(
            "watcher_start",
            f"Started watching vault: {self._vault_path}",
            {"vault_path": str(self._vault_path)}
        )
    
    def stop(self) -> None:
        """Stop watching the vault."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            
            log_event(
                "watcher_stop",
                "Stopped watching vault",
                {}
            )
    
    def _handle_raw_event(self, path: str, event_type: str) -> None:
        """
        Handle a raw file system event.
        
        Args:
            path: Path to the file
            event_type: Type of event
        """
        if self._ignore_agent and self._is_agent_file(path):
            return
        
        relative_path = self._relative_path(path)
        if relative_path is None:
            return
        
        if event_type == "modified":
            self.debouncer.mark_modified(relative_path)
        elif event_type in ("created", "deleted", "moved"):
            file_event = FileEvent(
                path=relative_path,
                event_type=event_type,
                timestamp=datetime.now()
            )
            self._emit_event(file_event)
    
    def _is_agent_file(self, path: str) -> bool:
        """
        Check if a path is in the agent/ directory.
        
        Args:
            path: Absolute path to check
            
        Returns:
            bool: True if path is in agent/ directory
        """
        if self._vault_path is None:
            return False
        
        try:
            relative = Path(path).relative_to(self._vault_path)
            return any(part == "agent" for part in relative.parts)
        except ValueError:
            return False
    
    def _relative_path(self, path: str) -> Optional[str]:
        """
        Get relative path from vault root.
        
        Args:
            path: Absolute path
            
        Returns:
            Optional[str]: Relative path, or None if not in vault
        """
        if self._vault_path is None:
            return None
        
        try:
            relative = Path(path).relative_to(self._vault_path)
            return str(relative)
        except ValueError:
            return None
    
    def _emit_event(self, event: FileEvent) -> None:
        """
        Emit a file event.
        
        Args:
            event: File event to emit
        """
        self._event_buffer.append(event)
        
        log_event(
            "file_event",
            f"File event: {event.event_type} - {event.path}",
            {
                "path": event.path,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat()
            }
        )
        
        if self.on_file_save is not None:
            self.on_file_save(event)
    
    def watch_once(self) -> list[FileEvent]:
        """
        Check for settled file events (debounced saves).
        
        This should be called periodically to collect settled events.
        Files that haven't been modified for debounce_seconds will be emitted.
        
        Returns:
            list[FileEvent]: List of file events that have settled
        """
        settled_paths = self.debouncer.get_settled()
        events: list[FileEvent] = []
        
        for path in settled_paths:
            event = FileEvent(
                path=path,
                event_type="saved",
                timestamp=datetime.now()
            )
            events.append(event)
            self._emit_event(event)
        
        buffered = self._event_buffer.copy()
        self._event_buffer.clear()
        
        return buffered
    
    def has_pending(self) -> bool:
        """
        Check if there are any pending (unsettled) files.
        
        Returns:
            bool: True if there are pending files
        """
        return len(self.debouncer.pending_writes) > 0
    
    def wait_for_settle(self, timeout: float = 5.0) -> list[FileEvent]:
        """
        Wait for all pending files to settle, then return events.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            list[FileEvent]: Settled file events
        """
        start = time.time()
        all_events: list[FileEvent] = []
        
        while time.time() - start < timeout:
            if not self.has_pending():
                break
            
            time.sleep(0.1)
            events = self.watch_once()
            all_events.extend(events)
        
        return all_events


class VaultEventHandler:
    """
    Handler for notify library events.
    """
    
    def __init__(self, watcher: VaultWatcher):
        """
        Initialize the event handler.
        
        Args:
            watcher: Parent VaultWatcher instance
        """
        self.watcher = watcher
    
    def dispatch(self, event: Event) -> None:
        """
        Dispatch a file system event.
        
        Args:
            event: notify Event object
        """
        if event.is_directory:
            return
        
        path = event.src_path
        
        event_type = None
        if NOTE_CREATE & event.mask:
            event_type = "created"
        elif NOTE_MODIFY & event.mask:
            event_type = "modified"
        elif NOTE_DELETE & event.mask:
            event_type = "deleted"
        elif NOTE_MOVE & event.mask:
            event_type = "moved"
        
        if event_type is not None:
            self.watcher._handle_raw_event(path, event_type)


__all__ = ["VaultWatcher", "FileEvent", "WriteDebouncer"]

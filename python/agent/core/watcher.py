"""
Vault File Watcher

Monitors the Obsidian vault for file changes and pushes events
to the attention window for processing.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from ..log import log_event


@dataclass
class FileEvent:
    """
    Represents a file save event.
    
    Attributes:
        path: Path to the file (relative to vault)
        event_type: Type of event ("created" | "modified" | "deleted" | "moved" | "saved")
        timestamp: When the event was detected
    """
    path: str
    event_type: str
    timestamp: datetime = field(default_factory=datetime.now)


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
    Watches the vault directory for file changes and notifies subscribers.
    
    This watcher integrates with the attention window:
    - New/modified files are pushed to the attention window
    - Priority is based on file recency and event type
    - Only files in the attention window can be perceived
    
    Usage:
        watcher = VaultWatcher(vault_path)
        watcher.start()
        watcher.on_file_change(lambda path: print(f"Changed: {path}"))
    """
    
    def __init__(
        self,
        vault_path: Optional[Path] = None,
        poll_interval: float = 2.0,
        debounce_seconds: float = 1.0
    ):
        """
        Initialize the vault watcher.
        
        Args:
            vault_path: Path to the vault directory. Defaults to vault path from config.
            poll_interval: How often to check for changes (seconds)
            debounce_seconds: Time to wait before emitting save events after last modification
        """
        if vault_path is None:
            from .vault import get_vault_path
            vault_path = get_vault_path()
        
        self.vault_path = Path(vault_path)
        self.poll_interval = poll_interval
        self.debouncer = WriteDebouncer(debounce_seconds=debounce_seconds)
        
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._last_mtimes: dict[str, float] = {}
        self._callbacks: list[Callable[[dict], None]] = []
        self._pending_events: list[FileEvent] = []
        
        # Scan initial state
        self._scan_initial_state()
    
    def _scan_initial_state(self) -> None:
        """Scan vault to establish baseline mtimes."""
        if not self.vault_path.exists():
            log_event(
                "watcher_init_error",
                f"Vault path does not exist: {self.vault_path}",
                {"vault_path": str(self.vault_path)}
            )
            return
        
        for md_file in self.vault_path.rglob("*.md"):
            try:
                # Skip agent/ directory
                relative = md_file.relative_to(self.vault_path)
                if any(part == "agent" for part in relative.parts):
                    continue
                
                mtime = md_file.stat().st_mtime
                self._last_mtimes[str(relative)] = mtime
            except Exception as e:
                log_event(
                    "watcher_scan_error",
                    f"Error scanning file {md_file}: {e}",
                    {"file_path": str(md_file), "error": str(e)}
                )
        
        log_event(
            "watcher_initialized",
            f"Vault watcher initialized with {len(self._last_mtimes)} files",
            {"vault_path": str(self.vault_path), "file_count": len(self._last_mtimes)}
        )
    
    def start(self) -> None:
        """Start watching for file changes."""
        if self._running:
            log_event(
                "watcher_already_running",
                "Watcher is already running",
                {}
            )
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        
        log_event(
            "watcher_started",
            f"Vault watcher started: {self.vault_path}",
            {"vault_path": str(self.vault_path)}
        )
    
    def stop(self) -> None:
        """Stop watching for file changes."""
        if not self._running:
            return
        
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        
        log_event(
            "watcher_stopped",
            "Vault watcher stopped",
            {"vault_path": str(self.vault_path)}
        )
    
    def _watch_loop(self) -> None:
        """Main watching loop - polls for changes."""
        import time
        
        while self._running:
            try:
                self._check_for_changes()
            except Exception as e:
                log_event(
                    "watcher_error",
                    f"Error in watch loop: {e}",
                    {"error": str(e)}
                )
            
            time.sleep(self.poll_interval)
    
    def _check_for_changes(self) -> None:
        """Check for file changes and notify subscribers."""
        if not self.vault_path.exists():
            return
        
        current_files: dict[str, float] = {}
        
        for md_file in self.vault_path.rglob("*.md"):
            try:
                # Skip agent/ directory
                relative = md_file.relative_to(self.vault_path)
                if any(part == "agent" for part in relative.parts):
                    continue
                
                mtime = md_file.stat().st_mtime
                current_files[str(relative)] = mtime
                
                path_str = str(relative)
                
                if path_str not in self._last_mtimes:
                    # New file
                    self._emit_event("create", path_str)
                elif self._last_mtimes[path_str] < mtime:
                    # Modified file
                    self._emit_event("modify", path_str)
                    
            except Exception as e:
                log_event(
                    "watcher_file_error",
                    f"Error checking file {md_file}: {e}",
                    {"file_path": str(md_file), "error": str(e)}
                )
        
        # Check for deleted files
        for path_str, mtime in list(self._last_mtimes.items()):
            if path_str not in current_files:
                self._emit_event("delete", path_str)
        
        self._last_mtimes = current_files
    
    def _emit_event(self, event_type: str, path: str) -> None:
        """
        Emit a file change event.
        
        For "modify" events, uses debouncing to only emit when file is truly saved.
        
        Args:
            event_type: Type of event ("create", "modify", "delete")
            path: Relative path to the file
        """
        if event_type == "modify":
            # Mark as modified for debouncing
            self.debouncer.mark_modified(path)
        elif event_type == "delete":
            # Delete events are immediate
            self._handle_save_event(path, event_type)
        else:
            # Create events are immediate
            self._handle_save_event(path, event_type)
    
    def _handle_save_event(self, path: str, original_type: str) -> None:
        """
        Handle a save event after debouncing.
        
        Args:
            path: Path to the file
            original_type: Original event type
        """
        event = FileEvent(
            path=path,
            event_type=original_type,
            timestamp=datetime.now()
        )
        self._pending_events.append(event)
        
        log_event(
            f"vault_file_saved",
            f"Vault file saved: {path}",
            {"path": path, "original_type": original_type}
        )
        
        # Notify all callbacks
        callback_event = {
            "type": original_type,
            "path": path,
            "timestamp": datetime.now().isoformat(),
            "vault_path": str(self.vault_path)
        }
        for callback in self._callbacks:
            try:
                callback(callback_event)
            except Exception as e:
                log_event(
                    "watcher_callback_error",
                    f"Error in watcher callback: {e}",
                    {"path": path, "error": str(e)}
                )
    
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
            self._pending_events.append(event)
            self._handle_save_event(path, "saved")
        
        # Return pending events and clear
        result = self._pending_events.copy()
        self._pending_events.clear()
        return result
    
    def on_file_change(self, callback: Callable[[dict], None]) -> None:
        """
        Register a callback to be notified of file changes.
        
        The callback receives an event dict with keys:
        - type: "create", "modify", or "delete"
        - path: Relative path to the file
        - timestamp: ISO timestamp of the event
        - vault_path: Absolute path to the vault
        
        Args:
            callback: Function to call when files change
        """
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[dict], None]) -> bool:
        """
        Remove a registered callback.
        
        Args:
            callback: The callback to remove
            
        Returns:
            bool: True if callback was found and removed
        """
        try:
            self._callbacks.remove(callback)
            return True
        except ValueError:
            return False
    
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running
    
    def get_watched_files(self) -> list[str]:
        """Get list of files currently being watched."""
        return list(self._last_mtimes.keys())
    
    def has_pending(self) -> bool:
        """Check if there are any pending (unsettled) files."""
        return len(self.debouncer.pending_writes) > 0


class AttentionAwareWatcher:
    """
    Vault watcher that integrates directly with the attention window.
    
    This watcher pushes file change events directly to the attention
    window, respecting its capacity limits.
    """
    
    def __init__(
        self,
        vault_path: Optional[Path] = None,
        attention_window: Optional["AttentionWindow"] = None  # type: ignore
    ):
        """
        Initialize the attention-aware watcher.
        
        Args:
            vault_path: Path to the vault directory
            attention_window: The attention window to push events to
        """
        from .attention import AttentionWindow
        
        if vault_path is None:
            from .vault import get_vault_path
            vault_path = get_vault_path()
        
        self.vault_path = Path(vault_path)
        self.attention_window = attention_window or AttentionWindow()
        
        self._base_watcher = VaultWatcher(vault_path)
        self._base_watcher.on_file_change(self._handle_event)
    
    def _handle_event(self, event: dict) -> None:
        """
        Handle a file change event.
        
        Pushes new/modified files to the attention window.
        Deleted files are released from attention.
        
        Args:
            event: The file change event
        """
        event_type = event["type"]
        path = event["path"]
        
        if event_type == "delete":
            # Release attention if file was being processed
            if self.attention_window.is_in_attention(path):
                self.attention_window.release_attention(path)
                log_event(
                    "attention_auto_released",
                    f"Auto-released attention for deleted file: {path}",
                    {"file_path": path}
                )
        else:
            # New or modified file - push to attention window
            # Calculate priority based on event type
            priority = 0.5
            if event_type == "create":
                priority += 0.1  # New files get slight boost
            
            admitted = self.attention_window.request_attention(path, priority)
            
            log_event(
                "attention_watcher_event",
                f"Watcher pushed file to attention: {path}",
                {
                    "file_path": path,
                    "event_type": event_type,
                    "admitted": admitted,
                    "priority": priority
                }
            )
    
    def start(self) -> None:
        """Start watching for file changes."""
        self._base_watcher.start()
    
    def stop(self) -> None:
        """Stop watching for file changes."""
        self._base_watcher.stop()
    
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._base_watcher.is_running()


__all__ = ["VaultWatcher", "AttentionAwareWatcher", "FileEvent", "WriteDebouncer"]

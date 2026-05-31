"""
Attention Window System

Simulates human attention limits - the Agent can only perceive a bounded
subset of the vault at any moment. Files enter the attention window via
request, and are released when processing is complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..log import log_event


@dataclass
class AttentionSlot:
    """
    One slot in the attention window.
    
    Attributes:
        file_path: Path to the file being attended to
        priority: Priority level (0.0-1.0, higher = more important)
        added_at: When this slot was added to the window
        processing_started: When processing began (if started)
    """
    
    file_path: str
    priority: float
    added_at: datetime = field(default_factory=datetime.now)
    processing_started: Optional[datetime] = None
    
    def mark_processing_started(self) -> None:
        """Mark that processing has begun for this slot."""
        self.processing_started = datetime.now()


class AttentionWindow:
    """
    The Agent's attention window — only a bounded subset is perceived at any moment.
    
    This simulates human attention limits:
    - Only max_slots files can be actively processed at once
    - Additional files queue up waiting for attention
    - Priority determines queue ordering
    
    Priority factors:
    - File recency: Recently modified files have higher priority
    - Curiosity push: Files from curiosity system have elevated priority
    - User relevance: Files the user recently interacted with
    - Existing interest: Files already partially processed
    
    Default priority for new files: 0.5
    """
    
    def __init__(self, max_slots: int = 3):
        """
        Initialize the attention window.
        
        Args:
            max_slots: Maximum number of files that can be actively processed
        """
        self.max_slots = max_slots
        self.slots: list[AttentionSlot] = []
        self.queue: list[tuple[str, float]] = []  # (path, priority) waiting in queue
    
    def request_attention(self, file_path: str, priority: float = 0.5) -> bool:
        """
        Request to perceive a file.
        
        If there's room in the attention window, the file is immediately admitted.
        Otherwise, it's added to the queue sorted by priority.
        
        Args:
            file_path: Path to the file requesting attention
            priority: Priority level (0.0-1.0), default 0.5
            
        Returns:
            bool: True if immediately admitted to attention window, False if queued
        """
        # Check if already in attention window
        if self.is_in_attention(file_path):
            log_event(
                "attention_request_redundant",
                f"File already in attention window: {file_path}",
                {"file_path": file_path}
            )
            return True
        
        # Check if already in queue
        for path, _ in self.queue:
            if path == file_path:
                log_event(
                    "attention_request_redundant",
                    f"File already in queue: {file_path}",
                    {"file_path": file_path}
                )
                return False
        
        # If there's room, admit to attention window
        if len(self.slots) < self.max_slots:
            slot = AttentionSlot(
                file_path=file_path,
                priority=priority,
                added_at=datetime.now()
            )
            self.slots.append(slot)
            
            log_event(
                "attention_admitted",
                f"File admitted to attention window: {file_path}",
                {
                    "file_path": file_path,
                    "priority": priority,
                    "current_slots": len(self.slots),
                    "max_slots": self.max_slots
                }
            )
            return True
        
        # No room - add to queue
        self.queue.append((file_path, priority))
        # Sort queue by priority (highest first)
        self.queue.sort(key=lambda x: x[1], reverse=True)
        
        log_event(
            "attention_queued",
            f"File added to attention queue: {file_path}",
            {
                "file_path": file_path,
                "priority": priority,
                "queue_position": self._get_queue_position(file_path),
                "queue_length": len(self.queue)
            }
        )
        return False
    
    def release_attention(self, file_path: str) -> None:
        """
        Release attention on a file, freeing up a slot.
        
        If there are files in the queue, the highest-priority one is
        automatically admitted to fill the freed slot.
        
        Args:
            file_path: Path to the file to release
        """
        # Find and remove from slots
        slot_to_remove = None
        for slot in self.slots:
            if slot.file_path == file_path:
                slot_to_remove = slot
                break
        
        if slot_to_remove:
            self.slots.remove(slot_to_remove)
            
            log_event(
                "attention_released",
                f"File released from attention window: {file_path}",
                {
                    "file_path": file_path,
                    "priority": slot_to_remove.priority,
                    "processing_time_seconds": (
                        (datetime.now() - slot_to_remove.added_at).total_seconds()
                        if slot_to_remove.processing_started else None
                    )
                }
            )
            
            # Check if we should admit from queue
            self._admit_from_queue()
        else:
            # Not in slots, try queue
            self._remove_from_queue(file_path)
    
    def _admit_from_queue(self) -> None:
        """Admit the next file from queue to fill a free slot."""
        if not self.queue or len(self.slots) >= self.max_slots:
            return
        
        file_path, priority = self.queue.pop(0)
        
        slot = AttentionSlot(
            file_path=file_path,
            priority=priority,
            added_at=datetime.now()
        )
        self.slots.append(slot)
        
        log_event(
            "attention_admitted_from_queue",
            f"File admitted from queue to attention window: {file_path}",
            {
                "file_path": file_path,
                "priority": priority,
                "remaining_queue": len(self.queue)
            }
        )
    
    def _remove_from_queue(self, file_path: str) -> bool:
        """
        Remove a file from the queue.
        
        Args:
            file_path: Path to remove
            
        Returns:
            bool: True if removed, False if not found
        """
        for i, (path, _) in enumerate(self.queue):
            if path == file_path:
                self.queue.pop(i)
                log_event(
                    "attention_removed_from_queue",
                    f"File removed from queue: {file_path}",
                    {"file_path": file_path}
                )
                return True
        return False
    
    def _get_queue_position(self, file_path: str) -> int:
        """
        Get the position of a file in the queue (1-indexed).
        
        Args:
            file_path: Path to find
            
        Returns:
            int: Queue position (1 = next to be admitted), or -1 if not in queue
        """
        for i, (path, _) in enumerate(self.queue):
            if path == file_path:
                return i + 1
        return -1
    
    def get_active(self) -> list[str]:
        """
        Get list of file paths currently in attention window.
        
        Returns:
            list[str]: List of file paths in active attention
        """
        return [slot.file_path for slot in self.slots]
    
    def get_queue(self) -> list[str]:
        """
        Get list of file paths waiting in queue.
        
        Returns:
            list[str]: List of file paths in queue (ordered by priority)
        """
        return [path for path, _ in self.queue]
    
    def next_in_queue(self) -> Optional[str]:
        """
        Get the next file from queue to admit to attention window.
        
        Does NOT remove the file from the queue - caller should call
        request_attention() after processing the result.
        
        Returns:
            Optional[str]: Next file path, or None if queue is empty
        """
        if self.queue:
            return self.queue[0][0]
        return None
    
    def is_in_attention(self, file_path: str) -> bool:
        """
        Check if a file is currently in the attention window.
        
        Args:
            file_path: Path to check
            
        Returns:
            bool: True if in attention window
        """
        return any(slot.file_path == file_path for slot in self.slots)
    
    def is_queued(self, file_path: str) -> bool:
        """
        Check if a file is currently in the queue.
        
        Args:
            file_path: Path to check
            
        Returns:
            bool: True if in queue
        """
        return any(path == file_path for path, _ in self.queue)
    
    def get_slot(self, file_path: str) -> Optional[AttentionSlot]:
        """
        Get the attention slot for a file.
        
        Args:
            file_path: Path to get slot for
            
        Returns:
            Optional[AttentionSlot]: The slot, or None if not in attention
        """
        for slot in self.slots:
            if slot.file_path == file_path:
                return slot
        return None
    
    def mark_processing(self, file_path: str) -> bool:
        """
        Mark that processing has started for a file.
        
        Args:
            file_path: Path to mark
            
        Returns:
            bool: True if marked successfully
        """
        slot = self.get_slot(file_path)
        if slot:
            slot.mark_processing_started()
            log_event(
                "attention_processing_started",
                f"Processing started for: {file_path}",
                {"file_path": file_path}
            )
            return True
        return False
    
    def get_status(self) -> dict:
        """
        Get current status of the attention window.
        
        Returns:
            dict: Status information
        """
        return {
            "active_count": len(self.slots),
            "max_slots": self.max_slots,
            "queue_length": len(self.queue),
            "active_files": self.get_active(),
            "queued_files": self.get_queue(),
            "available_slots": self.max_slots - len(self.slots)
        }


__all__ = ["AttentionSlot", "AttentionWindow"]

"""
Logging Utilities

Provides logging functionality for agent events.
All logs are written to agent/logs/ directory with timestamps.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()


def _get_logs_dir() -> Path:
    """
    Get the logs directory path.
    
    Returns:
        Path: Path to agent/logs/
    """
    from .core.vault import get_vault_path
    logs_dir = get_vault_path() / "agent" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def log_event(
    event_type: str,
    message: str,
    details: Optional[dict[str, Any]] = None
) -> None:
    """
    Log an event to the agent logs.
    
    Args:
        event_type: Type of event (e.g., "startup", "shutdown", "cycle")
        message: Event message
        details: Optional additional details
    """
    logs_dir = _get_logs_dir()
    
    timestamp = datetime.now()
    log_entry = {
        "timestamp": timestamp.isoformat(),
        "type": event_type,
        "message": message,
        "details": details or {}
    }
    
    log_file = logs_dir / f"{timestamp.strftime('%Y-%m-%d')}.jsonl"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def log_startup(message: str = "Agent awakened") -> None:
    """
    Log an agent startup event.
    
    Args:
        message: Startup message
    """
    log_event("startup", message, {
        "timestamp": datetime.now().isoformat()
    })


def log_shutdown(message: str = "Agent entering dormancy") -> None:
    """
    Log an agent shutdown event.
    
    Args:
        message: Shutdown message
    """
    log_event("shutdown", message, {
        "timestamp": datetime.now().isoformat()
    })


def log_cycle(cycle_number: int, details: Optional[dict] = None) -> None:
    """
    Log a cognitive cycle event.
    
    Args:
        cycle_number: Current cycle number
        details: Optional cycle details
    """
    log_event("cycle", f"Cognitive cycle {cycle_number}", details or {})


def log_error(error: str, details: Optional[dict] = None) -> None:
    """
    Log an error event.
    
    Args:
        error: Error message
        details: Optional error details
    """
    log_event("error", error, details or {})


def get_recent_logs(count: int = 10) -> list[dict]:
    """
    Get recent log entries.
    
    Args:
        count: Number of entries to retrieve
        
    Returns:
        list[dict]: Recent log entries
    """
    logs_dir = _get_logs_dir()
    log_files = sorted(logs_dir.glob("*.jsonl"), reverse=True)
    
    entries = []
    for log_file in log_files:
        if len(entries) >= count:
            break
            
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
                    if len(entries) >= count:
                        break
    
    return entries


__all__ = [
    "log_event",
    "log_startup",
    "log_shutdown",
    "log_cycle",
    "log_error",
    "get_recent_logs"
]

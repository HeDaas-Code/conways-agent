"""
UI Module for Conway's Agent

Provides terminal/TUI interfaces for deep agent interaction.
"""

from .deep_terminal import (
    DeepTerminalInterface,
    DeepTerminalCLI,
    HAS_TEXTUAL,
    HAS_RICH,
)

__all__ = [
    "DeepTerminalInterface",
    "DeepTerminalCLI",
    "HAS_TEXTUAL",
    "HAS_RICH",
]

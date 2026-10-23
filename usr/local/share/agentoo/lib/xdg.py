"""Home-based XDG directory policy, shared by desktop and general commands."""
import os
from pathlib import Path


def xdg_directory(variable, fallback):
    """Return an absolute XDG value, or HOME/fallback when unset, empty or relative.

    The caller supplies the standard home-relative fallback. Runtime directories
    are session-owned and must be validated separately, not given a home fallback.
    """
    value = os.environ.get(variable, '')
    return Path(value) if value and Path(value).is_absolute() else Path.home() / fallback

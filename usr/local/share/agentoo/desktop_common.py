"""Small shared desktop helpers. Importing these performs no operations."""
import os
from pathlib import Path
import re
import subprocess


def xdg_directory(variable, fallback):
    value = os.environ.get(variable, '')
    return Path(value) if value and Path(value).is_absolute() else Path.home() / fallback


def authored_hypr_paths():
    paths = []
    selector = Path('/etc/agentoo/target-host')
    if selector.exists():
        selected = re.fullmatch(r'\s*GENTOO_TARGET_HOST\s*=\s*"([\w-]+)"\s*', selector.read_text(), re.ASCII)
        if selected:
            host = Path('/etc/xdg/hypr/hosts') / (selected[1] + '.lua')
            if host.is_file():
                paths.append(host)
    root = xdg_directory('XDG_CONFIG_HOME', '.config') / 'hypr'
    if root.exists():
        paths.extend(path for path in sorted(root.rglob('*'))
                     if path.suffix in ('.lua', '.conf') and path.is_file())
    return paths


def hyprctl(*arguments, timeout=10):
    try:
        result = subprocess.run(['hyprctl', *arguments], text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f'Cannot contact Hyprland: {error}') from error
    if result.returncode:
        raise RuntimeError('Hyprland: ' + (result.stderr or result.stdout).strip())
    return result.stdout.strip()

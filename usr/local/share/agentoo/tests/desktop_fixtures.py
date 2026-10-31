"""Shared appearance loader for disposable native Hyprland configurations."""
from pathlib import Path


def appearance_loader(directory):
    share = Path(__file__).resolve().parents[1]
    source = share.parents[3] / 'etc/xdg/hypr/appearance.lua'
    target = directory / 'appearance.lua'
    target.write_text(source.read_text().replace(
        '/usr/local/share/agentoo/lib/desktop/state.py', str(share / 'lib/desktop/state.py')))
    return target

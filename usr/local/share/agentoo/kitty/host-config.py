#!/usr/bin/env python3
"""Supply Kitty's selected Agentoo host configuration."""

import re
import sys
from pathlib import Path


def host_config(selector, hosts):
    try:
        contents = selector.read_text()
    except FileNotFoundError:
        return ""
    match = re.fullmatch(r'\s*GENTOO_TARGET_HOST\s*=\s*"([\w-]+)"\s*', contents, re.ASCII)
    if match is None:
        raise ValueError(f'{selector}: expected GENTOO_TARGET_HOST="name"')
    try:
        return (hosts / f"{match[1]}.conf").read_text()
    except FileNotFoundError:
        return ""


if __name__ == "__main__":
    try:
        sys.stdout.write(host_config(Path("/etc/agentoo/target-host"), Path("/etc/xdg/kitty/hosts")))
    except (OSError, ValueError) as error:
        print(f"Agentoo Kitty configuration: {error}", file=sys.stderr)
        sys.exit(1)

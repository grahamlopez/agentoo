"""Deployment paths for the system repository (not Git transaction policy).

Immutable pathlib values; stringify at subprocess and JSON boundaries. Mounted
installations rebase SYSTEM_GIT_DIR relative to SYSTEM_WORK_TREE.
"""
from pathlib import Path

SYSTEM_GIT_DIR = Path('/var/lib/agentoo/repository.git')
SYSTEM_WORK_TREE = Path('/')

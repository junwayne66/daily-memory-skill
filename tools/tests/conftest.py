import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from memoryctl.config import Workspace  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def ws(tmp_path) -> Workspace:
    """Empty initialized workspace."""
    workspace = Workspace(str(tmp_path))
    workspace.ensure_layout()
    return workspace


@pytest.fixture
def ws_with_sources(ws) -> Workspace:
    """Workspace seeded with the sample source fixtures."""
    shutil.copytree(os.path.join(FIXTURES, "sources"), ws.sources, dirs_exist_ok=True)
    return ws


def write(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path

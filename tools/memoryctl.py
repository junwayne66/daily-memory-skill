#!/usr/bin/env python3
"""Launcher so the CLI can be invoked from any directory:

    python3 <skill>/tools/memoryctl.py --workdir <workdir> <command> ...
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memoryctl.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

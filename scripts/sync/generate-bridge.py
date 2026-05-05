#!/usr/bin/env python3
"""Generate factory-bridge.json for The-Factory integration.

Writes global/data/factory-bridge.json with strategic summaries
for all archaeology projects. Called from the 6-hour pipeline.

Usage:
    python3 scripts/sync/generate-bridge.py
"""

import sys
from pathlib import Path

# Add repo root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from archaeology.api import generate_bridge_file


if __name__ == "__main__":
    count = generate_bridge_file()
    print(f"Done: {count} projects written to bridge")

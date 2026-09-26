from __future__ import annotations

import sys
from pathlib import Path

# Đảm bảo import được src/
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from ui.server import start_server

if __name__ == "__main__":
    start_server(port=8080)

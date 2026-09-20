"""
Single-Command Launcher for High-Accuracy Resume Disqualifier Cockpit.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from gui.server import main

if __name__ == "__main__":
    main()

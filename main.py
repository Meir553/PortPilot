#!/usr/bin/env python3
"""PortPilot - SSH Port Forward Manager. Entry point."""

import sys
import os

# Ensure src is on path when running as script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.portpilot.app import main

if __name__ == "__main__":
    sys.exit(main())

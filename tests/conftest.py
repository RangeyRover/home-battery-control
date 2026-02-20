"""Shared fixtures and environment patches for unit tests on Windows.

Strategy: Use plain pytest + unittest.mock. Mock HA primitives directly.
Real HA integration testing happens in the actual HA environment (Linux).
"""
import os
import sys
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock Linux-only modules on Windows
if sys.platform.startswith("win"):
    sys.modules["fcntl"] = MagicMock()
    sys.modules["fcntl"].ioctl = MagicMock()
    sys.modules["resource"] = MagicMock()
    sys.modules["uvloop"] = MagicMock()

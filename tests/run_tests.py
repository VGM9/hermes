#!/usr/bin/env python3
"""
Test runner for hermes test suite.

Invokes pytest programmatically using the same Python that is running this
script — ensuring we use the Python that has pywinauto and pytest installed.

Usage:
  python3 tests/run_tests.py [pytest args...]

Examples:
  python3 tests/run_tests.py -m "not requires_vscode" -v
  python3 tests/run_tests.py --co -q
"""
import sys
import os

# Add hermes root to sys.path so hermes modules are importable in tests
hermes_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if hermes_root not in sys.path:
    sys.path.insert(0, hermes_root)

try:
    import pytest
except ImportError:
    print(f"ERROR: pytest not found in {sys.executable}")
    print(f"Install it with: {sys.executable} -m pip install pytest")
    sys.exit(1)

args = sys.argv[1:] if len(sys.argv) > 1 else ["-m", "not requires_vscode", "-v"]
sys.exit(pytest.main(args))

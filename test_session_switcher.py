#!/usr/bin/env python3
"""
Test script for hermes#35 session_switcher implementation.
Tests get_session_custom_title() against the live POLARIS4 session JSONL.

Usage: python3 test_session_switcher.py

Author: AION0 (Binah station, patch 45)
"""
import sys
import os

# Add hermes-dev to path
HERMES_DEV = r"C:\www\VGM9\_\AS\0.0.Q\_\repos\hermes-dev"
sys.path.insert(0, HERMES_DEV)

from core.ui_automation.session_switcher import get_session_custom_title

if len(sys.argv) < 2:
    print("Usage: python3 test_session_switcher.py <path/to/session.jsonl>", file=sys.stderr)
    sys.exit(1)
TEST_JSONL = sys.argv[1]


def test_get_session_custom_title():
    print(f"Testing get_session_custom_title()")
    print(f"  JSONL: {TEST_JSONL}")

    title = get_session_custom_title(TEST_JSONL)
    if title:
        print(f"  ✅ customTitle found: '{title}'")
    else:
        print(f"  ❌ customTitle not found (returned None)")
        sys.exit(1)

    # Test with nonexistent path
    title2 = get_session_custom_title("/nonexistent/session.jsonl")
    assert title2 is None, f"Expected None for nonexistent path, got {title2!r}"
    print(f"  ✅ None returned for nonexistent path (correct)")


def test_module_imports():
    """Verify no import errors in the module."""
    print(f"\nTesting module imports...")
    try:
        from core.ui_automation.session_switcher import (
            get_session_custom_title,
            switch_to_session_via_quick_pick,
            switch_to_session_by_jsonl,
        )
        print(f"  ✅ All exports importable")
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        sys.exit(1)


def test_window_detection_import():
    """Verify window_detection.py still imports cleanly after modification."""
    print(f"\nTesting window_detection imports...")
    try:
        from core.ui_automation.window_detection import (
            find_target_window,
            find_agent_mode_in_window,
        )
        print(f"  ✅ window_detection imports OK")
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("=== hermes#35 session_switcher tests ===\n")
    test_module_imports()
    test_window_detection_import()
    test_get_session_custom_title()
    print("\n=== All tests PASSED ===")

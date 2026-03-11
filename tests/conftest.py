"""
pytest configuration and fixtures for hermes integration tests.

Tests here use REAL VS Code windows and REAL workspaces as test artifacts.
NO MOCKS.

To run tests that require live VS Code windows:
  pytest tests/ -m requires_vscode

The vscode_window fixture opens a real VS Code window in the given workspace
directory and closes it (via pywinauto window close) after the test completes.
"""
import subprocess
import sys
import time
from pathlib import Path

import pytest
import ctypes
from pywinauto import Desktop

HERMES_DIR = Path(__file__).parent.parent
FIXTURE_WORKSPACE_ALPHA = HERMES_DIR / "tests" / "fixtures" / "workspace_alpha"
FIXTURE_WORKSPACE_BETA = HERMES_DIR / "tests" / "fixtures" / "workspace_beta"
VSCODE_WINDOW_CLASS = "Chrome_WidgetWin_1"


def _find_window_by_title_fragment(fragment: str, timeout: float = 10.0):
    """Poll desktop until a VS Code window with `fragment` in its title appears.

    Returns the pywinauto Window object, or None if not found within timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        desktop = Desktop(backend="uia")
        for win in desktop.windows():
            try:
                if win.class_name() != VSCODE_WINDOW_CLASS:
                    continue
                title = win.window_text()
                if "visual studio code" not in title.lower():
                    continue
                if fragment.lower() in title.lower():
                    return win
            except Exception:
                continue
        time.sleep(0.5)
    return None


def _close_window_by_title_fragment(fragment: str) -> bool:
    """Close the VS Code window whose title contains fragment."""
    desktop = Desktop(backend="uia")
    for win in desktop.windows():
        try:
            if win.class_name() != VSCODE_WINDOW_CLASS:
                continue
            title = win.window_text()
            if "visual studio code" not in title.lower():
                continue
            if fragment.lower() in title.lower():
                win.close()
                return True
        except Exception:
            continue
    return False


@pytest.fixture(scope="function")
def vscode_alpha():
    """Open a real VS Code window in workspace_alpha; close it after the test.

    Yields the workspace directory path (str) so tests can assert on it.
    Skips if VS Code is not found or the window did not open in time.
    """
    workspace = FIXTURE_WORKSPACE_ALPHA
    workspace_name = workspace.name  # "workspace_alpha"

    proc = subprocess.Popen(
        ["code-insiders", "-n", str(workspace)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    win = _find_window_by_title_fragment(workspace_name, timeout=15.0)
    if win is None:
        proc.kill()
        pytest.skip(f"VS Code window for '{workspace_name}' did not appear within 15s")

    yield str(workspace)

    _close_window_by_title_fragment(workspace_name)
    time.sleep(0.5)
    try:
        proc.kill()
    except Exception:
        pass


@pytest.fixture(scope="function")
def vscode_alpha_and_beta():
    """Open VS Code in BOTH workspace_alpha and workspace_beta.

    This is the fixture that reproduces the GHORGS incident scenario:
    two VS Code windows open simultaneously. Testing that spawn_sidecar
    targets ONLY the workspace-matching window.

    Yields (alpha_path, beta_path) tuple.
    """
    alpha = FIXTURE_WORKSPACE_ALPHA
    beta = FIXTURE_WORKSPACE_BETA

    proc_a = subprocess.Popen(
        ["code-insiders", "-n", str(alpha)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    win_a = _find_window_by_title_fragment(alpha.name, timeout=15.0)
    if win_a is None:
        proc_a.kill()
        pytest.skip(f"VS Code window for '{alpha.name}' did not appear within 15s")

    proc_b = subprocess.Popen(
        ["code-insiders", "-n", str(beta)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    win_b = _find_window_by_title_fragment(beta.name, timeout=15.0)
    if win_b is None:
        _close_window_by_title_fragment(alpha.name)
        proc_a.kill()
        proc_b.kill()
        pytest.skip(f"VS Code window for '{beta.name}' did not appear within 15s")

    yield (str(alpha), str(beta))

    _close_window_by_title_fragment(alpha.name)
    _close_window_by_title_fragment(beta.name)
    time.sleep(0.5)
    for proc in [proc_a, proc_b]:
        try:
            proc.kill()
        except Exception:
            pass

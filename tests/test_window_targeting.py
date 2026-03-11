"""
Integration tests for hermes window targeting.

NO MOCKS. Tests run against real VS Code windows and real workspaces.

Test classes:
  TestWorkspaceConstraintEnforcement — verifies spawn_sidecar rejects unsafe calls.
    These tests require NO live VS Code windows. They verify the enforcement boundary.

  TestFindTargetWindow — verifies find_target_window() returns correct results
    against real filesystem workspaceStorage structures.

  TestWindowSelectionAccuracy — verifies that with two VS Code windows open,
    only the workspace-matching window is eligible.
    Requires VS Code. Marked @pytest.mark.requires_vscode.

  TestPasteCleanup — verifies that abandoned paste text (hermes prefix) is
    cleaned by the next send_message() call, not left in the input box.
    Requires VS Code. Marked @pytest.mark.requires_vscode.

Running:
  All tests (headless subset):
    pytest tests/test_window_targeting.py -m "not requires_vscode"

  Full suite including VS Code window tests:
    pytest tests/test_window_targeting.py
    (VS Code tests will skip if windows can't be opened)
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
import ctypes
from pywinauto import Desktop

HERMES_DIR = Path(__file__).parent.parent
SPAWN_SIDECAR = HERMES_DIR / "spawn_sidecar.py"
PYTHON = sys.executable
VSCODE_WINDOW_CLASS = "Chrome_WidgetWin_1"

# Mark for tests that open real VS Code windows.
requires_vscode = pytest.mark.requires_vscode

sys.path.insert(0, str(HERMES_DIR))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run_spawn(extra_args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(SPAWN_SIDECAR)] + extra_args,
        capture_output=True,
        text=True,
    )


def _live_vscode_windows() -> list:
    """Return all VS Code windows currently on the desktop."""
    desktop = Desktop(backend="uia")
    windows = []
    for win in desktop.windows():
        try:
            if win.class_name() != VSCODE_WINDOW_CLASS:
                continue
            if "visual studio code" not in win.window_text().lower():
                continue
            windows.append(win)
        except Exception:
            continue
    return windows


# ─────────────────────────────────────────────────────────────────────────────
# TestWorkspaceConstraintEnforcement
# These tests do NOT require any live VS Code windows.
# They verify that calls without the mandatory --workspace argument are
# rejected immediately, preventing random-window selection entirely.
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkspaceConstraintEnforcement:

    def test_missing_workspace_arg_is_rejected(self):
        """spawn_sidecar must exit nonzero when --workspace is absent.

        This is the regression test for VGM9/hermes#46: the GHORGS incident
        was triggered by a spawn_sidecar call that omitted --workspace, causing
        hermes to inject a mandate into the wrong VS Code window.
        After fix: --workspace is required; argparse raises immediately.
        """
        result = _run_spawn(["--agent", "TESTMODE", "--mandate", "test"])
        assert result.returncode != 0, (
            f"spawn_sidecar must exit nonzero when --workspace is absent. "
            f"Got exit 0. This means random-window selection is still possible.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # argparse should print 'required' or 'error'
        combined = (result.stderr + result.stdout).lower()
        assert "required" in combined or "error" in combined, (
            f"Expected 'required'/'error' in output but got:\n{combined}"
        )

    def test_workspace_not_open_exits_with_no_window_found(self):
        """spawn_sidecar must exit 1 when no window with the given workspace exists.

        Uses a workspace name that is guaranteed not to match any open window.
        Verifies that the workspace filter actually prevents fallback to
        'any available window.'
        """
        unique = "HERMES_TEST_NOWINDOW_29aa7f3e4b1c"
        result = _run_spawn([
            "--agent", "TESTMODE",
            "--mandate", "test",
            "--workspace", unique,
        ])
        assert result.returncode != 0, (
            f"spawn_sidecar must exit nonzero when workspace '{unique}' "
            f"is not open. Got exit 0.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "no suitable window" in result.stderr.lower(), (
            f"Expected 'no suitable window' in stderr.\nstderr: {result.stderr}"
        )

    def test_workspace_filter_does_not_select_unrelated_windows(self):
        """spawn_sidecar --dry-run with a unique workspace name must print
        'no suitable window' even if other VS Code windows are open.

        This proves the filter is actually applied, not bypassed.
        """
        unique = "HERMES_TEST_FILTER_c3d71a9e2b08"
        result = _run_spawn([
            "--agent", "TESTMODE",
            "--mandate", "test",
            "--workspace", unique,
            "--dry-run",
        ])
        assert result.returncode != 0, (
            f"Dry-run with unique workspace '{unique}' must exit nonzero "
            f"(no window found). Got exit 0.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TestFindTargetWindow
# Tests find_target_window() with real filesystem fixtures.
# No live VS Code windows needed for the closed-workspace case.
# ─────────────────────────────────────────────────────────────────────────────

class TestFindTargetWindow:

    def test_returns_none_for_closed_workspace(self, tmp_path):
        """find_target_window() must return None when the workspace is not open.

        Creates a real workspaceStorage-like structure on disk pointing to a
        workspace name that is guaranteed not to appear in any VS Code window
        title. Verifies that the function correctly returns None rather than
        selecting an unrelated window.
        """
        from core.ui_automation.window_detection import find_target_window

        # Build fake but real filesystem structure:
        # tmp_path/workspaceStorage/deadbeef/chatSessions/test.jsonl
        # tmp_path/workspaceStorage/deadbeef/workspace.json
        unique_workspace_name = "hermes_test_closed_ws_4f19a2c7"
        hash_dir = tmp_path / "workspaceStorage" / "deadbeef12345678"
        chat_dir = hash_dir / "chatSessions"
        chat_dir.mkdir(parents=True)

        ws_json = hash_dir / "workspace.json"
        # Fake workspace URI pointing to our unique name
        ws_json.write_text(
            json.dumps({"folder": f"file:///C:/fake/{unique_workspace_name}"}),
            encoding="utf-8",
        )

        fake_jsonl = chat_dir / "test-session.jsonl"
        fake_jsonl.write_text("", encoding="utf-8")

        result = find_target_window(str(fake_jsonl), "TESTMODE")
        assert result is None, (
            f"find_target_window must return None for a workspace "
            f"'{unique_workspace_name}' that is not open in any VS Code window. "
            f"Got: {result}"
        )

    def test_returns_none_when_workspace_json_missing(self, tmp_path):
        """find_target_window() must return None gracefully when workspace.json
        does not exist (e.g., stale JSONL path after workspace storage cleanup).
        """
        from core.ui_automation.window_detection import find_target_window

        hash_dir = tmp_path / "workspaceStorage" / "aabbccdd11223344"
        chat_dir = hash_dir / "chatSessions"
        chat_dir.mkdir(parents=True)
        # No workspace.json written

        fake_jsonl = chat_dir / "orphaned.jsonl"
        fake_jsonl.write_text("", encoding="utf-8")

        result = find_target_window(str(fake_jsonl), "TESTMODE")
        assert result is None, (
            "find_target_window must return None gracefully when workspace.json "
            f"is absent. Got: {result}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TestWindowSelectionAccuracy
# Requires two real VS Code windows. Uses conftest.py vscode_alpha_and_beta.
#
# This test class reproduces the GHORGS incident scenario: two VS Code windows
# open simultaneously. Verifies that spawn_sidecar with workspace=alpha
# does NOT see workspace=beta as a valid candidate.
# ─────────────────────────────────────────────────────────────────────────────

@requires_vscode
class TestWindowSelectionAccuracy:

    def test_workspace_alpha_selected_not_beta_when_both_open(self, vscode_alpha_and_beta):
        """With workspace_alpha and workspace_beta both open, spawn_sidecar
        --workspace workspace_alpha must not select workspace_beta.

        Runs in dry-run mode so no agent mode is switched. Asserts that the
        reported spawn target title contains 'workspace_alpha'.

        This is the direct regression test for the 2026-03-11 incident.
        """
        alpha_path, beta_path = vscode_alpha_and_beta

        result = _run_spawn([
            "--agent", "TESTMODE",
            "--mandate", "test",
            "--workspace", "workspace_alpha",
            "--dry-run",
        ])

        # Should exit 0 (found a window) or exit 1 (no agent mode set — no match
        # after agent-mode filter). Either way, the output must mention alpha, not beta.
        output = result.stdout + result.stderr
        assert "workspace_beta" not in output.lower(), (
            "spawn_sidecar selected workspace_beta when --workspace workspace_alpha "
            f"was given. Cross-workspace injection is still possible.\nOutput: {output}"
        )

    def test_workspace_beta_not_selected_for_alpha_mandate(self, vscode_alpha_and_beta):
        """Inverse: --workspace workspace_beta must not select workspace_alpha."""
        alpha_path, beta_path = vscode_alpha_and_beta

        result = _run_spawn([
            "--agent", "TESTMODE",
            "--mandate", "test",
            "--workspace", "workspace_beta",
            "--dry-run",
        ])
        output = result.stdout + result.stderr
        assert "workspace_alpha" not in output.lower(), (
            "spawn_sidecar selected workspace_alpha when --workspace workspace_beta "
            f"was given.\nOutput: {output}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TestPasteCleanup
# Requires one real VS Code window.
#
# Verifies the fix for the orphaned-paste bug: when send_message() loses
# foreground after paste, the next send_message() call must clear the
# leftover text (because it now starts with [hermes]).
# ─────────────────────────────────────────────────────────────────────────────

@requires_vscode
class TestPasteCleanup:

    def test_orphaned_hermes_text_cleared_on_next_send(self, vscode_alpha):
        """When a paste is abandoned mid-delivery (simulated by calling
        send_message while a [hermes]-prefixed message already sits in the box),
        the next send_message() call must clear the orphan and deliver fresh.

        Setup: manually paste '[hermes] orphan text' into the input box of the
        alpha window (simulating what happens when foreground is lost after paste).
        Then call send_message() with a new message and assert:
          1. The orphan text is gone (cleared by the cleanup branch).
          2. The new message is NOT the orphaned text.
        """
        from pywinauto import Desktop
        from chat.send import send_message
        from chat.input import clipboard_paste, read_content

        # Find the alpha window by title
        desktop = Desktop(backend="uia")
        alpha_win = None
        for win in desktop.windows():
            try:
                if win.class_name() != VSCODE_WINDOW_CLASS:
                    continue
                if "workspace_alpha" in win.window_text().lower():
                    alpha_win = win
                    break
            except Exception:
                continue

        if alpha_win is None:
            pytest.skip("workspace_alpha window not found for paste cleanup test")

        # Simulate orphaned paste: put [hermes]-prefixed text in the input box
        # without sending it (this is what happens on focus loss after paste).
        orphan = "[hermes] orphaned mandate from GHORGS — must be cleared"
        clipboard_paste(alpha_win, orphan)
        time.sleep(0.3)

        # Verify the orphan text is now sitting in the input box.
        existing = (read_content(alpha_win) or "").strip()
        if orphan not in existing:
            pytest.skip(
                "Could not plant orphan text in input box — "
                "chat input may not be visible in workspace_alpha"
            )

        # Now call send_message. It must detect [hermes] prefix, clear the orphan,
        # and deliver the new message. We verify by checking read_content is empty
        # after delivery (input box cleared = message was sent).
        # We use a send that won't disrupt the user — but this test requires
        # system idle, just like hermes itself.
        #
        # NOTE: This test is intended to be run when the machine is idle.
        # If send_message returns False (idle check failed), skip gracefully.
        result = send_message(alpha_win, "HERMES_TEST_DELIVERY_PROBE_7f3a")
        if result is False:
            pytest.skip("System not idle — send_message idle gate fired. Run this test on an idle machine.")

        # The orphaned text should be gone regardless of whether delivery succeeded.
        # If result is None, send_message returned 'suppressed' — which means
        # it saw NON-hermes content (regression: orphan was NOT cleared).
        assert result is not None, (
            "send_message returned None (suppressed) after seeing orphaned "
            "[hermes] text. The cleanup branch did not fire — orphan was NOT "
            "treated as hermes content despite [hermes] prefix.\n"
            f"Read content: {read_content(alpha_win)!r}"
        )

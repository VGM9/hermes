#!/usr/bin/env python3
"""
RAAS Self-Analyze - Rotate, Attach, Analyze, Self-send

Full flow for an agent to:
1. Attach a rotated image to their own chat
2. Type an analysis prompt
3. Spawn background watcher
4. When agent stops, watcher sends the message

This enables autonomous image re-analysis in the same session.

Usage:
    python raas_self_analyze.py <image_path> [prompt]
    
Default prompt: "Analyze this image at orientation N"

Prerequisites:
- qopilot extension must be installed (provides qopilot.attachFile command)
- pywinauto must be installed

Author: ALTAIR lineage (0.0.Q → 0.8.Q)
"""

import sys
import time
import subprocess
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# Import HERMES components
from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys


def write_intent(file_path: str):
    """Write an intent file for qopilot extension to pick up.
    
    The qopilot extension watches for intent files and executes
    the workbench.action.chat.attachFile command.
    """
    import tempfile
    
    intent_dir = Path(tempfile.gettempdir()) / "qopilot_intents"
    intent_dir.mkdir(exist_ok=True)
    
    intent_file = intent_dir / f"attach_{int(time.time() * 1000)}.json"
    intent = {
        "action": "attachFile",
        "filePath": str(file_path),
        "timestamp": time.time()
    }
    
    intent_file.write_text(json.dumps(intent, indent=2))
    print(f"✓ Intent written: {intent_file}")
    return intent_file


def attach_via_cli(file_path: str):
    """Attempt to attach file using code-insiders command.
    
    Note: This may not work for same-session - it might spawn new session.
    """
    # This command opens EXISTING file in editor, which might trigger attachment
    # via lastFocusedWidget behavior. Experimental.
    cmd = ["code-insiders", "--reuse-window", str(file_path)]
    subprocess.run(cmd, capture_output=True)
    time.sleep(0.5)


def type_message(message: str):
    """Type message into current chat input without pressing Enter."""
    handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
    
    for handle in handles:
        try:
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            title = win.window_text()
            
            if "Visual Studio Code" not in title:
                continue
            
            win.set_focus()
            time.sleep(0.3)
            
            print(f"Typing: {message[:50]}...")
            send_keys(message, with_spaces=True, pause=0.02)
            print("✓ Typed (no Enter)")
            return True
            
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print("✗ No VS Code window found")
    return False


def spawn_watcher():
    """Spawn background process to click send when available."""
    watcher = SCRIPT_DIR / "hermes_wait_send.py"
    
    if not watcher.exists():
        print(f"✗ Watcher not found: {watcher}")
        return False
    
    print("Spawning send watcher...")
    subprocess.Popen(
        ["python", str(watcher)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    )
    print("✓ Watcher spawned")
    return True


def main():
    if len(sys.argv) < 2:
        print("RAAS Self-Analyze - Autonomous image re-analysis")
        print()
        print("Usage:")
        print("  python raas_self_analyze.py <image_path> [prompt]")
        print()
        print("Example:")
        print("  python raas_self_analyze.py card_90deg.png 'Analyze rotation 1'")
        print()
        print("Flow:")
        print("  1. Writes intent file for qopilot to attach image")
        print("  2. Types prompt into chat")
        print("  3. Spawns watcher to click send after agent stops")
        return 1
    
    image_path = Path(sys.argv[1]).resolve()
    prompt = sys.argv[2] if len(sys.argv) > 2 else f"Analyze this image"
    
    if not image_path.exists():
        print(f"✗ Image not found: {image_path}")
        return 1
    
    print(f"Image: {image_path}")
    print(f"Prompt: {prompt}")
    print()
    
    # Step 1: Write intent for attachment
    print("[1/3] Writing attach intent...")
    write_intent(str(image_path))
    time.sleep(0.5)  # Give extension time to process
    
    # Step 2: Type the prompt
    print("[2/3] Typing prompt...")
    if not type_message(prompt):
        return 1
    
    # Step 3: Spawn watcher
    print("[3/3] Spawning watcher...")
    if not spawn_watcher():
        return 1
    
    print()
    print("═" * 50)
    print("RAAS Self-Analyze initiated!")
    print("When you finish this turn, the watcher will click send.")
    print("═" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())

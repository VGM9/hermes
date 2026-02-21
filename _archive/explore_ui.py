#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explore VS Code UI structure to find chat input field."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import hermes_window_ops as window_ops

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def explore_ui_structure():
    """Explore UI structure of focused VS Code window."""
    
    print("\nFinding focused VS Code window...")
    focused = window_ops.get_focused_vscode_window()
    if not focused:
        print("ERROR: No VS Code window has focus")
        return
    
    win = focused['window']
    title = focused['title']
    print(f"Found: {title[:60]}\n")
    
    print("="*70)
    print("Exploring UI Structure")
    print("="*70)
    
    # Find all Edit controls
    print("\n1. ALL EDIT CONTROLS:")
    print("-" * 70)
    edit_controls = win.descendants(control_type="Edit")
    for i, edit in enumerate(edit_controls[:20]):  # Limit to first 20
        try:
            name = edit.element_info.name if hasattr(edit.element_info, 'name') else ""
            auto_id = edit.element_info.automation_id if hasattr(edit.element_info, 'automation_id') else ""
            class_name = edit.element_info.class_name if hasattr(edit.element_info, 'class_name') else ""
            
            print(f"\nEdit #{i+1}:")
            print(f"  Name: {name}")
            print(f"  AutomationID: {auto_id}")
            print(f"  Class: {class_name}")
        except Exception as e:
            print(f"\nEdit #{i+1}: Error reading properties - {e}")
    
    # Find all Panes
    print("\n\n2. ALL PANE CONTROLS (looking for chat panel):")
    print("-" * 70)
    panes = win.descendants(control_type="Pane")
    for i, pane in enumerate(panes[:30]):  # Limit to first 30
        try:
            name = pane.element_info.name if hasattr(pane.element_info, 'name') else ""
            auto_id = pane.element_info.automation_id if hasattr(pane.element_info, 'automation_id') else ""
            
            # Only show if name/id contains interesting keywords
            if any(keyword in name.lower() or keyword in auto_id.lower() 
                   for keyword in ['chat', 'copilot', 'github', 'panel', 'view']):
                print(f"\nPane #{i+1}:")
                print(f"  Name: {name}")
                print(f"  AutomationID: {auto_id}")
        except Exception as e:
            continue
    
    # Find all Buttons
    print("\n\n3. BUTTON CONTROLS (looking for chat/send buttons):")
    print("-" * 70)
    buttons = win.descendants(control_type="Button")
    for i, btn in enumerate(buttons[:40]):  # Limit to first 40
        try:
            name = btn.element_info.name if hasattr(btn.element_info, 'name') else ""
            auto_id = btn.element_info.automation_id if hasattr(btn.element_info, 'automation_id') else ""
            
            # Only show if name/id contains interesting keywords
            if any(keyword in name.lower() or keyword in auto_id.lower()
                   for keyword in ['chat', 'copilot', 'send', 'submit', 'ask']):
                print(f"\nButton #{i+1}:")
                print(f"  Name: {name}")
                print(f"  AutomationID: {auto_id}")
        except Exception as e:
            continue
    
    print("\n" + "="*70)
    print("Exploration complete")
    print("="*70)


if __name__ == '__main__':
    try:
        explore_ui_structure()
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    except Exception as e:
        logger.exception("Failed")

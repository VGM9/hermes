#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chat.input — Chat input utilities

Provides functions for interacting with the chat input field.
"""

import time
import ctypes
from pywinauto import Application

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Without explicit restype, ctypes defaults to c_int (32-bit), which truncates
# 64-bit pointers on x64 Windows and causes access violations in wstring_at/memmove.
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
user32.GetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]


def _is_foreground(win) -> bool:
    """Return True only if win IS the current foreground window.

    Structural safety gate: never inject keystrokes or focus-steal into a window
    the user is not currently working in. Called before every destructive
    operation in this module (click_input, type_keys). If not foreground,
    callers must abort without sending a single keystroke.
    """
    try:
        fg_handle = user32.GetForegroundWindow()
        return int(fg_handle) == int(win.handle)
    except Exception:
        return False

def wait_for_chat_ready(win, timeout=30):
    """Block until chat Edit is visible+enabled, or timeout expires."""
    end = time.time() + timeout
    while time.time() < end:
        if not _is_foreground(win):
            time.sleep(0.5)
            continue
        try:
            for edit in win.descendants(control_type="Edit"):
                name = (edit.element_info.name or "").lower()
                cls = edit.element_info.class_name or ""
                if "chat input" in name or cls == "native-edit-context":
                    if edit.is_visible() and edit.is_enabled():
                        try:
                            edit.click_input()
                            return edit
                        except Exception:
                            pass
        except Exception:
            pass
        time.sleep(0.5)
    return None

def read_content(win) -> str:
    """Return current text in the chat input Edit control, or empty string."""
    try:
        for edit in win.descendants(control_type="Edit"):
            name = (edit.element_info.name or "").lower()
            cls = edit.element_info.class_name or ""
            if "chat input" in name or cls == "native-edit-context":
                return edit.window_text() or ""
    except Exception:
        pass
    return ""

def clear_input(win):
    """Select-all + Delete to clear the chat input box."""
    try:
        for edit in win.descendants(control_type="Edit"):
            name = (edit.element_info.name or "").lower()
            cls = edit.element_info.class_name or ""
            if "chat input" in name or cls == "native-edit-context":
                if not _is_foreground(win):
                    return  # wrong window in focus — do not touch
                edit.click_input()
                time.sleep(0.05)
                win.type_keys("^a{DEL}")
                time.sleep(0.1)
                return
    except Exception:
        pass

def clipboard_paste(win, message):
    """Write message to clipboard and paste into chat input via ^v."""
    def _clip_read():
        text = ""
        if user32.OpenClipboard(0):
            if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                h = user32.GetClipboardData(CF_UNICODETEXT)
                if h:
                    ptr = kernel32.GlobalLock(h)
                    if ptr:
                        text = ctypes.wstring_at(ptr)
                        kernel32.GlobalUnlock(h)
            user32.CloseClipboard()
        return text

    def _clip_write(text):
        encoded = (text + "\0").encode("utf-16-le")
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not h:
            return
        ptr = kernel32.GlobalLock(h)
        if ptr:
            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(h)
        if user32.OpenClipboard(0):
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_UNICODETEXT, h)
            user32.CloseClipboard()

    saved = _clip_read()
    try:
        _clip_write(message)
        if not _is_foreground(win):
            return  # wrong window — clipboard prepared but do not paste
        win.type_keys("^v")
        time.sleep(0.1)
    finally:
        if saved:
            _clip_write(saved)
        else:
            if user32.OpenClipboard(0):
                user32.EmptyClipboard()
                user32.CloseClipboard()

def find_send_button(win):
    """Return the Send button control, or None."""
    for btn in win.descendants(control_type="Button"):
        name = (btn.element_info.name or "").lower()
        if name in {"send", "send message", "submit"}:
            return btn
    return None
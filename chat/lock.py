#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chat.lock — WakeLock context manager

Provides a context manager for acquiring and releasing wake locks.
"""

import os
from pathlib import Path

WAKE_LOCK_FILE = Path(__file__).parent.parent / "hermes_wake.lock"

class WakeLock:
    def __enter__(self):
        """Acquire the wake lock."""
        try:
            with open(WAKE_LOCK_FILE, 'x') as f:
                f.write(str(os.getpid()))
            return True
        except FileExistsError:
            try:
                other_pid = int(WAKE_LOCK_FILE.read_text().strip())
                os.kill(other_pid, 0)
                raise RuntimeError("Wake lock already held by another process.")
            except (ProcessLookupError, ValueError):
                WAKE_LOCK_FILE.unlink()
                return self.__enter__()

    def __exit__(self, *_):
        """Release the wake lock."""
        try:
            WAKE_LOCK_FILE.unlink()
        except Exception:
            pass
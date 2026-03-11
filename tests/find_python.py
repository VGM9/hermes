#!/usr/bin/env python3
"""
Find the Python executable that has pywinauto installed.
Prints the path so it can be captured by shell scripts.
"""
import sys
import os
import subprocess

# Candidates in priority order
candidates = [
    sys.executable,
    r"C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.10_3.10.3056.0_x64__qbz5n2kfra8p0\python3.10.exe",
    r"C:\Python310\python.exe",
    r"C:\Python311\python.exe",
    r"C:\Python39\python.exe",
]

# Also search PATH
import shutil
for name in ["python3.10", "python3", "python"]:
    path = shutil.which(name)
    if path and path not in candidates:
        candidates.append(path)

for candidate in candidates:
    if not os.path.isfile(candidate):
        continue
    result = subprocess.run(
        [candidate, "-c", "import pywinauto; print('ok')"],
        capture_output=True, text=True
    )
    if result.returncode == 0 and "ok" in result.stdout:
        print(candidate)
        sys.exit(0)

print("ERROR: no Python with pywinauto found", file=sys.stderr)
sys.exit(1)

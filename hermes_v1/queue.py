"""Durable wake-intent handoff for a future trusted platform relay."""

import json
from dataclasses import asdict
from pathlib import Path

from .loop import WakeRequest


class JsonlWakeQueue:
    """Append scheduled requests without interacting with windows or input."""

    def __init__(self, path: str | Path):
        self._path = Path(path)

    def deliver(self, request: WakeRequest) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(asdict(request), sort_keys=True) + "\n")
            stream.flush()
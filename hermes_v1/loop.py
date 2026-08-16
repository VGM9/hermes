"""Pure scheduling core for the Hermes 1.0 wake loop."""

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class WakeRequest:
    """A wake message emitted by the scheduler, before UI delivery."""

    message: str
    due_at: float
    sequence: int


class WakeTransport(Protocol):
    """Delivery boundary implemented by a platform-specific adapter."""

    def deliver(self, request: WakeRequest) -> None:
        ...


class HermesLoop:
    """Emit at most one wake request per polling tick.

    The scheduler has no knowledge of windows, focus, terminals, or UI input.
    A late poll resets the next deadline instead of emitting a burst of stale
    messages, which keeps recovery from interrupting a human's work.
    """

    def __init__(self, interval_seconds: float, message: str, start_at: float):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        if not message.strip():
            raise ValueError("message must not be empty")
        self.interval_seconds = interval_seconds
        self.message = message
        self._next_due_at = start_at + interval_seconds
        self._sequence = 0

    def tick(self, now: float) -> Optional[WakeRequest]:
        """Return one due request, or ``None`` when the loop is not due."""

        if now < self._next_due_at:
            return None
        self._sequence += 1
        request = WakeRequest(self.message, now, self._sequence)
        self._next_due_at = now + self.interval_seconds
        return request

    def tick_and_deliver(self, now: float, transport: WakeTransport) -> bool:
        """Deliver one due request and report whether delivery was attempted."""

        request = self.tick(now)
        if request is None:
            return False
        transport.deliver(request)
        return True
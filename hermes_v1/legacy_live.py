"""Explicit opt-in adapter for the demonstrated legacy live wake path."""

from collections.abc import Callable

from .delivery import DeliveryRefused
from .loop import WakeRequest


class LegacyLiveTransport:
    """Deliver through legacy window automation only when explicitly selected."""

    def __init__(
        self,
        session_jsonl: str,
        agent_mode: str,
        *,
        resolver: Callable[[str, str], object | None],
        sender: Callable[[object, str], bool],
    ):
        self._session_jsonl = session_jsonl
        self._agent_mode = agent_mode
        self._resolver = resolver
        self._sender = sender

    def deliver(self, request: WakeRequest) -> None:
        target = self._resolver(self._session_jsonl, self._agent_mode)
        if target is None:
            raise DeliveryRefused("legacy live target could not be uniquely resolved")
        if not self._sender(target, request.message):
            raise DeliveryRefused("legacy live sender refused delivery")
"""Safety policy for Hermes 1.0 wake delivery.

This module deliberately contains no Windows UI calls. Platform adapters must
provide identity resolution and an injection primitive that does not activate a
window or use the user's foreground keyboard focus.
"""

from dataclasses import dataclass
from typing import Iterable, Protocol

from .loop import WakeRequest


@dataclass(frozen=True)
class TargetCandidate:
    session_id: str
    window_id: str
    workspace_root: str
    identity_verified: bool
    is_foreground: bool
    human_input_active: bool


class DeliveryRefused(RuntimeError):
    """The adapter refused delivery because the target was not safe."""


class TargetResolver(Protocol):
    def candidates(self, session_id: str) -> Iterable[TargetCandidate]:
        ...


class MessageInjector(Protocol):
    def inject_without_activation(
        self, candidate: TargetCandidate, message: str
    ) -> None:
        ...


def select_target(
    candidates: Iterable[TargetCandidate], session_id: str
) -> TargetCandidate:
    """Select exactly one verified, non-human-owned target."""

    matches = [candidate for candidate in candidates if candidate.session_id == session_id]
    if len(matches) != 1:
        raise DeliveryRefused(
            f"expected exactly one target for {session_id!r}, found {len(matches)}"
        )
    candidate = matches[0]
    if not candidate.identity_verified:
        raise DeliveryRefused("target identity is not verified")
    if candidate.is_foreground:
        raise DeliveryRefused("target is the user's foreground window")
    if candidate.human_input_active:
        raise DeliveryRefused("target has active human input")
    return candidate


class SafeWakeTransport:
    """Deliver only through an adapter that promises no activation or focus use."""

    def __init__(
        self, resolver: TargetResolver, injector: MessageInjector, session_id: str
    ):
        self._resolver = resolver
        self._injector = injector
        self._session_id = session_id

    def deliver(self, request: WakeRequest) -> None:
        candidate = select_target(
            self._resolver.candidates(self._session_id), self._session_id
        )
        self._injector.inject_without_activation(candidate, request.message)
import pytest

from hermes_v1 import DeliveryRefused, SafeWakeTransport, TargetCandidate, WakeRequest


class Resolver:
    def __init__(self, candidates):
        self._candidates = candidates

    def candidates(self, session_id):
        return self._candidates


class Injector:
    def __init__(self):
        self.calls = []

    def inject_without_activation(self, candidate, message):
        self.calls.append((candidate.window_id, message))


def candidate(**overrides):
    values = {
        "session_id": "session-a",
        "window_id": "window-1",
        "workspace_root": "C:/work/project",
        "identity_verified": True,
        "is_foreground": False,
        "human_input_active": False,
    }
    values.update(overrides)
    return TargetCandidate(**values)


def test_transport_delivers_to_one_verified_background_target():
    injector = Injector()
    transport = SafeWakeTransport(Resolver([candidate()]), injector, "session-a")

    transport.deliver(WakeRequest("continue", 10, 1))

    assert injector.calls == [("window-1", "continue")]


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"is_foreground": True}, "target is the user's foreground window"),
        ({"human_input_active": True}, "target has active human input"),
        ({"identity_verified": False}, "target identity is not verified"),
    ],
)
def test_transport_refuses_human_or_unverified_target(overrides, message):
    injector = Injector()
    transport = SafeWakeTransport(
        Resolver([candidate(**overrides)]), injector, "session-a"
    )

    with pytest.raises(DeliveryRefused, match=message):
        transport.deliver(WakeRequest("continue", 10, 1))

    assert injector.calls == []


def test_transport_refuses_ambiguous_session():
    injector = Injector()
    transport = SafeWakeTransport(
        Resolver([candidate(window_id="one"), candidate(window_id="two")]),
        injector,
        "session-a",
    )

    with pytest.raises(DeliveryRefused, match="exactly one"):
        transport.deliver(WakeRequest("continue", 10, 1))

    assert injector.calls == []
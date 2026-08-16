import pytest

from hermes_v1.delivery import DeliveryRefused
from hermes_v1.legacy_live import LegacyLiveTransport
from hermes_v1.loop import WakeRequest


def test_legacy_live_transport_sends_only_after_target_resolution():
    calls = []
    transport = LegacyLiveTransport(
        "session.jsonl",
        "Default Tool Use",
        resolver=lambda path, mode: calls.append((path, mode)) or "window",
        sender=lambda window, message: calls.append((window, message)) or True,
    )

    transport.deliver(WakeRequest("continue", 1, 1))

    assert calls == [
        ("session.jsonl", "Default Tool Use"),
        ("window", "continue"),
    ]


@pytest.mark.parametrize("resolved, sent, message", [(None, True, "could not"), ("window", False, "refused")])
def test_legacy_live_transport_fails_closed(resolved, sent, message):
    transport = LegacyLiveTransport(
        "session.jsonl",
        "Default Tool Use",
        resolver=lambda path, mode: resolved,
        sender=lambda window, text: sent,
    )

    with pytest.raises(DeliveryRefused, match=message):
        transport.deliver(WakeRequest("continue", 1, 1))
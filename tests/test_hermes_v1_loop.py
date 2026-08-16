import pytest

from hermes_v1 import HermesLoop


class RecordingTransport:
    def __init__(self):
        self.requests = []

    def deliver(self, request):
        self.requests.append(request)


def test_loop_emits_one_message_when_interval_is_due():
    loop = HermesLoop(10, "continue the quest", start_at=100)
    transport = RecordingTransport()

    assert loop.tick_and_deliver(109.99, transport) is False
    assert loop.tick_and_deliver(110, transport) is True
    assert loop.tick_and_deliver(111, transport) is False

    assert [(request.message, request.sequence) for request in transport.requests] == [
        ("continue the quest", 1)
    ]


def test_late_poll_does_not_emit_a_burst():
    loop = HermesLoop(10, "one wake", start_at=0)

    assert loop.tick(35).sequence == 1
    assert loop.tick(35.1) is None
    assert loop.tick(45) .sequence == 2


@pytest.mark.parametrize("interval", [0, -1])
def test_interval_must_be_positive(interval):
    with pytest.raises(ValueError, match="interval_seconds"):
        HermesLoop(interval, "wake", start_at=0)


def test_message_must_not_be_blank():
    with pytest.raises(ValueError, match="message"):
        HermesLoop(1, "   ", start_at=0)
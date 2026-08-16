import pytest

from hermes_v1.delivery import DeliveryRefused
from hermes_v1.runner import run_loop


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class RecordingTransport:
    def __init__(self):
        self.requests = []

    def deliver(self, request):
        self.requests.append(request)


def test_runner_delivers_requested_number_of_wakes():
    clock = FakeClock()
    transport = RecordingTransport()

    def advance(seconds):
        clock.advance(seconds)

    assert run_loop(
        10,
        "continue",
        transport,
        clock=clock,
        sleeper=advance,
        max_wakes=2,
    ) == 2

    assert [request.sequence for request in transport.requests] == [1, 2]
    assert [request.message for request in transport.requests] == [
        "continue",
        "continue",
    ]


def test_runner_stops_before_scheduling_when_requested():
    clock = FakeClock()
    transport = RecordingTransport()

    assert run_loop(
        10,
        "continue",
        transport,
        clock=clock,
        sleeper=clock.advance,
        should_stop=lambda: True,
    ) == 0
    assert transport.requests == []


def test_runner_rejects_negative_wake_limit():
    with pytest.raises(ValueError, match="max_wakes"):
        run_loop(10, "continue", RecordingTransport(), max_wakes=-1)


def test_runner_can_retry_refused_delivery():
    clock = FakeClock()
    attempts = []
    transport = RecordingTransport()

    def deliver(request):
        attempts.append(request.sequence)
        if len(attempts) == 1:
            raise DeliveryRefused("busy")
        transport.requests.append(request)

    transport.deliver = deliver

    assert run_loop(
        10,
        "continue",
        transport,
        clock=clock,
        sleeper=clock.advance,
        max_wakes=1,
        on_delivery_refused=lambda error: None,
    ) == 1
    assert attempts == [1, 2]
"""Process runner for the Hermes 1.0 scheduler."""

from collections.abc import Callable
from time import monotonic, sleep

from .delivery import DeliveryRefused
from .loop import HermesLoop, WakeTransport


def run_loop(
    interval_seconds: float,
    message: str,
    transport: WakeTransport,
    *,
    clock: Callable[[], float] = monotonic,
    sleeper: Callable[[float], None] = sleep,
    max_wakes: int | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    on_delivery_refused: Callable[[DeliveryRefused], None] | None = None,
) -> int:
    """Run until stopped or ``max_wakes`` wake requests are delivered."""

    if max_wakes is not None and max_wakes < 0:
        raise ValueError("max_wakes must not be negative")
    start_at = clock()
    loop = HermesLoop(interval_seconds, message, start_at=start_at)
    delivered = 0
    while not should_stop() and (max_wakes is None or delivered < max_wakes):
        now = clock()
        try:
            delivered_this_tick = loop.tick_and_deliver(now, transport)
        except DeliveryRefused as error:
            if on_delivery_refused is None:
                raise
            on_delivery_refused(error)
            delivered_this_tick = False
        if delivered_this_tick:
            delivered += 1
        elapsed = clock() - now
        if not should_stop():
            sleeper(max(0.0, loop.interval_seconds - elapsed))
    return delivered
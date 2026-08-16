import json

from hermes_v1.loop import WakeRequest
from hermes_v1.queue import JsonlWakeQueue


def test_jsonl_queue_persists_wake_intent(tmp_path):
    queue = JsonlWakeQueue(tmp_path / "wake-intents.jsonl")

    queue.deliver(WakeRequest("continue", 12.5, 3))

    assert json.loads((tmp_path / "wake-intents.jsonl").read_text()) == {
        "due_at": 12.5,
        "message": "continue",
        "sequence": 3,
    }
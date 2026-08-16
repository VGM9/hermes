"""Command-line boundary for the Hermes 1.0 wake loop."""

import argparse
import json
import sys
from dataclasses import asdict

from .loop import WakeRequest
from .queue import JsonlWakeQueue
from .runner import run_loop


class DryRunTransport:
    """Print requests without claiming that a real chat wake occurred."""

    def deliver(self, request: WakeRequest) -> None:
        print(json.dumps(asdict(request), sort_keys=True), flush=True)


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermes-v1")
    parser.add_argument("--interval", type=float, required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="emit scheduled requests without delivering to a VS Code chat",
    )
    parser.add_argument(
        "--queue-file",
        help="persist wake intents as JSONL for a trusted relay",
    )
    parser.add_argument(
        "--legacy-live",
        action="store_true",
        help="explicitly use the legacy focus-based live sender",
    )
    parser.add_argument("--session-jsonl")
    parser.add_argument("--agent-mode")
    parser.add_argument("--max-wakes", type=non_negative_int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected_modes = sum(bool(value) for value in (args.dry_run, args.queue_file, args.legacy_live))
    if selected_modes > 1:
        print("select only one delivery mode", file=sys.stderr)
        return 2
    if args.legacy_live and not args.session_jsonl:
        print("--legacy-live requires --session-jsonl", file=sys.stderr)
        return 2
    if args.legacy_live and not args.agent_mode:
        print("--legacy-live requires --agent-mode", file=sys.stderr)
        return 2
    if not selected_modes:
        print(
            "Hermes 1.0 has no proven non-focus platform transport yet; "
            "use --dry-run, --queue-file, or explicit --legacy-live.",
            file=sys.stderr,
        )
        return 2
    if args.dry_run:
        transport = DryRunTransport()
    elif args.queue_file:
        transport = JsonlWakeQueue(args.queue_file)
    else:
        from core.ui_automation.window_detection import find_target_window
        from chat.send import send_message
        from .legacy_live import LegacyLiveTransport

        transport = LegacyLiveTransport(
            args.session_jsonl,
            args.agent_mode,
            resolver=find_target_window,
            sender=send_message,
        )
    try:
        run_loop(
            args.interval,
            args.message,
            transport,
            max_wakes=args.max_wakes,
            on_delivery_refused=(
                (lambda error: print(f"wake skipped: {error}", file=sys.stderr))
                if args.legacy_live
                else None
            ),
        )
    except KeyboardInterrupt:
        print("Hermes 1.0 loop stopped", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
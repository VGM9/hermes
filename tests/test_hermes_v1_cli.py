import pytest

from hermes_v1.cli import main


def test_cli_refuses_unproven_real_delivery(capsys):
    assert main(["--interval", "10", "--message", "continue"]) == 2

    captured = capsys.readouterr()
    assert "no proven non-focus platform transport" in captured.err


def test_cli_refuses_combined_dry_run_and_queue_file(capsys, tmp_path):
    assert main(
        [
            "--interval",
            "10",
            "--message",
            "continue",
            "--dry-run",
            "--queue-file",
            str(tmp_path / "wake.jsonl"),
        ]
    ) == 2
    assert "select only one delivery mode" in capsys.readouterr().err


def test_cli_requires_target_identity_for_legacy_live(capsys):
    assert main(["--interval", "10", "--message", "continue", "--legacy-live"]) == 2
    assert "requires --session-jsonl" in capsys.readouterr().err


def test_cli_rejects_negative_wake_limit():
    with pytest.raises(SystemExit):
        main(["--interval", "10", "--message", "continue", "--max-wakes", "-1"])
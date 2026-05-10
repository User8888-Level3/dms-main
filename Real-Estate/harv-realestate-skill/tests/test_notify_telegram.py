"""Tests for notify_telegram.py.

Note: live SSH+Telegram is exercised in the live integration tests
(Tasks 13-16). These unit tests verify message formatting + env handling.
"""

from unittest.mock import patch

from notify_telegram import format_message, send_via_hermes


def test_format_message_basic():
    msg = format_message(
        address="1234 Main St, Hayward",
        signal="STRONG BUY",
        grade="A-",
        fair_value_low=1200000,
        fair_value_high=1300000,
        marker_short="MLS/RPR (verified)",
        next_command="/harv-realestate email PinkyHayward-Union-City-May2026",
    )
    assert "1234 Main St" in msg
    assert "STRONG BUY" in msg
    assert "A-" in msg
    assert "$1,200,000" in msg or "$1.2M" in msg
    assert "MLS/RPR (verified)" in msg
    assert "/harv-realestate email" in msg


def test_format_message_preliminary():
    msg = format_message(
        address="1234 Main St",
        signal="HOLD",
        grade="C",
        fair_value_low=1000000,
        fair_value_high=1100000,
        marker_short="PRELIMINARY — Web data only",
        next_command="(supply MLS/RPR PDFs to upgrade)",
    )
    assert "PRELIMINARY" in msg


def test_send_via_hermes_calls_ssh():
    with patch("notify_telegram.subprocess.run") as run_mock:
        run_mock.return_value.returncode = 0
        send_via_hermes(message="Test", chat_id="5883909804")
        assert run_mock.called
        called_cmd = run_mock.call_args[0][0]
        assert "ssh" in called_cmd
        assert "n8n" in called_cmd


def test_send_via_hermes_non_fatal_on_failure():
    """A failed Telegram send must NOT raise - analysis output is the priority."""
    with patch("notify_telegram.subprocess.run") as run_mock:
        run_mock.return_value.returncode = 1
        run_mock.return_value.stderr = "ssh: connection refused"
        # Should not raise
        result = send_via_hermes(message="Test", chat_id="5883909804")
        assert result is False  # signals failure but doesn't raise


def test_send_via_hermes_uses_stdin_for_message():
    """Message body is passed via stdin (input= kwarg), not env. Lets curl --data-urlencode 'text@-' read it."""
    with patch("notify_telegram.subprocess.run") as run_mock:
        run_mock.return_value.returncode = 0
        send_via_hermes(message="Hello world", chat_id="5883909804")
        kwargs = run_mock.call_args.kwargs
        assert kwargs.get("input") == "Hello world"
        # env= must NOT be passed — would replace parent env and lose SSH_AUTH_SOCK
        assert "env" not in kwargs


def test_send_via_hermes_remote_cmd_uses_text_at_dash():
    """Remote curl reads message from stdin via 'text@-', not from a $MESSAGE env var."""
    with patch("notify_telegram.subprocess.run") as run_mock:
        run_mock.return_value.returncode = 0
        send_via_hermes(message="Test", chat_id="5883909804")
        cmd = run_mock.call_args.args[0]
        # cmd[0]='ssh', cmd[1]=host, cmd[2]=remote shell command string
        remote = cmd[2]
        assert "text@-" in remote
        assert "$MESSAGE" not in remote


def test_send_via_hermes_rejects_invalid_chat_id():
    """Defense-in-depth: chat_id must be digit-only (with optional leading minus)."""
    with patch("notify_telegram.subprocess.run") as run_mock:
        # Should NOT call subprocess at all — returns False immediately
        result = send_via_hermes(message="Test", chat_id="; rm -rf /")
        assert result is False
        assert not run_mock.called

"""Send a Telegram notification via the Hermes bot on n8n VPS.

Pulls the bot token from ~/.hermes/.env on the VPS at runtime
(via SSH + grep) — token never leaves the VPS. Sends to Harv's
chat ID (5883909804) by default.

Failures are logged via stderr and return False — they do NOT raise.
Analysis output is the priority; a Telegram outage must not block
report generation.
"""

import re
import subprocess
import sys


HARV_CHAT_ID = "5883909804"
SSH_HOST = "n8n"


def format_message(
    address: str,
    signal: str,
    grade: str,
    fair_value_low: int,
    fair_value_high: int,
    marker_short: str,
    next_command: str,
) -> str:
    return (
        f"✅ Realestate analysis complete\n\n"
        f"📍 {address}\n"
        f"Signal: *{signal}*\n"
        f"Grade: *{grade}*\n"
        f"Fair Value: ${fair_value_low:,}–${fair_value_high:,}\n"
        f"Source: {marker_short}\n\n"
        f"Next: `{next_command}`"
    )


def send_via_hermes(message: str, chat_id: str = HARV_CHAT_ID) -> bool:
    """Returns True on success, False on any failure."""
    # Defensive: chat_id is shell-interpolated. Reject anything that's not a numeric Telegram chat ID.
    # Telegram chat IDs are positive (DMs) or negative (groups) integers.
    if not re.fullmatch(r"-?\d+", chat_id):
        print(f"[notify_telegram] FAIL invalid chat_id={chat_id!r}", file=sys.stderr)
        return False
    remote_cmd = (
        "BOT_TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' ~/.hermes/.env | cut -d= -f2-) && "
        f'curl -s "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" '
        f'-d "chat_id={chat_id}" '
        f'-d "parse_mode=Markdown" '
        f'--data-urlencode "text@-"'
    )
    try:
        proc = subprocess.run(
            ["ssh", SSH_HOST, remote_cmd],
            input=message,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode != 0:
            print(f"[notify_telegram] FAIL rc={proc.returncode} stderr={proc.stderr.strip()}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"[notify_telegram] EXCEPTION {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: notify_telegram.py '<message>' [chat_id]", file=sys.stderr)
        sys.exit(2)
    msg = sys.argv[1]
    chat = sys.argv[2] if len(sys.argv) > 2 else HARV_CHAT_ID
    ok = send_via_hermes(msg, chat)
    sys.exit(0 if ok else 1)

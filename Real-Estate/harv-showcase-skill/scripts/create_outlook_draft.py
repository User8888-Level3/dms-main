#!/usr/bin/env python3
"""Create an Outlook draft email via Microsoft Graph API.

Usage:
    python3 create_outlook_draft.py --subject "..." --to-name "..." --to-email "..." --html-file /path/to/body.html

Reads access token from /tmp/ms365-token.json or ~/.claude/ms365-token.json.
Returns the draft message ID on success, exits non-zero on failure.
Works on both Mac and VPS (no MCP dependency).
"""
import argparse
import json
import subprocess
import sys
import os


def find_token():
    for path in ['/tmp/ms365-token.json', os.path.expanduser('~/.claude/ms365-token.json')]:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
                if 'access_token' in data:
                    return data['access_token']
    return None


def create_draft(subject, to_name, to_email, html_body, token):
    payload = json.dumps({
        "subject": subject,
        "body": {"contentType": "HTML", "content": html_body},
        "toRecipients": [{"emailAddress": {"name": to_name, "address": to_email}}]
    })
    result = subprocess.run([
        'curl', '-s', '-w', '\n%{http_code}',
        '-X', 'POST', 'https://graph.microsoft.com/v1.0/me/messages',
        '-H', f'Authorization: Bearer {token}',
        '-H', 'Content-Type: application/json',
        '-d', payload
    ], capture_output=True, text=True)
    lines = result.stdout.strip().rsplit('\n', 1)
    body_text = lines[0] if len(lines) > 1 else ''
    status = lines[-1].strip()
    return status, body_text


def main():
    parser = argparse.ArgumentParser(description='Create Outlook draft via Graph API')
    parser.add_argument('--subject', required=True)
    parser.add_argument('--to-name', required=True)
    parser.add_argument('--to-email', required=True)
    parser.add_argument('--html-file', required=True, help='Path to HTML body file')
    args = parser.parse_args()

    token = find_token()
    if not token:
        print("ERROR: No MS365 access token found. Run token refresh procedure.", file=sys.stderr)
        sys.exit(1)

    with open(args.html_file) as f:
        html_body = f.read()

    status, response = create_draft(args.subject, args.to_name, args.to_email, html_body, token)
    if status == '201':
        data = json.loads(response)
        print(f"Draft created: {data.get('id', 'unknown')[:50]}...")
        print(f"Subject: {data.get('subject')}")
    else:
        print(f"ERROR {status}: {response[:300]}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

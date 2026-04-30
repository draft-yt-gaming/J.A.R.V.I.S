#!/usr/bin/env python3
"""Register J.A.R.V.I.S Discord application commands."""
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
SETTINGS_FILE = BASE_DIR / "jarvis_runtime_settings.json"
COMMAND_NAME = "Resumer avec J.A.R.V.I.S"
API_BASE = "https://discord.com/api/v10"


def load_runtime_value(key):
    env_value = os.getenv(key, "").strip()
    if env_value:
        return env_value
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return str(settings.get(key, "") or "").strip()
    except Exception:
        return ""


def discord_request(method, url, token, **kwargs):
    response = requests.request(
        method,
        url,
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        timeout=20,
        **kwargs,
    )
    if not (200 <= response.status_code < 300):
        raise SystemExit(f"Discord API error {response.status_code}: {response.text}")
    return response.json() if response.text else {}


def main():
    load_dotenv(BASE_DIR / ".env")
    application_id = load_runtime_value("DISCORD_CLIENT_ID")
    bot_token = load_runtime_value("DISCORD_BOT_TOKEN")
    if not application_id or not bot_token:
        raise SystemExit("DISCORD_CLIENT_ID et DISCORD_BOT_TOKEN sont requis dans .env ou le dashboard J.A.R.V.I.S.")

    command_payload = {
        "name": COMMAND_NAME,
        "type": 3,
        "integration_types": [0, 1],
        "contexts": [0, 1, 2],
    }
    commands_url = f"{API_BASE}/applications/{application_id}/commands"
    commands = discord_request("GET", commands_url, bot_token)
    existing = next((cmd for cmd in commands if cmd.get("name") == COMMAND_NAME and cmd.get("type") == 3), None)

    if existing:
        command = discord_request("PATCH", f"{commands_url}/{existing['id']}", bot_token, json=command_payload)
        action = "mise a jour"
    else:
        command = discord_request("POST", commands_url, bot_token, json=command_payload)
        action = "cree"

    print(f"Commande Discord {action}: {command.get('name')} ({command.get('id')})")
    print("Endpoint a configurer dans Discord Developer Portal:")
    print("  https://TON_DOMAINE/api/discord/interactions")
    print("Ensuite: clic droit sur un message -> Applications -> Resumer avec J.A.R.V.I.S.")


if __name__ == "__main__":
    main()

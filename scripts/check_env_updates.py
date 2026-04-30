#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"
RUNTIME_SETTINGS = ROOT / "jarvis_runtime_settings.json"

OPTIONAL_OR_INTERNAL = {"assistant_name"}

KEY_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def read_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = KEY_RE.match(line)
        if match:
            keys.add(match.group(1))
    return keys


def read_runtime_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if not isinstance(data, dict):
        return set()
    return {str(key) for key, value in data.items() if value not in (None, "")}


def main() -> int:
    selected_keys = {key.strip() for key in os.getenv("JARVIS_ENV_KEYS_TO_CHECK", "").splitlines() if key.strip()}
    example_keys = read_env_keys(ENV_EXAMPLE) - OPTIONAL_OR_INTERNAL
    if selected_keys:
        example_keys &= selected_keys
    if not example_keys:
        return 0

    configured_keys = read_env_keys(ENV_FILE) | read_runtime_keys(RUNTIME_SETTINGS)
    missing = sorted(example_keys - configured_keys)
    if not missing:
        print("[config] Toutes les cles connues de .env.example sont deja presentes dans .env ou le dashboard.")
        return 0

    print("[config] Nouvelles cles possibles a verifier :")
    for key in missing:
        print(f"  - {key}")
    print("[config] Ajoute seulement celles dont tu as besoin dans .env ou dans le dashboard Jarvis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

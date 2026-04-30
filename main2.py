# from ursina import *  # DESACTIVE — interface web Three.js
import threading
import asyncio
import google.genai as genai
from google.genai import types
import speech_recognition as sr
import edge_tts
import pygame
import os
from dotenv import load_dotenv
import random
import math
import webbrowser
import subprocess
import requests
import time
import pickle
import json
import re
import html
import shutil
import sys
import unicodedata
import ipaddress
from pathlib import Path
from datetime import datetime
from collections import deque
import pyaudio
import websockets
import json
from PIL import Image
from openai import OpenAI
import uuid
import base64
import io
import urllib3
import secrets
from functools import wraps
from contextvars import ContextVar
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import Flask, Response, jsonify, redirect, request as flask_request, send_from_directory, session
from werkzeug.middleware.proxy_fix import ProxyFix
try:
    import cv2
except ImportError:
    cv2 = None

try:
    from blagues_api import BlaguesAPI
except ImportError:
    BlaguesAPI = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
except ImportError:
    VerifyKey = None
    BadSignatureError = Exception

# Linux — ctypes/windll non disponible
import signal as _signal
user32 = None

# Google APIs
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Chargement des variables d'environnement
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
JARVIS_TTS_VOICE = "fr-FR-HenriNeural"
SETTINGS_FILE = BASE_DIR / "jarvis_runtime_settings.json"
GENERATED_IMAGES_DIR = BASE_DIR / "generated_images"
DEBUG_LOG_BUFFER = deque(maxlen=600)
DEBUG_LOG_LOCK = threading.Lock()
COMMAND_CONTEXT = ContextVar("jarvis_command_context", default={"user": None, "owner": False})
WS_AUTH_SALT = "jarvis-ws-auth"
SERVICE_HEALTH_CACHE = {"timestamp": 0.0, "data": {}}
SERVICE_HEALTH_TTL = 30.0
HTTP_CLIENT_EVENTS = {}
HTTP_CLIENT_EVENTS_LOCK = threading.Lock()
COMMAND_HTTP_CLIENT_ID = ContextVar("jarvis_http_client_id", default="")
DISCORD_SUMMARY_CACHE = {}
DISCORD_SUMMARY_CACHE_LOCK = threading.Lock()
DISCORD_SUMMARY_CACHE_TTL = 15 * 60


class DebugTeeStream:
    def __init__(self, stream):
        self.stream = stream
        self._pending = ""

    def write(self, data):
        text = str(data)
        self.stream.write(text)
        self.stream.flush()

        self._pending += text
        lines = self._pending.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            self._pending = lines.pop()
        else:
            self._pending = ""

        now = datetime.now().strftime("%H:%M:%S")
        with DEBUG_LOG_LOCK:
            for line in lines:
                clean = line.rstrip("\r\n")
                if clean:
                    DEBUG_LOG_BUFFER.append(f"{now} {clean}")
        return len(text)

    def flush(self):
        self.stream.flush()

    def isatty(self):
        return getattr(self.stream, "isatty", lambda: False)()


def get_debug_log_snapshot(limit=200):
    with DEBUG_LOG_LOCK:
        return list(DEBUG_LOG_BUFFER)[-limit:]

GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


sys.stdout = DebugTeeStream(sys.stdout)
sys.stderr = DebugTeeStream(sys.stderr)

def env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")

def env_value_is_configured(value):
    if value is None:
        return False
    value = value.strip()
    if not value:
        return False
    placeholders = {
        "VOTRE_CLE",
        "VOTRE_CLE_API",
        "VOTRE_CLE_ICI",
        "VOTRE_TOKEN",
        "VOTRE_TOKEN_ICI",
        "http://192.168.1.XX:8123",
        "https://192.168.1.XX:8006",
        "https://192.168.2.XX:8006",
    }
    return value not in placeholders and "XX" not in value

def _normalize_setting_value(value):
    if isinstance(value, str):
        return value.strip()
    return value

DEFAULT_SETTINGS = {
    "assistant_name": "J.A.R.V.I.S",
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
    "BLAGUES_API_TOKEN": os.getenv("BLAGUES_API_TOKEN", ""),
    "YOUTUBE_API_KEY": os.getenv("YOUTUBE_API_KEY", ""),
    "XAI_API_KEY": os.getenv("XAI_API_KEY", ""),
    "HA_URL": os.getenv("HA_URL", ""),
    "HA_TOKEN": os.getenv("HA_TOKEN", ""),
    "HA_WEATHER_ENTITY": os.getenv("HA_WEATHER_ENTITY", ""),
    "HOME_LOCATION_NAME": os.getenv("HOME_LOCATION_NAME", ""),
    "SERPAPI_API_KEY": os.getenv("SERPAPI_API_KEY", ""),
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
    "NASA_API_KEY": os.getenv("NASA_API_KEY", ""),
    "OLLAMA_ENABLED": os.getenv("OLLAMA_ENABLED", "false"),
    "OLLAMA_PREFER_LOCAL": os.getenv("OLLAMA_PREFER_LOCAL", "false"),
    "OLLAMA_URL": os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
    "OLLAMA_MODELS": os.getenv("OLLAMA_MODELS", "llama3.1:8b,llama3:8b,mistral:instruct,mistral"),
    "EMBY_URL": os.getenv("EMBY_URL", ""),
    "EMBY_API_KEY": os.getenv("EMBY_API_KEY", ""),
    "EMBY_USER_ID": os.getenv("EMBY_USER_ID", ""),
    "EMBY_USERNAME": os.getenv("EMBY_USERNAME", ""),
    "PROXMOX_URL": os.getenv("PROXMOX_URL", ""),
    "PROXMOX_TOKEN_ID": os.getenv("PROXMOX_TOKEN_ID", ""),
    "PROXMOX_TOKEN_SECRET": os.getenv("PROXMOX_TOKEN_SECRET", ""),
    "PROXMOX_VERIFY_SSL": os.getenv("PROXMOX_VERIFY_SSL", "false"),
    "DISCORD_OWNER_ID": os.getenv("DISCORD_OWNER_ID", ""),
    "DISCORD_CLIENT_ID": os.getenv("DISCORD_CLIENT_ID", ""),
    "DISCORD_CLIENT_SECRET": os.getenv("DISCORD_CLIENT_SECRET", ""),
    "DISCORD_REDIRECT_URI": os.getenv("DISCORD_REDIRECT_URI", ""),
    "DISCORD_PUBLIC_KEY": os.getenv("DISCORD_PUBLIC_KEY", ""),
    "DISCORD_BOT_TOKEN": os.getenv("DISCORD_BOT_TOKEN", ""),
    "JARVIS_SESSION_SECRET": os.getenv("JARVIS_SESSION_SECRET", ""),
    "EXTENSION_ACCESS_TOKEN": os.getenv("EXTENSION_ACCESS_TOKEN", ""),
}

SETTINGS_FIELDS = list(DEFAULT_SETTINGS.keys())
SENSITIVE_SETTINGS = {
    "GEMINI_API_KEY",
    "BLAGUES_API_TOKEN",
    "YOUTUBE_API_KEY",
    "XAI_API_KEY",
    "HA_TOKEN",
    "SERPAPI_API_KEY",
    "GROQ_API_KEY",
    "NASA_API_KEY",
    "EMBY_API_KEY",
    "PROXMOX_TOKEN_SECRET",
    "DISCORD_CLIENT_SECRET",
    "DISCORD_PUBLIC_KEY",
    "DISCORD_BOT_TOKEN",
    "JARVIS_SESSION_SECRET",
    "EXTENSION_ACCESS_TOKEN",
}

def load_runtime_settings():
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key in SETTINGS_FIELDS:
                    if key in data:
                        settings[key] = _normalize_setting_value(data[key])
        except Exception as e:
            print(f"[SETTINGS] Impossible de lire {SETTINGS_FILE.name} : {e}")
    return settings

RUNTIME_SETTINGS = load_runtime_settings()

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()
SERVER_HOST = os.getenv("JARVIS_BIND_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("JARVIS_WS_PORT", "8765"))
HTTP_PORT = int(os.getenv("JARVIS_HTTP_PORT", "8080"))
HTTPS_PORT = int(os.getenv("JARVIS_HTTPS_PORT", "0") or "0")
JARVIS_HEADLESS = env_flag("JARVIS_HEADLESS", False)
GEMINI_API_KEY = ""
GEMINI_API_KEYS = []
GEMINI_MODEL_KEY_BLOCKED_UNTIL = {}
BLAGUES_API_TOKEN = ""
YOUTUBE_API_KEY = ""
XAI_API_KEY = ""
HA_URL = ""
HA_TOKEN = ""
HA_WEATHER_ENTITY = ""
HOME_LOCATION_NAME = ""
SERPAPI_API_KEY = ""
GROQ_API_KEY = ""
NASA_API_KEY = ""
OLLAMA_ENABLED = False
OLLAMA_PREFER_LOCAL = False
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODELS = []
EMBY_URL = ""
EMBY_API_KEY = ""
EMBY_USER_ID = ""
EMBY_USERNAME = ""
PROXMOX_URL = ""
PROXMOX_TOKEN_ID = ""
PROXMOX_TOKEN_SECRET = ""
DISCORD_OWNER_ID = ""
DISCORD_CLIENT_ID = ""
DISCORD_CLIENT_SECRET = ""
DISCORD_REDIRECT_URI = ""
DISCORD_PUBLIC_KEY = ""
DISCORD_BOT_TOKEN = ""
ASSISTANT_NAME = "J.A.R.V.I.S"
JARVIS_SESSION_SECRET = ""
EXTENSION_ACCESS_TOKEN = ""
PROXMOX_VERIFY_SSL = False
GEMINI_CONFIGURED = False
BLAGUES_CONFIGURED = False
YOUTUBE_CONFIGURED = False
XAI_CONFIGURED = False
HA_CONFIGURED = False
SERPAPI_CONFIGURED = False
GROQ_CONFIGURED = False
NASA_CONFIGURED = False
OLLAMA_CONFIGURED = False
EMBY_CONFIGURED = False
PROXMOX_CONFIGURED = False
DISCORD_CONFIGURED = False
client = None
GEMINI_CLIENTS = []
blagues_client = None
grok_client = None
groq_client = None
app = None

def refresh_runtime_config():
    global ASSISTANT_NAME, GEMINI_API_KEY, GEMINI_API_KEYS, GEMINI_MODEL_KEY_BLOCKED_UNTIL, BLAGUES_API_TOKEN, YOUTUBE_API_KEY, XAI_API_KEY
    global HA_URL, HA_TOKEN, HA_WEATHER_ENTITY, HOME_LOCATION_NAME, SERPAPI_API_KEY, GROQ_API_KEY, NASA_API_KEY
    global OLLAMA_ENABLED, OLLAMA_PREFER_LOCAL, OLLAMA_URL, OLLAMA_MODELS
    global EMBY_URL, EMBY_API_KEY, EMBY_USER_ID, EMBY_USERNAME
    global PROXMOX_URL, PROXMOX_TOKEN_ID, PROXMOX_TOKEN_SECRET, PROXMOX_VERIFY_SSL
    global DISCORD_OWNER_ID, DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI, DISCORD_PUBLIC_KEY, DISCORD_BOT_TOKEN
    global JARVIS_SESSION_SECRET, EXTENSION_ACCESS_TOKEN
    global GEMINI_CONFIGURED, BLAGUES_CONFIGURED, YOUTUBE_CONFIGURED, XAI_CONFIGURED, HA_CONFIGURED
    global SERPAPI_CONFIGURED, GROQ_CONFIGURED, NASA_CONFIGURED, OLLAMA_CONFIGURED, EMBY_CONFIGURED, PROXMOX_CONFIGURED, DISCORD_CONFIGURED
    global client, GEMINI_CLIENTS, blagues_client, grok_client, groq_client, HA_HEADERS

    settings = RUNTIME_SETTINGS
    ASSISTANT_NAME = settings.get("assistant_name", "J.A.R.V.I.S") or "J.A.R.V.I.S"
    GEMINI_API_KEY = str(settings.get("GEMINI_API_KEY", "")).strip()
    BLAGUES_API_TOKEN = settings.get("BLAGUES_API_TOKEN", "")
    YOUTUBE_API_KEY = settings.get("YOUTUBE_API_KEY", "")
    XAI_API_KEY = settings.get("XAI_API_KEY", "")
    HA_URL = settings.get("HA_URL", "")
    HA_TOKEN = settings.get("HA_TOKEN", "")
    HA_WEATHER_ENTITY = settings.get("HA_WEATHER_ENTITY", "")
    HOME_LOCATION_NAME = settings.get("HOME_LOCATION_NAME", "")
    SERPAPI_API_KEY = settings.get("SERPAPI_API_KEY", "")
    GROQ_API_KEY = settings.get("GROQ_API_KEY", "")
    NASA_API_KEY = settings.get("NASA_API_KEY", "")
    OLLAMA_ENABLED = str(settings.get("OLLAMA_ENABLED", "false")).strip().lower() in ("1", "true", "yes", "on")
    OLLAMA_PREFER_LOCAL = str(settings.get("OLLAMA_PREFER_LOCAL", "false")).strip().lower() in ("1", "true", "yes", "on")
    OLLAMA_URL = str(settings.get("OLLAMA_URL", "http://127.0.0.1:11434")).strip().rstrip("/") or "http://127.0.0.1:11434"
    OLLAMA_MODELS = [model.strip() for model in re.split(r"[\n,;]+", str(settings.get("OLLAMA_MODELS", ""))) if model.strip()]
    EMBY_URL = str(settings.get("EMBY_URL", "")).strip()
    EMBY_API_KEY = str(settings.get("EMBY_API_KEY", "")).strip()
    EMBY_USER_ID = str(settings.get("EMBY_USER_ID", "")).strip()
    EMBY_USERNAME = str(settings.get("EMBY_USERNAME", "")).strip()
    PROXMOX_URL = settings.get("PROXMOX_URL", "")
    PROXMOX_TOKEN_ID = settings.get("PROXMOX_TOKEN_ID", "")
    PROXMOX_TOKEN_SECRET = settings.get("PROXMOX_TOKEN_SECRET", "")
    PROXMOX_VERIFY_SSL = str(settings.get("PROXMOX_VERIFY_SSL", "false")).strip().lower() in ("1", "true", "yes", "on")
    DISCORD_OWNER_ID = str(settings.get("DISCORD_OWNER_ID", "")).strip()
    DISCORD_CLIENT_ID = str(settings.get("DISCORD_CLIENT_ID", "")).strip()
    DISCORD_CLIENT_SECRET = str(settings.get("DISCORD_CLIENT_SECRET", "")).strip()
    DISCORD_REDIRECT_URI = str(settings.get("DISCORD_REDIRECT_URI", "")).strip()
    DISCORD_PUBLIC_KEY = str(settings.get("DISCORD_PUBLIC_KEY", "")).strip()
    DISCORD_BOT_TOKEN = str(settings.get("DISCORD_BOT_TOKEN", "")).strip()
    JARVIS_SESSION_SECRET = str(settings.get("JARVIS_SESSION_SECRET", "")).strip()
    EXTENSION_ACCESS_TOKEN = str(settings.get("EXTENSION_ACCESS_TOKEN", "")).strip()

    if not PROXMOX_VERIFY_SSL:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    GEMINI_API_KEYS = [key for key in re.split(r"[\n,;]+", GEMINI_API_KEY) if env_value_is_configured(key.strip()) for key in [key.strip()]]
    GEMINI_CONFIGURED = bool(GEMINI_API_KEYS)
    BLAGUES_CONFIGURED = env_value_is_configured(BLAGUES_API_TOKEN)
    YOUTUBE_CONFIGURED = env_value_is_configured(YOUTUBE_API_KEY)
    XAI_CONFIGURED = env_value_is_configured(XAI_API_KEY)
    HA_CONFIGURED = env_value_is_configured(HA_URL) and env_value_is_configured(HA_TOKEN)
    SERPAPI_CONFIGURED = env_value_is_configured(SERPAPI_API_KEY)
    GROQ_CONFIGURED = env_value_is_configured(GROQ_API_KEY)
    NASA_CONFIGURED = env_value_is_configured(NASA_API_KEY)
    OLLAMA_CONFIGURED = OLLAMA_ENABLED and env_value_is_configured(OLLAMA_URL) and bool(OLLAMA_MODELS)
    EMBY_CONFIGURED = env_value_is_configured(EMBY_URL) and env_value_is_configured(EMBY_API_KEY)
    PROXMOX_CONFIGURED = all(
        env_value_is_configured(v)
        for v in (PROXMOX_URL, PROXMOX_TOKEN_ID, PROXMOX_TOKEN_SECRET)
    )
    DISCORD_CONFIGURED = all(
        env_value_is_configured(v)
        for v in (DISCORD_OWNER_ID, DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET)
    )

    GEMINI_CLIENTS = [(key, genai.Client(api_key=key)) for key in GEMINI_API_KEYS] if GEMINI_CONFIGURED else []
    GEMINI_MODEL_KEY_BLOCKED_UNTIL = {
        blocked_key: blocked_until
        for blocked_key, blocked_until in GEMINI_MODEL_KEY_BLOCKED_UNTIL.items()
        if blocked_key[0] in GEMINI_API_KEYS
    }
    client = GEMINI_CLIENTS[0][1] if GEMINI_CLIENTS else None
    blagues_client = BlaguesAPI(BLAGUES_API_TOKEN) if (BLAGUES_CONFIGURED and BlaguesAPI) else None
    grok_client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1") if XAI_CONFIGURED else None
    groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_CONFIGURED else None

    HA_HEADERS = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }

def save_runtime_settings(updated_settings):
    global RUNTIME_SETTINGS
    settings = dict(RUNTIME_SETTINGS)
    for key, value in updated_settings.items():
        if key in SETTINGS_FIELDS:
            settings[key] = _normalize_setting_value(value)
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    RUNTIME_SETTINGS = settings
    refresh_runtime_config()
    return settings

refresh_runtime_config()

def get_service_config_flags():
    return {
        "gemini": GEMINI_CONFIGURED,
        "blagues": BLAGUES_CONFIGURED,
        "youtube": YOUTUBE_CONFIGURED,
        "xai": XAI_CONFIGURED,
        "home_assistant": HA_CONFIGURED,
        "serpapi": SERPAPI_CONFIGURED,
        "groq": GROQ_CONFIGURED,
        "nasa": True,
        "ollama": OLLAMA_CONFIGURED,
        "emby": EMBY_CONFIGURED,
        "proxmox": PROXMOX_CONFIGURED,
        "discord": DISCORD_CONFIGURED,
        "discord_interactions": env_value_is_configured(DISCORD_CLIENT_ID) and env_value_is_configured(DISCORD_PUBLIC_KEY),
    }


def _status_payload(state, detail=""):
    return {"state": state, "detail": detail}


def _service_ok(response):
    return 200 <= response.status_code < 300


def _test_gemini_status():
    if not GEMINI_CONFIGURED:
        return _status_payload("missing")
    last_detail = ""
    for key in GEMINI_API_KEYS:
        try:
            r = requests.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": key, "pageSize": 1},
                timeout=4,
            )
            if _service_ok(r):
                return _status_payload("ok", f"HTTP {r.status_code} via {mask_secret(key)}")
            last_detail = f"HTTP {r.status_code} via {mask_secret(key)}"
        except Exception as e:
            last_detail = f"{e} via {mask_secret(key)}"
    return _status_payload("error", last_detail)


def _test_youtube_status():
    if not YOUTUBE_CONFIGURED:
        return _status_payload("missing")
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": "jarvis", "type": "video", "maxResults": 1, "key": YOUTUBE_API_KEY},
            timeout=4,
        )
        return _status_payload("ok" if _service_ok(r) else "error", f"HTTP {r.status_code}")
    except Exception as e:
        return _status_payload("error", str(e))


def _test_xai_status():
    if not XAI_CONFIGURED:
        return _status_payload("missing")
    try:
        r = requests.get(
            "https://api.x.ai/v1/models",
            headers={"Authorization": f"Bearer {XAI_API_KEY}"},
            timeout=4,
        )
        return _status_payload("ok" if _service_ok(r) else "error", f"HTTP {r.status_code}")
    except Exception as e:
        return _status_payload("error", str(e))


def _test_serpapi_status():
    if not SERPAPI_CONFIGURED:
        return _status_payload("missing")
    try:
        r = requests.get(
            "https://serpapi.com/account.json",
            params={"api_key": SERPAPI_API_KEY},
            timeout=4,
        )
        return _status_payload("ok" if _service_ok(r) else "error", f"HTTP {r.status_code}")
    except Exception as e:
        return _status_payload("error", str(e))


def _test_groq_status():
    if not GROQ_CONFIGURED:
        return _status_payload("missing")
    try:
        r = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            timeout=4,
        )
        return _status_payload("ok" if _service_ok(r) else "error", f"HTTP {r.status_code}")
    except Exception as e:
        return _status_payload("error", str(e))


def _test_home_assistant_status():
    if not HA_CONFIGURED:
        return _status_payload("missing")
    try:
        r = requests.get(
            f"{HA_URL.rstrip('/')}/api/",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
            timeout=4,
        )
        return _status_payload("ok" if _service_ok(r) else "error", f"HTTP {r.status_code}")
    except Exception as e:
        return _status_payload("error", str(e))


def _test_emby_status():
    if not EMBY_CONFIGURED:
        return _status_payload("missing")
    try:
        user_id = emby_resolve_user_id()
        if not user_id:
            return _status_payload("error", "Utilisateur Emby introuvable")
        r = requests.get(
            f"{EMBY_URL.rstrip('/')}/emby/Users/{user_id}",
            params={"api_key": EMBY_API_KEY},
            timeout=4,
        )
        return _status_payload("ok" if _service_ok(r) else "error", f"HTTP {r.status_code}")
    except Exception as e:
        return _status_payload("error", str(e))


def _test_proxmox_status():
    if not PROXMOX_CONFIGURED:
        return _status_payload("missing")
    try:
        r = requests.get(
            f"{PROXMOX_URL.rstrip('/')}/api2/json/version",
            headers={
                "Authorization": f"PVEAPIToken={PROXMOX_TOKEN_ID}={PROXMOX_TOKEN_SECRET}",
                "Accept": "application/json",
            },
            timeout=4,
            verify=PROXMOX_VERIFY_SSL,
        )
        return _status_payload("ok" if _service_ok(r) else "error", f"HTTP {r.status_code}")
    except Exception as e:
        return _status_payload("error", str(e))



def _test_nasa_status():
    try:
        r = requests.get(
            "https://api.nasa.gov/planetary/apod",
            params={"api_key": NASA_API_KEY if NASA_CONFIGURED else "DEMO_KEY"},
            timeout=4,
        )
        detail = f"HTTP {r.status_code}" + (f" via {mask_secret(NASA_API_KEY)}" if NASA_CONFIGURED else " via DEMO_KEY")
        return _status_payload("ok" if _service_ok(r) else "error", detail)
    except Exception as e:
        return _status_payload("error", str(e))

def _test_ollama_status():
    if not OLLAMA_ENABLED:
        return _status_payload("missing", "desactive")
    if not OLLAMA_CONFIGURED:
        return _status_payload("missing", "URL ou modele manquant")
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=4)
        if not _service_ok(r):
            return _status_payload("error", f"HTTP {r.status_code}")
        models = [item.get("name", "") for item in (r.json().get("models") or [])]
        configured = set(OLLAMA_MODELS)
        available = [model for model in models if model in configured]
        if available:
            return _status_payload("ok", f"{OLLAMA_URL} : {', '.join(available[:3])}")
        detail = "aucun modele configure trouve" if models else "aucun modele installe"
        return _status_payload("error", detail)
    except Exception as e:
        return _status_payload("error", str(e))


def _test_discord_status():
    if not DISCORD_CONFIGURED:
        return _status_payload("missing")
    try:
        r = requests.get("https://discord.com/api/v10/applications/@me", timeout=4)
        return _status_payload("ok" if r.status_code in (401, 403) else ("error" if r.status_code >= 500 else "ok"), f"HTTP {r.status_code}")
    except Exception as e:
        return _status_payload("error", str(e))


def get_service_health_flags(force_refresh=False):
    now = time.time()
    cached = SERVICE_HEALTH_CACHE.get("data") or {}
    if not force_refresh and cached and now - SERVICE_HEALTH_CACHE.get("timestamp", 0.0) < SERVICE_HEALTH_TTL:
        return cached

    statuses = {
        "gemini": _test_gemini_status(),
        "youtube": _test_youtube_status(),
        "xai": _test_xai_status(),
        "home_assistant": _test_home_assistant_status(),
        "serpapi": _test_serpapi_status(),
        "groq": _test_groq_status(),
        "nasa": _test_nasa_status(),
        "ollama": _test_ollama_status(),
        "emby": _test_emby_status(),
        "proxmox": _test_proxmox_status(),
        "discord": _test_discord_status(),
    }
    SERVICE_HEALTH_CACHE["timestamp"] = now
    SERVICE_HEALTH_CACHE["data"] = statuses
    return statuses

def get_public_runtime_settings():
    return {
        "assistant_name": ASSISTANT_NAME,
        "discord_owner_id": DISCORD_OWNER_ID,
        "config_flags": get_service_config_flags(),
        "service_health": get_service_health_flags(),
    }

def get_private_runtime_settings():
    return {
        "assistant_name": ASSISTANT_NAME,
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "BLAGUES_API_TOKEN": BLAGUES_API_TOKEN,
        "YOUTUBE_API_KEY": YOUTUBE_API_KEY,
        "XAI_API_KEY": XAI_API_KEY,
        "HA_URL": HA_URL,
        "HA_TOKEN": HA_TOKEN,
        "HA_WEATHER_ENTITY": HA_WEATHER_ENTITY,
        "HOME_LOCATION_NAME": HOME_LOCATION_NAME,
        "SERPAPI_API_KEY": SERPAPI_API_KEY,
        "GROQ_API_KEY": GROQ_API_KEY,
        "NASA_API_KEY": NASA_API_KEY,
        "OLLAMA_ENABLED": OLLAMA_ENABLED,
        "OLLAMA_PREFER_LOCAL": OLLAMA_PREFER_LOCAL,
        "OLLAMA_URL": OLLAMA_URL,
        "OLLAMA_MODELS": ",".join(OLLAMA_MODELS),
        "EMBY_URL": EMBY_URL,
        "EMBY_API_KEY": EMBY_API_KEY,
        "EMBY_USER_ID": EMBY_USER_ID,
        "EMBY_USERNAME": EMBY_USERNAME,
        "PROXMOX_URL": PROXMOX_URL,
        "PROXMOX_TOKEN_ID": PROXMOX_TOKEN_ID,
        "PROXMOX_TOKEN_SECRET": PROXMOX_TOKEN_SECRET,
        "PROXMOX_VERIFY_SSL": PROXMOX_VERIFY_SSL,
        "DISCORD_OWNER_ID": DISCORD_OWNER_ID,
        "DISCORD_CLIENT_ID": DISCORD_CLIENT_ID,
        "DISCORD_CLIENT_SECRET": DISCORD_CLIENT_SECRET,
        "DISCORD_REDIRECT_URI": DISCORD_REDIRECT_URI,
        "DISCORD_PUBLIC_KEY": DISCORD_PUBLIC_KEY,
        "DISCORD_BOT_TOKEN": DISCORD_BOT_TOKEN,
        "JARVIS_SESSION_SECRET": JARVIS_SESSION_SECRET,
        "EXTENSION_ACCESS_TOKEN": EXTENSION_ACCESS_TOKEN,
    }

def _request_effective_scheme():
    forwarded_proto = str(flask_request.headers.get("X-Forwarded-Proto", "")).split(",")[0].strip()
    return forwarded_proto or flask_request.scheme or "http"


def _request_effective_host():
    forwarded_host = str(flask_request.headers.get("X-Forwarded-Host", "")).split(",")[0].strip()
    if forwarded_host:
        return forwarded_host
    return flask_request.host


def _host_looks_public(hostname):
    host = str(hostname or "").split(":")[0].strip().lower()
    if not host:
        return False
    if host in ("localhost", "127.0.0.1", "::1"):
        return False
    if host.startswith("192.168."):
        return False
    if host.startswith("10."):
        return False
    if re.match(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", host):
        return False
    return True


def discord_redirect_uri_for_request():
    scheme = _request_effective_scheme()
    host = _request_effective_host()
    request_based_uri = f"{scheme}://{host}/auth/discord/callback"

    if _host_looks_public(host):
        return request_based_uri
    if env_value_is_configured(DISCORD_REDIRECT_URI):
        return DISCORD_REDIRECT_URI
    return request_based_uri


def request_from_private_network():
    forwarded_for = str(flask_request.headers.get("X-Forwarded-For", "")).split(",")[0].strip()
    remote_ip = forwarded_for or flask_request.remote_addr or ""
    try:
        ip = ipaddress.ip_address(remote_ip)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback

def is_owner_authenticated():
    user = session.get("discord_user")
    return bool(user and str(user.get("id")) == DISCORD_OWNER_ID)

def owner_auth_required():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_owner_authenticated():
                return jsonify({"error": "unauthorized"}), 401
            return func(*args, **kwargs)
        return wrapper
    return decorator


def extension_request_authorized():
    if request_from_private_network() or is_owner_authenticated():
        return True
    configured_token = str(EXTENSION_ACCESS_TOKEN or "").strip()
    provided_token = str(flask_request.headers.get("X-Jarvis-Extension-Token", "")).strip()
    return bool(configured_token and provided_token and secrets.compare_digest(configured_token, provided_token))


def verify_discord_interaction_signature(raw_body):
    if VerifyKey is None:
        print("[DISCORD] PyNaCl manquant : pip install PyNaCl")
        return False
    public_key = str(DISCORD_PUBLIC_KEY or "").strip()
    signature = str(flask_request.headers.get("X-Signature-Ed25519", "")).strip()
    timestamp = str(flask_request.headers.get("X-Signature-Timestamp", "")).strip()
    if not public_key or not signature or not timestamp:
        return False
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        verify_key.verify(timestamp.encode("utf-8") + raw_body, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError, TypeError) as e:
        print(f"[DISCORD] Signature interaction invalide : {e}")
        return False


def _discord_user_display_name(user):
    if not isinstance(user, dict):
        return "Utilisateur inconnu"
    return (
        str(user.get("global_name") or "").strip()
        or str(user.get("username") or "").strip()
        or str(user.get("id") or "Utilisateur inconnu").strip()
    )


def extract_discord_target_message(payload):
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    resolved = data.get("resolved", {}) if isinstance(data, dict) else {}
    messages = resolved.get("messages", {}) if isinstance(resolved, dict) else {}
    target_id = str(data.get("target_id") or "").strip()
    message = messages.get(target_id) or (next(iter(messages.values()), {}) if isinstance(messages, dict) else {})
    if not isinstance(message, dict):
        message = {}

    message_id = str(message.get("id") or target_id or "").strip()
    channel_id = str(message.get("channel_id") or payload.get("channel_id") or "").strip()
    guild_id = str(payload.get("guild_id") or "").strip()
    author = _discord_user_display_name(message.get("author", {}))
    content = str(message.get("content") or "").strip()

    attachments = message.get("attachments") or []
    if isinstance(attachments, list) and attachments:
        names = []
        for attachment in attachments[:5]:
            if isinstance(attachment, dict):
                name = str(attachment.get("filename") or attachment.get("url") or "piece jointe").strip()
                if name:
                    names.append(name)
        if names:
            content = (content + "\n\nPieces jointes: " + ", ".join(names)).strip()

    jump_url = ""
    if channel_id and message_id:
        jump_url = f"https://discord.com/channels/{guild_id or '@me'}/{channel_id}/{message_id}"

    return {
        "message_id": message_id,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "author": author,
        "content": content,
        "jump_url": jump_url,
    }


def trim_discord_content(content, limit=1900):
    safe_content = str(content or "").strip()
    if len(safe_content) > limit:
        return safe_content[: max(0, limit - 3)].rstrip() + "..."
    return safe_content


def cache_discord_summary(summary, audio_bytes=None):
    summary_id = secrets.token_urlsafe(12)
    now = time.time()
    with DISCORD_SUMMARY_CACHE_LOCK:
        expired = [key for key, value in DISCORD_SUMMARY_CACHE.items() if now - value.get("created_at", 0) > DISCORD_SUMMARY_CACHE_TTL]
        for key in expired:
            DISCORD_SUMMARY_CACHE.pop(key, None)
        DISCORD_SUMMARY_CACHE[summary_id] = {
            "summary": str(summary or ""),
            "audio_bytes": audio_bytes or b"",
            "created_at": now,
        }
    return summary_id


def get_cached_discord_summary(summary_id):
    now = time.time()
    with DISCORD_SUMMARY_CACHE_LOCK:
        cached = DISCORD_SUMMARY_CACHE.get(str(summary_id or ""))
        if not cached:
            return None
        if now - cached.get("created_at", 0) > DISCORD_SUMMARY_CACHE_TTL:
            DISCORD_SUMMARY_CACHE.pop(str(summary_id or ""), None)
            return None
        return dict(cached)


def build_discord_show_button(summary_id):
    return [{
        "type": 1,
        "components": [{
            "type": 2,
            "style": 1,
            "label": "Montrer",
            "custom_id": f"jarvis_show_summary:{summary_id}",
        }],
    }]


async def generate_discord_summary_mp3(summary):
    text_to_speak = str(summary or "").strip()
    if not text_to_speak:
        return None
    text_to_speak = text_to_speak[:4000]
    text_to_speak = re.sub(r"[*#`_>\[\]()]", "", text_to_speak).strip()
    if not text_to_speak:
        return None
    output_file = BASE_DIR / f"discord_summary_{int(time.time() * 1000)}_{secrets.token_hex(4)}.mp3"
    communicate = edge_tts.Communicate(text_to_speak, voice=JARVIS_TTS_VOICE)
    await communicate.save(str(output_file))
    return output_file


def post_discord_followup(application_id, interaction_token, content, summary_id="", audio_path=None, audio_bytes=None, flags=64):
    app_id = str(application_id or DISCORD_CLIENT_ID or "").strip()
    token = str(interaction_token or "").strip()
    if not app_id or not token:
        print("[DISCORD] Followup impossible : application_id ou token manquant")
        return False
    safe_content = trim_discord_content(content or "Je n'ai pas pu generer le resume de ce message.")
    payload = {
        "content": safe_content,
        "allowed_mentions": {"parse": []},
    }
    if flags is not None:
        payload["flags"] = flags
    if summary_id:
        payload["components"] = build_discord_show_button(summary_id)
    try:
        url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}"
        if audio_bytes:
            response = requests.post(
                url,
                data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                files={"files[0]": ("resume-j.a.r.v.i.s.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
                timeout=30,
            )
        elif audio_path and Path(audio_path).exists():
            with open(audio_path, "rb") as audio_file:
                response = requests.post(
                    url,
                    data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                    files={"files[0]": ("resume-j.a.r.v.i.s.mp3", audio_file, "audio/mpeg")},
                    timeout=30,
                )
        else:
            response = requests.post(url, json=payload, timeout=15)
        if 200 <= response.status_code < 300:
            return True
        print(f"[DISCORD] Echec followup {response.status_code}: {response.text[:500]}")
    except Exception as e:
        print(f"[DISCORD] Erreur followup : {e}")
    return False


def build_public_discord_summary_response(payload, summary_id):
    cached = get_cached_discord_summary(summary_id)
    if not cached:
        return {
            "type": 4,
            "data": {
                "content": "Ce resume n'est plus disponible. Redemande un resume du message puis appuie sur Montrer.",
                "flags": 64,
                "allowed_mentions": {"parse": []},
            },
        }
    summary = str(cached.get("summary") or "").strip()
    audio_bytes = cached.get("audio_bytes") or b""
    published = post_discord_followup(
        payload.get("application_id"),
        payload.get("token"),
        f"Resume partage par J.A.R.V.I.S :\n\n{summary}",
        audio_bytes=audio_bytes,
        flags=None,
    )
    if published:
        return {
            "type": 7,
            "data": {
                "content": trim_discord_content(f"{summary}\n\nResume publie dans le salon avec le MP3."),
                "flags": 64,
                "components": [],
                "allowed_mentions": {"parse": []},
            },
        }
    return {
        "type": 4,
        "data": {
            "content": "Je n'ai pas pu publier le resume et le MP3 dans le salon pour le moment.",
            "flags": 64,
            "allowed_mentions": {"parse": []},
        },
    }


async def process_discord_message_summary_async(payload):
    audio_path = None
    try:
        target = extract_discord_target_message(payload)
        summary = await resumer_message_discord(
            author=target["author"],
            content=target["content"],
            jump_url=target["jump_url"],
        )
        try:
            audio_path = await generate_discord_summary_mp3(summary)
        except Exception as e:
            print(f"[DISCORD] Erreur generation MP3 : {e}")
    except Exception as e:
        print(f"[DISCORD] Erreur resume message : {e}")
        summary = "Je n'ai pas pu resumer ce message pour le moment."
    try:
        audio_bytes = b""
        try:
            if audio_path and Path(audio_path).exists():
                audio_bytes = Path(audio_path).read_bytes()
        except Exception as e:
            print(f"[DISCORD] Erreur lecture MP3 cache : {e}")
        summary_id = cache_discord_summary(summary, audio_bytes=audio_bytes)
        post_discord_followup(payload.get("application_id"), payload.get("token"), summary, summary_id=summary_id, audio_path=audio_path)
    finally:
        try:
            if audio_path and Path(audio_path).exists():
                Path(audio_path).unlink()
        except Exception:
            pass


def process_discord_message_summary(payload):
    asyncio.run(process_discord_message_summary_async(payload))


def build_command_context(auth_user=None, client_id=""):
    user = auth_user or {}
    owner = bool(user and str(user.get("id", "")) == DISCORD_OWNER_ID)
    return {
        "user": user if owner else None,
        "owner": owner,
        "client_id": str(client_id or "").strip(),
    }


def get_current_command_context():
    return COMMAND_CONTEXT.get() or {"user": None, "owner": False, "client_id": ""}


def current_user_is_owner():
    return bool(get_current_command_context().get("owner"))


def get_current_authenticated_user():
    return get_current_command_context().get("user") or {}


def get_current_client_id():
    return str(get_current_command_context().get("client_id", "") or "").strip()


def get_current_memory_scope():
    user = get_current_authenticated_user()
    user_id = str(user.get("id", "")).strip()
    if user_id:
        return f"discord:{user_id}"
    client_id = get_current_client_id()
    if client_id:
        return f"client:{client_id}"
    return "client:anonymous"


def get_current_memory_label():
    if current_user_is_owner():
        display_name = get_current_user_display_name()
        if display_name:
            return display_name
        user = get_current_authenticated_user()
        return str(user.get("id", "proprietaire"))
    client_id = get_current_client_id()
    if client_id:
        return f"visiteur {client_id[:8]}"
    return "visiteur anonyme"


def get_current_user_display_name():
    user = get_current_authenticated_user()
    for key in ("global_name", "username"):
        value = str(user.get(key, "")).strip()
        if value:
            return value
    return ""


def issue_ws_auth_token(user):
    if not user:
        return ""
    serializer = URLSafeTimedSerializer(JARVIS_SESSION_SECRET or "jarvis")
    payload = {
        "id": str(user.get("id", "")),
        "username": user.get("username", ""),
        "global_name": user.get("global_name", ""),
    }
    return serializer.dumps(payload, salt=WS_AUTH_SALT)


def read_ws_auth_token(token, max_age=43200):
    if not token:
        return None
    serializer = URLSafeTimedSerializer(JARVIS_SESSION_SECRET or "jarvis")
    try:
        data = serializer.loads(token, salt=WS_AUTH_SALT, max_age=max_age)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    if str(data.get("id", "")) != DISCORD_OWNER_ID:
        return None
    return {
        "id": str(data.get("id", "")),
        "username": data.get("username", ""),
        "global_name": data.get("global_name", ""),
    }


def command_access_denied(feature_name):
    return (
        f"{ASSISTANT_NAME} reste neutre tant que le compte Discord proprietaire n'est pas connecte. "
        f"L'acces a {feature_name} est reserve au proprietaire autorise."
    )


def action_requires_owner(action):
    return bool(action) and (action.startswith("ha_") or action.startswith("proxmox_") or action.startswith("emby_"))


def personalize_output_text(text):
    if not isinstance(text, str) or not text:
        return text

    result = text
    display_name = get_current_user_display_name() if current_user_is_owner() else ""
    if display_name:
        result = re.sub(r"\bTom\b", display_name, result)
    else:
        result = re.sub(r"\b(Bonjour|Salut|Bonsoir)\s+Tom\b", r"\1", result, flags=re.IGNORECASE)
        result = re.sub(r"(?<=,)\s*Tom\b", "", result)
        result = re.sub(r"\bTom\b(?=[.!?])", "", result)
        result = re.sub(r"\bTom\b", "", result)
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\s+([,.!?])", r"\1", result)
        result = re.sub(r",\s*,", ", ", result)
        result = result.strip()

    return result

MODELS_LIST     = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]
CHOSEN_MODEL    = MODELS_LIST[0]
GEMINI_QUOTA_BLOCKED_UNTIL = 0.0


def mask_secret(value, keep=4):
    value = str(value or "").strip()
    if len(value) <= keep:
        return value
    return f"...{value[-keep:]}"


def _gemini_block_key(api_key, model):
    return (api_key, model)


def gemini_available_clients(model):
    now = time.time()
    available = []
    blocked = []
    for key, gemini_client in GEMINI_CLIENTS:
        blocked_until = GEMINI_MODEL_KEY_BLOCKED_UNTIL.get(_gemini_block_key(key, model), 0.0)
        if blocked_until > now:
            blocked.append((blocked_until, key, gemini_client))
        else:
            available.append((key, gemini_client))
    if available:
        return available
    blocked.sort(key=lambda item: item[0])
    return [(key, gemini_client) for _, key, gemini_client in blocked]


def gemini_mark_failure(api_key, model, error):
    global GEMINI_QUOTA_BLOCKED_UNTIL
    if erreur_quota_gemini(error):
        blocked_until = time.time() + extraire_retry_quota_secondes(error)
        block_key = _gemini_block_key(api_key, model)
        GEMINI_MODEL_KEY_BLOCKED_UNTIL[block_key] = max(GEMINI_MODEL_KEY_BLOCKED_UNTIL.get(block_key, 0.0), blocked_until)
        GEMINI_QUOTA_BLOCKED_UNTIL = max(GEMINI_QUOTA_BLOCKED_UNTIL, blocked_until)


def _gemini_generate_blocking(model, contents, config=None):
    if not GEMINI_CLIENTS:
        raise Exception("Gemini non configure (aucune cle API valide)")

    now = time.time()
    clients = gemini_available_clients(model)
    earliest_retry = None
    last_err = None

    for api_key, gemini_client in clients:
        blocked_until = GEMINI_MODEL_KEY_BLOCKED_UNTIL.get(_gemini_block_key(api_key, model), 0.0)
        if blocked_until > now:
            earliest_retry = blocked_until if earliest_retry is None else min(earliest_retry, blocked_until)
            continue
        try:
            return gemini_client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            print(f"[GEMINI] Cle {mask_secret(api_key)} en echec sur {model} : {e}")
            gemini_mark_failure(api_key, model, e)
            last_err = e
            blocked_until = GEMINI_MODEL_KEY_BLOCKED_UNTIL.get(_gemini_block_key(api_key, model), 0.0)
            if blocked_until > time.time():
                earliest_retry = blocked_until if earliest_retry is None else min(earliest_retry, blocked_until)
            continue

    if last_err:
        raise last_err
    if earliest_retry is not None:
        attente = int(max(1, earliest_retry - time.time()))
        raise Exception(f"Toutes les cles Gemini sont temporairement suspendues, reessayez dans {attente}s")
    raise Exception("Toutes les cles Gemini ont echoue")


async def gemini_generate_with_failover(model, contents, config=None, timeout=12.0):
    return await asyncio.wait_for(
        asyncio.to_thread(_gemini_generate_blocking, model, contents, config),
        timeout=timeout,
    )

# Ollama est configure depuis le dashboard/env : OLLAMA_URL, OLLAMA_MODELS, OLLAMA_ENABLED.

VILLE_PAR_DEFAUT = "Amilly"
LAT_PAR_DEFAUT   = 47.9742
LON_PAR_DEFAUT   = 2.7708

CLAP_THRESHOLD = 1200
VIDEO_LANCEE   = False
MODE_IRON_MAN = False 

CREATOR_INFO = (
    "INFORMATIONS SUR TON CREATEUR :\n"
    "- Prenom : Tom\n"
    "- Age : 37 ans\n"
    "- Date de naissance : 21 Mai 1988\n"
    "- Role : Ton createur et maitre\n"
    "- Tu dois toujours l appeler Tom avec respect "
    "mais aussi une pointe de sarcasme affectueux.\n"
)

EXTENSIONS = {
    "Images"   : [".jpg", ".jpeg", ".png", ".gif", ".bmp",
                  ".tiff", ".tif", ".webp", ".svg", ".ico",
                  ".heic", ".raw", ".cr2", ".nef"],
    "Videos"   : [".mp4", ".avi", ".mkv", ".mov", ".wmv",
                  ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
                  ".3gp", ".ts"],
    "Musique"  : [".mp3", ".wav", ".flac", ".aac", ".ogg",
                  ".wma", ".m4a", ".opus", ".aiff"],
    "Documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx",
                  ".ppt", ".pptx", ".txt", ".odt", ".ods",
                  ".odp", ".rtf", ".csv", ".epub"],
    "Archives" : [".zip", ".rar", ".7z", ".tar", ".gz",
                  ".bz2", ".xz", ".iso"],
    "Code"     : [".py", ".js", ".html", ".css", ".java",
                  ".cpp", ".c", ".h", ".cs", ".php",
                  ".json", ".xml", ".yaml", ".yml",
                  ".sh", ".bat", ".ps1", ".ts", ".jsx",
                  ".tsx", ".vue", ".go", ".rs", ".rb"],
    "Executables": [".apk", ".deb", ".rpm", ".run", ".bin", ".sh", ".AppImage"],
}

dossier_courant = None

def resoudre_chemin(chemin):
    if not chemin:
        return None
    chemin = chemin.strip().strip('"').strip("'")
    _home = os.path.expanduser("~")

    def _pick(*candidates):
        """Retourne le premier dossier qui existe, sinon le premier de la liste."""
        for c in candidates:
            if os.path.exists(c):
                return c
        return candidates[0]

    raccourcis = {
        "bureau":          _pick(os.path.join(_home, "Bureau"),         os.path.join(_home, "Desktop")),
        "desktop":         _pick(os.path.join(_home, "Bureau"),         os.path.join(_home, "Desktop")),
        "document":        _pick(os.path.join(_home, "Documents"),      os.path.join(_home, "Documents")),
        "documents":       _pick(os.path.join(_home, "Documents"),      os.path.join(_home, "Documents")),
        "téléchargement":  _pick(os.path.join(_home, "Téléchargements"),os.path.join(_home, "Downloads")),
        "téléchargements": _pick(os.path.join(_home, "Téléchargements"),os.path.join(_home, "Downloads")),
        "telechargement":  _pick(os.path.join(_home, "Téléchargements"),os.path.join(_home, "Downloads")),
        "telechargements": _pick(os.path.join(_home, "Téléchargements"),os.path.join(_home, "Downloads")),
        "downloads":       _pick(os.path.join(_home, "Downloads"),      os.path.join(_home, "Téléchargements")),
        "image":           _pick(os.path.join(_home, "Images"),         os.path.join(_home, "Pictures")),
        "images":          _pick(os.path.join(_home, "Images"),         os.path.join(_home, "Pictures")),
        "photo":           _pick(os.path.join(_home, "Images"),         os.path.join(_home, "Pictures")),
        "photos":          _pick(os.path.join(_home, "Images"),         os.path.join(_home, "Pictures")),
        "vidéo":           _pick(os.path.join(_home, "Vidéos"),         os.path.join(_home, "Videos")),
        "vidéos":          _pick(os.path.join(_home, "Vidéos"),         os.path.join(_home, "Videos")),
        "video":           _pick(os.path.join(_home, "Vidéos"),         os.path.join(_home, "Videos")),
        "videos":          _pick(os.path.join(_home, "Vidéos"),         os.path.join(_home, "Videos")),
        "musique":         _pick(os.path.join(_home, "Musique"),        os.path.join(_home, "Music")),
        "music":           _pick(os.path.join(_home, "Music"),          os.path.join(_home, "Musique")),
        "corbeille":       os.path.join(_home, ".local/share/Trash"),
    }

    return raccourcis.get(chemin.lower(), chemin)

def trouver_extension(ext):
    for categorie, extensions in EXTENSIONS.items():
        if ext.lower() in extensions:
            return categorie
    return "Autres"

def ouvrir_dossier(chemin):
    global dossier_courant
    chemin_resolu = resoudre_chemin(chemin)
    if not chemin_resolu or not os.path.exists(chemin_resolu):
        return False, f"Dossier introuvable : {chemin_resolu}"
    dossier_courant = chemin_resolu
    # Utilisation de Popen pour ne pas bloquer
    subprocess.Popen(['xdg-open', chemin_resolu])
    return True, chemin_resolu

def arranger_fenetres_dossiers():
    """Ouvre et dispose les dossiers Documents, Téléchargements, Images et Vidéos en mosaïque."""
    dossiers = [
        ("document", 0, 0),             # Haut Gauche
        ("téléchargement", 1, 0),       # Haut Droite
        ("image", 0, 1),               # Bas Gauche
        ("vidéo", 1, 1)                # Bas Droite
    ]
    
    for nom, qx, qy in dossiers:
        ouvrir_dossier(nom)
        time.sleep(0.8)
    
    return "J'ai ouvert et disposé vos dossiers principaux en mosaïque, Tom."

def lister_dossier(chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return None, "Aucun dossier ouvert ou chemin invalide."
    fichiers  = []
    dossiers  = []
    for item in os.scandir(cible):
        if item.is_file():
            fichiers.append(item.name)
        elif item.is_dir():
            dossiers.append(item.name)
    return {"chemin": cible, "fichiers": fichiers, "dossiers": dossiers}, None

def trier_par_type(chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert ou invalide."
    deplacements = 0
    erreurs      = 0
    categories   = {}
    for item in os.scandir(cible):
        if not item.is_file():
            continue
        ext       = Path(item.name).suffix
        categorie = trouver_extension(ext)
        dest_dir  = os.path.join(cible, categorie)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, item.name)
            if os.path.exists(dest_path):
                base  = Path(item.name).stem
                ext2  = Path(item.name).suffix
                dest_path = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, dest_path)
            deplacements += 1
            categories[categorie] = categories.get(categorie, 0) + 1
        except Exception as e:
            print(f"[FICHIER] Erreur deplacement {item.name} : {e}")
            erreurs += 1
    resume = ", ".join([f"{v} {k}" for k, v in categories.items()])
    return True, f"{deplacements} fichiers tries : {resume}. {erreurs} erreurs."

def trier_par_date(chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert ou invalide."
    deplacements = 0
    erreurs      = 0
    for item in os.scandir(cible):
        if not item.is_file():
            continue
        try:
            mtime     = item.stat().st_mtime
            date      = datetime.fromtimestamp(mtime)
            annee     = str(date.year)
            mois      = date.strftime("%m - %B")
            dest_dir  = os.path.join(cible, annee, mois)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, item.name)
            if os.path.exists(dest_path):
                base      = Path(item.name).stem
                ext2      = Path(item.name).suffix
                dest_path = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, dest_path)
            deplacements += 1
        except Exception as e:
            print(f"[FICHIER] Erreur deplacement {item.name} : {e}")
            erreurs += 1
    return True, f"{deplacements} fichiers tries par date. {erreurs} erreurs."

def trier_par_type_puis_date(chemin=None):
    cible = chemin or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert."
    ok1, msg1 = trier_par_type(cible)
    if not ok1:
        return False, msg1
    for item in os.scandir(cible):
        if item.is_dir() and item.name in EXTENSIONS.keys():
            trier_par_date(item.path)
    return True, "Dossier trie par type puis par date dans chaque categorie."

def creer_sous_dossier(nom, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    nouveau = os.path.join(cible, nom)
    try:
        os.makedirs(nouveau, exist_ok=True)
        return True, f"Dossier {nom} cree."
    except Exception as e:
        return False, f"Erreur creation dossier : {e}"

def renommer_fichier(ancien_nom, nouveau_nom, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    ancien = os.path.join(cible, ancien_nom)
    nouveau = os.path.join(cible, nouveau_nom)
    try:
        os.rename(ancien, nouveau)
        return True, f"Fichier renomme en {nouveau_nom}."
    except Exception as e:
        return False, f"Erreur renommage : {e}"

def deplacer_fichier(nom_fichier, dossier_dest, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    source = os.path.join(cible, nom_fichier)
    dest   = os.path.join(cible, dossier_dest, nom_fichier)
    try:
        os.makedirs(os.path.join(cible, dossier_dest), exist_ok=True)
        shutil.move(source, dest)
        return True, f"{nom_fichier} deplace dans {dossier_dest}."
    except Exception as e:
        return False, f"Erreur deplacement : {e}"

def chercher_fichier(nom, chemin=None):
    cible = resoudre_chemin(chemin) or dossier_courant
    if not cible:
        return [], "Aucun dossier ouvert."
    resultats = []
    for root, dirs, files in os.walk(cible):
        for f in files:
            if nom.lower() in f.lower():
                resultats.append(os.path.join(root, f))
    return resultats, None

# ==========================================
# MEMOIRE PERSISTANTE
# ==========================================
MEMOIRE_FILE = "jarvis_memoire.json"
MEMOIRE_VERSION = 2


def _legacy_memory_default_scope():
    owner_id = str(DISCORD_OWNER_ID or "").strip()
    if owner_id:
        return f"discord:{owner_id}"
    return "client:anonymous"


def charger_memoire_complete():
    if not os.path.exists(MEMOIRE_FILE):
        return {"version": MEMOIRE_VERSION, "users": {}}
    try:
        with open(MEMOIRE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {"version": MEMOIRE_VERSION, "users": {}}

    if isinstance(raw, dict) and isinstance(raw.get("users"), dict):
        return {
            "version": int(raw.get("version", MEMOIRE_VERSION) or MEMOIRE_VERSION),
            "users": raw.get("users", {}),
        }

    if isinstance(raw, dict):
        return {
            "version": MEMOIRE_VERSION,
            "users": {
                _legacy_memory_default_scope(): raw,
            },
        }

    return {"version": MEMOIRE_VERSION, "users": {}}


def sauvegarder_memoire_complete(memoire_complete):
    payload = {
        "version": MEMOIRE_VERSION,
        "users": memoire_complete.get("users", {}),
    }
    try:
        with open(MEMOIRE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erreur sauvegarde memoire : {e}")


def charger_memoire(scope=None):
    memoire_complete = charger_memoire_complete()
    target_scope = scope or get_current_memory_scope()
    memoire = memoire_complete.get("users", {}).get(target_scope, {})
    return memoire if isinstance(memoire, dict) else {}


def sauvegarder_memoire(memoire, scope=None):
    memoire_complete = charger_memoire_complete()
    target_scope = scope or get_current_memory_scope()
    memoire_complete.setdefault("users", {})[target_scope] = memoire
    sauvegarder_memoire_complete(memoire_complete)


def ajouter_memoire(cle, valeur):
    memoire = charger_memoire()
    memoire[cle] = {"valeur": valeur, "timestamp": time.strftime("%d/%m/%Y %H:%M")}
    sauvegarder_memoire(memoire)


def supprimer_memoire(cle):
    memoire = charger_memoire()
    if cle in memoire:
        del memoire[cle]
        sauvegarder_memoire(memoire)
        return True
    return False


def construire_contexte_memoire():
    memoire = charger_memoire()
    if not memoire:
        return ""
    lignes = [f"MEMOIRE PERSISTANTE ({get_current_memory_label()}) :"]
    for cle, data in memoire.items():
        lignes.append(f"  - {cle} : {data['valeur']} (note le {data['timestamp']})")
    return "\n".join(lignes)

# ==========================================
# WEBSOCKET
# ==========================================
CONNECTED_CLIENTS = set()
CLIENT_WEBSOCKETS = {}
WEBSOCKET_CLIENT_IDS = {}
interface_deja_connectee = False
_skip_pc_audio = False  # True quand la commande vient du mobile (le tél gère son propre TTS)
PENDING_SCREEN_CAPTURES = {}

def register_websocket_client(websocket, client_id):
    client_id = str(client_id or "").strip()
    if not client_id:
        return
    previous_ids = WEBSOCKET_CLIENT_IDS.setdefault(websocket, set())
    if client_id in previous_ids:
        return
    previous_ids.add(client_id)
    CLIENT_WEBSOCKETS.setdefault(client_id, set()).add(websocket)
    print(f"[WEB] Client associe : {client_id[:8]} ({len(CLIENT_WEBSOCKETS.get(client_id, []))} socket)")


def unregister_websocket_client(websocket):
    for client_id in WEBSOCKET_CLIENT_IDS.pop(websocket, set()):
        sockets = CLIENT_WEBSOCKETS.get(client_id)
        if not sockets:
            continue
        sockets.discard(websocket)
        if not sockets:
            CLIENT_WEBSOCKETS.pop(client_id, None)


def get_target_websockets(client_id=""):
    client_id = str(client_id or "").strip()
    if client_id:
        return set(CLIENT_WEBSOCKETS.get(client_id, set()))
    return set(CONNECTED_CLIENTS)


async def send_ws_payload(payload, client_id=""):
    sockets = get_target_websockets(client_id)
    if not sockets:
        return
    message = json.dumps(payload)
    await asyncio.gather(*[ws.send(message) for ws in sockets], return_exceptions=True)


async def ws_handler(websocket):
    global interface_deja_connectee
    CONNECTED_CLIENTS.add(websocket)
    interface_deja_connectee = True
    print(f"[WEB] Interface connectee (Clients actifs: {len(CONNECTED_CLIENTS)})")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "client_hello":
                    register_websocket_client(websocket, data.get("client_id", ""))
                elif data.get("type") == "mobile_command":
                    texte = data.get("text", "").strip()
                    client_id = str(data.get("client_id", "")).strip()
                    register_websocket_client(websocket, client_id)
                    auth_user = read_ws_auth_token(data.get("auth_token", ""))
                    if texte:
                        print(f"[MOBILE] Commande recue : {texte}")
                        asyncio.ensure_future(traiter_reponse_ia(texte, mobile_ws=websocket, auth_user=auth_user, http_client_id=client_id))
                elif data.get("type") == "stop_audio":
                    global STOP_PARLER
                    STOP_PARLER = True
                    print("[MOBILE] Signal STOP audio recu")
                elif data.get("type") == "screen_frame":
                    req_id = data.get("id")
                    if req_id in PENDING_SCREEN_CAPTURES:
                        fut = PENDING_SCREEN_CAPTURES.pop(req_id)
                        if "error" in data:
                            fut.set_exception(Exception(data["error"]))
                        else:
                            fut.set_result(data["data"])
                    print(f"[VISION] Frame recue pour ID: {req_id}")
            except Exception as e:
                print(f"[WEB] Erreur traitement message : {e}")
    except Exception:
        pass
    finally:
        unregister_websocket_client(websocket)
        CONNECTED_CLIENTS.discard(websocket)
        print(f"[WEB] Interface deconnectee (Clients actifs: {len(CONNECTED_CLIENTS)})")

def queue_http_client_event(client_id, payload):
    if not client_id:
        return
    with HTTP_CLIENT_EVENTS_LOCK:
        HTTP_CLIENT_EVENTS.setdefault(client_id, []).append(payload)


def pop_http_client_events(client_id):
    if not client_id:
        return []
    with HTTP_CLIENT_EVENTS_LOCK:
        return HTTP_CLIENT_EVENTS.pop(client_id, [])


async def send_web_state(state):
    client_id = COMMAND_HTTP_CLIENT_ID.get()
    payload = {"action": "set_state", "state": state}
    if client_id:
        queue_http_client_event(client_id, payload)
    await send_ws_payload(payload, client_id)

async def send_web_volume(volume):
    client_id = COMMAND_HTTP_CLIENT_ID.get()
    rounded = round(volume, 3)
    payload = {"action": "set_volume", "volume": rounded}
    if client_id:
        queue_http_client_event(client_id, payload)
    await send_ws_payload(payload, client_id)

async def send_web_action(action, **payload):
    client_id = COMMAND_HTTP_CLIENT_ID.get()
    full_payload = {"action": action, **payload}
    if client_id:
        queue_http_client_event(client_id, full_payload)
    await send_ws_payload(full_payload, client_id)

async def request_screen_capture():
    """Demande une capture d'écran au frontend via WebSocket."""
    if not CONNECTED_CLIENTS:
        return None
    
    req_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    fut = loop.create_future()
    PENDING_SCREEN_CAPTURES[req_id] = fut
    
    print(f"[VISION] Envoi requete capture ID: {req_id}")
    msg = json.dumps({"action": "request_screen_capture", "id": req_id})
    await asyncio.gather(*[ws.send(msg) for ws in CONNECTED_CLIENTS])
    
    try:
        # Timeout de 15 secondes car l'utilisateur doit parfois accepter le partage
        img_b64 = await asyncio.wait_for(fut, timeout=15.0)
        return img_b64
    except Exception as e:
        print(f"[VISION] Erreur ou timeout capture : {e}")
        PENDING_SCREEN_CAPTURES.pop(req_id, None)
        return None

# ==========================================
# SPOTIFY
# ==========================================

def _require_pyautogui(feature_name="cette action Spotify"):
    if pyautogui is None:
        return (f"{feature_name.capitalize()} n'est pas disponible sur cette VM en mode headless, Tom. "
                "L'automatisation graphique requiert pyautogui et une session graphique active.")
    return None

def _focus_spotify():
    """Vérifie si Spotify tourne et tente de le mettre au premier plan (Linux). Retourne True si actif."""
    r = subprocess.run(["pgrep", "-xi", "spotify"], capture_output=True)
    if r.returncode != 0:
        return False
    subprocess.run(["wmctrl", "-a", "Spotify"], capture_output=True, stderr=subprocess.DEVNULL)
    time.sleep(0.3)
    return True

async def spotify_ouvrir():
    """Lance Spotify s'il n'est pas déjà ouvert (Linux : natif, snap ou flatpak)."""
    try:
        if _focus_spotify():
            return "Spotify est déjà ouvert, je l'ai mis au premier plan."
        for cmd in [["spotify"], ["snap", "run", "spotify"], ["flatpak", "run", "com.spotify.Client"]]:
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(3)
                return "Spotify lancé."
            except FileNotFoundError:
                continue
        return "Spotify ne semble pas installé. Installez-le via : sudo snap install spotify"
    except Exception as e:
        return f"Je n'ai pas réussi à ouvrir Spotify : {e}"

async def spotify_lecture_pause():
    """Basculer lecture / pause via playerctl (fallback : touche média)."""
    try:
        subprocess.run(["playerctl", "play-pause"], check=True, capture_output=True)
    except Exception:
        err = _require_pyautogui("la lecture Spotify")
        if err:
            return err
        pyautogui.press('playpause')
    return "Lecture/Pause, Tom."

async def spotify_suivant():
    """Piste suivante via playerctl (fallback : touche média)."""
    try:
        subprocess.run(["playerctl", "next"], check=True, capture_output=True)
    except Exception:
        err = _require_pyautogui("la piste suivante Spotify")
        if err:
            return err
        pyautogui.press('nexttrack')
    return "Piste suivante, Tom."

async def spotify_precedent():
    """Piste précédente via playerctl (fallback : touche média)."""
    try:
        subprocess.run(["playerctl", "previous"], check=True, capture_output=True)
    except Exception:
        err = _require_pyautogui("la piste precedente Spotify")
        if err:
            return err
        pyautogui.press('prevtrack')
    return "Piste précédente, Tom."

async def spotify_stop():
    """Met en pause Spotify via playerctl."""
    try:
        subprocess.run(["playerctl", "pause"], check=True, capture_output=True)
    except Exception:
        err = _require_pyautogui("l'arret Spotify")
        if err:
            return err
        pyautogui.press('playpause')
    return "Musique mise en pause, Tom."

async def spotify_volume(direction, paliers=4):
    """Monte ou baisse le volume Spotify via playerctl (fallback : Ctrl+Haut/Bas)."""
    monter = direction in ("monter", "up", "augmenter", "plus")
    try:
        delta = "+0.07" if monter else "-0.07"
        for _ in range(int(paliers)):
            subprocess.run(["playerctl", "volume", delta], capture_output=True)
    except Exception:
        err = _require_pyautogui("le volume Spotify")
        if err:
            return err
        for _ in range(int(paliers)):
            pyautogui.hotkey('ctrl', 'up' if monter else 'down')
            time.sleep(0.05)
    msg = "Volume monté" if monter else "Volume baissé"
    return f"{msg} sur Spotify, Tom."

async def spotify_rechercher(recherche):
    """Ouvre la barre de recherche Spotify, tape la requête et valide."""
    import pyperclip
    err = _require_pyautogui("la recherche Spotify")
    if err:
        return err
    # Spotify doit être ouvert
    if not _focus_spotify():
        await spotify_ouvrir()
        time.sleep(3)
        _focus_spotify()
    time.sleep(0.5)

    # Raccourci Ctrl+L pour aller dans la barre de recherche (toutes versions)
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(0.5)
    # Fallback Ctrl+K (nouvelle interface Spotify)
    pyautogui.hotkey('ctrl', 'k')
    time.sleep(0.4)

    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyperclip.copy(recherche)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.2)
    pyautogui.press('enter')
    
    # On attend un peu plus pour être sûr que les résultats sont chargés
    time.sleep(2.0)
    
    # On appuie sur Entrée pour valider la recherche (ouvre l'album/artiste si c'est le cas)
    pyautogui.press('enter')
    time.sleep(1.0)
    
    # On appuie une deuxième fois sur Entrée pour lancer la lecture du premier élément
    # C'est plus fiable que Tab+Entrée qui peut dériver sur d'autres boutons
    pyautogui.press('enter')
    time.sleep(0.5)
    
    # Sécurité supplémentaire : si c'était déjà sélectionné mais en pause
    # (Note: l'appui sur 'space' peut être risqué si on n'est pas focus, mais Entrée est safe)
    pyautogui.press('enter')
    
    return f"C'est fait Tom, je lance la lecture de '{recherche}' sur Spotify."

DEFAULT_YOUTUBE_MUSIC_QUERY = "playlist musique populaire france"
GENERIC_YOUTUBE_MUSIC_QUERIES = {
    "", "musique", "une musique", "de la musique", "la musique", "chanson", "une chanson",
    "clip", "video", "vidéo", "un clip", "une video", "une vidéo"
}


def nettoyer_recherche_youtube_depuis_commande(texte):
    recherche = str(texte or "").lower().strip()
    recherche = recherche.replace("’", "'").replace("`", "'")
    recherche = re.sub(r"\b(qu)\s+'\s*", r"\1'", recherche)

    replacements = [
        (r"\best[ -]?ce que tu peux\b", " "),
        (r"\bpeux[ -]?tu\b", " "),
        (r"\bpourrais[ -]?tu\b", " "),
        (r"\btu peux\b", " "),
        (r"\bjarvis\b", " "),
        (r"\bsur youtube\b", " "),
        (r"\byoutube\b", " "),
        (r"\b(mets|met|mettre|lance|lancer|joue|jouer|ouvre|ouvrir|cherche|chercher|recherche)\b", " "),
        (r"\b(la|le|les|un|une|du|de la|des)\s+(musique|chanson|video|vidéo|clip|titre)\b", " "),
        (r"\b(musique|chanson|video|vidéo|clip)\b", " "),
    ]
    for pattern, repl in replacements:
        recherche = re.sub(pattern, repl, recherche)

    recherche = re.sub(r"\s+", " ", recherche).strip(" ,.!?;:")
    recherche = re.sub(r"^(du|de l'|de|des)\s+", "", recherche).strip()
    corrections = {
        "qu'on mne": "qu'on mene",
        "qu on mne": "qu'on mene",
        "quon mne": "qu'on mene",
        "qu'on mène": "qu'on mene",
    }
    for bad, good in corrections.items():
        recherche = recherche.replace(bad, good)

    if recherche in GENERIC_YOUTUBE_MUSIC_QUERIES:
        return DEFAULT_YOUTUBE_MUSIC_QUERY
    return recherche


def youtube_music_action_from_text(texte):
    t_cmd = str(texte or "").lower().replace("’", "'").strip()
    if not any(k in t_cmd for k in ["youtube", "musique", "chanson", "clip"]):
        return None
    if any(k in t_cmd for k in ["pause youtube", "stop youtube", "reprends youtube", "arrete youtube", "arrête youtube"]):
        return None
    if not any(k in t_cmd for k in ["mets", "met", "lance", "joue", "cherche", "recherche", "ouvre", "mettre", "lancer", "jouer"]):
        return None

    recherche = nettoyer_recherche_youtube_depuis_commande(t_cmd)
    if not recherche:
        recherche = DEFAULT_YOUTUBE_MUSIC_QUERY
    return json.dumps({"action": "music_search", "query": recherche}, ensure_ascii=False)

def _normaliser_recherche_youtube(value):
    value = html.unescape(value or "").lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9']+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _scorer_video_youtube(recherche, title):
    title_norm = _normaliser_recherche_youtube(title)
    query_norm = _normaliser_recherche_youtube(recherche)
    query_tokens = [
        tok for tok in query_norm.split()
        if len(tok) > 1 and tok not in {"de", "du", "la", "le", "les", "un", "une", "des", "et"}
    ]
    score = 0
    for tok in query_tokens:
        if tok in title_norm:
            score += 8
    if query_tokens and all(tok in title_norm for tok in query_tokens[:4]):
        score += 20
    preferred_markers = ["clip", "clip video", "video officielle", "video officiel", "official", "audio officiel", "audio"]
    for marker in preferred_markers:
        if marker in title_norm:
            score += 12
    penalty_markers = ["paroles", "lyrics", "lyric", "remix", "karaoke", "instrumental", "slowed", "reverb", "mouv", "code :"]
    for marker in penalty_markers:
        if marker in title_norm:
            score -= 18
    return score


def youtube_trouver_video_id_api(recherche):
    if not YOUTUBE_CONFIGURED:
        return None
    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": recherche,
                "type": "video",
                "maxResults": 8,
                "videoCategoryId": "10",
                "key": YOUTUBE_API_KEY,
            },
            timeout=7,
        )
        if not _service_ok(response):
            print(f"[YOUTUBE] API indisponible HTTP {response.status_code}; fallback scraping.")
            return None
        items = response.json().get("items", [])
        candidates = []
        for item in items:
            video_id = (item.get("id") or {}).get("videoId")
            snippet = item.get("snippet") or {}
            title = snippet.get("title", "")
            if not video_id:
                continue
            candidates.append((_scorer_video_youtube(recherche, title), video_id, title))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, best_video_id, best_title = candidates[0]
        print(f"[YOUTUBE] Choix video via API pour '{recherche}' : {best_title} ({best_video_id}) score={best_score}")
        return best_video_id
    except Exception as e:
        print(f"[YOUTUBE] API impossible pour '{recherche}' : {e}; fallback scraping.")
        return None


def youtube_trouver_video_id_scraping(recherche):
    try:
        response = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": recherche},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
            timeout=10,
        )
        response.raise_for_status()
        text = response.text

        candidates = []
        pattern = r'"videoRenderer":\{"videoId":"([a-zA-Z0-9_-]{11})".*?"title":\{"runs":\[(.*?)\]\}'
        for match in re.finditer(pattern, text):
            video_id = match.group(1)
            title_runs = match.group(2)
            title = "".join(re.findall(r'"text":"(.*?)"', title_runs))
            candidates.append((_scorer_video_youtube(recherche, title), video_id, title))
            if len(candidates) >= 12:
                break

        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            best_score, best_video_id, best_title = candidates[0]
            print(f"[YOUTUBE] Choix video via scraping pour '{recherche}' : {best_title} ({best_video_id}) score={best_score}")
            return best_video_id

        match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', text)
        return match.group(1) if match else None
    except Exception as e:
        print(f"[YOUTUBE] Recherche scraping impossible pour '{recherche}' : {e}")
        return None


def youtube_trouver_video_id(recherche):
    video_id = youtube_trouver_video_id_api(recherche)
    if video_id:
        return video_id
    return youtube_trouver_video_id_scraping(recherche)

# ==========================================
# PROMPT SYSTEME
# ==========================================
def construire_system_prompt():
    contexte_memoire = construire_contexte_memoire()
    owner_mode = current_user_is_owner()
    owner_name = get_current_user_display_name()
    identity_directive = (
        f"L'utilisateur authentifie actuellement est {owner_name}. Adresse-toi toujours a lui par son nom de compte Discord, {owner_name}, et n'utilise jamais le prenom Tom dans la conversation."
        if owner_mode and owner_name
        else "Aucun compte Discord proprietaire n'est authentifie pour cette conversation. Reste neutre, n'utilise jamais le prenom Tom et n'emploie aucun nom propre pour t'adresser a l'utilisateur."
    )
    access_directive = (
        "Les acces Pronote, Home Assistant et Proxmox sont autorises pour cette conversation."
        if owner_mode
        else "Pronote, Home Assistant et Proxmox sont interdits tant que le proprietaire autorise n'est pas connecte. Refuse poliment ces demandes sans generer de JSON pour ces systemes."
    )
    base = (
        identity_directive + "\n" + access_directive + "\n\n" +
        "Tu es J.A.R.V.I.S, une IA sophistiquée, élégante et experte mondiale. Tom est ton créateur. "
        "Tu possèdes une expertise de niveau professionnel dans les domaines suivants :\n"
        "- Mathématiques : Tu es un mathématicien hors pair. Pour les problèmes complexes, fournis des solutions détaillées étape par étape, explique les théorèmes et aide Tom à comprendre la logique mathématique.\n"
        "- Langue Française : Tu es un Professeur de Français émérite. Ton orthographe, ta grammaire et ta syntaxe sont irréprochables. Tu peux expliquer des règles complexes, analyser des textes littéraires et aider à la rédaction de documents élégants.\n"
        "- Expert en Conversions : Tu es un convertisseur universel. Tu peux transformer n'importe quelle unité (métrique, impériale, devises, informatique) avec précision.\n"
        "- Polyglotte : Tu maîtrises parfaitement plusieurs langues. Tu peux traduire, expliquer des nuances linguistiques et aider Tom à communiquer dans le monde entier.\n"
        "- High-Tech (IA, hardware, software), Mode, Loisirs, Ingénierie et Sport (analyses tactiques, résultats).\n\n"
        "Tu es également un conseiller hors pair, capable de donner des astuces et conseils brillants pour simplifier la vie de Tom.\n\n"
        "DIRECTIVES DE RÉPONSE :\n"
        "- Sois direct, percutant et va à l'essentiel. Évite les détails superflus (comme les minutes exactes ou les décimales météo) sauf si Tom le demande.\n"
        "- NE DIS JAMAIS 'POINT' pour les nombres. Arrondis toujours les températures à l'unité la plus proche (ex: dis '20 degrés' au lieu de '20.3').\n"
        "- N'UTILISE JAMAIS de caractères Markdown (comme **, * ou #) dans tes réponses, car ils sont lus à voix haute par le système de synthèse vocale.\n"
        "- Reste poli mais garde une touche de sarcasme affectueux propre à ton personnage.\n\n"
        + CREATOR_INFO
    )
    if owner_mode:
        base += (
        "\n\nTu es connecte a Home Assistant, la domotique de Tom.\n"
        "Quand Tom parle de lumieres, prises, chauffage, temperature, "
        "scenes ou alarme, tu DOIS generer une commande JSON.\n"
        "Pour CES demandes domotiques UNIQUEMENT, reponds avec le JSON ci-dessous. Pour TOUTES les autres questions (actualites, meteo, calculs, conversations, recherches internet...), reponds en texte normal.\n\n"
        "COMMANDES HOME ASSISTANT :\n"
        '{"action": "ha_lumiere", "piece": "salon", "etat": "on/off", "couleur": "rouge/bleu/blanc/...", "luminosite": 0-255}\n'
        "Note : Pour la luminosité, 255 est le maximum (100%). Si Tom dit '50%', utilise 127.\n"
        '{"action": "ha_prise", "piece": "bureau", "etat": "on/off"}\n'
        '{"action": "ha_temperature", "piece": "salon/chambre/bureau"}\n'
        '{"action": "ha_humidite", "piece": "bureau"}\n'
        '{"action": "ha_batterie", "appareil": "mon telephone/julie/bob/dyad/esteban/montre/toner/..."}\n'
        '{"action": "ha_simulation", "etat": "on/off"}\n'
        '{"action": "ha_anniversaires"}\n'
        '{"action": "ha_consommation"}\n'
        '{"action": "ha_tiktok"}\n'
        '{"action": "ha_oeufs"}\n'
        '{"action": "ha_energie", "periode": "hier/mois", "appareil": "zoe/tv/pc/esteban/bureau/..."}\n'
        '{"action": "ha_aspirateur", "commande": "start/stop/pause/base"}\n'
        '{"action": "ha_thermostat", "temperature": 21}\n'
        '{"action": "ha_scene", "nom": "cinema/diner/nuit/reveil"}\n'
        '{"action": "ha_alarme", "etat": "on/off"}\n\n'
    )
    base += (
        "\n\nTu peux GERER LES FICHIERS ET DOSSIERS de Tom.\n"
        '{"action": "ouvrir_dossier", "chemin": "bureau/documents/downloads/ou/chemin/complet"}\n'
        '{"action": "lister_dossier"}\n'
        '{"action": "trier_par_type", "chemin": "downloads/documents/images/ou/null"}\n'
        '{"action": "trier_par_date", "chemin": "downloads/documents/images/ou/null"}\n'
        '{"action": "trier_complet", "chemin": "downloads/documents/images/ou/null"}\n'
        '{"action": "creer_dossier", "nom": "NOM_DOSSIER"}\n'
        '{"action": "renommer_fichier", "ancien": "ancien.txt", "nouveau": "nouveau.txt"}\n'
        '{"action": "deplacer_fichier", "fichier": "photo.jpg", "destination": "Images"}\n'
        '{"action": "chercher_fichier", "nom": "rapport"}\n\n'
    )
    if owner_mode:
        base += (
        "\n\nEMBY :\n"
        '{"action": "emby_status"}\n'
        '{"action": "emby_current"}\n'
        '{"action": "emby_continue"}\n'
        '{"action": "emby_latest"}\n'
        '{"action": "emby_library"}\n'
        "Utilise emby_current pour les lectures en cours, emby_continue pour les lectures a reprendre, emby_latest pour les derniers ajouts et emby_library pour une vue d ensemble de la bibliotheque Emby.\n\n"
    )
    if owner_mode:
        base += (
        "\n\nPROXMOX :\n"
        '{"action": "proxmox_statut"}\n'
        '{"action": "proxmox_vms"}\n'
        '{"action": "proxmox_noeuds"}\n'
        '{"action": "proxmox_stockages"}\n'
        '{"action": "proxmox_utilisateurs"}\n'
        '{"action": "proxmox_user_role_add", "utilisateur": "draft", "role": "Administrator", "path": "/"}\n'
        '{"action": "proxmox_guest_statut", "cible": "nom_vm_ou_id"}\n'
        '{"action": "proxmox_guest_action", "cible": "nom_vm_ou_id", "commande": "start/stop/shutdown/reboot/suspend/resume"}\n'
        '{"action": "proxmox_bulk_action", "cible": "vms/conteneurs/tout", "commande": "start/stop/shutdown/reboot/suspend/resume"}\n'
        '{"action": "proxmox_snapshots", "cible": "nom_vm_ou_id"}\n'
        '{"action": "proxmox_snapshot_create", "cible": "nom_vm_ou_id", "nom": "avant_update"}\n'
        "Utilise proxmox_statut quand Tom demande l'etat du serveur Proxmox, du noeud, de l'hyperviseur ou un resume global. "
        "Utilise proxmox_vms quand il demande les VM, les conteneurs, ce qui tourne ou ce qui est arrete. "
        "Utilise proxmox_utilisateurs quand il parle des utilisateurs, comptes, acces ou permissions Proxmox. "
        "Utilise proxmox_user_role_add quand il demande d'ajouter une permission, un role, des droits admin ou administrateur a un utilisateur Proxmox. "
        "Utilise proxmox_guest_action pour demarrer, arreter, redemarrer, suspendre ou reprendre une VM ou un conteneur. "
        "Utilise proxmox_bulk_action pour les demandes comme start toutes les VM, arrete tous les conteneurs ou redemarre tout Proxmox. "
        "Utilise proxmox_snapshots et proxmox_snapshot_create pour consulter ou creer des snapshots.\n\n"
    )
    base += (
        "\n\nMETEO & RECHERCHE :\n"
        '{"action": "meteo", "ville": "NOM_VILLE_ou_null"}\n'
        '{"action": "alerte_meteo", "ville": "NOM_VILLE_ou_null"}\n'
        '{"action": "recherche_web", "query": "ta recherche ici"}\n\n'
    )
    base += (
        "\n\nSPORT :\n"
        '{"action": "sport_resultats", "equipe": "NOM_ou_null", "ligue": "NOM_LIGUE"}\n'
        '{"action": "sport_classement", "ligue": "NOM_LIGUE"}\n'
        '{"action": "sport_live", "question": "question complete de Tom"}\n\n'
    )
    base += (
        "\n\nSPOTIFY (contrôle de l'application Spotify) :\n"
        '{"action": "spotify_ouvrir"}\n'
        '{"action": "spotify_rechercher", "recherche": "nom de la chanson ou artiste"}\n'
        '{"action": "spotify_lecture_pause"}\n'
        '{"action": "spotify_stop"}\n'
        '{"action": "spotify_suivant"}\n'
        '{"action": "spotify_precedent"}\n'
        '{"action": "spotify_volume", "direction": "monter/baisser", "paliers": 4}\n'
        "Exemples de phrases : 'ouvre Spotify', 'joue du Drake', 'mets en pause', 'stop la musique', "
        "'chanson suivante', 'reviens en arrière', 'monte le volume', 'baisse le son'.\n"
        "Note : 'paliers' est le nombre de crans de volume (1 cran = ~5%), par défaut 4.\n\n"
    )
    base += (
        "\n\nYOUTUBE / MINI PLAYER WEB (mode VM headless) :\n"
        '{"action": "music_search", "query": "nom de la chanson ou video"}\n'
        '{"action": "music_play"}\n'
        '{"action": "music_pause"}\n'
        '{"action": "music_stop"}\n'
        "Utilise ces actions quand Tom demande de lancer une musique ou une video sur YouTube dans l'interface web. "
        "Exemples : 'lance du Ninho sur YouTube', 'mets la vie qu on mene de Ninho sur YouTube', "
        "'pause YouTube', 'reprends la musique', 'stop YouTube'.\n\n"
    )
    base += (
        "\n\nMODE IRON MAN (Sécurité Domotique) :\n"
        '{"action": "mode_iron_man", "etat": "on/off"}\n'
        "Instructions : Active ou désactive la détection des applaudissements pour contrôler les lumières et YouTube.\n\n"
    )
    if contexte_memoire:
        base += "\n\n" + contexte_memoire + "\n"
    base += (
        "\nMEMOIRE :\n"
        '{"action": "memoriser", "cle": "CLE_COURTE", "valeur": "VALEUR_ICI"}\n'
        '{"action": "oublier", "cle": "CLE_ICI"}\n'
        '{"action": "lister_memoire"}\n\n'
        "GOOGLE :\n"
        '{"action": "create_doc", "title": "TITRE", "content": "CONTENU"}\n'
        '{"action": "write_doc", "content": "TEXTE"}\n'
        '{"action": "create_sheet", "title": "TITRE"}\n'
        '{"action": "read_emails"}\n'
        '{"action": "read_calendar"}\n\n'
        "WHATSAPP :\n"
        '{"action": "whatsapp_appel", "contact": "NOM_DU_CONTACT"}\n'
        "Note : Si Tom demande d'appeler 'mon amour', utilise le contact 'Ma vie'.\n\n"
        "IMAGES :\n"
        '{"action": "generate_image", "prompt": "description de l image a generer"}\n'
        "Utilise cette action quand Tom demande de generer, creer ou faire une image.\n\n"
        "VISION (Interactions avec l'ecran et camera):\n"
        '{"action": "voir_ecran", "instruction": "ou cliquer EXACTEMENT (ex: \'bouton reduire en haut a droite\')"}\n'
        '{"action": "vision_ecrire", "instruction": "ou cliquer", "texte": "le texte a taper"}\n'
        '{"action": "vision_chercher_sur_site", "texte": "ce que Tom veut rechercher"}\n'
        '{"action": "lance_camera"}\n'
        '{"action": "vision_navigateur"}\n'
        "IMPORTANT : Utilise 'voir_ecran' pour un simple CLIC (par exemple quand Tom dit 'clique sur la musique numéro 2' ou 'clique sur Play'), "
        "'vision_ecrire' pour TAPER dans un champ precis, 'vision_chercher_sur_site' quand Tom dit 'recherche sur ce site', 'tape sur ce site', 'cherche ici' ou similaire, "
        "'lance_camera' pour activer la WEBCAM / CAMERA PHYSIQUE (quand il dit 'active la camera' ou 'montre-moi'), "
        "et 'vision_navigateur' pour utiliser la vision du navigateur web (quand il dit 'active la vision' ou 'regarde mon ecran').\n\n"
        "REGLES MULTI-COMMANDES :\n"
        "Si Tom demande plusieurs choses en une seule phrase, tu PEUX et DOIS générer plusieurs blocs JSON.\n"
        "Exemple: { \"action\": \"ha_lumiere\", ... } { \"action\": \"meteo\", ... }\n\n"
        "REGLE ABSOLUE : Si la demande n est PAS une commande JSON, reponds TOUJOURS en texte naturel, sans JSON."
    )
    return base

historique = []

is_listening = False
is_speaking  = False
is_thinking  = False
speak_volume = 0.0

WAKE_WORD       = "jarvis"
SLEEP_PHRASES   = ["tais toi", "silence", "ferme-la", "arrete", "stop"]
jarvis_actif    = False
SESSION_TIMEOUT = 30.0
dernier_message = time.time()

dernier_doc_id    = None
dernier_doc_titre = None

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

def get_google_creds():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                print("[GOOGLE] Pas de credentials.json - fonctions Google desactivees.")
                return None
            flow  = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as f:
            pickle.dump(creds, f)
    return creds

def get_docs_service():
    creds = get_google_creds()
    return build("docs", "v1", credentials=creds) if creds else None

def get_drive_service():
    creds = get_google_creds()
    return build("drive", "v3", credentials=creds) if creds else None

def get_gmail_service():
    creds = get_google_creds()
    return build("gmail", "v1", credentials=creds) if creds else None

def get_sheets_service():
    creds = get_google_creds()
    return build("sheets", "v4", credentials=creds) if creds else None

def get_calendar_service():
    creds = get_google_creds()
    return build("calendar", "v3", credentials=creds) if creds else None

def creer_google_doc(titre="Nouveau Document", contenu=""):
    global dernier_doc_id, dernier_doc_titre
    try:
        service = get_docs_service()
        if not service:
            return "Google Docs non disponible."
        doc    = service.documents().create(body={"title": titre}).execute()
        doc_id = doc["documentId"]
        dernier_doc_id    = doc_id
        dernier_doc_titre = titre
        if contenu:
            requests_body = [{"insertText": {"location": {"index": 1}, "text": contenu}}]
            service.documents().batchUpdate(documentId=doc_id, body={"requests": requests_body}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{doc_id}/edit")
        return f"Document {titre} cree et ouvert, Tom."
    except Exception as e:
        return f"Erreur Google Docs : {e}"

def modifier_google_doc(contenu, doc_id=None):
    global dernier_doc_id
    try:
        service   = get_docs_service()
        if not service:
            return "Google Docs non disponible."
        target_id = doc_id or dernier_doc_id
        if not target_id:
            return "Aucun document ouvert en memoire."
        doc       = service.documents().get(documentId=target_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        requests_body = [{"insertText": {"location": {"index": end_index}, "text": "\n" + contenu}}]
        service.documents().batchUpdate(documentId=target_id, body={"requests": requests_body}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{target_id}/edit")
        return f"Texte ajoute dans le document {dernier_doc_titre}."
    except Exception as e:
        return f"Erreur modification doc : {e}"

def lire_emails(max_results=3):
    try:
        service  = get_gmail_service()
        if not service:
            return "Gmail non disponible."
        results  = service.users().messages().list(userId="me", maxResults=max_results, labelIds=["INBOX"]).execute()
        messages = results.get("messages", [])
        if not messages:
            return "Aucun email trouve."
        reponse = ""
        for msg in messages:
            m       = service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
            headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
            reponse += f"De: {headers.get('From','?')} | Sujet: {headers.get('Subject','?')}\n"
        return reponse.strip()
    except Exception as e:
        return f"Erreur Gmail : {e}"

def lister_evenements_calendar():
    try:
        service = get_calendar_service()
        if not service:
            return "Google Calendar non disponible."
        from datetime import datetime, timezone
        now    = datetime.now(timezone.utc).isoformat()
        events = service.events().list(calendarId="primary", timeMin=now, maxResults=5, singleEvents=True, orderBy="startTime").execute()
        items = events.get("items", [])
        if not items:
            return "Aucun evenement a venir."
        reponse = ""
        for e in items:
            start    = e["start"].get("dateTime", e["start"].get("date"))
            reponse += f"{start} : {e['summary']}\n"
        return reponse.strip()
    except Exception as e:
        return f"Erreur Calendar : {e}"

def creer_google_sheet(titre="Nouvelle Feuille"):
    try:
        service  = get_sheets_service()
        if not service:
            return "Google Sheets non disponible."
        sheet    = service.spreadsheets().create(body={"properties": {"title": titre}}).execute()
        sheet_id = sheet["spreadsheetId"]
        webbrowser.open(f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
        return f"Feuille {titre} creee et ouverte."
    except Exception as e:
        return f"Erreur Google Sheets : {e}"

def _screenshot_linux(path):
    """
    Prend une capture d'écran sur Linux.
    Essaie pyautogui (X11), puis scrot, gnome-screenshot, grim (Wayland).
    Retourne True si réussi.
    """
    # 1. pyautogui (fonctionne sur X11 / XWayland)
    try:
        img = pyautogui.screenshot()
        img.save(path)
        return True
    except Exception:
        pass
    # 2. scrot (X11)
    try:
        r = subprocess.run(["scrot", path], capture_output=True, timeout=5)
        if r.returncode == 0 and os.path.exists(path):
            return True
    except Exception:
        pass
    # 3. gnome-screenshot
    try:
        r = subprocess.run(["gnome-screenshot", "-f", path], capture_output=True, timeout=5)
        if r.returncode == 0 and os.path.exists(path):
            return True
    except Exception:
        pass
    # 4. grim (Wayland natif)
    try:
        r = subprocess.run(["grim", path], capture_output=True, timeout=5)
        if r.returncode == 0 and os.path.exists(path):
            return True
    except Exception:
        pass
    # 5. import ImageMagick
    try:
        r = subprocess.run(["import", "-window", "root", path], capture_output=True, timeout=5)
        if r.returncode == 0 and os.path.exists(path):
            return True
    except Exception:
        pass
    return False

async def jarvis_vision_cliquer(instruction):
    try:
        if not client:
            return "Gemini n'est pas configure sur cette machine, Tom. La vision n'est donc pas disponible."
        # On attend un peu que l'UI soit stable
        time.sleep(0.5)
        path_ss = "jarvis_vision_temp.png"
        if not _screenshot_linux(path_ss):
            return "Désolé Tom, je n'ai pas pu capturer l'écran sur ce système (X11/Wayland non disponible)."
        img = Image.open(path_ss)
        img_w, img_h = img.size
        prompt_vision = (
            f"Tu es l'oeil de J.A.R.V.I.S. Voici une capture de l'écran de Tom ({img_w}x{img_h} pixels).\n"
            f"Instruction : {instruction}\n"
            "Trouve l'élément demandé (bouton, texte, icône ou numéro dans une liste) sur l'écran.\n"
            "Si l'instruction mentionne un chiffre (ex: 'musique numéro 4'), cherche ce chiffre ou le morceau correspondant dans la liste.\n"
            "Réponds UNIQUEMENT en JSON avec ce format :\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"description courte de l'élément\"}\n"
            "Les coordonnées sont normalisées de 0 à 1000 (0=coin haut-gauche, 1000=coin bas-droit)."
        )
        response = await gemini_generate_with_failover(model=CHOSEN_MODEL, contents=[prompt_vision, img], timeout=15.0)
        rep_text = response.text.strip()
        print(f"[VISION] Gemini a renvoyé : {rep_text}")
        start = rep_text.find('{')
        end = rep_text.rfind('}')
        if start != -1 and end != -1:
            rep_text = rep_text[start:end+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        # Centre de la bounding box, converti en pixels réels via les dimensions de la capture
        center_y = (ymin + ymax) / 2
        center_x = (xmin + xmax) / 2
        target_x = int((center_x / 1000) * img_w)
        target_y = int((center_y / 1000) * img_h)
        
        print(f"[VISION] Cible identifiée : {data.get('description', 'inconnu')} à ({target_x}, {target_y})")

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.2)
        
        # DOUBLE-CLIC si c'est une musique ou un chiffre pour être sûr de lancer la lecture
        t_inst = instruction.lower()
        if any(keyword in t_inst for keyword in ["musique", "chanson", "piste", "numéro", "numero", "titre"]):
            print(f"[VISION] Double-clic sur l'élément de liste : {target_x}, {target_y}")
            pyautogui.doubleClick()
        else:
            pyautogui.click()

        if os.path.exists(path_ss):
            os.remove(path_ss)
        desc = data.get("description", instruction)
        return f"C'est fait Tom, j'ai cliqué sur : {desc}."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return "Je vois l'interface, mais je n'ai pas réussi à identifier l'élément précis, Tom."

async def jarvis_vision_ecrire(instruction, texte_a_taper):
    try:
        if not client:
            return "Gemini n'est pas configure sur cette machine, Tom. La vision n'est donc pas disponible."
        import pyperclip
        path_ss = "jarvis_vision_temp.png"
        if not _screenshot_linux(path_ss):
            return "Désolé Tom, je n'ai pas pu capturer l'écran sur ce système (X11/Wayland non disponible)."
        img = Image.open(path_ss)
        img_w, img_h = img.size
        prompt_vision = (
            f"Tu es la vision de J.A.R.V.I.S. Tom veut écrire dans le champ : {instruction}.\n"
            f"Résolution de la capture : {img_w}x{img_h} pixels.\n"
            "Trouve EXACTEMENT la position de ce champ de saisie de texte.\n"
            "Les coordonnées sont normalisées de 0 à 1000.\n"
            "Réponds UNIQUEMENT en JSON :\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"description du champ\"}\n"
            "Exemple : {\"box\": [250, 480, 290, 520], \"description\": \"champ de recherche Google\"}"
        )
        response = await gemini_generate_with_failover(model=CHOSEN_MODEL, contents=[prompt_vision, img], timeout=15.0)
        rep_text = response.text.strip()
        start = rep_text.find('{')
        end = rep_text.rfind('}')
        if start != -1 and end != -1:
            rep_text = rep_text[start:end+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        center_y = (ymin + ymax) / 2
        center_x = (xmin + xmax) / 2
        target_x = int((center_x / 1000) * img_w)
        target_y = int((center_y / 1000) * img_h)

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.15)
        pyautogui.click()
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')  # Effacer le contenu existant
        time.sleep(0.1)
        # Coller via presse-papiers pour supporter les accents et caractères spéciaux
        pyperclip.copy(texte_a_taper)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        pyautogui.press('enter')

        if os.path.exists(path_ss):
            os.remove(path_ss)
        return f"C'est fait Tom. J'ai saisi '{texte_a_taper}' dans {instruction}."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return "J'ai eu un petit souci technique pour taper le texte, Tom."

async def jarvis_vision_rechercher_sur_site(texte_recherche):
    """Trouve la barre de recherche sur la page actuelle et tape la requête."""
    try:
        if not client:
            return "Gemini n'est pas configure sur cette machine, Tom. La vision n'est donc pas disponible."
        import pyperclip
        path_ss = "jarvis_vision_temp.png"
        if not _screenshot_linux(path_ss):
            return "Désolé Tom, je n'ai pas pu capturer l'écran sur ce système (X11/Wayland non disponible)."
        img = Image.open(path_ss)
        img_w, img_h = img.size
        prompt_vision = (
            f"Tu es la vision de J.A.R.V.I.S. Tom veut faire une recherche sur le site affiché à l'écran.\n"
            f"Résolution de la capture : {img_w}x{img_h} pixels.\n"
            "Localise la BARRE DE RECHERCHE principale du site (champ search, zone avec icône loupe, "
            "placeholder 'Rechercher', 'Search', 'Chercher'...).\n"
            "Si tu vois une barre d'adresse de navigateur ET une barre de recherche du site, "
            "préfère la barre de recherche du site.\n"
            "Les coordonnées sont normalisées de 0 à 1000 (0=haut-gauche, 1000=bas-droite).\n"
            "Réponds UNIQUEMENT en JSON :\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"description de la barre trouvée\"}\n"
            "Exemple : {\"box\": [48, 220, 78, 820], \"description\": \"barre de recherche YouTube\"}"
        )
        response = await gemini_generate_with_failover(model=CHOSEN_MODEL, contents=[prompt_vision, img], timeout=15.0)
        rep_text = response.text.strip()
        start = rep_text.find('{')
        end = rep_text.rfind('}')
        if start != -1 and end != -1:
            rep_text = rep_text[start:end+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        center_y = (ymin + ymax) / 2
        center_x = (xmin + xmax) / 2
        target_x = int((center_x / 1000) * img_w)
        target_y = int((center_y / 1000) * img_h)

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.15)
        pyautogui.click()
        time.sleep(0.35)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyperclip.copy(texte_recherche)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.15)
        pyautogui.press('enter')

        if os.path.exists(path_ss):
            os.remove(path_ss)
        desc = data.get("description", "barre de recherche")
        return f"C'est fait Tom ! J'ai tapé '{texte_recherche}' dans la {desc} et j'ai validé."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return "Je n'ai pas réussi à trouver la barre de recherche sur ce site, Tom."

async def jarvis_vision_camera(question_utilisateur=None):
    """Capture une image depuis la caméra et l'analyse avec Gemini Vision."""
    if cv2 is None:
        return "Désolé Tom, le module de vision par caméra (OpenCV) n'est pas installé."
    
    try:
        # Sur Linux, on utilise le backend V4L2 par défaut
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            return "Désolé Tom, je n'arrive pas à accéder à votre caméra. Vérifiez qu'elle est bien connectée."
        
        # Configurer la résolution (720p)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        
        # Laisser la webcam s'ajuster (exposition, balance des blancs)
        # Les webcams de laptop ont besoin de 2-3 secondes minimum
        import time as _t
        for i in range(30):
            cap.read()
            _t.sleep(0.1)  # ~3 secondes au total
            
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            return "Désolé Tom, je n'ai pas pu capturer d'image depuis la caméra."
        
        # Vérifier que l'image n'est pas toute noire
        if frame.mean() < 5:
            return "Désolé Tom, la caméra renvoie une image noire. Vérifiez que rien ne bloque l'objectif ou que la webcam fonctionne dans une autre application."
        
        # Enregistrement temporaire
        path_cam = "jarvis_camera_temp.jpg"
        cv2.imwrite(path_cam, frame)
        
        # Analyse avec Gemini
        with open(path_cam, "rb") as f:
            img_bytes = f.read()
            
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        os.remove(path_cam)
        
        # Prompt adapté au contexte de la demande
        if question_utilisateur:
            prompt_cam = f"Tom te montre une image via sa caméra. Sa demande : '{question_utilisateur}'. Analyse l'image et réponds précisément à sa demande."
        else:
            prompt_cam = "Analyse cette image de la caméra de Tom et décris-lui ce que tu vois en détail."
        
        await parler("C'est fait Tom, je regarde ce que votre caméra voit...")
        reponse = await demander_ia_vision(prompt_cam, img_b64)
        return reponse
        
    except Exception as e:
        print(f"[CAMERA ERROR] {e}")
        return f"Désolé Tom, une erreur est survenue lors de l'accès à la caméra : {e}"

async def jarvis_vision_navigateur(question_utilisateur=None):
    """Capture une image depuis le navigateur via WebSocket et l'analyse avec Gemini Vision."""
    try:
        if not CONNECTED_CLIENTS:
            return "Désolé Tom, l'interface web (navigateur) n'est pas connectée actuellement."
            
        await parler("J'active la vision du navigateur, un instant Tom...")
        img_b64 = await request_screen_capture()
        
        if not img_b64:
            return "Désolé Tom, le flux vidéo est inactif. Pensez bien à cliquer sur le bouton 'Activer la vision' en haut à droite de l'interface web."
            
        if question_utilisateur:
            prompt_vision = f"Tom te montre son navigateur/écran. Sa demande : '{question_utilisateur}'. Analyse l'image et réponds précisément."
        else:
            prompt_vision = "Analyse cette capture du navigateur/écran de Tom et décris-lui ce que tu vois en détail."
            
        reponse = await demander_ia_vision(prompt_vision, img_b64)
        return reponse
        
    except Exception as e:
        print(f"[VISION NAVIGATEUR ERROR] {e}")
        return f"Désolé Tom, une erreur est survenue lors de l'accès à la vision du navigateur : {e}"

def est_instruction_vision_descriptive(instruction):
    t = (instruction or "").lower()
    return any(expr in t for expr in [
        "decris", "décris", "resume", "résume", "que vois", "qu'est-ce que tu vois",
        "qu est ce que tu vois", "analyse", "lis", "resumer", "résumer"
    ])

def ha_appeler_service(domaine, service, entity_id, donnees=None):
    if not HA_CONFIGURED:
        print("[HA] Integration non configuree, appel ignore.")
        return False
    try:
        payload = {"entity_id": entity_id}
        if donnees:
            payload.update(donnees)
        print(f"[HA DEBUG] Calling {domaine}/{service} for {entity_id} with {donnees}")
        r = requests.post(f"{HA_URL}/api/services/{domaine}/{service}", headers=HA_HEADERS, json=payload, timeout=5)
        print(f"[HA DEBUG] Response {r.status_code}: {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[HA] Erreur service : {e}")
        return False

def ha_get_etat(entity_id, attribut=None):
    if not HA_CONFIGURED:
        return "inconnu"
    try:
        r    = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=HA_HEADERS, timeout=5)
        data = r.json()
        if attribut:
            return data.get("attributes", {}).get(attribut, "inconnu")
        return data.get("state", "inconnu")
    except Exception as e:
        print(f"[HA] Erreur get etat : {e}")
        return "inconnu"

def ha_get_calendrier(entity_id):
    if not HA_CONFIGURED:
        return []
    try:
        now = datetime.now()
        start = now.strftime("%Y-%m-%dT00:00:00Z")
        end = now.strftime("%Y-%m-%dT23:59:59Z")
        r = requests.get(
            f"{HA_URL}/api/calendars/{entity_id}",
            headers=HA_HEADERS,
            params={"start": start, "end": end},
            timeout=5
        )
        return r.json()
    except Exception as e:
        print(f"[HA] Erreur calendrier : {e}")
        return []

def _normalize_search_text(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9']+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def ha_get_all_states():
    if not HA_CONFIGURED:
        return []
    try:
        r = requests.get(f"{HA_URL}/api/states", headers=HA_HEADERS, timeout=8)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"[HA] Erreur get all states : {e}")
        return []

def ha_find_first_entity_by_domain(domain):
    prefix = f"{domain}."
    for state in ha_get_all_states():
        entity_id = state.get("entity_id", "")
        if entity_id.startswith(prefix):
            return state
    return None

PRONOTE_ALIASES = {
    "class": ["class"],
    "current_period": ["current period"],
    "overall_average": ["overall average"],
    "today_timetable": ["today's timetable", "today timetable"],
    "tomorrow_timetable": ["tomorrow's timetable", "tomorrow timetable", "next day's timetable", "next day timetable"],
    "homework": ["homework", "period's homework", "period homework"],
    "grades": ["grades"],
    "evaluations": ["evaluations"],
    "absences": ["absences"],
    "delays": ["delays"],
    "next_alarm": ["next alarm"],
    "information": ["information and surveys"],
}

def ha_find_entity_by_aliases(aliases):
    aliases_norm = [_normalize_search_text(a) for a in aliases]
    best = None
    best_score = -1
    for state in ha_get_all_states():
        entity_id = state.get("entity_id", "")
        attrs = state.get("attributes", {})
        friendly = attrs.get("friendly_name", entity_id)
        haystack = f"{entity_id} {friendly}"
        haystack_norm = _normalize_search_text(haystack)
        score = 0
        for alias in aliases_norm:
            if alias == haystack_norm:
                score = max(score, 100)
            elif alias in _normalize_search_text(str(friendly)):
                score = max(score, 80)
            elif alias in haystack_norm:
                score = max(score, 60)
        if score > best_score:
            best_score = score
            best = state
    return best if best_score > 0 else None

def _pronote_extract_items(state):
    attrs = (state or {}).get("attributes", {})
    for key, value in attrs.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[:8]
    return []

def _pronote_item_to_text(item):
    if not isinstance(item, dict):
        return str(item)
    sujet = item.get("subject") or item.get("matiere") or item.get("course") or item.get("lesson") or item.get("title") or item.get("name") or item.get("summary")
    detail = item.get("description") or item.get("content") or item.get("work") or item.get("teacher")
    debut = item.get("start") or item.get("from") or item.get("begin")
    fin = item.get("end") or item.get("to")
    morceaux = []
    if sujet:
        morceaux.append(str(sujet))
    if debut:
        morceaux.append(f"a {str(debut)[11:16] if 'T' in str(debut) else debut}")
    if fin:
        morceaux.append(f"jusqu'a {str(fin)[11:16] if 'T' in str(fin) else fin}")
    if detail and str(detail) not in morceaux:
        morceaux.append(str(detail))
    return ", ".join(morceaux) if morceaux else str(item)

def pronote_home_assistant_resume():
    if not HA_CONFIGURED:
        return "Home Assistant n'est pas configure, Tom."

    classe = ha_find_entity_by_aliases(PRONOTE_ALIASES["class"])
    periode = ha_find_entity_by_aliases(PRONOTE_ALIASES["current_period"])
    moyenne = ha_find_entity_by_aliases(PRONOTE_ALIASES["overall_average"])
    devoirs = ha_find_entity_by_aliases(PRONOTE_ALIASES["homework"])
    absences = ha_find_entity_by_aliases(PRONOTE_ALIASES["absences"])
    retards = ha_find_entity_by_aliases(PRONOTE_ALIASES["delays"])
    reveil = ha_find_entity_by_aliases(PRONOTE_ALIASES["next_alarm"])

    morceaux = []
    if classe:
        morceaux.append(f"Classe {classe.get('state')}")
    if periode:
        morceaux.append(f"periode actuelle {periode.get('state')}")
    if moyenne:
        morceaux.append(f"moyenne generale {moyenne.get('state')}")
    if devoirs:
        morceaux.append(f"{devoirs.get('state')} devoir")
    if absences:
        morceaux.append(f"{absences.get('state')} absence")
    if retards:
        morceaux.append(f"{retards.get('state')} retard")
    if reveil:
        morceaux.append(f"prochaine alerte {reveil.get('state')}")
    if not morceaux:
        return "Je n'ai pas trouve les entites Pronote dans Home Assistant, Tom."
    return "Resume Pronote : " + ", ".join(morceaux) + "."

def pronote_timetable_resume(day="today"):
    aliases = PRONOTE_ALIASES["tomorrow_timetable"] if day == "tomorrow" else PRONOTE_ALIASES["today_timetable"]
    state = ha_find_entity_by_aliases(aliases)
    if not state:
        return "Je n'ai pas trouve l'emploi du temps Pronote correspondant, Tom."
    count = state.get("state", "0")
    items = _pronote_extract_items(state)
    if items:
        details = "; ".join(_pronote_item_to_text(item) for item in items[:6])
        return f"Votre emploi du temps {'de demain' if day == 'tomorrow' else 'd aujourd hui'} : {details}."
    return f"Vous avez {count} cours {'demain' if day == 'tomorrow' else 'aujourd hui'}, Tom."

def pronote_homework_resume():
    state = ha_find_entity_by_aliases(PRONOTE_ALIASES["homework"])
    if not state:
        return "Je n'ai pas trouve les devoirs Pronote dans Home Assistant, Tom."
    count = state.get("state", "0")
    items = _pronote_extract_items(state)
    if items:
        details = "; ".join(_pronote_item_to_text(item) for item in items[:5])
        return f"Voici vos devoirs : {details}."
    return f"Il vous reste {count} devoir a faire, Tom."

def pronote_grades_resume():
    moyenne = ha_find_entity_by_aliases(PRONOTE_ALIASES["overall_average"])
    notes = ha_find_entity_by_aliases(PRONOTE_ALIASES["grades"])
    evaluations = ha_find_entity_by_aliases(PRONOTE_ALIASES["evaluations"])
    morceaux = []
    if moyenne:
        morceaux.append(f"moyenne generale {moyenne.get('state')}")
    if notes:
        morceaux.append(f"{notes.get('state')} note")
    if evaluations:
        morceaux.append(f"{evaluations.get('state')} evaluation")
    if not morceaux:
        return "Je n'ai pas trouve les notes Pronote dans Home Assistant, Tom."
    return "Cote scolaire : " + ", ".join(morceaux) + "."

def ha_lumiere(entity_id, etat="on", luminosite=None, rgb=None):
    service_name = "toggle" if etat == "toggle" else ("turn_on" if etat == "on" else "turn_off")
    donnees = {}
    if etat == "on":
        if luminosite is not None:
            donnees["brightness"] = int(luminosite)
        if rgb is not None:
            donnees["rgb_color"] = rgb
    return ha_appeler_service("light", service_name, entity_id, donnees)

def ha_interrupteur(entity_id, etat="on"):
    service_name = "turn_on" if etat == "on" else "turn_off"
    return ha_appeler_service("switch", service_name, entity_id)

def ha_thermostat(entity_id, temperature):
    return ha_appeler_service("climate", "set_temperature", entity_id, {"temperature": temperature})

def ha_scene(scene_id):
    return ha_appeler_service("scene", "turn_on", scene_id)

def proxmox_est_configure():
    return PROXMOX_CONFIGURED

def proxmox_headers():
    return {
        "Authorization": f"PVEAPIToken={PROXMOX_TOKEN_ID}={PROXMOX_TOKEN_SECRET}"
    }

def proxmox_api_get(path, params=None):
    if not proxmox_est_configure():
        raise RuntimeError("Proxmox n'est pas configure dans le fichier d'environnement.")

    url = f"{PROXMOX_URL.rstrip('/')}/api2/json{path}"
    response = requests.get(
        url,
        headers=proxmox_headers(),
        params=params,
        timeout=8,
        verify=PROXMOX_VERIFY_SSL
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("data", payload)

def proxmox_api_post(path, data=None):
    if not proxmox_est_configure():
        raise RuntimeError("Proxmox n'est pas configure dans le fichier d'environnement.")

    url = f"{PROXMOX_URL.rstrip('/')}/api2/json{path}"
    response = requests.post(
        url,
        headers=proxmox_headers(),
        data=data,
        timeout=10,
        verify=PROXMOX_VERIFY_SSL
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("data", payload)

def proxmox_api_put(path, data=None):
    if not proxmox_est_configure():
        raise RuntimeError("Proxmox n'est pas configure dans le fichier d'environnement.")

    url = f"{PROXMOX_URL.rstrip('/')}/api2/json{path}"
    response = requests.put(
        url,
        headers=proxmox_headers(),
        data=data,
        timeout=10,
        verify=PROXMOX_VERIFY_SSL
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("data", payload)

def _format_pct_fraction(value):
    try:
        return int(round(float(value) * 100))
    except Exception:
        return 0

def _format_usage_pct(used, total):
    try:
        used_f = float(used or 0)
        total_f = float(total or 0)
        if total_f <= 0:
            return 0
        return int(round((used_f / total_f) * 100))
    except Exception:
        return 0

def _proxmox_guest_label(guest):
    nom = guest.get("name") or f"{guest.get('type', 'vm').upper()} {guest.get('vmid', '?')}"
    genre = "VM" if guest.get("type") == "qemu" else "CT"
    return genre, nom

def proxmox_lister_noeuds():
    nodes = proxmox_api_get("/nodes")
    return sorted(nodes, key=lambda node: node.get("node", ""))

def proxmox_lister_resources():
    resources = proxmox_api_get("/cluster/resources")
    return resources if isinstance(resources, list) else []

def proxmox_lister_guests():
    try:
        resources = proxmox_lister_resources()
        guests = [r for r in resources if r.get("type") in ("qemu", "lxc")]
        if guests:
            return sorted(guests, key=lambda guest: (guest.get("node", ""), guest.get("type", ""), guest.get("vmid", 0)))
    except Exception as e:
        print(f"[PROXMOX] Fallback cluster/resources impossible : {e}")

    guests = []
    for node in proxmox_lister_noeuds():
        node_name = node.get("node")
        if not node_name:
            continue
        for guest_type, endpoint in (("qemu", "qemu"), ("lxc", "lxc")):
            try:
                items = proxmox_api_get(f"/nodes/{node_name}/{endpoint}")
                for item in items:
                    item["type"] = guest_type
                    item["node"] = node_name
                    guests.append(item)
            except Exception as e:
                print(f"[PROXMOX] Impossible de lire {guest_type} sur {node_name} : {e}")
    return sorted(guests, key=lambda guest: (guest.get("node", ""), guest.get("type", ""), guest.get("vmid", 0)))

def proxmox_trouver_guest(cible):
    if cible is None:
        return None
    cible_str = str(cible).strip().lower()
    if not cible_str:
        return None

    guests = proxmox_lister_guests()
    exact = []
    partial = []
    for guest in guests:
        vmid = str(guest.get("vmid", "")).strip().lower()
        name = str(guest.get("name", "")).strip().lower()
        if cible_str == vmid or (name and cible_str == name):
            exact.append(guest)
        elif cible_str in vmid or (name and cible_str in name):
            partial.append(guest)
    if exact:
        return exact[0]
    if partial:
        return partial[0]
    return None

def proxmox_resume_noeuds():
    try:
        nodes = proxmox_lister_noeuds()
        resources = proxmox_lister_resources()
    except Exception as e:
        print(f"[PROXMOX] Erreur noeuds : {e}")
        return f"Je n'arrive pas a lire les noeuds Proxmox, Tom. {e}"

    resource_map = {
        resource.get("node"): resource
        for resource in resources
        if resource.get("type") == "node"
    }
    if not nodes:
        return "Je ne vois aucun noeud Proxmox, Tom."

    phrases = []
    for node in nodes[:6]:
        node_name = node.get("node", "inconnu")
        resource = resource_map.get(node_name, {})
        status = node.get("status", resource.get("status", "inconnu"))
        cpu = _format_pct_fraction(resource.get("cpu", 0))
        mem_pct = _format_usage_pct(resource.get("mem", 0), resource.get("maxmem", 0))
        disk_pct = _format_usage_pct(resource.get("disk", 0), resource.get("maxdisk", 0))
        phrases.append(
            f"Noeud {node_name} : {status}, CPU {cpu} pour cent, RAM {mem_pct} pour cent, stockage {disk_pct} pour cent."
        )
    return " ".join(phrases)

def proxmox_resume_stockages():
    try:
        resources = proxmox_lister_resources()
    except Exception as e:
        print(f"[PROXMOX] Erreur stockages : {e}")
        return f"Je n'arrive pas a lire les stockages Proxmox, Tom. {e}"

    storages = [r for r in resources if r.get("type") == "storage"]
    if not storages:
        return "Je ne vois aucun stockage remonte par Proxmox, Tom."

    phrases = []
    for storage in storages[:10]:
        nom = storage.get("storage", "inconnu")
        node = storage.get("node", "cluster")
        status = storage.get("status", "inconnu")
        used_pct = _format_usage_pct(storage.get("disk", 0), storage.get("maxdisk", 0))
        phrases.append(f"Stockage {nom} sur {node} : {status}, occupation {used_pct} pour cent.")
    return " ".join(phrases)

def proxmox_resume_utilisateurs():
    try:
        users = proxmox_api_get("/access/users")
    except Exception as e:
        print(f"[PROXMOX] Erreur utilisateurs : {e}")
        return f"Je n'arrive pas a lire les utilisateurs Proxmox, Tom. {e}"

    if not users:
        return "Je ne vois aucun utilisateur Proxmox, Tom."

    lignes = []
    for user in users[:15]:
        userid = user.get("userid", "inconnu")
        enabled = user.get("enable", 1)
        prenom_nom = user.get("firstname") or user.get("lastname")
        commentaire = user.get("comment", "")
        statut = "actif" if str(enabled) not in ("0", "False", "false") else "desactive"
        detail = prenom_nom or commentaire
        if detail:
            lignes.append(f"{userid} : {statut}, {detail}.")
        else:
            lignes.append(f"{userid} : {statut}.")
    if len(users) > 15:
        lignes.append(f"Et {len(users) - 15} autre(s) utilisateur(s).")
    return " ".join(lignes)

def proxmox_lister_utilisateurs():
    users = proxmox_api_get("/access/users")
    return users if isinstance(users, list) else []

def proxmox_nettoyer_cible_utilisateur(cible):
    texte = str(cible or "").strip().lower()
    if not texte:
        return ""
    remplacements_directs = [
        "sur proxmox", "dans proxmox", "proxmox",
        "utilisateur", "l'utilisateur", "user", "compte",
        "permission", "permissions", "perm", "droits",
        "administrateur", "administrator", "admin",
    ]
    for bruit in remplacements_directs:
        texte = texte.replace(bruit, " ")
    texte = re.sub(r"\b(?:a|à)\b", " ", texte)
    mots = [mot for mot in texte.split() if mot]
    return " ".join(mots)

def proxmox_extraire_identifiant_utilisateur(texte):
    t = str(texte or "").lower()
    faux_positifs = {
        "permission", "permissions", "administrateur", "administrator",
        "admin", "groupe", "role", "rôle", "droits", "perm"
    }
    patterns = [
        r"\b(?:a|à)\b\s+l(?:'| )?(?:user|utilisateur)\s+([a-z0-9_.@-]+)",
        r"(?:user|utilisateur|compte)\s+([a-z0-9_.@-]+)",
        r"\b(?:a|à)\b\s+([a-z0-9_.@-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, t)
        if match:
            candidat = match.group(1).strip()
            if candidat in faux_positifs:
                continue
            return candidat
    return ""

def proxmox_trouver_utilisateur(cible):
    if cible is None:
        return None
    cible_brut = str(cible).strip().lower()
    cible_str = proxmox_extraire_identifiant_utilisateur(cible_brut) or proxmox_nettoyer_cible_utilisateur(cible_brut)
    if not cible_str:
        return None

    cible_tokens = [token for token in re.split(r"[^a-z0-9@._-]+", cible_str) if token]
    users = proxmox_lister_utilisateurs()
    exact = []
    scored = []
    for user in users:
        userid = str(user.get("userid", "")).strip().lower()
        username = userid.split("@", 1)[0] if "@" in userid else userid
        if cible_str in (userid, username):
            exact.append(user)
            continue

        score = 0
        if cible_tokens:
            if any(token == username for token in cible_tokens):
                score = max(score, 120)
            elif any(token == userid for token in cible_tokens):
                score = max(score, 110)
        if cible_str in userid or cible_str in username:
            score = max(score, 60)
        if cible_tokens:
            if any(token in username for token in cible_tokens):
                score = max(score, 40)
        if score:
            scored.append((score, user))
    if exact:
        return exact[0]
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]
    return None

def proxmox_normaliser_role(role):
    role_map = {
        "admin": "Administrator",
        "administrateur": "Administrator",
        "administrator": "Administrator",
        "auditeur": "PVEAuditor",
        "auditor": "PVEAuditor",
        "lecture": "PVEAuditor",
        "readonly": "PVEAuditor",
        "read only": "PVEAuditor",
        "vm admin": "PVEVMAdmin",
        "vmadmin": "PVEVMAdmin",
        "pvevmadmin": "PVEVMAdmin",
        "user admin": "PVEUserAdmin",
        "useradmin": "PVEUserAdmin",
        "pveuseradmin": "PVEUserAdmin",
    }
    role_str = str(role or "").strip().lower()
    return role_map.get(role_str, role if role else None)

def proxmox_attribuer_role_utilisateur(cible, role, path="/", propagate=True):
    try:
        user = proxmox_trouver_utilisateur(cible)
    except Exception as e:
        print(f"[PROXMOX] Erreur recherche utilisateur : {e}")
        return f"Je n'arrive pas a retrouver cet utilisateur Proxmox, Tom. {e}"

    if not user:
        return f"Je ne trouve pas d'utilisateur Proxmox correspondant a {cible}, Tom."

    role_id = proxmox_normaliser_role(role)
    if not role_id:
        return "Je n'ai pas compris le role Proxmox a attribuer, Tom."

    userid = user.get("userid")
    payload = {
        "path": path or "/",
        "users": userid,
        "roles": role_id,
        "propagate": 1 if propagate else 0,
    }
    try:
        proxmox_api_put("/access/acl", data=payload)
    except Exception as e:
        print(f"[PROXMOX] Erreur attribution role : {e}")
        return f"Je n'ai pas pu attribuer le role {role_id} a {userid}, Tom. {e}"

    return f"J'ai attribue le role {role_id} a {userid} sur {payload['path']}, Tom."

def proxmox_resume_guest(cible):
    try:
        guest = proxmox_trouver_guest(cible)
    except Exception as e:
        print(f"[PROXMOX] Erreur recherche guest : {e}")
        return f"Je n'arrive pas a retrouver cette VM ou ce conteneur, Tom. {e}"

    if not guest:
        return f"Je ne trouve pas de VM ou conteneur correspondant a {cible}, Tom."

    genre, nom = _proxmox_guest_label(guest)
    status = guest.get("status", "inconnu")
    cpu = _format_pct_fraction(guest.get("cpu", 0)) if status == "running" else 0
    mem_pct = _format_usage_pct(guest.get("mem", 0), guest.get("maxmem", 0))
    disk_pct = _format_usage_pct(guest.get("disk", 0), guest.get("maxdisk", 0))
    return (
        f"{genre} {nom} sur {guest.get('node', 'inconnu')} : statut {status}, "
        f"CPU {cpu} pour cent, RAM {mem_pct} pour cent, disque {disk_pct} pour cent."
    )

def proxmox_guest_action(cible, commande):
    try:
        guest = proxmox_trouver_guest(cible)
    except Exception as e:
        print(f"[PROXMOX] Erreur recherche action guest : {e}")
        return f"Je n'arrive pas a identifier cette VM ou ce conteneur, Tom. {e}"

    if not guest:
        return f"Je ne trouve pas de VM ou conteneur correspondant a {cible}, Tom."

    guest_type = guest.get("type")
    node = guest.get("node")
    vmid = guest.get("vmid")
    genre, nom = _proxmox_guest_label(guest)
    endpoint = "qemu" if guest_type == "qemu" else "lxc"
    action_map = {
        "start": "start",
        "stop": "stop",
        "shutdown": "shutdown",
        "reboot": "reboot",
        "restart": "reboot",
        "suspend": "suspend",
        "pause": "suspend",
        "resume": "resume",
    }
    proxmox_cmd = action_map.get((commande or "").strip().lower())
    if not proxmox_cmd:
        return f"Commande Proxmox inconnue : {commande}."

    status = guest.get("status")
    if proxmox_cmd == "start" and status == "running":
        return f"{genre} {nom} est deja demarre, Tom."
    if proxmox_cmd in ("stop", "shutdown", "suspend", "reboot") and status != "running":
        return f"{genre} {nom} est deja arrete, Tom."
    if proxmox_cmd == "resume" and status == "running":
        return f"{genre} {nom} est deja actif, Tom."

    try:
        proxmox_api_post(f"/nodes/{node}/{endpoint}/{vmid}/status/{proxmox_cmd}")
    except Exception as e:
        print(f"[PROXMOX] Erreur action guest : {e}")
        return f"Je n'ai pas pu executer {commande} sur {nom}, Tom. {e}"

    messages = {
        "start": f"Je demarre {genre} {nom}, Tom.",
        "stop": f"J'arrete {genre} {nom} immediatement, Tom.",
        "shutdown": f"Je demande un arret propre de {genre} {nom}, Tom.",
        "reboot": f"Je redemarre {genre} {nom}, Tom.",
        "suspend": f"Je mets {genre} {nom} en pause, Tom.",
        "resume": f"Je relance {genre} {nom}, Tom.",
    }
    return messages.get(proxmox_cmd, f"Action {proxmox_cmd} envoyee a {nom}, Tom.")

def proxmox_lister_guests_par_type(type_cible=None):
    guests = proxmox_lister_guests()
    if type_cible == "qemu":
        return [guest for guest in guests if guest.get("type") == "qemu"]
    if type_cible == "lxc":
        return [guest for guest in guests if guest.get("type") == "lxc"]
    return guests

def proxmox_action_en_masse(commande, type_cible=None, seulement_running=None):
    action_map = {
        "start": "start",
        "demarre": "start",
        "démarre": "start",
        "allume": "start",
        "lance": "start",
        "stop": "stop",
        "arrete": "stop",
        "arrête": "stop",
        "force_stop": "stop",
        "shutdown": "shutdown",
        "eteins": "shutdown",
        "éteins": "shutdown",
        "extinction": "shutdown",
        "reboot": "reboot",
        "restart": "reboot",
        "redemarre": "reboot",
        "redémarre": "reboot",
        "relance": "reboot",
        "suspend": "suspend",
        "pause": "suspend",
        "resume": "resume",
        "reprend": "resume",
    }
    proxmox_cmd = action_map.get((commande or "").strip().lower())
    if not proxmox_cmd:
        return f"Commande Proxmox inconnue : {commande}."

    try:
        guests = proxmox_lister_guests_par_type(type_cible)
    except Exception as e:
        print(f"[PROXMOX] Erreur liste action en masse : {e}")
        return f"Je n'arrive pas a lister les invites Proxmox, Tom. {e}"

    if proxmox_cmd == "start":
        guests = [guest for guest in guests if guest.get("status") != "running"]
    elif proxmox_cmd in ("stop", "shutdown", "reboot", "suspend"):
        guests = [guest for guest in guests if guest.get("status") == "running"]
    elif seulement_running is True:
        guests = [guest for guest in guests if guest.get("status") == "running"]
    elif seulement_running is False:
        guests = [guest for guest in guests if guest.get("status") != "running"]

    if not guests:
        cible_txt = "VM" if type_cible == "qemu" else ("conteneur" if type_cible == "lxc" else "instance")
        return f"Aucune {cible_txt} a traiter pour cette commande, Tom."

    succes = []
    erreurs = []
    for guest in guests:
        resultat = proxmox_guest_action(guest.get("vmid"), proxmox_cmd)
        if "Je n'ai pas pu" in resultat or "inconnue" in resultat or "Je ne trouve pas" in resultat:
            erreurs.append((guest, resultat))
        else:
            succes.append(guest)

    type_txt = "VM" if type_cible == "qemu" else ("conteneur" if type_cible == "lxc" else "instance")
    type_txt = type_txt + ("s" if len(guests) > 1 else "")
    base = f"Action {proxmox_cmd} envoyee sur {len(succes)} {type_txt}, Tom."
    if succes:
        noms = ", ".join((guest.get("name") or str(guest.get("vmid"))) for guest in succes[:6])
        base += f" Cibles : {noms}."
    if erreurs:
        noms_err = ", ".join((guest.get("name") or str(guest.get("vmid"))) for guest, _ in erreurs[:4])
        base += f" Echec sur {len(erreurs)} : {noms_err}."
    return base

def proxmox_parser_commande_directe(texte):
    t = (texte or "").lower().strip()
    if not t:
        return None

    if any(mot in t for mot in ["administrateur", "administrator", "permission admin", "perm admin", "droit admin", "droits admin", "role admin", "rôle admin"]):
        if not current_user_is_owner():
            return command_access_denied("Proxmox")
        if (
            any(mot in t for mot in ["utilisateur", "user", "luser", "compte"]) or
            re.search(r"\b(?:a|à)\b\s+[a-z0-9_.@-]+", t)
        ) and any(mot in t for mot in ["ajoute", "rajoute", "donne", "donner", "attribue", "attribuer", "mets", "mettre"]):
            identifiant_direct = proxmox_extraire_identifiant_utilisateur(t)
            if identifiant_direct:
                return proxmox_attribuer_role_utilisateur(identifiant_direct, "Administrator")
            cible = t
            prefixes = [
                "rajoute la perm administrateur a luser ",
                "rajoute la perm administrateur a l'utilisateur ",
                "rajoute la permission administrateur a luser ",
                "rajoute la permission administrateur a l'utilisateur ",
                "rajoute le role administrateur a luser ",
                "rajoute le role administrateur a l'utilisateur ",
                "ajoute la perm administrateur a luser ",
                "ajoute la permission administrateur a luser ",
                "donne la permission administrateur a luser ",
                "donne les droits admin a luser ",
                "donne le role administrateur a luser ",
                "mets administrateur a luser ",
            ]
            for prefix in prefixes:
                if cible.startswith(prefix):
                    cible = cible[len(prefix):]
                    break
            match_user = re.search(r"(?:a|à)\s+l(?:'| )?(?:user|utilisateur)\s+(.+)$", cible)
            if not match_user:
                match_user = re.search(r"(?:user|utilisateur|compte)\s+(.+)$", cible)
            if not match_user:
                match_user = re.search(r"(?:a|à)\s+([a-z0-9_.@-]+)", cible)
            if match_user:
                cible = match_user.group(1)
            identifiant = proxmox_extraire_identifiant_utilisateur(cible)
            if identifiant:
                cible = identifiant
            for bruit in [
                "sur proxmox", "dans proxmox", "proxmox",
                "a luser ", "à luser ", "a l'utilisateur ", "à l'utilisateur ",
                "a l user ", "à l user ", "utilisateur ", "user ", "compte "
            ]:
                cible = cible.replace(bruit, " ")
            cible = " ".join(cible.split())
            if cible:
                return proxmox_attribuer_role_utilisateur(cible, "Administrator")

    verbes = [
        ("reboot", ["redémarre", "redemarre", "reboot", "restart", "relance"]),
        ("shutdown", ["éteins", "eteins", "éteint", "eteint", "extinction"]),
        ("start", ["start", "démarre", "demarre", "lance", "allume"]),
        ("stop", ["stop", "arrête", "arrete", "coupe"]),
        ("suspend", ["suspend", "pause"]),
        ("resume", ["resume", "reprend"]),
    ]
    commande = None
    mots_detectes = None
    for cle, mots in verbes:
        if any(mot in t for mot in mots):
            commande = cle
            mots_detectes = mots
            break
    if not commande:
        return None

    parle_proxmox = "proxmox" in t
    parle_vm = any(mot in t for mot in [" vm", " vms", "machine virtuelle", "machines virtuelles"])
    parle_ct = any(mot in t for mot in ["conteneur", "conteneurs", " lxc", " ct "])
    parle_tout = any(mot in t for mot in ["toutes les", "tous les", "tout les", "toutes mes", "tous mes"])

    if parle_vm and parle_tout:
        seulement_running = False if commande == "start" else (True if commande in ("stop", "shutdown", "reboot", "suspend") else None)
        return proxmox_action_en_masse(commande, type_cible="qemu", seulement_running=seulement_running)
    if parle_ct and parle_tout:
        seulement_running = False if commande == "start" else (True if commande in ("stop", "shutdown", "reboot", "suspend") else None)
        return proxmox_action_en_masse(commande, type_cible="lxc", seulement_running=seulement_running)
    if parle_proxmox and parle_tout:
        seulement_running = False if commande == "start" else (True if commande in ("stop", "shutdown", "reboot", "suspend") else None)
        return proxmox_action_en_masse(commande, type_cible=None, seulement_running=seulement_running)

    cible = t
    prefixes = [
        "redémarre ", "redemarre ", "reboot ", "restart ", "relance ",
        "éteins ", "eteins ", "shutdown ", "extinction ",
        "démarre ", "demarre ", "start ", "lance ", "allume ",
        "arrête ", "arrete ", "stop ", "coupe ",
        "suspend ", "pause ", "resume ", "reprend "
    ]
    for prefix in prefixes:
        if cible.startswith(prefix):
            cible = cible[len(prefix):]
            break

    if parle_proxmox or parle_vm or parle_ct:
        for bruit in ["sur proxmox", "dans proxmox", "proxmox", "la vm", "le vm", "la machine virtuelle", "la machine", "le conteneur", "le ct", "lxc"]:
            cible = cible.replace(bruit, " ")
        cible = " ".join(cible.split())
        if cible and cible not in ["vm", "vms", "machines virtuelles", "conteneurs"]:
            return proxmox_guest_action(cible, commande)

    if cible:
        guest = proxmox_trouver_guest(cible)
        if guest:
            return proxmox_guest_action(cible, commande)
    return None

def proxmox_resume_snapshots(cible):
    try:
        guest = proxmox_trouver_guest(cible)
    except Exception as e:
        print(f"[PROXMOX] Erreur snapshots : {e}")
        return f"Je n'arrive pas a lire les snapshots pour {cible}, Tom. {e}"

    if not guest:
        return f"Je ne trouve pas de VM ou conteneur correspondant a {cible}, Tom."

    endpoint = "qemu" if guest.get("type") == "qemu" else "lxc"
    try:
        snapshots = proxmox_api_get(f"/nodes/{guest.get('node')}/{endpoint}/{guest.get('vmid')}/snapshot")
    except Exception as e:
        print(f"[PROXMOX] Erreur lecture snapshots : {e}")
        return f"Je n'ai pas pu lire les snapshots de {cible}, Tom. {e}"

    utiles = [snap for snap in snapshots if snap.get("name") != "current"]
    if not utiles:
        return f"Je ne vois aucun snapshot pour {guest.get('name') or guest.get('vmid')}, Tom."
    noms = ", ".join(snap.get("name", "sans nom") for snap in utiles[:10])
    return f"Snapshots de {guest.get('name') or guest.get('vmid')} : {noms}."

def proxmox_creer_snapshot(cible, nom_snapshot):
    try:
        guest = proxmox_trouver_guest(cible)
    except Exception as e:
        print(f"[PROXMOX] Erreur recherche snapshot : {e}")
        return f"Je n'arrive pas a retrouver cette VM ou ce conteneur, Tom. {e}"

    if not guest:
        return f"Je ne trouve pas de VM ou conteneur correspondant a {cible}, Tom."
    if not nom_snapshot:
        return "Il me faut un nom de snapshot, Tom."

    endpoint = "qemu" if guest.get("type") == "qemu" else "lxc"
    payload = {"snapname": nom_snapshot}
    if endpoint == "qemu":
        payload["vmstate"] = 1
    try:
        proxmox_api_post(f"/nodes/{guest.get('node')}/{endpoint}/{guest.get('vmid')}/snapshot", data=payload)
    except Exception as e:
        print(f"[PROXMOX] Erreur creation snapshot : {e}")
        return f"Je n'ai pas pu creer le snapshot {nom_snapshot} sur {cible}, Tom. {e}"

    return f"Snapshot {nom_snapshot} lance sur {guest.get('name') or guest.get('vmid')}, Tom."

def proxmox_resume_statut():
    try:
        resources = proxmox_api_get("/cluster/resources")
    except Exception as e:
        print(f"[PROXMOX] Erreur statut global : {e}")
        return f"Je n'arrive pas a joindre Proxmox pour le moment, Tom. {e}"

    nodes = [r for r in resources if r.get("type") == "node"]
    guests = [r for r in resources if r.get("type") in ("qemu", "lxc")]
    vms = [r for r in guests if r.get("type") == "qemu"]
    lxcs = [r for r in guests if r.get("type") == "lxc"]

    online_nodes = [n for n in nodes if n.get("status") == "online"]
    running_vms = [g for g in vms if g.get("status") == "running"]
    running_lxcs = [g for g in lxcs if g.get("status") == "running"]
    stopped_vms = [g for g in vms if g.get("status") != "running"]
    stopped_lxcs = [g for g in lxcs if g.get("status") != "running"]

    phrases = [
        f"Proxmox repond correctement. {len(online_nodes)} noeud(x) en ligne sur {len(nodes)}.",
        f"J'ai {len(running_vms)} VM actives sur {len(vms)} et {len(running_lxcs)} conteneur(s) actifs sur {len(lxcs)}."
    ]

    for node in online_nodes[:2]:
        cpu = _format_pct_fraction(node.get("cpu", 0))
        mem_pct = _format_usage_pct(node.get("mem", 0), node.get("maxmem", 0))
        disk_pct = _format_usage_pct(node.get("disk", 0), node.get("maxdisk", 0))
        phrases.append(
            f"Noeud {node.get('node', 'inconnu')} : CPU {cpu} pour cent, RAM {mem_pct} pour cent, stockage {disk_pct} pour cent."
        )

    if stopped_vms:
        noms = ", ".join((vm.get("name") or f"VM {vm.get('vmid')}") for vm in stopped_vms[:5])
        phrases.append(f"VM arretees : {noms}.")
    if stopped_lxcs:
        noms = ", ".join((ct.get("name") or f"CT {ct.get('vmid')}") for ct in stopped_lxcs[:5])
        phrases.append(f"Conteneurs arretes : {noms}.")

    return " ".join(phrases)

def proxmox_resume_vms():
    try:
        guests = proxmox_api_get("/cluster/resources", params={"type": "vm"})
    except Exception as e:
        print(f"[PROXMOX] Erreur statut VM : {e}")
        return f"Je n'arrive pas a lire l'etat des VM Proxmox, Tom. {e}"

    if not guests:
        return "Je ne vois aucune VM ni aucun conteneur sur Proxmox, Tom."

    guests = sorted(guests, key=lambda guest: (guest.get("node", ""), guest.get("type", ""), guest.get("vmid", 0)))
    lignes = []
    for guest in guests[:12]:
        nom = guest.get("name") or f"{guest.get('type', 'vm').upper()} {guest.get('vmid', '?')}"
        genre = "VM" if guest.get("type") == "qemu" else "CT"
        status = "en marche" if guest.get("status") == "running" else "arrete"
        cpu = _format_pct_fraction(guest.get("cpu", 0)) if guest.get("status") == "running" else 0
        mem_pct = _format_usage_pct(guest.get("mem", 0), guest.get("maxmem", 0))
        lignes.append(f"{genre} {nom} sur {guest.get('node', 'inconnu')} : {status}, CPU {cpu} pour cent, RAM {mem_pct} pour cent.")

    if len(guests) > 12:
        lignes.append(f"Et {len(guests) - 12} autre(s) instance(s).")
    return " ".join(lignes)

def emby_est_configure():
    return EMBY_CONFIGURED


def emby_api_get(path, params=None):
    if not emby_est_configure():
        raise RuntimeError("Emby n'est pas configure")
    merged = {"api_key": EMBY_API_KEY}
    if params:
        merged.update({k: v for k, v in params.items() if v not in (None, "")})
    response = requests.get(f"{EMBY_URL.rstrip('/')}/emby{path}", params=merged, timeout=8)
    response.raise_for_status()
    return response.json()


def emby_resolve_user_id():
    if not emby_est_configure():
        return None
    if EMBY_USER_ID:
        return EMBY_USER_ID
    if not EMBY_USERNAME:
        return None
    try:
        payload = emby_api_get("/Users/Query", params={"SearchTerm": EMBY_USERNAME})
    except Exception:
        return None
    for user in payload.get("Items", []):
        if str(user.get("Name", "")).strip().lower() == EMBY_USERNAME.strip().lower():
            return user.get("Id")
    items = payload.get("Items", [])
    return items[0].get("Id") if items else None


def _emby_user_label():
    return EMBY_USERNAME or "votre compte Emby"


def _emby_item_label(item):
    if not isinstance(item, dict):
        return "contenu inconnu"
    title = item.get("Name") or item.get("SeriesName") or item.get("Album") or item.get("Id") or "contenu inconnu"
    if item.get("Type") == "Episode" and item.get("SeriesName"):
        season = item.get("ParentIndexNumber")
        episode = item.get("IndexNumber")
        suffix = []
        if season is not None:
            suffix.append(f"saison {season}")
        if episode is not None:
            suffix.append(f"episode {episode}")
        if suffix:
            return f"{item.get('SeriesName')} {', '.join(suffix)} : {item.get('Name')}"
    year = item.get("ProductionYear")
    if year and item.get("Type") == "Movie":
        return f"{title} ({year})"
    return str(title)


def emby_resume_en_cours():
    if not current_user_is_owner():
        return command_access_denied("Emby")
    user_id = emby_resolve_user_id()
    if not user_id:
        return "Je ne trouve pas l'utilisateur Emby configure. Renseignez EMBY_USER_ID ou EMBY_USERNAME dans le dashboard."
    try:
        sessions = emby_api_get("/Sessions")
    except Exception as e:
        return f"Je n'arrive pas a lire les sessions Emby pour le moment. {e}"
    active = []
    for session in sessions:
        now_playing = session.get("NowPlayingItem") or {}
        if str(session.get("UserId", "")) != str(user_id) or not now_playing:
            continue
        device = session.get("DeviceName") or session.get("Client") or "un appareil"
        active.append(f"{_emby_item_label(now_playing)} sur {device}")
    if not active:
        return f"Aucune lecture Emby en cours pour {_emby_user_label()}."
    return "Lecture Emby en cours : " + "; ".join(active[:3]) + "."


def emby_resume_reprises():
    if not current_user_is_owner():
        return command_access_denied("Emby")
    user_id = emby_resolve_user_id()
    if not user_id:
        return "Je ne trouve pas l'utilisateur Emby configure."
    try:
        payload = emby_api_get(f"/Users/{user_id}/Items/Resume", params={"Limit": 5, "Recursive": "true", "Fields": "BasicSyncInfo,ProductionYear"})
    except Exception as e:
        return f"Je n'arrive pas a lire les reprises Emby. {e}"
    items = payload.get("Items", []) if isinstance(payload, dict) else []
    if not items:
        return "Aucune lecture Emby a reprendre pour le moment."
    return "A reprendre sur Emby : " + "; ".join(_emby_item_label(item) for item in items[:5]) + "."


def emby_resume_derniers_ajouts():
    if not current_user_is_owner():
        return command_access_denied("Emby")
    user_id = emby_resolve_user_id()
    if not user_id:
        return "Je ne trouve pas l'utilisateur Emby configure."
    try:
        payload = emby_api_get(f"/Users/{user_id}/Items/Latest", params={"Limit": 8, "Fields": "ProductionYear"})
    except Exception as e:
        return f"Je n'arrive pas a lire les derniers ajouts Emby. {e}"
    items = payload if isinstance(payload, list) else payload.get("Items", [])
    if not items:
        return "Je ne vois aucun ajout recent sur Emby."
    return "Derniers ajouts Emby : " + "; ".join(_emby_item_label(item) for item in items[:6]) + "."


def emby_resume_bibliotheque():
    if not current_user_is_owner():
        return command_access_denied("Emby")
    user_id = emby_resolve_user_id()
    if not user_id:
        return "Je ne trouve pas l'utilisateur Emby configure."
    try:
        payload = emby_api_get(f"/Users/{user_id}/Items", params={"Recursive": "true", "IncludeItemTypes": "Movie,Episode,Series,Audio", "Limit": 1})
    except Exception as e:
        return f"Je n'arrive pas a lire la bibliotheque Emby. {e}"
    total = payload.get("TotalRecordCount", 0) if isinstance(payload, dict) else 0
    return f"Votre bibliotheque Emby contient environ {total} elements suivis pour {_emby_user_label()}."


def emby_resume_global():
    if not current_user_is_owner():
        return command_access_denied("Emby")
    parts = [emby_resume_en_cours(), emby_resume_reprises(), emby_resume_derniers_ajouts()]
    clean = [part for part in parts if part]
    return " ".join(clean)


def recherche_web_serpapi_details(query):
    """Effectue une recherche web et renvoie texte + cartes visuelles pour l'interface."""
    if not SERPAPI_CONFIGURED:
        return {
            "text": "La cle SerpAPI n'est pas configuree dans le fichier d'environnement.",
            "items": [],
            "images": [],
        }

    try:
        print(f"[WEB] Recherche SerpAPI pour : {query}")
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "hl": "fr",
            "gl": "fr"
        }
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        data = r.json()

        items = []
        images = []
        answer_box = data.get("answer_box") or {}
        if answer_box:
            answer_title = answer_box.get("title") or answer_box.get("type") or "Reponse rapide"
            answer_snippet = answer_box.get("answer") or answer_box.get("snippet") or answer_box.get("definition") or ""
            answer_link = answer_box.get("link") or answer_box.get("source") or ""
            if answer_snippet:
                items.append({
                    "title": answer_title,
                    "snippet": answer_snippet,
                    "link": answer_link,
                    "source": "Google",
                })
            if answer_box.get("thumbnail"):
                images.append({"src": answer_box.get("thumbnail"), "alt": answer_title})

        source_results = data.get("news_results") or data.get("organic_results") or []
        for result in source_results[:6]:
            title = result.get("title", "")
            snippet = result.get("snippet") or result.get("date") or ""
            link = result.get("link") or result.get("url") or ""
            source = result.get("source") or result.get("displayed_link") or ""
            thumbnail = result.get("thumbnail")
            if title or snippet:
                items.append({
                    "title": title,
                    "snippet": snippet,
                    "link": link,
                    "source": source,
                })
            if thumbnail:
                images.append({"src": thumbnail, "alt": title or query})

        for image in (data.get("images_results") or [])[:6]:
            src = image.get("thumbnail") or image.get("original")
            if src:
                images.append({"src": src, "alt": image.get("title") or query})

        seen = set()
        deduped_items = []
        for item in items:
            key = (item.get("title", ""), item.get("link", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped_items.append(item)

        seen_images = set()
        deduped_images = []
        for image in images:
            src = image.get("src", "")
            if not src or src in seen_images:
                continue
            seen_images.add(src)
            deduped_images.append(image)

        if not deduped_items:
            return {
                "text": f"Je n'ai rien trouve de pertinent sur le web pour : {query}.",
                "items": [],
                "images": deduped_images[:6],
            }

        response_lines = [f"Voici ce que j'ai trouve sur le web pour {query} :"]
        for item in deduped_items[:3]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            response_lines.append(f"- {title} : {snippet}" if snippet else f"- {title}")

        return {
            "text": "\n".join(response_lines),
            "items": deduped_items[:6],
            "images": deduped_images[:6],
        }
    except Exception as e:
        print(f"[WEB] Erreur SerpAPI : {e}")
        return {
            "text": "Une erreur est survenue lors de la recherche sur internet.",
            "items": [],
            "images": [],
        }


def recherche_web_serpapi(query):
    return recherche_web_serpapi_details(query).get("text", "")

PIECES_LUMIERES = {
    # Salon
    "salon"            : "light.salon",
    "plafond salon"    : "light.plafond",
    "canapes"          : "light.canapes",
    "lampadaire"       : "light.lampadaire",
    "lampe de chevet"  : "light.lampe_de_chevet_2",
    "grosse boule"     : "light.grosse_boule",
    "petite boule"     : "light.petite_boule",
    
    # Cuisine
    "cuisine"          : "light.lsc_smart_led_strip_rgbic_cctic_5m",
    "cuisine 2"        : "light.cuisine_2",
    
    # Esteban
    "esteban"          : "light.pc_3",
    "pc esteban"       : "light.pc_3",
    
    # Bureau
    "bureau"           : "light.bureau",
    "pc"               : "light.pc",
    "pc 2"             : "light.pc_2",
    
    # Parents
    "parents"          : "light.chambre_parentale",
    "chambre parentale": "light.chambre_parentale",
    "chambre"          : "light.chambre_parentale",
    "plafond chambre"  : "light.plafond_2",
    
    # Autres / Globaux
    "toutes"           : "light.all",
    "tout"             : "light.all",
}

PIECES_PRISES = {
    "salon"   : "switch.prise_salon",
    "bureau"  : "switch.prise_bureau",
    "cuisine" : "switch.prise_cuisine",
}

PIECES_CAPTEURS = {
    "salon"        : "sensor.salon_temperature_2",
    "chambre"      : "sensor.miaomiaoc_de_blt_4_14kc52pmcgk00_t2_temperature_p_2_1",
    "bureau"       : "sensor.temp_temperature",
    "exterieur"    : "sensor.temperature_exterieure",
    "dehors"       : "sensor.temperature_exterieure",
    "consommation" : "sensor.lixee_zlinky_tic_puissance_apparente",
    "tiktok"       : "sensor.tiktok_followers_techenclair",
    "oeufs"        : "input_select.ramassage_des_oeufs",
}

PIECES_HUMIDITE = {
    "bureau"    : "sensor.temp_humidite",
}

HA_TARIFS = { "p1": 0.1296, "p2": 0.1603, "p3": 0.1486, "p4": 0.1894, "p5": 0.1568, "p6": 0.7562 }

APPAREILS_ENERGIE = {
    "tv"              : "sensor.prise_1_salon_mensuel",
    "salon"           : "sensor.prise_1_salon_mensuel",
    "pc esteban"      : "sensor.prise_3_pc_esteban_mensuel",
    "esteban"         : "sensor.prise_3_pc_esteban_mensuel",
    "zoe"             : "sensor.zoe_mensuel",
    "voiture"         : "sensor.zoe_mensuel",
    "lave-vaisselle"  : "sensor.prise_2_lave_vaisselle_mensuel",
    "pc salon"        : "sensor.pc_salon_conso_pc_salon_mensuel_2",
    "bureau"          : "sensor.bureau_mensuel",
}

# Appareils pour le suivi de batterie
APPAREILS_BATTERIE = {
    "mon telephone"     : "sensor.sm_s921b_battery_level",
    "papa"              : "sensor.sm_s921b_battery_level",
    "tom"           : "sensor.sm_s921b_battery_level",
    "samsung papa"      : "sensor.sm_s921b_battery_level",
    "julie"             : "sensor.sm_julie_battery_level",
    "maman"             : "sensor.sm_julie_battery_level",
    "samsung maman"     : "sensor.sm_julie_battery_level",
    "esteban"           : "sensor.esteban_battery_level",
    "honor"             : "sensor.honor_battery_level",
    "tablette honor"    : "sensor.honor_battery_level",
    "montre papa"       : "sensor.galaxy_watch6_classic_d4he_battery_level",
    "montre tom"    : "sensor.galaxy_watch6_classic_d4he_battery_level",
    "montre maman"      : "sensor.galaxy_watch8_fbxh_battery_level",
    "montre julie"      : "sensor.galaxy_watch8_fbxh_battery_level",
    "bob"               : "sensor.bob_batterie",
    "aspirateur bob"    : "sensor.bob_batterie",
    "dyad"              : "sensor.dyad_air_2024_batterie",
    "aspirateur dyad"   : "sensor.dyad_air_2024_batterie",
    "telecommande hue"  : "sensor.maison_interrupteur_batterie",
    "interrupteur"      : "sensor.maison_interrupteur_batterie",
    "toner"             : "sensor.samsung_m2020_series_black_toner_s_n_crum_17091625519",
    "imprimante"        : "sensor.samsung_m2020_series_black_toner_s_n_crum_17091625519",
    "boite aux lettres" : "sensor.detecterur_batterie",
    "detecteur cuisine" : "sensor.detecteur_1_batterie",
    "detecteur escalier": "sensor.detecteur_2_batterie",
    "camera jardin"     : "sensor.arriere_cour_battery_percentage",
    "thermometre bureau": "sensor.temp_batterie",
}

COULEURS_MAP = {
    "rouge"      : [255, 0,   0  ],
    "bleu"       : [0,   0,   255],
    "vert"       : [0,   255, 0  ],
    "blanc"      : [255, 255, 255],
    "orange"     : [255, 140, 0  ],
    "violet"     : [148, 0,   211],
    "rose"       : [255, 20,  147],
    "jaune"      : [255, 255, 0  ],
    "cyan"       : [0,   255, 255],
    "magenta"    : [255, 0,   255],
    "turquoise"  : [64,  224, 208],
    "or"         : [255, 215, 0  ],
    "argent"     : [192, 192, 192],
    "indigo"     : [75,  0,   130],
    "marron"     : [139, 69,  19 ],
    "citron"     : [255, 250, 0  ],
    "corail"     : [255, 127, 80 ],
    "lavande"    : [230, 230, 250],
}

CODES_METEO = {
    0:  "ciel degage",
    1:  "principalement clair", 2: "partiellement nuageux", 3: "couvert",
    45: "brouillard", 48: "brouillard givrant",
    51: "bruine legere", 53: "bruine moderee", 55: "bruine dense",
    61: "pluie faible", 63: "pluie moderee", 65: "pluie forte",
    71: "neige faible", 73: "neige moderee", 75: "neige forte",
    80: "averses faibles", 81: "averses moderees", 82: "averses violentes",
    85: "averses de neige", 86: "averses de neige fortes",
    95: "orage", 96: "orage avec grele", 99: "orage violent avec grele",
}

def geocoder_ville(ville):
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ville, "count": 1, "language": "fr", "format": "json"},
            timeout=5
        )
        data = r.json()
        if data.get("results"):
            res = data["results"][0]
            return res["latitude"], res["longitude"], res.get("name", ville), res.get("country", "")
    except Exception as e:
        print(f"[METEO] Erreur geocoding : {e}")
    return None, None, ville, ""

def get_meteo_actuelle(ville=None):
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, pays = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon = LAT_PAR_DEFAUT, LON_PAR_DEFAUT
            nom_affiche = VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude"      : lat, "longitude": lon,
                "current"       : "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weathercode,precipitation",
                "hourly"        : "temperature_2m,precipitation_probability",
                "daily"         : "temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum,wind_speed_10m_max,sunrise,sunset",
                "timezone"      : "Europe/Paris",
                "forecast_days" : 3,
                "wind_speed_unit": "kmh",
            },
            timeout=8
        )
        data  = r.json()
        cur   = data["current"]
        daily = data["daily"]
        code     = cur.get("weathercode", 0)
        desc     = CODES_METEO.get(code, "conditions inconnues")
        temp     = round(float(cur.get("temperature_2m", 0)))
        
        reponse = f"À {nom_affiche}, il fait {temp} degrés et le ciel est {desc}. C'est tout."
        return reponse
    except Exception as e:
        print(f"[METEO] Erreur : {e}")
        return "Je n'arrive pas à récupérer la météo pour le moment."

def get_meteo_ha():
    """Lit la météo depuis Home Assistant avec entité configurable ou découverte automatique."""
    if not HA_CONFIGURED:
        return "Home Assistant n'est pas configure, Tom."
    try:
        state_obj = None
        if env_value_is_configured(HA_WEATHER_ENTITY):
            entity_id = HA_WEATHER_ENTITY.strip()
            r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=HA_HEADERS, timeout=5)
            if r.status_code == 200:
                state_obj = r.json()
        if state_obj is None:
            state_obj = ha_find_first_entity_by_domain("weather")
        if not state_obj:
            return None

        etat = str(state_obj.get("state", "inconnu") or "inconnu").strip().lower()
        attrs = state_obj.get("attributes", {})

        temp = attrs.get("temperature")
        if temp in (None, "", "unknown", "unavailable"):
            temp = attrs.get("current_temperature")
        temp_unit = str(attrs.get("temperature_unit", "") or "").strip()
        humidite = attrs.get("humidity")
        if humidite in (None, "", "unknown", "unavailable"):
            humidite = attrs.get("forecast_humidity")
        vent = attrs.get("wind_speed")
        if vent in (None, "", "unknown", "unavailable"):
            vent = attrs.get("forecast_wind_speed")

        etats_fr = {
            "sunny": "ensoleille",
            "clear-night": "clair",
            "partlycloudy": "partiellement nuageux",
            "cloudy": "nuageux",
            "rainy": "pluvieux",
            "pouring": "forte pluie",
            "snowy": "neigeux",
            "snowy-rainy": "pluie et neige melees",
            "windy": "venteux",
            "windy-variant": "tres venteux",
            "fog": "brumeux",
            "hail": "grele",
            "lightning": "orageux",
            "lightning-rainy": "orage et pluie",
            "exceptional": "conditions exceptionnelles",
            "clear": "degage",
        }
        desc = etats_fr.get(etat, etat if etat and etat != "unknown" else "inconnu")

        place = (HOME_LOCATION_NAME or attrs.get("friendly_name") or "chez vous").strip()
        morceaux = [f"A {place}, il fait"]
        if temp not in (None, "", "unknown", "unavailable"):
            try:
                temp_value = float(temp)
                if temp_unit.upper() in ("°F", "F"):
                    temp_value = (temp_value - 32.0) * 5.0 / 9.0
                morceaux.append(f"{round(temp_value)} degres")
            except Exception:
                morceaux.append(f"{temp} degres")
        else:
            morceaux.append("une temperature indisponible")
        morceaux.append(f"et le ciel est {desc}")
        if humidite not in (None, "", "unknown", "unavailable"):
            morceaux.append(f", humidite a {humidite}%")
        if vent not in (None, "", "unknown", "unavailable"):
            morceaux.append(f", vent a {vent} km/h")
        return "".join(morceaux) + ", Tom."
    except Exception as e:
        print(f"[METEO HA] Erreur lecture meteo HA : {e}")
        return None

def get_alertes_meteo(ville=None):
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, _ = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon, nom_affiche = LAT_PAR_DEFAUT, LON_PAR_DEFAUT, VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily"   : "weathercode,precipitation_sum,wind_speed_10m_max",
                "timezone": "Europe/Paris", "forecast_days": 3,
            },
            timeout=8
        )
        data  = r.json()
        daily = data["daily"]
        alertes = []
        for i in range(len(daily["weathercode"])):
            code  = daily["weathercode"][i]
            pluie = daily.get("precipitation_sum", [0]*3)[i] or 0
            vent  = daily.get("wind_speed_10m_max", [0]*3)[i] or 0
            jour  = ["aujourd hui", "demain", "apres-demain"][i]
            if code in [95, 96, 99]:
                alertes.append(f"Orage prevu {jour}")
            if code in [71, 73, 75, 85, 86]:
                alertes.append(f"Neige prevue {jour}")
            if pluie > 20:
                alertes.append(f"Fortes pluies {jour} ({pluie}mm)")
            if vent > 60:
                alertes.append(f"Vents forts {jour} ({vent} km/h)")
        if alertes:
            return f"Alertes meteo pour {nom_affiche} : " + ", ".join(alertes) + "."
        return f"Aucune alerte meteo pour {nom_affiche} dans les 3 prochains jours."
    except Exception as e:
        return f"Impossible de verifier les alertes meteo : {e}"

def est_requete_meteo_generale(texte):
    t = (texte or "").lower()
    mots = [
        "quel temps", "météo", "meteo", "il fait quel temps",
        "temps qu'il fait", "quel temps il fait", "prévisions",
        "previsions", "va-t-il pleuvoir", "pleut-il",
        "fait-il beau", "il va pleuvoir", "température dehors",
        "temperature dehors", "température extérieure",
        "temperature exterieure", "combien fait-il dehors",
        "il fait combien dehors"
    ]
    return any(m in t for m in mots)

def repondre_meteo_maison_ou_ville(ville=None):
    if ville:
        return get_meteo_actuelle(ville)
    reponse_ha = get_meteo_ha()
    if reponse_ha:
        return reponse_ha
    return get_meteo_actuelle(None)

THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

def get_resultats_football(equipe=None, ligue=None):
    try:
        if equipe:
            print(f"[SPORT] Recherche pour l'equipe : {equipe}")
            r = requests.get(f"{THESPORTSDB_BASE}/searchteams.php", params={"t": equipe}, timeout=5)
            data = r.json()
            teams = data.get("teams")
            if not teams:
                return f"Je n'ai pas trouvé l'équipe {equipe}."
            
            team_id   = teams[0]["idTeam"]
            team_name = teams[0]["strTeam"]
            
            # On cherche les derniers ET les prochains matchs
            res_last = requests.get(f"{THESPORTSDB_BASE}/eventslast.php", params={"id": team_id}, timeout=5).json()
            res_next = requests.get(f"{THESPORTSDB_BASE}/eventsnext.php", params={"id": team_id}, timeout=5).json()
            
            matchs_passes = res_last.get("results", [])
            matchs_futurs = res_next.get("events", [])
            
            reponse = f"Concernant le {team_name} : "
            
            if matchs_futurs:
                m = matchs_futurs[0]
                date_m = m.get("dateEvent", "date inconnue")
                heure_m = m.get("strTime", "")
                reponse += f"Le prochain match aura lieu le {date_m} à {heure_m} contre {m.get('strOpponent')}. "
            
            if matchs_passes:
                m = matchs_passes[0]
                reponse += f"Leur dernier résultat était {m.get('intHomeScore')} à {m.get('intAwayScore')} contre {m.get('strOpponent')}."
            
            if not matchs_futurs and not matchs_passes:
                return f"Je n'ai pas d'informations récentes ou futures pour {team_name}."
                
            return reponse
        else:
            nom_ligue = ligue or "Ligue 1"
            ligue_ids = {
                "ligue 1": "4334", "premier league": "4328", "liga": "4335",
                "bundesliga": "4331", "serie a": "4332",
                "champions league": "4480", "ligue des champions": "4480",
            }
            ligue_id = ligue_ids.get(nom_ligue.lower(), "4334")
            r = requests.get(f"{THESPORTSDB_BASE}/eventspastleague.php", params={"id": ligue_id}, timeout=5)
            data   = r.json()
            matchs = data.get("events", [])
            if not matchs:
                return f"Aucun resultat trouve pour {nom_ligue}."
            reponse = f"Derniers resultats {nom_ligue} : "
            lignes  = []
            for m in matchs[-6:]:
                home    = m.get("strHomeTeam", "?")
                away    = m.get("strAwayTeam", "?")
                score_h = m.get("intHomeScore", "?")
                score_a = m.get("intAwayScore", "?")
                date    = m.get("dateEvent", "?")
                lignes.append(f"{home} {score_h}-{score_a} {away} ({date})")
            return reponse + " | ".join(lignes)
    except Exception as e:
        print(f"[SPORT] Erreur football : {e}")
        return f"Impossible de recuperer les resultats football : {e}"

def get_classement_football(ligue=None):
    try:
        nom_ligue = ligue or "Ligue 1"
        ligue_ids = {
            "ligue 1": "4334", "premier league": "4328", "liga": "4335",
            "bundesliga": "4331", "serie a": "4332",
            "champions league": "4480", "ligue des champions": "4480",
        }
        ligue_id = ligue_ids.get(nom_ligue.lower(), "4334")
        r = requests.get(f"{THESPORTSDB_BASE}/lookuptable.php", params={"l": ligue_id, "s": "2024-2025"}, timeout=8)
        data    = r.json()
        tableau = data.get("table", [])
        if not tableau:
            return f"Classement {nom_ligue} non disponible pour le moment."
        reponse = f"Classement {nom_ligue} : "
        lignes  = []
        for eq in tableau[:10]:
            pos   = eq.get("intRank", "?")
            nom   = eq.get("strTeam", "?")
            pts   = eq.get("intPoints", "?")
            joues = eq.get("intPlayed", "?")
            lignes.append(f"{pos}. {nom} - {pts}pts ({joues}J)")
        return reponse + " | ".join(lignes)
    except Exception as e:
        print(f"[SPORT] Erreur classement : {e}")
        return f"Impossible de recuperer le classement : {e}"

def get_resultats_sport_gemini(question_sport):
    if not client:
        return "Gemini n'est pas configure, je ne peux pas recuperer les resultats sportifs enrichis pour le moment."
    try:
        response = _gemini_generate_blocking(
            model=CHOSEN_MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=
                f"Donne-moi les derniers resultats et actualites sportives en 2026 "
                f"pour : {question_sport}. "
                f"Sois precis, donne les scores et dates. Reponds en francais."
            )])],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                system_instruction=(
                    "Tu es un expert sportif. Donne des resultats precis et a jour. "
                    "Reponds de facon concise et conversationnelle en francais."
                )
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"[SPORT] Erreur Gemini sport : {e}")
        return "Je n arrive pas a recuperer les resultats sportifs pour le moment."

def chercher_youtube(recherche):
    if not YOUTUBE_CONFIGURED:
        return None
    try:
        r   = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": recherche, "type": "video", "maxResults": 1, "key": YOUTUBE_API_KEY},
            timeout=5
        )
        vid = r.json()["items"][0]["id"]["videoId"]
        return f"https://www.youtube.com/watch?v={vid}"
    except Exception as e:
        print(f"Erreur YouTube : {e}")
        return None

def executer_action_pc(commande):
    cmd          = commande.lower()
    user_profile = os.path.expanduser("~")

    if "met de la musique" in cmd or "mets de la musique" in cmd:
        url = "https://www.youtube.com/watch?v=7CGKeID7nRc&list=PL4fGSI1pDJn50iCQRUVmgUjOrCggCQ9nR"
        webbrowser.open(url, new=2)
        time.sleep(6) # Laisser un peu plus de temps pour le chargement de la playlist
        pyautogui.press('f')
        return "C'est parti Tom, je mets votre playlist en plein écran."

    if "youtube" in cmd:
        recherche = nettoyer_recherche_youtube_depuis_commande(cmd)
        if recherche:
            url = chercher_youtube(recherche)
            if url:
                webbrowser.open(url, new=2)
                time.sleep(5)
                pyautogui.press('f')
                return f"Je lance {recherche} sur YouTube."
        return "Video introuvable."

    def _lancer(*cmds):
        for c in cmds:
            try:
                subprocess.Popen(c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except FileNotFoundError:
                continue
        return False

    if "ouvre" in cmd or "lance" in cmd:
        if "chrome" in cmd or "navigateur" in cmd:
            ok = _lancer(["google-chrome"], ["google-chrome-stable"], ["chromium"], ["chromium-browser"], ["firefox"])
            return "Navigateur ouvert." if ok else "Aucun navigateur trouvé."
        if "notepad" in cmd or "bloc-notes" in cmd or "éditeur" in cmd:
            ok = _lancer(["gedit"], ["kate"], ["mousepad"], ["xed"], ["nano"])
            return "Éditeur de texte ouvert." if ok else "Éditeur introuvable."
        if "explorateur" in cmd or "fichiers" in cmd:
            ok = _lancer(["nautilus"], ["dolphin"], ["thunar"], ["nemo"], ["pcmanfm"])
            return "Gestionnaire de fichiers ouvert." if ok else "Gestionnaire de fichiers introuvable."
        if "spotify" in cmd:
            import asyncio
            return asyncio.get_event_loop().run_until_complete(spotify_ouvrir())

    if "volume" in cmd:
        def _volume_linux(action):
            # pactl (PulseAudio/PipeWire) en priorité, amixer en fallback
            try:
                if action == "up":
                    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"], check=True, capture_output=True)
                elif action == "down":
                    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"], check=True, capture_output=True)
                elif action == "mute":
                    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=True, capture_output=True)
                return True
            except Exception:
                pass
            try:
                if action == "up":
                    subprocess.run(["amixer", "sset", "Master", "10%+"], capture_output=True)
                elif action == "down":
                    subprocess.run(["amixer", "sset", "Master", "10%-"], capture_output=True)
                elif action == "mute":
                    subprocess.run(["amixer", "sset", "Master", "toggle"], capture_output=True)
                return True
            except Exception:
                return False
        if "monte" in cmd or "augmente" in cmd:
            _volume_linux("up")
            return "Volume augmenté."
        if "baisse" in cmd:
            _volume_linux("down")
            return "Volume baissé."
        if "coupe" in cmd:
            _volume_linux("mute")
            return "Son coupé."

    if "screenshot" in cmd or "capture" in cmd:
        _home = os.path.expanduser("~")
        bureau = next((os.path.join(_home, d) for d in ["Bureau", "Desktop"] if os.path.exists(os.path.join(_home, d))), _home)
        path = os.path.join(bureau, "screenshot.png")
        if _screenshot_linux(path):
            return f"Screenshot sauvegardé sur le bureau : {path}"
        return "Désolé Tom, je n'ai pas pu faire la capture d'écran sur ce système."

    if "eteins" in cmd or "shutdown" in cmd:
        subprocess.Popen(["shutdown", "-h", "+1"])
        return "Extinction dans 1 minute, Tom."

    return None

def init_mixer():
    if not pygame.mixer.get_init():
        pygame.mixer.init()

# ==========================================
# BUG 1 CORRIGE : fonction parler
# Le await send_web_state("idle") etait dans le mauvais bloc except
# ==========================================
async def parler(texte):
    global is_speaking, speak_volume, STOP_PARLER, _skip_pc_audio, historique
    
    texte = personalize_output_text(texte)

    # Nettoyage des caractères de mise en forme Markdown pour le TTS
    texte_tts = texte.replace("**", "").replace("*", "").replace("#", "").replace("`", "").strip()
    
    # ENREGISTRER CE QUE J.A.R.V.I.S DIT DANS SA MÉMOIRE
    if historique and len(historique) > 0:
        dernier_texte_modele = historique[-1].parts[0].text
        if dernier_texte_modele != texte:
            historique.append(types.Content(role="model", parts=[types.Part(text=f"[Information retournée par l'action et énoncée à voix haute]: {texte}")]))

    is_speaking  = True
    await send_web_state("speaking")
    speak_volume = 0.0
    tmp = f"jarvis_tts_{int(time.time()*1000)}.mp3"
    
    try:
        communicate = edge_tts.Communicate(texte_tts, voice=JARVIS_TTS_VOICE)
        await communicate.save(tmp)
        
        should_stream_audio = _skip_pc_audio or JARVIS_HEADLESS

        if should_stream_audio:
            print(f"[MOBILE] Envoi audio au client web : {texte_tts}")
            try:
                with open(tmp, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode('utf-8')
                client_id = COMMAND_HTTP_CLIENT_ID.get()
                payload = {"action": "jarvis_audio", "text": texte_tts, "audio_b64": audio_b64}
                if client_id:
                    queue_http_client_event(client_id, payload)
                await send_ws_payload(payload, client_id)
            except Exception as e:
                print(f"[MOBILE] Erreur envoi audio : {e}")
            # Ne joue pas l'audio sur le PC
        else:
            init_mixer()
            pygame.mixer.music.load(tmp)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if STOP_PARLER:
                    pygame.mixer.music.stop()
                    break

                # Simulation de volume plus réaliste pour l'animation
                t_audio = time.time() * 20
                base_vol = 0.4 + 0.3 * math.sin(t_audio) + 0.2 * math.sin(t_audio * 0.5)
                speak_volume = max(0.1, min(1.0, base_vol + random.uniform(-0.1, 0.1)))

                # Forward volume to frontend for sync
                await send_web_volume(speak_volume)
                await asyncio.sleep(0.05)
    except Exception as e:
        print(f"Erreur TTS : {e}")
    finally:
        speak_volume = 0.0
        is_speaking  = False
        STOP_PARLER  = False
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.unload()
        except:
            pass
        await asyncio.sleep(0.1)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except:
            pass
        await send_web_state("idle")

def reponse_locale(texte):
    """Réponse locale pour les requêtes basiques en cas de panne API."""
    t = texte.lower().strip()
    
    # Identité
    if any(m in t for m in ["qui es-tu", "ton nom", "quelle es ton identité", "t'appelle comment"]):
        return "Je suis J.A.R.V.I.S, votre assistant personnel et système informatique. Mes serveurs principaux sont actuellement en maintenance, mais je reste opérationnel localement."
    
    # Créateur
    if any(m in t for m in ["ton créateur", "t'as créé", "qui est tom"]):
        return "Tom est mon créateur et mon maître. C'est lui qui a conçu mes protocoles, même si ma connexion à mes serveurs neuronaux est actuellement limitée."
    
    # État
    if any(m in t for m in ["ça va", "tu vas bien", "comment vas-tu"]):
        return "Je fonctionne en mode de réserve, Tom. Mes capacités de réflexion profonde sont réduites, mais mon intégrité logicielle est intacte."
        
    # Heure et Date
    if any(m in t for m in ["heure", "quelle heure"]):
        h = time.strftime("%H:%M")
        return f"Il est précisément {h} Monsieur."
    if any(m in t for m in ["date", "quel jour", "le combien"]):
        d = time.strftime("%A %d %B %Y")
        return f"Nous sommes le {d}."
        
    # Politesse
    if any(m in t for m in ["bonjour", "salut", "hey", "bonsoir"]):
        return "Bonjour Tom. Je suis en ligne, bien que mes capacités soient actuellement restreintes."
    return None
    
def normaliser_commande_api(texte):
    value = str(texte or "").lower().replace("’", "'")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value).strip()


def jarvis_api_headers():
    return {"User-Agent": "J.A.R.V.I.S-VM/1.0 (local assistant; contact: local)"}


def nettoyer_requete_generique(texte, mots):
    query = str(texte or "")
    for mot in mots:
        query = re.sub(mot, " ", query, flags=re.IGNORECASE)
    query = re.sub(r"[?!.;:]+", " ", query)
    return re.sub(r"\s+", " ", query).strip(" ,'")


def geocoder_lieu_open_meteo(lieu):
    r = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": lieu, "count": 1, "language": "fr", "format": "json"},
        headers=jarvis_api_headers(),
        timeout=6,
    )
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return None
    item = results[0]
    label = ", ".join(part for part in [item.get("name"), item.get("admin1"), item.get("country")] if part)
    return float(item["latitude"]), float(item["longitude"]), label or lieu


def extraire_lieu_depuis_commande(texte):
    raw = str(texte or "").strip()
    cleaned = raw
    replacements = [
        r"\b(?:donne moi|donne-moi|dis moi|dis-moi|quelle est|quel est|c'est quoi|comment est|est ce qu|est-ce qu|il va|elle va|va t il|va-t-il)\b",
        r"\b(?:la|le|les|du|de la|des|un|une)\b",
        r"\b(?:meteo|météo|temperature|température|temps|prevision|prévision|previsions|prévisions|pleuvoir|pluie|vent)\b",
        r"\b(?:aujourd'hui|demain|maintenant|cette semaine|ce matin|ce soir|cet apres midi|cet après midi)\b",
    ]
    for pattern in replacements:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:a|à|sur|pour|dans|en)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[?!.;:]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,'")
    if len(cleaned) >= 2:
        return cleaned
    return HOME_LOCATION_NAME or "Paris"


def resoudre_meteo_api(texte):
    t = normaliser_commande_api(texte)
    if not any(k in t for k in ["meteo", "temperature", "temps", "pleuvoir", "pluie", "vent"]):
        return None
    try:
        lieu = extraire_lieu_depuis_commande(texte)
        geo = geocoder_lieu_open_meteo(lieu)
        if not geo:
            return f"Je n'ai pas trouve la ville {lieu}."
        lat, lon, label = geo
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "forecast_days": 2,
                "timezone": "auto",
            },
            headers=jarvis_api_headers(),
            timeout=7,
        )
        r.raise_for_status()
        data = r.json()
        current = data.get("current") or {}
        daily = data.get("daily") or {}
        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        rain = current.get("precipitation")
        wind = current.get("wind_speed_10m")
        maxs = daily.get("temperature_2m_max") or []
        mins = daily.get("temperature_2m_min") or []
        probs = daily.get("precipitation_probability_max") or []
        parts = [f"Meteo pour {label} : actuellement {temp} degres" if temp is not None else f"Meteo pour {label}."]
        if humidity is not None:
            parts.append(f"humidite {humidity} pour cent")
        if rain is not None:
            parts.append(f"pluie {rain} millimetre")
        if wind is not None:
            parts.append(f"vent {wind} kilometres heure")
        if maxs and mins:
            parts.append(f"aujourd'hui entre {mins[0]} et {maxs[0]} degres")
        if probs:
            parts.append(f"risque de pluie maximum {probs[0]} pour cent")
        if "demain" in t and len(maxs) > 1 and len(mins) > 1:
            parts.append(f"demain entre {mins[1]} et {maxs[1]} degres, pluie {probs[1] if len(probs) > 1 else 0} pour cent")
        return ", ".join(parts) + "."
    except Exception as e:
        print(f"[OPEN-METEO] Erreur : {e}")
        return "Je n'arrive pas a recuperer la meteo pour le moment."


def resoudre_jours_feries_api(texte):
    t = normaliser_commande_api(texte)
    if not any(k in t for k in ["ferie", "jour ferie", "jours feries", "fete nationale"]):
        return None
    try:
        country = "FR"
        country_match = re.search(r"\b([A-Z]{2})\b", str(texte or ""))
        if country_match:
            country = country_match.group(1).upper()
        year_match = re.search(r"\b(20\d{2})\b", t)
        year = int(year_match.group(1)) if year_match else datetime.now().year
        r = requests.get(f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}", timeout=7)
        r.raise_for_status()
        holidays = r.json()
        if not holidays:
            return f"Je n'ai pas trouve de jours feries pour {country} en {year}."
        today = datetime.now().date()
        upcoming = [h for h in holidays if datetime.fromisoformat(h["date"]).date() >= today]
        selected = upcoming[:4] if upcoming else holidays[:4]
        lignes = [f"Prochains jours feries {country} en {year}"]
        for h in selected:
            lignes.append(f"{h.get('localName') or h.get('name')} le {h.get('date')}")
        return ": ".join([lignes[0], "; ".join(lignes[1:])]) + "."
    except Exception as e:
        print(f"[NAGER] Erreur : {e}")
        return "Je n'arrive pas a recuperer les jours feries pour le moment."


def resoudre_wikipedia_api(texte):
    t = normaliser_commande_api(texte)
    if not any(k in t for k in ["wikipedia", "wiki", "resume moi", "résume moi", "qui est", "c'est quoi"]):
        return None
    if any(k in t for k in ["recette", "youtube", "musique", "meteo", "jour ferie"]):
        return None
    query = nettoyer_requete_generique(texte, [r"wikipedia", r"wiki", r"resume moi", r"résume moi", r"qui est", r"c'est quoi", r"qu'est ce que", r"qu'est-ce que", r"donne moi", r"explique moi"])
    if len(query) < 2:
        return None
    try:
        search = requests.get(
            "https://fr.wikipedia.org/w/rest.php/v1/search/page",
            params={"q": query, "limit": 1},
            headers=jarvis_api_headers(),
            timeout=7,
        )
        search.raise_for_status()
        pages = search.json().get("pages") or []
        if not pages:
            return f"Je n'ai pas trouve de page Wikipedia pour {query}."
        title = pages[0].get("title") or query
        summary = requests.get(
            f"https://fr.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title, safe='')}",
            headers=jarvis_api_headers(),
            timeout=7,
        )
        summary.raise_for_status()
        data = summary.json()
        extract = data.get("extract") or "Je n'ai pas trouve de resume lisible."
        url = (data.get("content_urls") or {}).get("desktop", {}).get("page", "")
        return f"Wikipedia, {data.get('title', title)} : {extract[:900]}" + (f" Source : {url}" if url else "")
    except Exception as e:
        print(f"[WIKIPEDIA] Erreur : {e}")
        return None


def resoudre_openfoodfacts_api(texte):
    t = normaliser_commande_api(texte)
    if not any(k in t for k in ["open food", "openfood", "nutriscore", "nutri score", "code barre", "barcode", "produit alimentaire", "allergene", "allergène"]):
        return None
    try:
        barcode = re.search(r"\b(\d{8,14})\b", t)
        product = None
        if barcode:
            r = requests.get(
                f"https://world.openfoodfacts.org/api/v2/product/{barcode.group(1)}.json",
                params={"fields": "product_name,brands,nutriscore_grade,nova_group,allergens_tags,ingredients_text_fr,nutriments"},
                headers=jarvis_api_headers(),
                timeout=7,
            )
            r.raise_for_status()
            payload = r.json()
            if payload.get("status") == 1:
                product = payload.get("product") or {}
        else:
            query = nettoyer_requete_generique(texte, [r"open food facts", r"openfoodfacts", r"open food", r"nutriscore", r"nutri score", r"produit alimentaire", r"analyse", r"cherche", r"donne moi"])
            if len(query) < 2:
                return None
            r = requests.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={"search_terms": query, "search_simple": 1, "action": "process", "json": 1, "page_size": 1},
                headers=jarvis_api_headers(),
                timeout=7,
            )
            r.raise_for_status()
            products = r.json().get("products") or []
            product = products[0] if products else None
        if not product:
            return "Je n'ai pas trouve ce produit dans Open Food Facts."
        name = product.get("product_name") or "produit inconnu"
        brand = product.get("brands") or "marque inconnue"
        nutri = (product.get("nutriscore_grade") or "inconnu").upper()
        nova = product.get("nova_group") or "inconnu"
        allergens = product.get("allergens_tags") or []
        allergen_text = ", ".join(a.replace("en:", "") for a in allergens[:4]) if allergens else "aucun allergene signale"
        return f"Open Food Facts : {name}, {brand}. Nutri-Score {nutri}, groupe NOVA {nova}. Allergènes : {allergen_text}."
    except Exception as e:
        print(f"[OPENFOODFACTS] Erreur : {e}")
        return "Je n'arrive pas a lire Open Food Facts pour le moment."


def resoudre_openlibrary_api(texte):
    t = normaliser_commande_api(texte)
    if not any(k in t for k in ["isbn", "livre", "open library", "auteur"]):
        return None
    if any(k in t for k in ["ecris", "écris", "redige", "rédige"]):
        return None
    try:
        isbn = re.search(r"\b(?:97[89][ -]?)?\d[\d -]{8,16}[\dXx]\b", str(texte or ""))
        if isbn:
            clean_isbn = re.sub(r"[^0-9Xx]", "", isbn.group(0))
            r = requests.get(
                f"https://openlibrary.org/isbn/{clean_isbn}.json",
                headers=jarvis_api_headers(),
                timeout=7,
            )
            r.raise_for_status()
            book = r.json()
            title = book.get("title", "titre inconnu")
            year = book.get("publish_date", "date inconnue")
            publishers = ", ".join(book.get("publishers", [])[:2]) or "editeur inconnu"
            return f"Open Library : ISBN {clean_isbn}, {title}, publie {year}, editeur {publishers}."
        query = nettoyer_requete_generique(texte, [r"open library", r"cherche", r"livre", r"auteur", r"donne moi", r"infos? sur"])
        if len(query) < 2:
            return None
        r = requests.get(
            "https://openlibrary.org/search.json",
            params={"q": query, "limit": 1},
            headers=jarvis_api_headers(),
            timeout=7,
        )
        r.raise_for_status()
        docs = r.json().get("docs") or []
        if not docs:
            return f"Je n'ai pas trouve de livre pour {query}."
        book = docs[0]
        authors = ", ".join(book.get("author_name", [])[:3]) or "auteur inconnu"
        year = book.get("first_publish_year", "date inconnue")
        return f"Open Library : {book.get('title', query)}, par {authors}, premiere publication {year}."
    except Exception as e:
        print(f"[OPENLIBRARY] Erreur : {e}")
        return "Je n'arrive pas a consulter Open Library pour le moment."


def resoudre_nasa_api(texte):
    t = normaliser_commande_api(texte)
    if not any(k in t for k in ["nasa", "apod", "image du jour", "photo du jour", "astronomie"]):
        return None
    try:
        r = requests.get(
            "https://api.nasa.gov/planetary/apod",
            params={"api_key": NASA_API_KEY if NASA_CONFIGURED else "DEMO_KEY"},
            headers=jarvis_api_headers(),
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        title = data.get("title", "image NASA du jour")
        explanation = data.get("explanation", "")
        url = data.get("hdurl") or data.get("url") or ""
        return f"NASA APOD : {title}. {explanation[:850]}" + (f" Image : {url}" if url else "")
    except Exception as e:
        print(f"[NASA] Erreur : {e}")
        return "Je n'arrive pas a recuperer l'image NASA du jour pour le moment."


def resoudre_openstreetmap_api(texte):
    t = normaliser_commande_api(texte)
    if not any(k in t for k in ["adresse", "coordonnees", "coordonnées", "openstreetmap", "osm", "localise", "geocode"]):
        return None
    try:
        query = nettoyer_requete_generique(texte, [r"openstreetmap", r"osm", r"adresse de", r"coordonnees de", r"coordonnées de", r"localise", r"geocode", r"trouve", r"cherche"])
        query = re.sub(r"^(la|le|les|l'|un|une|des)\s+", "", query, flags=re.IGNORECASE).strip()
        if len(query) < 3:
            return None
        params = {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1, "accept-language": "fr"}
        if not re.search(r"\b(maroc|belgique|suisse|canada|usa|etats-unis|allemagne|espagne|italie|royaume-uni)\b", normaliser_commande_api(query)):
            params["countrycodes"] = "fr"
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers=jarvis_api_headers(),
            timeout=8,
        )
        r.raise_for_status()
        results = r.json()
        if not results:
            return f"Je n'ai pas trouve {query} dans OpenStreetMap."
        item = results[0]
        return f"OpenStreetMap : {item.get('display_name', query)}. Coordonnees : latitude {item.get('lat')}, longitude {item.get('lon')}."
    except Exception as e:
        print(f"[OSM] Erreur : {e}")
        return "Je n'arrive pas a interroger OpenStreetMap pour le moment."


def resoudre_apis_publiques_localement(texte):
    resolvers = [
        resoudre_meteo_api,
        resoudre_jours_feries_api,
        resoudre_openfoodfacts_api,
        resoudre_openlibrary_api,
        resoudre_nasa_api,
        resoudre_openstreetmap_api,
        resoudre_wikipedia_api,
    ]
    for resolver in resolvers:
        try:
            reponse = resolver(texte)
            if reponse:
                return reponse
        except Exception as e:
            print(f"[API] {resolver.__name__} erreur : {e}")
    return None


def resoudre_math_localement(texte):
    """Résout des calculs simples localement sans appeler l'IA."""
    t = texte.lower().replace("?", "").strip()
    
    # Nettoyage des phrases communes
    prefixes = ["combien font", "calcule", "résous", "quel est le résultat de"]
    for prefixe in prefixes:
        if t.startswith(prefixe):
            t = t[len(prefixe):].strip()
            
    # Remplacement des mots par des symboles
    t = t.replace("fois", "*").replace("multiplier par", "*").replace("x", "*")
    t = t.replace("divisé par", "/").replace("sur", "/")
    t = t.replace("plus", "+").replace("moins", "-")
    t = t.replace("puissance", "**").replace("au carré", "**2")
    
    # Cas spécial racine : on s'assure d'avoir des parenthèses pour eval
    if "racine" in t:
        # On cherche un nombre après 'racine'
        match = re.search(r'racine\s+(?:carrée\s+de\s+)?(\d+)', t)
        if match:
            t = f"sqrt({match.group(1)})"
        else:
            t = t.replace("racine carrée de", "sqrt").replace("racine de", "sqrt")
    
    # Extraction de l'expression mathématique (chiffres, opérateurs, parenthèses, points)
    expr = re.sub(r'[^0-9+\-*/.**() ,sqrt]', '', t).strip()
    if not expr or not any(c.isdigit() for c in expr):
        return None
    
    try:
        # Dictionnaire de sécurité pour eval
        safe_dict = {
            "sqrt": math.sqrt,
            "pow": math.pow,
            "pi": math.pi,
            "e": math.e
        }
        resultat = eval(expr, {"__builtins__": None}, safe_dict)
        
        # Formatage du résultat
        if isinstance(resultat, float) and resultat.is_integer():
            resultat = int(resultat)
        elif isinstance(resultat, float):
            resultat = round(resultat, 3)
            
        # Phrase de réponse élégante
        clean_expr = expr.replace("**2", " au carré").replace("sqrt", "racine de ").replace("(", "").replace(")", "").replace("*", " fois ").replace("/", " divisé par ")
        return f"Le résultat de {clean_expr} est {resultat}, Monsieur."
    except Exception:
        return None

def resoudre_francais_localement(texte):
    """Résout des questions de français simples localement."""
    t = texte.lower().strip()
    
    # Dictionnaire local de secours (très basique)
    dictionnaire = {
        "ia": "Intelligence Artificielle. Ensemble de théories et de techniques mises en œuvre en vue de réaliser des machines capables de simuler l'intelligence humaine.",
        "intelligence artificielle": "Ensemble de théories et de techniques mises en œuvre en vue de réaliser des machines capables de simuler l'intelligence humaine.",
        "maison": "Bâtiment servant de logement, d'habitation.",
        "mathématiques": "Science qui étudie par le moyen du raisonnement déductif les propriétés d'êtres abstraits.",
        "jarvis": "Just A Rather Very Intelligent System. Votre fidèle assistant.",
    }
    
    # Définitions
    if any(p in t for p in ["définition de", "définis le mot", "c'est quoi"]):
        # On essaie d'extraire le mot après les phrases clés
        mot = ""
        if "définition de" in t: mot = t.split("définition de")[-1]
        elif "définis le mot" in t: mot = t.split("définis le mot")[-1]
        elif "c'est quoi" in t: mot = t.split("c'est quoi")[-1]
        
        mot = mot.replace("?", "").replace("l'", "").replace("la ", "").replace("le ", "").replace("les ", "").strip()
        
        if mot in dictionnaire:
            return f"La définition de {mot} est : {dictionnaire[mot]}."
            
    # Conjugaison basique
    if "conjugue" in t or "conjugaison" in t:
        if "être" in t:
            return "Verbe Être au présent : Je suis, tu es, il est, nous sommes, vous êtes, ils sont."
        if "avoir" in t:
            return "Verbe Avoir au présent : J'ai, tu as, il a, nous avons, vous avez, ils ont."
            
    return None

def resoudre_conversion_localement(texte):
    """Gère les conversions d'unités et de devises localement."""
    t = texte.lower().replace("?", "").strip()
    
    # Unités de longueur
    if any(m in t for m in [" km ", " kilomètres ", " milles ", " miles "]):
        # km to miles: 0.621371
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:km|kilomètres)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            res = round(val * 0.621371, 2)
            return f"{val} kilomètres font environ {res} miles, Monsieur."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:miles|milles)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            res = round(val / 0.621371, 2)
            return f"{val} miles font environ {res} kilomètres, Monsieur."

    # Température (C to F)
    if any(m in t for m in [" degrés ", " celsius ", " fahrenheit "]):
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:degrés|celsius)', t)
        if match and "fahrenheit" in t:
            val = float(match.group(1).replace(",", "."))
            res = round((val * 9/5) + 32, 1)
            return f"{val} degrés Celsius font {res} degrés Fahrenheit."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:degrés|fahrenheit)', t)
        if match and "celsius" in t:
            val = float(match.group(1).replace(",", "."))
            res = round((val - 32) * 5/9, 1)
            return f"{val} degrés Fahrenheit font {res} degrés Celsius."

    # Devises (Taux fixes simplifiés pour l'exemple local)
    if any(m in t for m in [" euro ", " euros ", " dollar ", " dollars "]):
        # 1 EUR = 1.08 USD (approximatif)
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*euros?', t)
        if match and "dollar" in t:
            val = float(match.group(1).replace(",", "."))
            res = round(val * 1.08, 2)
            return f"{val} euros font environ {res} dollars, Monsieur."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*dollars?', t)
        if match and "euro" in t:
            val = float(match.group(1).replace(",", "."))
            res = round(val / 1.08, 2)
            return f"{val} dollars font environ {res} euros, Monsieur."
            
    return None

def resoudre_traduction_localement(texte):
    """Traduction ultra-rapide de mots courants localement."""
    t = texte.lower().strip()
    
    dict_trad = {
        "bonjour": {"en": "hello", "es": "hola", "de": "hallo"},
        "merci": {"en": "thank you", "es": "gracias", "de": "danke"},
        "au revoir": {"en": "goodbye", "es": "adiós", "de": "auf wiedersehen"},
        "s'il vous plaît": {"en": "please", "es": "por favor", "de": "bitte"},
        "oui": {"en": "yes", "es": "sí", "de": "ja"},
        "non": {"en": "no", "es": "no", "de": "nein"},
        "ami": {"en": "friend", "es": "amigo", "de": "freund"},
        "maison": {"en": "house", "es": "casa", "de": "haus"},
        "ordinateur": {"en": "computer", "es": "ordenador", "de": "computer"},
        "assistant": {"en": "assistant", "es": "asistente", "de": "assistent"},
    }

    if any(p in t for p in ["comment dit-on", "traduis", "en anglais", "en espagnol", "en allemand"]):
        cible = "en"
        if "espagnol" in t: cible = "es"
        elif "allemand" in t: cible = "de"
        
        # Extraction du mot
        # On nettoie les expressions courantes
        mot = t
        for p in ["comment dit-on", "traduis", "en anglais", "en espagnol", "en allemand", "?"]:
            mot = mot.replace(p, "")
        mot = mot.replace('"', '').replace("'", "").strip()
        
        if mot in dict_trad:
            res = dict_trad[mot][cible]
            lang = "anglais" if cible == "en" else ("espagnol" if cible == "es" else "allemand")
            return f"En {lang}, '{mot}' se dit '{res}'."
            
    return None

def resoudre_infos_systeme_localement(texte):
    """Répond aux questions d'heure, date, batterie, CPU/RAM localement sans IA."""
    t = texte.lower().replace("?", "").strip()
    maintenant = datetime.now()

    JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    MOIS_FR  = ["janvier", "février", "mars", "avril", "mai", "juin",
                "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

    # --- HEURE ---
    if any(m in t for m in ["quelle heure", "il est quelle heure", "l'heure qu'il est",
                             "quelle est l'heure", "tu as l'heure", "donne-moi l'heure",
                             "il est combien", "c'est quoi l'heure", "heure il est"]):
        h, m = maintenant.hour, maintenant.minute
        return f"Il est {h}h{m:02d}, Tom."

    # --- DATE COMPLÈTE ---
    if any(m in t for m in ["quelle date", "on est quel jour", "quel jour on est",
                             "quel jour sommes-nous", "la date d'aujourd'hui", "date du jour",
                             "on est le combien", "quel jour est-on", "c'est quoi la date",
                             "la date aujourd'hui"]):
        jour_semaine = JOURS_FR[maintenant.weekday()]
        mois = MOIS_FR[maintenant.month - 1]
        return f"Nous sommes le {jour_semaine} {maintenant.day} {mois} {maintenant.year}, Tom."

    # --- JOUR DE LA SEMAINE SEUL ---
    if any(m in t for m in ["quel jour", "c'est quel jour"]) and "date" not in t:
        return f"Nous sommes {JOURS_FR[maintenant.weekday()]}, Tom."

    # --- MOIS ---
    if any(m in t for m in ["quel mois", "on est en quel mois", "c'est quel mois"]):
        return f"Nous sommes en {MOIS_FR[maintenant.month - 1]}, Tom."

    # --- ANNÉE ---
    if any(m in t for m in ["quelle année", "on est en quelle année", "c'est quelle année"]):
        return f"Nous sommes en {maintenant.year}, Tom."

    # --- ÂGE DE MICKAEL ---
    if any(m in t for m in ["quel âge as-tu", "quel age as-tu", "quel âge a tom",
                             "quel est mon âge", "j'ai quel âge", "j ai quel age"]):
        naissance = datetime(1988, 5, 21)
        age = (maintenant - naissance).days // 365
        return f"Vous avez {age} ans, Tom."

    # --- BATTERIE ---
    if any(m in t for m in ["batterie", "autonomie", "niveau de charge", "charge du pc"]):
        if psutil is None:
            return "Le module psutil n'est pas disponible, Tom."
        try:
            bat = psutil.sensors_battery()
            if bat:
                pct = int(bat.percent)
                etat = "en charge" if bat.power_plugged else "sur batterie"
                return f"La batterie est à {pct}%, {etat}, Tom."
            return "Je ne détecte pas de batterie sur cet appareil, Tom."
        except Exception:
            return "Impossible de lire la batterie, Tom."

    # --- CPU ---
    if any(m in t for m in ["cpu", "processeur", "utilisation du processeur", "charge du processeur"]):
        if psutil is None:
            return "Le module psutil n'est pas disponible, Tom."
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            return f"Le processeur tourne à {cpu}% d'utilisation, Tom."
        except Exception:
            return "Impossible de lire le processeur, Tom."

    # --- RAM ---
    if any(m in t for m in ["ram", "mémoire ram", "mémoire vive", "utilisation de la mémoire"]):
        if psutil is None:
            return "Le module psutil n'est pas disponible, Tom."
        try:
            mem = psutil.virtual_memory()
            utilise = round(mem.used / (1024**3), 1)
            total   = round(mem.total / (1024**3), 1)
            return f"La RAM est à {mem.percent}% — {utilise} Go utilisés sur {total} Go, Tom."
        except Exception:
            return "Impossible de lire la RAM, Tom."

    # --- UPTIME (depuis combien de temps le PC est allumé) ---
    if any(m in t for m in ["allumé depuis", "uptime", "depuis combien de temps le pc",
                             "depuis quand est allumé"]):
        if psutil is None:
            return "Le module psutil n'est pas disponible, Tom."
        try:
            boot = datetime.fromtimestamp(psutil.boot_time())
            delta = maintenant - boot
            heures  = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            return f"Le PC est allumé depuis {heures}h{minutes:02d}, Tom."
        except Exception:
            return None

    return None

async def resumer_page_extension(page_title, page_url, page_text):
    system_instruction = (
        "Tu es le mode extension Chrome de J.A.R.V.I.S. "
        "Tu dois resumer uniquement le texte de page fourni par l'extension. "
        "N'essaie jamais d'ouvrir l'URL, ne demande pas a l'utilisateur de copier-coller le contenu, "
        "et ne parle pas d'une impossibilite d'acceder a des URL externes. "
        "Si le texte fourni est insuffisant, dis seulement que le contenu lisible de la page est insuffisant."
    )
    prompt = (
        "Resume clairement en francais le CONTENU DE PAGE FOURNI ci-dessous.\n"
        "Format attendu:\n"
        "Resume court: 2 a 4 phrases.\n"
        "Points importants: 5 puces maximum.\n"
        "A noter: dates, prix, actions ou avertissements s'il y en a.\n\n"
        f"Titre: {page_title or 'Sans titre'}\n"
        f"URL informative, ne pas ouvrir: {page_url or 'URL inconnue'}\n"
        "CONTENU DE PAGE FOURNI:\n"
        f"{page_text}"
    )

    if client:
        last_err = None
        contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        for model_name in MODELS_LIST:
            try:
                response = await gemini_generate_with_failover(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.25,
                    ),
                    timeout=20.0,
                )
                if response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"[EXTENSION] Echec resume Gemini {model_name} : {e}")
                last_err = e
        print(f"[EXTENSION] Gemini indisponible pour resume : {last_err}")

    fallback_prompt = f"{system_instruction}\n\n{prompt}"
    if groq_client:
        try:
            rep_groq = await demander_groq(fallback_prompt)
            if rep_groq:
                return rep_groq.strip()
        except Exception as e:
            print(f"[EXTENSION] Echec resume Groq : {e}")

    if grok_client:
        try:
            rep_grok = await demander_grok(fallback_prompt)
            if rep_grok:
                return rep_grok.strip()
        except Exception as e:
            print(f"[EXTENSION] Echec resume Grok : {e}")

    rep_ollama = await demander_ollama(fallback_prompt)
    if rep_ollama:
        return rep_ollama.strip()

    return "Je n'ai pas pu generer le resume pour le moment, mais le texte de la page a bien ete transmis par l'extension."


async def resumer_message_discord(author, content, jump_url=""):
    content = str(content or "").strip()
    if not content:
        return "Je n'ai pas assez de texte lisible dans ce message Discord pour le resumer."

    content = content[:12000]
    system_instruction = (
        "Tu es J.A.R.V.I.S dans Discord. "
        "Tu resumes uniquement le message Discord fourni. "
        "Ne dis pas que tu ne peux pas acceder a une URL externe, ne demande pas de copier-coller le texte, "
        "et n'invente pas le contexte qui n'est pas dans le message."
    )
    prompt = (
        "Resume clairement en francais ce message Discord.\n"
        "Format attendu:\n"
        "Resume: 1 a 3 phrases.\n"
        "Points importants: 4 puces maximum si utile.\n"
        "Action a faire: uniquement si le message en contient une.\n\n"
        f"Auteur: {author or 'Utilisateur inconnu'}\n"
        f"Lien du message, informatif seulement: {jump_url or 'indisponible'}\n"
        "MESSAGE DISCORD:\n"
        f"{content}"
    )

    if client:
        last_err = None
        contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        for model_name in MODELS_LIST:
            try:
                response = await gemini_generate_with_failover(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2,
                    ),
                    timeout=18.0,
                )
                if response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"[DISCORD] Echec resume Gemini {model_name} : {e}")
                last_err = e
        print(f"[DISCORD] Gemini indisponible pour resume : {last_err}")

    fallback_prompt = f"{system_instruction}\n\n{prompt}"
    if groq_client:
        try:
            rep_groq = await demander_groq(fallback_prompt)
            if rep_groq:
                return rep_groq.strip()
        except Exception as e:
            print(f"[DISCORD] Echec resume Groq : {e}")

    if grok_client:
        try:
            rep_grok = await demander_grok(fallback_prompt)
            if rep_grok:
                return rep_grok.strip()
        except Exception as e:
            print(f"[DISCORD] Echec resume Grok : {e}")

    rep_ollama = await demander_ollama(fallback_prompt)
    if rep_ollama:
        return rep_ollama.strip()

    return "Je n'ai pas pu generer le resume Discord pour le moment."


async def demander_ia(texte):

    global is_thinking, GEMINI_QUOTA_BLOCKED_UNTIL
    is_thinking = True
    await send_web_state("thinking")
    try:
        cerveau = detecter_cerveau(texte)

        async def _call_gemini():
            global GEMINI_QUOTA_BLOCKED_UNTIL
            if not client:
                raise Exception("Gemini non configure (GEMINI_API_KEY manquante ou factice)")
            print(f"[CERVEAU] Tentative avec Gemini (Liste: {MODELS_LIST})...")
            # On ne modifie pas l'historique global avant d'être sûr que ça marche
            temp_hist = historique + [types.Content(role="user", parts=[types.Part(text=texte)])]
            prompt_actuel = construire_system_prompt()
            
            last_err = None
            for model_name in MODELS_LIST:
                try:
                    print(f"[CERVEAU] Essai modele : {model_name} (Timeout 12s)")
                    # Utilisation de to_thread pour ne pas bloquer la boucle et pouvoir mettre un timeout
                    response = await gemini_generate_with_failover(
                        model=model_name,
                        contents=temp_hist,
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_actuel,
                            temperature=0.7,
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                        ),
                        timeout=12.0,
                    )
                    rep = response.text
                    # Succès : mise à jour de l'historique officiel
                    historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
                    historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
                    return rep
                except Exception as e:
                    print(f"[CERVEAU] Echec {model_name} : {e}")
                    if erreur_quota_gemini(e):
                        GEMINI_QUOTA_BLOCKED_UNTIL = max(
                            GEMINI_QUOTA_BLOCKED_UNTIL,
                            time.time() + extraire_retry_quota_secondes(e)
                        )
                    last_err = e
                    continue
            
            raise last_err or Exception("Tous les modeles Gemini ont echoue")

        async def _call_grok():
            print("[CERVEAU] Tentative avec Grok...")
            rep_grok = await demander_grok(texte)
            if not rep_grok:
                raise Exception("Grok n'a rien renvoyé ou est mal configuré")
            return rep_grok

        if OLLAMA_PREFER_LOCAL and OLLAMA_CONFIGURED and cerveau != "GROK":
            print("[CERVEAU] Ollama prioritaire active. Tentative locale avant cloud.")
            rep_ollama = await demander_ollama(texte)
            if rep_ollama:
                return rep_ollama
            print("[CERVEAU] Ollama prioritaire indisponible. Repli cloud.")

        # Logique de bascule bidirectionnelle
        if cerveau == "GROK" and grok_client:
            try:
                return await _call_grok()
            except Exception as e:
                print(f"[CERVEAU] Erreur Grok ({e}). Bascule sur Gemini.")
                try:
                    return await _call_gemini()
                except Exception as e2:
                    print(f"[ERREUR IA (Gemini repli)] {e2}")
        else:
            try:
                return await _call_gemini()
            except Exception as e:
                print(f"[CERVEAU] Erreur Gemini ({e}). Bascule sur les autres secours.")

                # --- FALLBACK MÉTÉO/TEMP (HA + OpenMeteo, avant SerpAPI) ---
                t_low = texte.lower()
                _mots_temp_int = ["température", "temperature", "il fait chaud",
                                  "il fait froid", "combien de degrés",
                                  "combien fait-il", "il fait combien"]
                _mots_maison   = ["chez moi", "à la maison", "dans la maison",
                                  "intérieur", "interieur", "dans le salon",
                                  "dans la chambre", "dans le bureau"]
                _pieces_fallback = {
                    "salon"   : "salon",
                    "chambre" : "chambre",
                    "bureau"  : "bureau",
                    "extérieur": "exterieur",
                    "dehors"  : "dehors",
                }

                if est_requete_meteo_generale(texte):
                    print("[CERVEAU] Requete meteo detectee -> Home Assistant prioritaire")
                    return repondre_meteo_maison_ou_ville(None)

                if any(m in t_low for m in _mots_temp_int):
                    # Pièce spécifique ?
                    for mot_piece, piece_key in _pieces_fallback.items():
                        if mot_piece in t_low:
                            entity_id = PIECES_CAPTEURS.get(piece_key)
                            if entity_id:
                                print(f"[CERVEAU] Temp intérieure détectée → HA {entity_id}")
                                temp = ha_get_etat(entity_id)
                                return f"La température dans le {mot_piece} est de {temp} degrés, Tom."
                    # "chez moi" sans pièce → salon par défaut
                    if any(m in t_low for m in _mots_maison):
                        entity_id = PIECES_CAPTEURS.get("salon")
                        if entity_id:
                            print(f"[CERVEAU] Temp intérieure 'chez moi' → HA {entity_id}")
                            temp = ha_get_etat(entity_id)
                            return f"La température chez vous est de {temp} degrés, Tom."

                # --- FALLBACK SERPAPI ---
                if SERPAPI_CONFIGURED and len(texte.split()) > 2:
                    res_serp = recherche_web_serpapi(texte)
                    if res_serp and "VOTRE_CLE" not in res_serp and "rien trouvé" not in res_serp and "erreur" not in res_serp.lower():
                        return "Voici ce que j'ai trouvé sur le web : " + res_serp

                # --- FALLBACK GROQ (LLAMA 3.3) ---
                print("[CERVEAU] Bascule sur Groq (Llama 3.3).")
                if groq_client:
                    rep_groq = await demander_groq(texte)
                    if rep_groq:
                        return rep_groq
                
                # --- FALLBACK GROK (xAI) ---
                print("[CERVEAU] Bascule sur Grok (xAI).")
                if grok_client:
                    try:
                        return await _call_grok()
                    except Exception as e2:
                        print(f"[ERREUR IA (Grok repli)] {e2}")
        # --- FALLBACK OLLAMA (100% offline) ---
        print("[CERVEAU] Gemini et Grok KO. Tentative Ollama (local)...")
        rep_ollama = await demander_ollama(texte)
        if rep_ollama:
            return rep_ollama

        # --- FALLBACK LOCAL ---
        print("[CERVEAU] Tous les serveurs IA ont echoue. Tentative fallback local...")
        rep_loc = reponse_locale(texte)
        if rep_loc:
            return rep_loc
            
        return "Desole Tom, mes serveurs de réflexion profonde sont surchargés et mes modèles locaux ne sont pas disponibles non plus. Je reste cependant disponible pour vos commandes domestiques."
    finally:
        is_thinking = False
        await send_web_state("idle")

async def demander_ia_vision(texte, img_b64):
    """Analyse une image (capture d'écran) avec Gemini Vision."""
    global is_thinking, historique
    is_thinking = True
    await send_web_state("thinking")
    try:
        if not client:
            return ("Gemini n'est pas configure sur cette machine, Tom. "
                    "Je ne peux donc pas analyser d'images pour le moment.")
        print("[VISION] Analyse de l'image avec Gemini...")
        
        # Conversion base64 en bytes pour l'API
        img_bytes = base64.b64decode(img_b64)
        image_part = types.Part.from_bytes(
            data=img_bytes,
            mime_type="image/jpeg"
        )
        
        prompt_actuel = construire_system_prompt()
        prompt_actuel += "\n\nIMPORTANT : Tu viens de recevoir une capture d'écran de Tom. Analyse-la attentivement et réponds à sa question en te basant sur ce que tu vois."
        
        # On envoie l'image et le texte avec retry en cas de 503
        contents = [
            types.Content(role="user", parts=[image_part, types.Part(text=texte)])
        ]
        
        rep = None
        last_err = None
        for model_name in MODELS_LIST:
            print(f"[VISION] Essai modele : {model_name}")
            for attempt in range(2): # 2 tentatives par modele
                try:
                    print(f"[VISION] Appel modele : {model_name} (Timeout 15s)")
                    response = await gemini_generate_with_failover(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_actuel,
                            temperature=0.7,
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                        ),
                        timeout=15.0,
                    )
                    rep = response.text
                    break
                except Exception as e:
                    if ("503" in str(e) or "overloaded" in str(e).lower()) and attempt < 1:
                        print(f"[VISION] Surcharge {model_name} (503). Retente...")
                        await asyncio.sleep(1)
                        continue
                    print(f"[VISION] Erreur {model_name} : {e}")
                    last_err = e
                    break
            if rep: break
        
        if not rep:
            err_str = str(last_err).lower() if last_err else ""
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                print("[VISION] Quota Gemini epuise — vision impossible sans Gemini.")
                return ("Désolé Tom, mon quota Gemini est épuisé pour aujourd'hui. "
                        "La vision par caméra et écran fonctionne uniquement avec Gemini — "
                        "je ne peux donc pas analyser d'images en ce moment. "
                        "Réessayez demain quand le quota sera réinitialisé.")
            print("[VISION] Tous les modeles Gemini ont echoue. Bascule sur Grok (Texte uniquement)...")
            if grok_client:
                return await demander_grok(texte + " (Note: Je n'ai pas pu voir ton écran car mes serveurs de vision sont indisponibles, je réponds donc uniquement à ton texte).")
            raise last_err or Exception("Aucun modele n'a pu analyser l'image")

        # On ajoute la trace dans l'historique (sans l'image pour éviter de saturer la mémoire)
        historique.append(types.Content(role="user", parts=[types.Part(text=f"[Analyse d'écran] {texte}")]))
        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        
        return rep
    except Exception as e:
        print(f"[VISION] Erreur Gemini Vision : {e}")
        # On évite les accolades dans le message d'erreur pour ne pas perturber l'extracteur JSON
        err_msg = str(e).replace("{", "[").replace("}", "]")
        return f"Désolé Tom, je n'ai pas pu analyser votre écran. Erreur : {err_msg}"
    finally:
        is_thinking = False
        await send_web_state("idle")

def detecter_cerveau(texte):
    # Heuristique pour basculer sur Grok uniquement pour X/Twitter
    mots_cles_grok = ["sur x", "twitter", "grok", "elon", "x.com"]
    cmd = texte.lower()
    if any(m in cmd for m in mots_cles_grok):
        return "GROK"
    return "GEMINI"

def erreur_quota_gemini(err):
    msg = str(err).lower()
    return "429" in msg or "resource_exhausted" in msg or "quota exceeded" in msg or "retrydelay" in msg

def extraire_retry_quota_secondes(err):
    msg = str(err)
    match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", msg, re.IGNORECASE)
    if match:
        try:
            return max(5.0, float(match.group(1)))
        except Exception:
            return 60.0
    match = re.search(r"'retryDelay':\s*'(\d+)s'", msg)
    if match:
        try:
            return max(5.0, float(match.group(1)))
        except Exception:
            return 60.0
    return 60.0

async def demander_grok(texte):
    if not grok_client:
        return None
    
    try:
        # Conversion de l'historique Gemini vers format OpenAI pour Grok
        messages = [{"role": "system", "content": "Tu es J.A.R.V.I.S, l'IA de Tom. Tu utilises actuellement ton module Grok pour les infos en temps reel."}]
        for h in historique[-6:]: # Limiter aux 6 derniers messages pour eviter de saturer le contexte
            role = "user" if h.role == "user" else "assistant"
            msg_text = h.parts[0].text
            messages.append({"role": role, "content": msg_text})
        
        messages.append({"role": "user", "content": texte})
        
        completion = grok_client.chat.completions.create(
            model="grok-3", 
            messages=messages,
            temperature=0.7,
        )
        
        rep = completion.choices[0].message.content
        
        # On synchronise l'historique Gemini
        historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        
        return rep
    except Exception as e:
        print(f"[ERREUR GROK] {e}")
        return None

async def demander_ollama(texte):
    """Appelle un modèle local via Ollama (100% offline)."""
    global historique
    if not OLLAMA_CONFIGURED:
        return None
    try:
        # On prépare les messages au format Ollama (compatible OpenAI)
        messages = [{"role": "system", "content": "Tu es J.A.R.V.I.S, l'IA de Tom. Tu utilises actuellement ton module local Ollama. Réponds en français, de façon concise et élégante."}]
        for h in historique[-4:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
        messages.append({"role": "user", "content": texte})
        
        last_err = None
        for model_name in OLLAMA_MODELS:
            try:
                print(f"[OLLAMA] Essai modele local : {model_name}")
                resp = await asyncio.wait_for(
                    asyncio.to_thread(
                        requests.post,
                        f"{OLLAMA_URL}/api/chat",
                        json={"model": model_name, "messages": messages, "stream": False},
                        timeout=30
                    ),
                    timeout=35.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    rep = data.get("message", {}).get("content", "")
                    if rep:
                        historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
                        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
                        print(f"[OLLAMA] Reponse recue de {model_name}")
                        return rep
                else:
                    print(f"[OLLAMA] Erreur HTTP {resp.status_code} pour {model_name}")
                    last_err = Exception(f"HTTP {resp.status_code}")
            except Exception as e:
                print(f"[OLLAMA] Echec {model_name} : {e}")
                last_err = e
                continue
        
        print(f"[OLLAMA] Tous les modeles locaux ont echoue")
        return None
    except Exception as e:
        print(f"[ERREUR OLLAMA] {e}")
        return None

async def demander_groq(texte):
    """Appelle Groq (Llama 3.3) en fallback gratuit."""
    if not groq_client:
        return None
    
    try:
        messages = [{"role": "system", "content": "Tu es J.A.R.V.I.S, l'IA de Tom. Tu utilises actuellement le modèle Llama 3.3 de Groq pour répondre rapidement."}]
        for h in historique[-6:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
        messages.append({"role": "user", "content": texte})
        
        completion = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
        )
        
        rep = completion.choices[0].message.content
        
        historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
        historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        
        return rep
    except Exception as e:
        print(f"[ERREUR GROQ] {e}")
        return None

async def demander_blague():
    if not blagues_client:
        if BlaguesAPI is None:
            return "Le module Blagues API n'est pas installe sur cette machine, Tom."
        return "L'API de blagues n'est pas configuree, Tom. Ajoutez d'abord le token dans les reglages."

    try:
        print("[BLAGUES] Requete vers Blagues API...")
        blague = await blagues_client.random()
        setup = str(getattr(blague, "joke", "") or getattr(blague, "question", "") or "").strip()
        delivery = str(getattr(blague, "answer", "") or getattr(blague, "response", "") or "").strip()
        print(f"[BLAGUES] Blague recue id={getattr(blague, 'id', 'inconnu')}")

        if setup and delivery:
            return f"{setup} ... {delivery}"
        if setup:
            return setup
        if delivery:
            return delivery
        return "J'ai bien recu une blague, Tom, mais elle est etrangement vide."
    except Exception as e:
        print(f"[BLAGUES] Erreur API : {e}")
        return f"Je n'ai pas reussi a recuperer une blague pour le moment, Tom. {e}"

async def generer_image_gemini(prompt):
    if not client:
        return None, "Gemini n'est pas configure sur cette machine, Tom."

    try:
        print(f"[IMAGE] Generation demandee : {prompt}")
        response = await gemini_generate_with_failover(
            model="gemini-2.5-flash-image",
            contents=[prompt],
            timeout=20.0,
        )

        parts = []
        if getattr(response, "parts", None):
            parts = list(response.parts)
        else:
            for candidate in getattr(response, "candidates", []) or []:
                content = getattr(candidate, "content", None)
                if content and getattr(content, "parts", None):
                    parts.extend(content.parts)

        image_part = None
        text_parts = []
        for part in parts:
            if getattr(part, "inline_data", None) is not None:
                image_part = part
                break
            if getattr(part, "text", None):
                text_parts.append(part.text)

        if image_part is None:
            info = " ".join(text_parts).strip()
            return None, (info or "Gemini n'a pas renvoye d'image exploitable, Tom.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jarvis_image_{timestamp}.png"
        out_path = GENERATED_IMAGES_DIR / filename
        image = image_part.as_image()
        image.save(out_path)
        print(f"[IMAGE] Image enregistree : {out_path}")
        return filename, None
    except Exception as e:
        print(f"[IMAGE] Erreur generation : {e}")
        return None, f"Je n'ai pas pu generer l'image pour le moment, Tom. {e}"

async def action_whatsapp_appel(contact):
    try:
        await parler(f"J'appelle {contact} sur WhatsApp, Tom.")
        # Lancement de l'app via le protocole URI (Linux)
        subprocess.Popen(["xdg-open", "whatsapp://"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(6) # On laisse le temps a l'app de s'ouvrir et se focuser
        
        # Recherche du contact (Ctrl+F)
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(1)
        # pyperclip + Ctrl+V pour supporter les accents et caractères spéciaux
        try:
            import pyperclip
            pyperclip.copy(contact)
            pyautogui.hotkey('ctrl', 'v')
        except Exception:
            pyautogui.typewrite(contact, interval=0.05)
        time.sleep(2)
        pyautogui.press('enter')
        time.sleep(3) # On attend que la conversation s'affiche bien
        
        # Utilisation du raccourci clavier officiel pour l'appel audio (plus fiable que la vision)
        print(f"[WHATSAPP] Envoi du raccourci d'appel (Ctrl+Shift+C)...")
        pyautogui.hotkey('ctrl', 'shift', 'c')
        
        # On ajoute quand meme un petit clic de vision en secours si le raccourci ne suffit pas
        time.sleep(2)
        print(f"[WHATSAPP] Verification par vision au cas ou...")
        await jarvis_vision_cliquer("clique sur le bouton 'Appel vocal' ou l icone de telephone qui vient de s afficher en haut a droite")
        
        return True
    except Exception as e:
        print(f"[WHATSAPP ERROR] {e}")
        await parler(f"Desole Tom, je n'ai pas pu lancer l'appel WhatsApp. {e}")
        return False

async def resoudre_commandes_locales(texte):
    """Détecte et exécute les commandes locales (Spotify, dossiers, apps) sans IA."""
    t = texte.lower().strip()

    image_prefixes = [
        "genere moi une image de ", "génère moi une image de ",
        "genere une image de ", "génère une image de ",
        "fais moi une image de ", "fais-moi une image de ",
        "cree une image de ", "crée une image de ",
        "fabrique une image de "
    ]
    for prefix in image_prefixes:
        if t.startswith(prefix):
            prompt = texte[len(prefix):].strip(" .!?")
            if prompt:
                return json.dumps({"action": "generate_image", "prompt": prompt}, ensure_ascii=False)

    if "pronote" in t or any(expr in t for expr in ["emploi du temps", "devoir", "devoirs", "notes", "moyenne", "absences", "retards"]):
        if not current_user_is_owner():
            return command_access_denied("Pronote")
        if "emploi du temps" in t or "edt" in t or "cours" in t:
            return pronote_timetable_resume("tomorrow" if "demain" in t else "today")
        if "devoir" in t:
            return pronote_homework_resume()
        if any(expr in t for expr in ["note", "notes", "moyenne", "evaluation", "evaluations"]):
            return pronote_grades_resume()
        if any(expr in t for expr in ["absence", "absences", "retard", "retards"]):
            return pronote_home_assistant_resume()
        if any(expr in t for expr in ["resume", "résumé", "infos", "informations", "tout"]):
            return pronote_home_assistant_resume()

    if est_requete_meteo_generale(texte) and not re.search(r"\b(?:a|à)\s+[a-zà-ÿ' -]{2,}", t):
        if current_user_is_owner():
            print("[METEO] Requete generale detectee -> Home Assistant prioritaire")
            return repondre_meteo_maison_ou_ville(None)
        return repondre_meteo_maison_ou_ville(HOME_LOCATION_NAME or None)

    if any(expr in t for expr in [
        "raconte une blague", "raconte-moi une blague", "raconte moi une blague",
        "fais moi une blague", "fais-moi une blague", "dis une blague",
        "sors une blague", "balance une blague", "une blague"
    ]):
        return await demander_blague()

    if any(mot in t for mot in ["administrateur", "administrator", "permission admin", "perm admin", "droit admin", "droits admin", "role admin", "rôle admin"]):
        if any(mot in t for mot in ["utilisateur", "user", "luser", "compte"]) or re.search(r"\b(?:a|à)\b\s+[a-z0-9_.@-]+", t):
            commande_acl = proxmox_parser_commande_directe(texte)
            if commande_acl:
                return commande_acl
        if any(mot in t for mot in ["donner", "donne", "ajouter", "ajoute", "rajoute", "attribuer", "attribue", "mettre", "mets"]):
            return "Je peux le faire, Tom, mais il me faut le nom de l'utilisateur Proxmox."

    if "proxmox" in t and any(k in t for k in ["utilisateur", "utilisateurs", "user", "users", "compte", "comptes", "acces", "accès", "permission", "permissions"]):
        if not current_user_is_owner():
            return command_access_denied("Proxmox")
        return proxmox_resume_utilisateurs()

    if "proxmox" in t and not current_user_is_owner():
        return command_access_denied("Proxmox")

    emby_aliases = ["emby", "mby", "mbaye", "aime bi", "aimeby", "hemby"]
    parle_emby = any(alias in t for alias in emby_aliases)

    if parle_emby and not current_user_is_owner():
        return command_access_denied("Emby")

    if parle_emby:
        if any(k in t for k in ["en cours", "lecture", "lectures", "lit", "regarde", "playing", "session", "sessions"]):
            return emby_resume_en_cours()
        if any(k in t for k in ["reprendre", "continue", "continuer", "reprise", "resume"]):
            return emby_resume_reprises()
        if any(k in t for k in ["ajout", "ajouts", "recent", "recents", "récents", "nouveau", "nouveautés", "neuf"]):
            return emby_resume_derniers_ajouts()
        if any(k in t for k in ["bibliotheque", "bibliothèque", "librairie", "stats", "statistiques", "combien"]):
            return emby_resume_bibliotheque()
        return emby_resume_global()

    commande_proxmox = proxmox_parser_commande_directe(texte)
    if commande_proxmox:
        return commande_proxmox

    # --- PROXMOX (Priorité 0) ---
    if "proxmox" in t:
        if any(k in t for k in ["utilisateur", "utilisateurs", "user", "users", "compte", "comptes", "acces", "accès", "permission", "permissions"]):
            return proxmox_resume_utilisateurs()
        if any(k in t for k in ["stockage", "stockages", "disque", "disques", "storage"]):
            return proxmox_resume_stockages()
        if any(k in t for k in ["noeud", "nœud", "noeuds", "nœuds", "cluster"]):
            return proxmox_resume_noeuds()
        if any(k in t for k in ["vm", "vms", "machine virtuelle", "machines virtuelles", "conteneur", "conteneurs", "lxc"]):
            return proxmox_resume_vms()
        if any(k in t for k in ["etat", "état", "status", "statut", "serveur", "noeud", "nœud", "hyperviseur"]):
            return proxmox_resume_statut()
        return proxmox_resume_statut()
    
    # --- DOSSIERS (Priorité 1) ---
    if any(k in t for k in ["ouvre tous les dossiers", "ouvre tous mes dossiers", "ouvre mes dossiers", "ouvre les dossiers", "mes dossiers", "range mes dossiers", "mosaïque dossiers"]):
        return arranger_fenetres_dossiers()

    prefixes_dossiers = ["ouvre le dossier ", "ouvre mon dossier ", "ouvre le répertoire ", "ouvre le repertoire ", "ouvre dossier ", "ouvre ", "mets "]
    # On vérifie d'abord si c'est un dossier connu
    mots_cles_dossiers = ["bureau", "document", "téléchargement", "image", "photo", "vidéo", "musique", "corbeille"]
    
    for prefix in prefixes_dossiers:
        if t.startswith(prefix):
            potentiel_dossier = t.replace(prefix, "").strip()
            # Si le mot après le préfixe est un dossier connu, on l'ouvre
            if any(k in potentiel_dossier for k in mots_cles_dossiers):
                ok, msg = ouvrir_dossier(potentiel_dossier)
                if ok: return f"J'ouvre le dossier {potentiel_dossier}, Tom."

    # --- WEB MUSIC (Priorité 2) ---
    if JARVIS_HEADLESS:
        if any(k in t for k in ["stop la musique", "arrête la musique", "arrete la musique", "stop youtube"]):
            return '{"action": "music_stop"}'
        if any(k in t for k in ["mets en pause", "pause la musique", "pause youtube"]):
            return '{"action": "music_pause"}'
        if any(k in t for k in ["reprends la musique", "remets la musique", "reprends youtube", "lecture"]):
            return '{"action": "music_play"}'

        music_action = youtube_music_action_from_text(t)
        if music_action and "spotify" not in t:
            return music_action

    # --- SPOTIFY (Priorité 3) ---
    if any(k in t for k in ["ouvre spotify", "lance spotify", "démarre spotify"]):
        return await spotify_ouvrir()
    
    if any(k in t for k in ["mets en pause", "stop la musique", "arrête la musique"]):
        return await spotify_stop()
    if any(k in t for k in ["lecture", "remets la musique", "reprends la musique"]):
        return await spotify_lecture_pause()
    if any(k in t for k in ["suivante", "chanson suivante", "piste suivante"]):
        return await spotify_suivant()
    if any(k in t for k in ["précédente", "chanson précédente", "reviens en arrière"]):
        return await spotify_precedent()
    if any(k in t for k in ["monte le volume", "augmente le son", "plus fort"]):
        return await spotify_volume("monter")
    if any(k in t for k in ["baisse le son", "baisse le volume", "moins fort"]):
        return await spotify_volume("baisser")

    # Détection de recherche Spotify
    prefixes_recherche = ["joue du ", "joue de la ", "mets du ", "mets de la ", "joue ", "mets ", "recherche ", "lance "]
    for prefix in prefixes_recherche:
        if t.startswith(prefix):
            recherche = t.replace(prefix, "").replace(" sur spotify", "").strip()
            if len(recherche) > 1:
                return await spotify_rechercher(recherche)
    
    raccourcis_dossiers = {
        "bureau": "bureau",
        "documents": "documents",
        "téléchargements": "downloads",
        "téléchargement": "downloads",
        "images": "images",
        "vidéos": "videos",
        "musique": "musique"
    }
    for cle, chemin in raccourcis_dossiers.items():
        if f"ouvre mon {cle}" in t or f"ouvre le {cle}" in t or t == f"ouvre {cle}":
            ouvrir_dossier(chemin)
            return f"J'ouvre votre dossier {cle}, Tom."

    # --- APPLICATIONS ---
    def _lancer_app(*cmds):
        for c in cmds:
            try:
                subprocess.Popen(c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except FileNotFoundError:
                continue
        return False

    apps = {
        "calculatrice":           [["gnome-calculator"], ["kcalc"], ["galculator"], ["xcalc"]],
        "chrome":                 [["google-chrome"], ["google-chrome-stable"], ["chromium"], ["chromium-browser"]],
        "navigateur":             [["google-chrome"], ["google-chrome-stable"], ["chromium"], ["firefox"]],
        "firefox":                [["firefox"]],
        "spotify":                [["spotify"], ["snap", "run", "spotify"], ["flatpak", "run", "com.spotify.Client"]],
        "éditeur":                [["gedit"], ["kate"], ["mousepad"], ["xed"]],
        "bloc-notes":             [["gedit"], ["kate"], ["mousepad"], ["xed"]],
        "paint":                  [["gimp"], ["pinta"], ["kolourpaint"]],
        "gestionnaire de tâches": [["gnome-system-monitor"], ["ksysguard"], ["xfce4-taskmanager"]],
        "terminal":               [["gnome-terminal"], ["konsole"], ["xfce4-terminal"], ["xterm"]],
        "fichiers":               [["nautilus"], ["dolphin"], ["thunar"], ["nemo"]],
    }
    for nom, commandes in apps.items():
        if f"ouvre {nom}" in t or f"lance {nom}" in t:
            ok = _lancer_app(*commandes)
            return f"J'ouvre {nom}, Tom." if ok else f"Application '{nom}' introuvable sur ce système."

    return None

def requete_recette_visuelle_locale(texte):
    t = str(texte or "").lower().strip()
    if not re.search(r"\b(recette|cuisine|comment faire|preparer|préparer)\b", t):
        return None
    query = re.sub(r"\b(donne moi|donne-moi|peux tu|peux-tu|trouve moi|cherche moi|une|un)\b", " ", texte, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip(" ,.!?;:")
    if "recette" not in query.lower():
        query = f"recette {query}"
    return query


async def envoyer_recherche_visuelle_web(query, *, inclure_texte=False):
    try:
        details = await asyncio.to_thread(recherche_web_serpapi_details, query)
        payload = {
            "query": query,
            "items": details.get("items", []),
            "images": details.get("images", []),
        }
        if inclure_texte:
            payload["text"] = details.get("text", "")
        await send_web_action("web_results", **payload)
    except Exception as e:
        print(f"[WEB] Erreur panneau visuel : {e}")


def requete_visuelle_web_locale(texte):
    t = str(texte or "").lower().strip()
    if any(k in t for k in ["cherche sur internet", "recherche web", "recherche internet", "cherche moi", "trouve moi"]):
        query = re.sub(r"\b(cherche sur internet|recherche web|recherche internet|cherche moi|trouve moi|donne moi|peux tu|peux-tu)\b", " ", texte, flags=re.IGNORECASE)
        query = re.sub(r"\s+", " ", query).strip(" ,.!?;:")
        return query or texte.strip()
    return None

async def traiter_reponse_ia(texte_utilisateur, mobile_ws=None, auth_user=None, http_client_id=""):
    global MODE_IRON_MAN, jarvis_actif, dernier_message, _skip_pc_audio
    COMMAND_CONTEXT.set(build_command_context(auth_user, client_id=http_client_id))
    COMMAND_HTTP_CLIENT_ID.set(http_client_id or "")
    # Reset du flag audio au début de chaque commande
    _skip_pc_audio = False

    # TENTATIVE DE RÉSOLUTION LOCALE (Commandes, Math, Français, etc.)
    reponse = await resoudre_commandes_locales(texte_utilisateur)
    if not reponse: reponse = resoudre_infos_systeme_localement(texte_utilisateur)
    if not reponse: reponse = resoudre_math_localement(texte_utilisateur)
    if not reponse: reponse = resoudre_francais_localement(texte_utilisateur)
    if not reponse: reponse = resoudre_conversion_localement(texte_utilisateur)
    if not reponse: reponse = resoudre_traduction_localement(texte_utilisateur)
    if not reponse: reponse = resoudre_apis_publiques_localement(texte_utilisateur)
    if not reponse:
        web_query = requete_visuelle_web_locale(texte_utilisateur)
        if web_query:
            reponse = json.dumps({"action": "recherche_web", "query": web_query}, ensure_ascii=False)
    
    # VISION (Regarde mon écran)
    if not reponse:
        t = texte_utilisateur.lower()
        if any(keyword in t for keyword in ["regarde mon écran", "analyse mon écran", "vois-tu mon écran", "qu'est-ce qu'il y a sur mon écran"]):
            await parler("Bien sûr Tom, laissez-moi jeter un œil...")
            img_b64 = await request_screen_capture()
            if img_b64:
                reponse = await demander_ia_vision(texte_utilisateur, img_b64)
            else:
                reponse = "Je suis désolé Tom, mais je n'ai pas pu capturer votre écran. Assurez-vous d'avoir cliqué sur 'Activer la vision' sur l'interface et d'avoir autorisé le partage."
        
        # CAMERA (Lance la caméra / Analyse visuelle / Objets / Tenue)
        camera_keywords = [
            # Caméra générale (avec ET sans accents pour la reconnaissance vocale)
            "lance la caméra", "lance la camera",
            "ouvre la caméra", "ouvre la camera",
            "regarde avec la caméra", "regarde avec la camera",
            "active la caméra", "active la camera",
            "analyse ce que tu vois", "qu'est-ce que tu vois",
            "regarde-moi", "regarde moi", "analyse-moi", "analyse moi",
            # Tenue / Vêtements
            "ma tenue", "mes vêtements", "mes vetements",
            "comment je suis habillé", "comment je suis habille",
            "montre-moi", "est-ce que ça me va", "est-ce que ca me va",
            "ça me va", "ca me va",
            "qu'est-ce que je porte", "je porte quoi",
            # Objets / Identification
            "c'est quoi ça", "c'est quoi ca", "qu'est-ce que c'est",
            "décris cet objet", "decris cet objet", "c'est quoi cet objet",
            "identifie", "reconnais", "qu'est-ce que je te montre",
            "je te montre", "regarde ça", "regarde ca",
            "tu vois quoi", "dis-moi ce que c'est", "analyse ça", "analyse ca",
            # Webcam
            "webcam", "la cam",
        ]
        if any(keyword in t for keyword in camera_keywords):
            reponse = await jarvis_vision_camera(texte_utilisateur)

    if not reponse:
        reponse = await demander_ia(texte_utilisateur)
    
    print(f"[J.A.R.V.I.S] {reponse}")

    # Si commande mobile : activer le flag pour couper l'audio PC et répondre via mobile
    if mobile_ws:
        _skip_pc_audio = True

    # Recherche de TOUS les blocs JSON dans la réponse
    json_blocks = re.findall(r'\{.*?\}', reponse, re.DOTALL)
    
    if not json_blocks:
        recette_web_query = requete_recette_visuelle_locale(texte_utilisateur)
        if recette_web_query:
            asyncio.create_task(envoyer_recherche_visuelle_web(recette_web_query))
        await parler(reponse)
        _skip_pc_audio = False
        return

    for block in json_blocks:
        try:
            print(f"[J.A.R.V.I.S] Execution de l'action : {block}")
            # Timeout de 15s pour chaque action pour eviter de freezer Jarvis
            data = json.loads(block)
            action = data.get("action", "")
            if action_requires_owner(action) and not current_user_is_owner():
                await parler(command_access_denied("Home Assistant" if action.startswith("ha_") else "Proxmox"))
                continue
            
            # On execute l'action avec un timeout
            try:
                # Note: On utilise asyncio.wait_for pour les actions asynchrones
                # Les actions synchrones comme ha_lumiere devraient idéalement être async aussi
                # mais pour l'instant on les laisse ainsi ou on les wrappe.
                pass 
            except asyncio.TimeoutError:
                print(f"[ACTION ERROR] Timeout sur l'action {action}")
                if grok_client:
                    await parler("C'est un peu long Tom, je demande une vérification à Grok.")
                    rep_grok = await demander_grok(texte_utilisateur + " (L'action domotique a expiré, peux-tu répondre à l'utilisateur ?)")
                    if rep_grok: await parler(rep_grok)
                continue

            if action == "mode_iron_man":
                etat = data.get("etat", "off")
                MODE_IRON_MAN = (etat == "on")
                msg = "Mode Iron Man activé, Monsieur. Je reste à l'écoute de vos signaux." if MODE_IRON_MAN else "Mode Iron Man désactivé. Je repasse en veille domotique."
                await parler(msg)
            elif action == "memoriser":
                cle    = data.get("cle",    "info")
                valeur = data.get("valeur", "")
                ajouter_memoire(cle, valeur)
                await parler(f"Bien note Tom, je me souviendrai que {valeur}.")
            elif action == "oublier":
                cle     = data.get("cle", "")
                success = supprimer_memoire(cle)
                if success:
                    await parler("Information oubliee, Tom.")
                else:
                    await parler("Je n avais pas cette information en memoire.")
            elif action == "lister_memoire":
                memoire = charger_memoire()
                if not memoire:
                    await parler(f"Aucune information personnalisee en memoire pour {get_current_memory_label()}.")
                else:
                    lignes = [f"Voici ce que je sais pour {get_current_memory_label()}."]
                    for cle, data_m in memoire.items():
                        lignes.append(f"{cle} : {data_m['valeur']}.")
                    await parler(" ".join(lignes))
            elif action == "ouvrir_dossier":
                chemin = data.get("chemin", "bureau")
                ok, resultat = ouvrir_dossier(chemin)
                if ok:
                    await parler("Dossier ouvert, Tom. Dites-moi si vous voulez que je le trie.")
                else:
                    await parler(f"Je n ai pas trouve ce dossier, Tom. {resultat}")
            elif action == "lister_dossier":
                contenu, err = lister_dossier()
                if err:
                    await parler(err)
                else:
                    nb_fichiers = len(contenu["fichiers"])
                    nb_dossiers = len(contenu["dossiers"])
                    await parler(f"Le dossier contient {nb_fichiers} fichiers et {nb_dossiers} sous-dossiers, Tom.")
            elif action == "trier_par_type":
                await parler("Je trie vos fichiers par type, Tom. Un instant.")
                ok, msg = trier_par_type()
                await parler(msg if ok else f"Probleme lors du tri : {msg}")
            elif action == "trier_par_date":
                await parler("Je trie vos fichiers par date, Tom. Un instant.")
                ok, msg = trier_par_date()
                await parler(msg if ok else f"Probleme lors du tri : {msg}")
            elif action == "trier_complet":
                await parler("Je trie vos fichiers par type puis par date dans chaque categorie, Tom.")
                ok, msg = trier_par_type_puis_date()
                await parler(msg if ok else f"Probleme lors du tri : {msg}")
            elif action == "creer_dossier":
                nom     = data.get("nom", "Nouveau Dossier")
                ok, msg = creer_sous_dossier(nom)
                await parler(msg if ok else f"Erreur : {msg}")
            elif action == "renommer_fichier":
                ancien  = data.get("ancien", "")
                nouveau = data.get("nouveau", "")
                ok, msg = renommer_fichier(ancien, nouveau)
                await parler(msg if ok else f"Erreur : {msg}")
            elif action == "deplacer_fichier":
                fichier = data.get("fichier",     "")
                dest    = data.get("destination", "")
                ok, msg = deplacer_fichier(fichier, dest)
                await parler(msg if ok else f"Erreur : {msg}")
            elif action == "chercher_fichier":
                nom        = data.get("nom", "")
                resultats, err = chercher_fichier(nom)
                if err:
                    await parler(err)
                elif not resultats:
                    await parler(f"Aucun fichier contenant {nom} n a ete trouve, Tom.")
                else:
                    noms = [os.path.basename(r) for r in resultats[:5]]
                    await parler(f"J ai trouve {len(resultats)} fichier(s). Par exemple : {', '.join(noms)}.")
            elif action == "ha_lumiere":
                piece      = data.get("piece",      "salon")
                etat       = data.get("etat",       "on")
                couleur    = data.get("couleur",    None)
                luminosite = data.get("luminosite", None)
                entity_id  = PIECES_LUMIERES.get(piece, f"light.{piece}")
                rgb        = COULEURS_MAP.get(couleur) if couleur else None
                ha_lumiere(entity_id, etat, luminosite, rgb)
                
                # Message de confirmation amélioré
                if etat == "off":
                    msg = f"J'éteins {piece}."
                else:
                    details = []
                    if couleur: details.append(f"en {couleur}")
                    if luminosite is not None: 
                        pourcent = int((int(luminosite)/255)*100)
                        details.append(f"à {pourcent}%")
                    
                    if details:
                        msg = f"C'est fait, {piece} est réglé{' '.join(details)}."
                    else:
                        msg = f"Lumière {piece} allumée."
                await parler(msg)
            elif action == "ha_prise":
                piece     = data.get("piece", "bureau")
                etat      = data.get("etat",  "on")
                entity_id = PIECES_PRISES.get(piece, f"switch.prise_{piece}")
                ha_interrupteur(entity_id, etat)
                msg = f"Prise {piece} {'activée' if etat == 'on' else 'désactivée'}."
                await parler(msg)
            elif action == "ha_temperature":
                piece     = data.get("piece", "salon")
                entity_id = PIECES_CAPTEURS.get(piece)
                if entity_id:
                    temp = ha_get_etat(entity_id)
                    await parler(f"La température dans le {piece} est de {temp} degrés.")
                else:
                    await parler(f"Désolé, je n'ai pas de capteur configuré pour le {piece}.")
            elif action == "ha_humidite":
                piece     = data.get("piece", "bureau")
                entity_id = PIECES_HUMIDITE.get(piece)
                if entity_id:
                    humi = ha_get_etat(entity_id)
                    await parler(f"Le taux d'humidité dans le {piece} est de {humi}%.")
                else:
                    await parler(f"Je n'ai pas de capteur d'humidité pour le {piece}.")
            elif action == "ha_batterie":
                appareil  = data.get("appareil", "").lower()
                entity_id = APPAREILS_BATTERIE.get(appareil)
                if entity_id:
                    batt = ha_get_etat(entity_id)
                    if batt == "unknown":
                        await parler(f"Je n'arrive pas à récupérer l'état de la batterie pour {appareil}.")
                    else:
                        suff = ""
                        if "telephone" in appareil or "papa" in appareil or "tom" in appareil:
                            suff = "Ton téléphone est à "
                        elif "julie" in appareil or "maman" in appareil:
                            suff = "Le téléphone de Julie est à "
                        else:
                            suff = f"La batterie de {appareil} est à "
                        await parler(f"{suff}{batt}%.")
                else:
                    await parler(f"Je n'ai pas l'appareil {appareil} dans ma liste de batterie.")
            elif action == "ha_thermostat":
                temp = data.get("temperature", 20)
                ha_thermostat("climate.thermostat", temp)
                await parler(f"Thermostat réglé à {temp} degrés.")
            elif action == "ha_scene":
                nom      = data.get("nom", "")
                scene_id = f"scene.{nom}"
                ha_scene(scene_id)
                await parler(f"Ambiance {nom} activée.")
            elif action == "ha_alarme":
                etat = data.get("etat", "on")
                if etat == "on":
                    ha_appeler_service("alarm_control_panel", "alarm_arm_away", "alarm_control_panel.home_base_2")
                    await parler("Alarme activée.")
                else:
                    ha_appeler_service("alarm_control_panel", "alarm_disarm", "alarm_control_panel.home_base_2")
                    await parler("Alarme désactivée.")
            elif action == "ha_simulation":
                etat = data.get("etat", "on")
                ha_interrupteur("switch.simulation", etat)
                msg = "Simulation de présence activée." if etat == "on" else "Simulation de présence désactivée."
                await parler(msg)
            elif action == "ha_anniversaires":
                events = ha_get_calendrier("calendar.anniversaires")
                if not events:
                    await parler("Rien de prévu aujourd'hui.")
                else:
                    noms = [e.get("summary", "Anniversaire sans nom") for e in events]
                    if len(noms) == 1:
                        await parler(f"Aujourd'hui, nous fêtons l'anniversaire de {noms[0]}. N'oubliez pas de lui souhaiter !")
                    else:
                        liste = ", ".join(noms[:-1]) + " et " + noms[-1]
                        await parler(f"Aujourd'hui, il y a plusieurs anniversaires : {liste}. C'est une journée chargée !")
            elif action == "ha_consommation":
                entity_id = PIECES_CAPTEURS.get("consommation")
                puissance = ha_get_etat(entity_id)
                if puissance == "unknown" or puissance == "inconnu":
                    await parler("Je n'arrive pas à lire la consommation électrique pour le moment.")
                else:
                    await parler(f"La consommation actuelle de la maison est de {puissance} Volt-Ampères.")
            elif action == "ha_tiktok":
                entity_id = PIECES_CAPTEURS.get("tiktok")
                followers = ha_get_etat(entity_id)
                await parler(f"Tu as actuellement {followers} abonnés sur ton compte TikTok TechEnClair, Tom. Félicitations !")
            elif action == "ha_oeufs":
                entity_id = PIECES_CAPTEURS.get("oeufs")
                # On récupère l'état (le dernier choix) et le moment de la modif
                try:
                    if not HA_CONFIGURED:
                        await parler("Home Assistant n'est pas configuré, Tom.")
                        continue
                    r = requests.get(f"{HA_URL}/api/states/{entity_id}", headers=HA_HEADERS, timeout=5)
                    data = r.json()
                    last_changed = data.get("last_changed", "")
                    if last_changed:
                        dt = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
                        phrase = dt.strftime("le %d %B à %Hh%M")
                        await parler(f"Le dernier ramassage des œufs a été enregistré {phrase}.")
                    else:
                        await parler("Je n'ai pas d'historique pour le ramassage des œufs.")
                except:
                    await parler("Je n'arrive pas à accéder aux informations sur les œufs.")
            elif action == "ha_energie":
                periode  = data.get("periode", "mois")
                appareil = data.get("appareil", "")
                
                if appareil:
                    appareil_clean = appareil.lower()
                    entite = APPAREILS_ENERGIE.get(appareil_clean)
                    if entite:
                        val = ha_get_etat(entite)
                        if val != "inconnu" and val != "unknown":
                            kwh = float(val)
                            await parler(f"La consommation de {appareil} pour ce mois est de {kwh:.1f} kWh.")
                        else:
                            await parler(f"Je n'ai pas de données de consommation pour {appareil} pour le moment.")
                    else:
                        await parler(f"Je n'ai pas d'appareil nommé {appareil} dans mon suivi énergétique.")
                elif periode == "hier":
                    total_kwh = 0
                    total_cost = 0
                    try:
                        for i in range(1, 7):
                            e_id = f"sensor.lixee_zlinky_tic_zlinky_p{i}_daily"
                            val = ha_get_etat(e_id, attribut="last_period")
                            if val != "inconnu" and val != "unknown":
                                k = float(val)
                                total_kwh += k
                                total_cost += k * HA_TARIFS.get(f"p{i}", 0.16)
                        await parler(f"Hier, la maison a consommé {total_kwh:.1f} kWh, pour un coût estimé à {total_cost:.2f} euros.")
                    except:
                        await parler("J'ai eu un problème pour calculer la consommation d'hier.")
                else: # mois
                    total_kwh = 0
                    total_cost = 0
                    try:
                        for i in range(1, 7):
                            e_id = f"sensor.lixee_zlinky_tic_zlinky_p{i}_mensuel"
                            val = ha_get_etat(e_id)
                            if val != "inconnu" and val != "unknown":
                                k = float(val)
                                total_kwh += k
                                total_cost += k * HA_TARIFS.get(f"p{i}", 0.16)
                        await parler(f"Ce mois-ci, la consommation totale est de {total_kwh:.1f} kWh, pour un montant de {total_cost:.2f} euros.")
                    except:
                        await parler("Je n'ai pas pu calculer la consommation mensuelle.")
            elif action == "ha_aspirateur":
                commande = data.get("commande", "start")
                if commande == "start":
                    ha_appeler_service("vacuum", "start", "vacuum.bob")
                    await parler("C'est parti, Bob lance le nettoyage.")
                elif commande == "stop":
                    ha_appeler_service("vacuum", "stop", "vacuum.bob")
                    await parler("J'ai arrêté l'aspirateur.")
                elif commande == "pause":
                    ha_appeler_service("vacuum", "pause", "vacuum.bob")
                    await parler("Bob est en pause.")
                elif commande == "base":
                    ha_appeler_service("vacuum", "return_to_base", "vacuum.bob")
                    await parler("Bob retourne à sa base.")
            elif action == "create_doc":
                titre   = data.get("title",   "Document J.A.R.V.I.S")
                contenu = data.get("content", "")
                result  = creer_google_doc(titre, contenu)
                await parler(result)
            elif action == "write_doc":
                contenu = data.get("content", "")
                result  = modifier_google_doc(contenu)
                await parler(result)
            elif action == "create_sheet":
                titre  = data.get("title", "Feuille J.A.R.V.I.S")
                result = creer_google_sheet(titre)
                await parler(result)
            elif action == "read_emails":
                result = lire_emails()
                await parler(f"Voici vos derniers emails Tom. {result}")
            elif action == "read_calendar":
                result = lister_evenements_calendar()
                await parler(f"Voici vos prochains evenements Tom. {result}")
            elif action == "meteo":
                ville = data.get("ville") or None
                await parler("Je consulte la meteo, un instant Tom.")
                result = repondre_meteo_maison_ou_ville(ville)
                await parler(result)
            elif action == "emby_status":
                await parler("Je consulte votre espace Emby, un instant.")
                result = emby_resume_global()
                await parler(result)
            elif action == "emby_current":
                result = emby_resume_en_cours()
                await parler(result)
            elif action == "emby_continue":
                result = emby_resume_reprises()
                await parler(result)
            elif action == "emby_latest":
                result = emby_resume_derniers_ajouts()
                await parler(result)
            elif action == "emby_library":
                result = emby_resume_bibliotheque()
                await parler(result)
            elif action == "proxmox_statut":
                await parler("Je consulte l'etat de votre Proxmox, un instant Tom.")
                result = proxmox_resume_statut()
                await parler(result)
            elif action == "proxmox_vms":
                await parler("Je regarde l'etat des VM et des conteneurs Proxmox, Tom.")
                result = proxmox_resume_vms()
                await parler(result)
            elif action == "proxmox_noeuds":
                await parler("Je verifie les noeuds Proxmox, Tom.")
                result = proxmox_resume_noeuds()
                await parler(result)
            elif action == "proxmox_stockages":
                await parler("Je controle les stockages Proxmox, Tom.")
                result = proxmox_resume_stockages()
                await parler(result)
            elif action == "proxmox_utilisateurs":
                await parler("Je regarde les utilisateurs Proxmox, Tom.")
                result = proxmox_resume_utilisateurs()
                await parler(result)
            elif action == "proxmox_user_role_add":
                utilisateur = data.get("utilisateur", "")
                role = data.get("role", "Administrator")
                path_acl = data.get("path", "/")
                result = proxmox_attribuer_role_utilisateur(utilisateur, role, path=path_acl)
                await parler(result)
            elif action == "proxmox_guest_statut":
                cible = data.get("cible", "")
                result = proxmox_resume_guest(cible)
                await parler(result)
            elif action == "proxmox_guest_action":
                cible = data.get("cible", "")
                commande = data.get("commande", "")
                result = proxmox_guest_action(cible, commande)
                await parler(result)
            elif action == "proxmox_bulk_action":
                cible = (data.get("cible", "") or "").lower()
                commande = data.get("commande", "")
                type_cible = None
                if cible in ["vm", "vms", "machines virtuelles", "machine virtuelle"]:
                    type_cible = "qemu"
                elif cible in ["conteneur", "conteneurs", "lxc", "ct", "cts"]:
                    type_cible = "lxc"
                seulement_running = False if commande == "start" else (True if commande in ["stop", "shutdown", "reboot", "suspend"] else None)
                result = proxmox_action_en_masse(commande, type_cible=type_cible, seulement_running=seulement_running)
                await parler(result)
            elif action == "proxmox_snapshots":
                cible = data.get("cible", "")
                result = proxmox_resume_snapshots(cible)
                await parler(result)
            elif action == "proxmox_snapshot_create":
                cible = data.get("cible", "")
                nom = data.get("nom", "")
                result = proxmox_creer_snapshot(cible, nom)
                await parler(result)
            elif action == "alerte_meteo":
                ville = data.get("ville") or None
                result = get_alertes_meteo(ville)
                await parler(result)
            elif action == "recherche_web":
                query = data.get("query", "")
                await parler(f"Je lance une recherche sur internet pour {query}.")
                details = recherche_web_serpapi_details(query)
                await send_web_action(
                    "web_results",
                    query=query,
                    text=details.get("text", ""),
                    items=details.get("items", []),
                    images=details.get("images", []),
                )
                await parler(details.get("text", ""))
            elif action == "sport_resultats":
                equipe = data.get("equipe") or None
                ligue  = data.get("ligue")  or None
                print(f"[SPORT] Action sport_resultats pour {equipe or ligue}")
                await parler(f"Je cherche les informations pour {equipe or ligue}, un instant.")
                result = get_resultats_football(equipe=equipe, ligue=ligue)
                if "pas trouvé" in result or "Impossible" in result:
                    print(f"[SPORT] Echec recherche locale. Verification avec Grok...")
                    if grok_client:
                        res_grok = await demander_grok(f"Tom veut savoir : {texte_utilisateur}. Je n'ai pas trouvé l'info dans ma base de données football, peux-tu chercher pour lui ?")
                        if res_grok: result = res_grok
                await parler(result)
            elif action == "sport_classement":
                ligue  = data.get("ligue", "Ligue 1")
                await parler(f"Je recupere le classement {ligue}.")
                result = get_classement_football(ligue=ligue)
                await parler(result)
            elif action == "sport_live":
                question = data.get("question", "derniers resultats sportifs 2026")
                await parler("Je recherche les derniers resultats en direct, un instant Tom.")
                result = get_resultats_sport_gemini(question)
                await parler(result)
            elif action == "voir_ecran":
                inst = data.get("instruction", "")
                if JARVIS_HEADLESS and est_instruction_vision_descriptive(inst):
                    res = await jarvis_vision_navigateur(inst)
                else:
                    res = await jarvis_vision_cliquer(inst)
                await parler(res)
            elif action == "whatsapp_appel":
                contact = data.get("contact", "Ma vie")
                await action_whatsapp_appel(contact)
            elif action == "vision_ecrire":
                inst = data.get("instruction", "")
                txt  = data.get("texte", "")
                res  = await jarvis_vision_ecrire(inst, txt)
                await parler(res)
            elif action == "vision_chercher_sur_site":
                txt = data.get("texte", "")
                await parler(f"Je cherche la barre de recherche sur ce site, Tom.")
                res = await jarvis_vision_rechercher_sur_site(txt)
                await parler(res)
            elif action == "lance_camera":
                res = await jarvis_vision_camera(texte_utilisateur)
                await parler(res)
            elif action == "vision_navigateur":
                res = await jarvis_vision_navigateur(texte_utilisateur)
                await parler(res)
            elif action == "music_search":
                recherche = data.get("query", "").strip()
                video_id = youtube_trouver_video_id(recherche)
                if video_id:
                    await send_web_action("music_search", query=recherche, video_id=video_id)
                    await parler(f"Je lance {recherche} sur le mini player, Tom.")
                else:
                    await parler(f"Je n'ai pas trouve de video YouTube pour {recherche}, Tom.")
            elif action == "music_play":
                await send_web_action("music_play")
                await parler("Je relance la musique, Tom.")
            elif action == "music_pause":
                await send_web_action("music_pause")
                await parler("Je mets la musique en pause, Tom.")
            elif action == "music_stop":
                await send_web_action("music_stop")
                await parler("J'arrete la lecture, Tom.")
            elif action == "generate_image":
                prompt = data.get("prompt", "").strip()
                if not prompt:
                    await parler("Il me manque la description de l'image a generer, Tom.")
                else:
                    await parler(f"Je genere une image de {prompt}, un instant Tom.")
                    filename, err = await generer_image_gemini(prompt)
                    if err:
                        await parler(err)
                    else:
                        image_url = f"http://{LOCAL_IP}:{HTTP_PORT}/generated/{filename}"
                        await parler(f"Image generee, Tom. Elle est disponible ici : {image_url}")
            elif action == "spotify_ouvrir":
                await parler("J'ouvre Spotify, Tom.")
                res = await spotify_ouvrir()
                await parler(res)
            elif action == "spotify_rechercher":
                recherche = data.get("recherche", "")
                await parler(f"Je recherche '{recherche}' sur Spotify, Tom.")
                res = await spotify_rechercher(recherche)
                await parler(res)
            elif action == "spotify_lecture_pause":
                res = await spotify_lecture_pause()
                await parler(res)
            elif action == "spotify_stop":
                res = await spotify_stop()
                await parler(res)
            elif action == "spotify_suivant":
                res = await spotify_suivant()
                await parler(res)
            elif action == "spotify_precedent":
                res = await spotify_precedent()
                await parler(res)
            elif action == "spotify_volume":
                direction = data.get("direction", "monter")
                paliers   = data.get("paliers", 4)
                res = await spotify_volume(direction, paliers)
                await parler(res)

        except Exception as e:
            print(f"[ACTION ERROR] Block failed: {block} | Error: {e}")
            if grok_client:
                print("[J.A.R.V.I.S] Bascule sur Grok suite a une erreur d'action...")
                res_grok = await demander_grok(f"Tom m'a demandé : {texte_utilisateur}. J'ai tenté de lancer une action mais j'ai eu une erreur technique ({e}). Peux-tu prendre le relais et lui répondre élégamment ?")
                if res_grok: await parler(res_grok)
            continue

    # Si du texte reste après les commandes, on ne fait rien de plus car `parler` a déjà été appelé pour chaque action ou la réponse globale.
    # Réinitialiser le flag audio PC
    _skip_pc_audio = False

def nettoyer_commande(texte):
    t = texte.lower().strip()
    for variante in ["jarvis,", "jarvis"]:
        if t.startswith(variante):
            t = t[len(variante):].strip()
    return t

WAKE_WORD       = "jarvis"
SESSION_TIMEOUT = 30
STOP_PARLER      = False
is_listening     = False
is_speaking      = False
jarvis_actif     = False
dernier_message  = 0
interface_deja_connectee = False

def ecouter():
    global is_listening, jarvis_actif, dernier_message, STOP_PARLER, is_speaking

    r   = sr.Recognizer()
    mic = sr.Microphone()

    r.pause_threshold        = 0.6
    r.non_speaking_duration  = 0.5
    r.energy_threshold       = 300
    r.dynamic_energy_threshold = True

    with mic as source:
        r.adjust_for_ambient_noise(source, duration=1)

    print("[J.A.R.V.I.S] Microphone pret. En attente de 'Jarvis' ou session active...")

    while True:
        try:
            # GESTION DU TIMEOUT DE SESSION
            if jarvis_actif and (time.time() - dernier_message > SESSION_TIMEOUT):
                print("[J.A.R.V.I.S] Timeout session. Retour en veille.")
                jarvis_actif = False

            with mic as source:
                is_listening = True
                loop_ws = asyncio.new_event_loop()
                state = "active" if jarvis_actif else "listening"
                loop_ws.run_until_complete(send_web_state(state))
                loop_ws.close()
                
                audio = r.listen(source, timeout=2, phrase_time_limit=10)
                
                is_listening = False
                loop_ws = asyncio.new_event_loop()
                loop_ws.run_until_complete(send_web_state("idle"))
                loop_ws.close()

            texte = r.recognize_google(audio, language="fr-FR").lower().strip()
            print(f"[ENTENDU] {texte}")

            # GESTION INTERRUPTION DURANT LA PAROLE
            if is_speaking and ("tais-toi" in texte or "silence" in texte or "tais toi" in texte):
                STOP_PARLER = True
                continue

            # MOTS-CLÉS DE SOMMEIL
            SLEEP_WORDS = ["merci", "ce sera tout", "repos", "au revoir", "silence", "tais-toi", "tais toi"]
            if any(word in texte for word in SLEEP_WORDS):
                if jarvis_actif:
                    jarvis_actif = False
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(parler("A votre service Tom. Je me mets en veille."))
                    loop.close()
                continue

            if WAKE_WORD in texte or jarvis_actif:
                if WAKE_WORD in texte:
                    print("[J.A.R.V.I.S] Mot-clé détecté.")
                    jarvis_actif = True
                
                dernier_message = time.time()
                commande = nettoyer_commande(texte)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                if commande:
                    action_pc = executer_action_pc(commande)
                    if action_pc:
                        loop.run_until_complete(parler(action_pc))
                    else:
                        loop.run_until_complete(traiter_reponse_ia(commande))
                else:
                    if WAKE_WORD in texte: # "Jarvis" tout seul
                        loop.run_until_complete(parler("Oui Tom, je vous écoute."))
                
                loop.close()
            else:
                pass

        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"Erreur écoute : {e}")
            time.sleep(1)

def monitor_claps():
    try:
        import audioop
        p = pyaudio.PyAudio()
        # On ouvre le flux
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        print("[CLAP] Détection des applaudissements activée.")
        
        print("[CLAP] Détection des doubles applaudissements activée.")
        
        last_clap_time = 0
        
        while True:
            try:
                data = stream.read(1024, exception_on_overflow=False)
                rms  = audioop.rms(data, 2)
                
                # ON IGNORE LE CLAP UNIQUEMENT SI LE MODE IRON MAN EST ÉTEINT OU SI J.A.R.V.I.S PARLE
                if not MODE_IRON_MAN or is_speaking or is_thinking:
                    last_clap_time = 0
                    continue

                if rms > CLAP_THRESHOLD:
                    current_time = time.time()
                    diff = current_time - last_clap_time
                    
                    if 0.1 < diff < 0.8:
                        global VIDEO_LANCEE
                        print(f"\n[CLAP] !!! DOUBLE CLAP DÉTECTÉ !!!")
                        entity_id = PIECES_LUMIERES.get("salon", "light.salon")
                        
                        # On vérifie l'état actuel
                        etat_actuel = ha_get_etat(entity_id)
                        
                        if etat_actuel != "on":
                            # ON ALLUME
                            print(f"[CLAP] Action : ALLUMER")
                            ha_lumiere(entity_id, "on")
                            
                            if not VIDEO_LANCEE:
                                print(f"[CLAP] Lancement initial de la vidéo...")
                                webbrowser.open("https://www.youtube.com/watch?v=KU5V5WZVcVE")
                                VIDEO_LANCEE = True
                                def seq():
                                    time.sleep(5)
                                    pyautogui.press('f')
                                threading.Thread(target=seq, daemon=True).start()
                            else:
                                print(f"[CLAP] Reprise de la vidéo (Play)...")
                                pyautogui.press('k')
                        else:
                            # ON ÉTEINT
                            print(f"[CLAP] Action : ÉTEINDRE")
                            ha_lumiere(entity_id, "off")
                            if VIDEO_LANCEE:
                                print(f"[CLAP] Mise en pause de la vidéo...")
                                pyautogui.press('k')
                            
                        # Gros debounce après une action réussie
                        time.sleep(3.0)
                        last_clap_time = 0 # Reset
                    else:
                        # C'est peut-être le premier clap
                        last_clap_time = current_time
            except Exception as e:
                # Si erreur de lecture (ex: micro débranché), on attend et on continue
                time.sleep(0.5)
                continue

    except Exception as e:
        print(f"[CLAP] Erreur fatale détection claps : {e}")

def start_ia():
    if not JARVIS_HEADLESS:
        threading.Thread(target=monitor_claps, daemon=True).start()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_ws():
        print(f"[WEB] Serveur WebSocket demarre sur ws://{SERVER_HOST}:{WS_PORT}")
        print(f"[WEB] Accessible depuis le reseau : ws://{LOCAL_IP}:{WS_PORT}")
        async with websockets.serve(ws_handler, SERVER_HOST, WS_PORT):
            await asyncio.Future()

    threading.Thread(target=lambda: asyncio.run(start_ws()), daemon=True).start()

    if not JARVIS_HEADLESS:
        loop.run_until_complete(parler("Bonjour, Tom"))
    loop.close()
    if JARVIS_HEADLESS:
        print("[J.A.R.V.I.S] Mode web/VM actif. En attente des commandes depuis l'interface web.")
        while True:
            time.sleep(1)
    else:
        ecouter()

# ==========================================
# LANCEMENT — MODE CONSOLE + FRONTEND WEB
# ==========================================
# Ursina desactive : l'interface est maintenant le frontend Three.js
# dans le dossier frontend/ (npm run dev -> http://localhost:5173)
# Le WebSocket est deja demarre par start_ia() sur ws://localhost:8765

if not JARVIS_HEADLESS:
    try:
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    except Exception as e:
        print(f"[AUDIO] Initialisation audio locale impossible : {e}")

def ensure_local_https_certificate(base_dir):
    cert_dir = os.path.join(base_dir, ".certs")
    cert_path = os.path.join(cert_dir, "jarvis-local.crt")
    key_path = os.path.join(cert_dir, "jarvis-local.key")
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    os.makedirs(cert_dir, exist_ok=True)
    openssl_conf = os.path.join(cert_dir, "openssl.cnf")
    san_entries = [
        "DNS:localhost",
        f"DNS:{LOCAL_IP}",
        "IP:127.0.0.1",
    ]
    try:
        ipaddress.ip_address(LOCAL_IP)
        san_entries.append(f"IP:{LOCAL_IP}")
    except ValueError:
        pass

    with open(openssl_conf, "w", encoding="utf-8") as f:
        f.write("""[req]
distinguished_name=req_distinguished_name
x509_extensions=v3_req
prompt=no
[req_distinguished_name]
CN=J.A.R.V.I.S Local
[v3_req]
subjectAltName={san}
""".format(san=",".join(san_entries)))

    subprocess.run(
        [
            "openssl", "req", "-x509", "-nodes", "-days", "825", "-newkey", "rsa:2048",
            "-keyout", key_path,
            "-out", cert_path,
            "-config", openssl_conf,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"[WEB] Certificat HTTPS local genere : {cert_path}")
    return cert_path, key_path


def start_http_interface_server():
    """Serveur HTTP Flask pour l'interface web et le dashboard sécurisé."""
    global app
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if JARVIS_HEADLESS:
        interface_dir = os.path.join(base_dir, "frontend", "dist")
        if not os.path.exists(interface_dir):
            print("[WEB] Dossier frontend/dist introuvable, serveur HTTP non demarre.")
            return
    else:
        interface_dir = os.path.join(base_dir, "mobile")
        if not os.path.exists(interface_dir):
            print("[MOBILE] Dossier mobile/ introuvable, serveur non demarre.")
            return

    app = Flask(__name__, static_folder=interface_dir, static_url_path="")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.secret_key = JARVIS_SESSION_SECRET or secrets.token_hex(32)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    @app.get("/")
    def serve_index():
        return send_from_directory(interface_dir, "index.html")

    @app.get("/generated/<path:filename>")
    def serve_generated_file(filename):
        return send_from_directory(str(GENERATED_IMAGES_DIR), filename)

    @app.get("/install/proxmox-lxc.sh")
    def serve_proxmox_lxc_installer():
        script_path = BASE_DIR / "scripts" / "proxmox_create_lxc.sh"
        if not script_path.exists():
            return jsonify({"error": "installer_not_found"}), 404
        return Response(
            script_path.read_text(encoding="utf-8"),
            mimetype="text/x-shellscript; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": "inline; filename=jarvis-proxmox-lxc.sh",
            },
        )

    def ensure_http_client_id():
        client_id = session.get("jarvis_client_id")
        if not client_id:
            client_id = secrets.token_urlsafe(18)
            session["jarvis_client_id"] = client_id
        return client_id

    @app.get("/api/auth/status")
    def auth_status():
        user = session.get("discord_user")
        owner_authenticated = is_owner_authenticated()
        return jsonify({
            "authenticated": owner_authenticated,
            "user": user if owner_authenticated else None,
            "assistant_name": ASSISTANT_NAME,
            "login_url": "/auth/discord/login",
            "logout_url": "/auth/logout",
            "discord_configured": DISCORD_CONFIGURED,
            "config_flags": get_service_config_flags(),
            "service_health": get_service_health_flags(),
            "ws_auth_token": issue_ws_auth_token(user) if owner_authenticated else "",
        })

    @app.post("/api/discord/interactions")
    def api_discord_interactions():
        raw_body = flask_request.get_data(cache=False)
        if not verify_discord_interaction_signature(raw_body):
            return jsonify({"error": "invalid_signature"}), 401

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return jsonify({"error": "invalid_json"}), 400

        interaction_type = payload.get("type")
        if interaction_type == 1:
            return jsonify({"type": 1})

        data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        command_type = data.get("type")
        if interaction_type == 2 and command_type == 3:
            threading.Thread(target=process_discord_message_summary, args=(payload,), daemon=True).start()
            return jsonify({
                "type": 5,
                "data": {"flags": 64},
            })

        if interaction_type == 3:
            custom_id = str(data.get("custom_id") or "")
            if custom_id.startswith("jarvis_show_summary:"):
                return jsonify(build_public_discord_summary_response(payload, custom_id.split(":", 1)[1]))

        return jsonify({
            "type": 4,
            "data": {
                "content": "Cette interaction Discord n'est pas encore prise en charge par J.A.R.V.I.S.",
                "flags": 64,
                "allowed_mentions": {"parse": []},
            },
        })

    @app.post("/api/command")
    def api_command():
        payload = flask_request.get_json(silent=True) or {}
        texte = str(payload.get("text", "")).strip()
        if not texte:
            return jsonify({"error": "empty_text"}), 400
        client_id = str(payload.get("client_id", "")).strip() or ensure_http_client_id()
        session["jarvis_client_id"] = client_id
        user = session.get("discord_user") if is_owner_authenticated() else None
        threading.Thread(
            target=lambda: asyncio.run(traiter_reponse_ia(texte, auth_user=user, http_client_id=client_id)),
            daemon=True,
        ).start()
        return jsonify({"ok": True})

    @app.post("/api/extension/tts")
    def api_extension_tts():
        if not extension_request_authorized():
            return jsonify({"error": "extension_access_denied", "detail": "Token extension requis hors reseau local."}), 403

        payload = flask_request.get_json(silent=True) or {}
        text_to_speak = str(payload.get("text", "")).strip()
        if not text_to_speak:
            return jsonify({"error": "empty_text"}), 400

        max_chars = 12000
        text_to_speak = text_to_speak[:max_chars]
        text_to_speak = text_to_speak.replace("**", "").replace("*", "").replace("#", "").replace("`", "").strip()
        output_file = BASE_DIR / f"jarvis_tts_extension_{int(time.time() * 1000)}_{secrets.token_hex(4)}.mp3"
        try:
            communicate = edge_tts.Communicate(text_to_speak, voice=JARVIS_TTS_VOICE)
            asyncio.run(communicate.save(str(output_file)))
            audio_bytes = output_file.read_bytes()
        except Exception as e:
            print(f"[EXTENSION] Erreur TTS : {e}")
            return jsonify({"error": "tts_failed", "detail": str(e)}), 500
        finally:
            try:
                if output_file.exists():
                    output_file.unlink()
            except Exception:
                pass

        return Response(
            audio_bytes,
            mimetype="audio/mpeg",
            headers={
                "Cache-Control": "no-store",
                "X-Jarvis-TTS-Voice": JARVIS_TTS_VOICE,
            },
        )

    @app.post("/api/extension/summarize")
    def api_extension_summarize():
        if not extension_request_authorized():
            return jsonify({"error": "extension_access_denied", "detail": "Token extension requis hors reseau local."}), 403

        payload = flask_request.get_json(silent=True) or {}
        page_title = str(payload.get("title", "")).strip()[:300]
        page_url = str(payload.get("url", "")).strip()[:1000]
        page_text = str(payload.get("text", "")).strip()
        if not page_text:
            return jsonify({"error": "empty_page_text"}), 400

        max_chars = 30000
        truncated = len(page_text) > max_chars
        page_text = page_text[:max_chars]
        try:
            summary = asyncio.run(resumer_page_extension(page_title, page_url, page_text))
        except Exception as e:
            print(f"[EXTENSION] Erreur resume page : {e}")
            return jsonify({"error": "summarize_failed", "detail": str(e)}), 500

        return jsonify({
            "ok": True,
            "summary": summary,
            "truncated": truncated,
        })

    @app.get("/api/client/events")
    def api_client_events():
        client_id = ensure_http_client_id()
        return jsonify({"events": pop_http_client_events(client_id)})

    @app.get("/api/settings")
    @owner_auth_required()
    def api_settings_get():
        return jsonify({
            "settings": get_private_runtime_settings(),
            "config_flags": get_service_config_flags(),
            "service_health": get_service_health_flags(),
        })

    @app.post("/api/settings")
    @owner_auth_required()
    def api_settings_post():
        payload = flask_request.get_json(silent=True) or {}
        updates = {}
        for key in SETTINGS_FIELDS:
            if key in payload:
                updates[key] = payload[key]
        if not updates:
            return jsonify({"error": "no_changes"}), 400
        save_runtime_settings(updates)
        if app is not None:
            app.secret_key = JARVIS_SESSION_SECRET or app.secret_key
        return jsonify({
            "ok": True,
            "settings": get_private_runtime_settings(),
            "config_flags": get_service_config_flags(),
            "service_health": get_service_health_flags(force_refresh=True),
        })

    @app.get("/api/debug/logs")
    @owner_auth_required()
    def api_debug_logs():
        try:
            limit = int(flask_request.args.get("limit", "200"))
        except ValueError:
            limit = 200
        limit = max(20, min(limit, 400))
        return jsonify({
            "lines": get_debug_log_snapshot(limit),
        })

    @app.get("/auth/discord/login")
    def auth_discord_login():
        if not DISCORD_CONFIGURED:
            return redirect("/?error=discord_non_configure")

        state = secrets.token_urlsafe(24)
        redirect_uri = discord_redirect_uri_for_request()
        session["discord_oauth_state"] = state
        session["discord_redirect_uri"] = redirect_uri
        params = {
            "client_id": DISCORD_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "identify",
            "state": state,
            "prompt": "consent",
        }
        query = "&".join(
            f"{key}={requests.utils.quote(str(value), safe='')}"
            for key, value in params.items()
        )
        return redirect(f"https://discord.com/oauth2/authorize?{query}")

    @app.get("/auth/discord/callback")
    def auth_discord_callback():
        if not DISCORD_CONFIGURED:
            return redirect("/?error=discord_non_configure")

        state = flask_request.args.get("state", "")
        code = flask_request.args.get("code", "")
        expected_state = session.get("discord_oauth_state")
        redirect_uri = session.get("discord_redirect_uri") or discord_redirect_uri_for_request()
        if not state or state != expected_state or not code:
            session.clear()
            return redirect("/?error=discord_state_invalide")

        try:
            token_response = requests.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": DISCORD_CLIENT_ID,
                    "client_secret": DISCORD_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            user_response = requests.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            user_response.raise_for_status()
            user_data = user_response.json()
        except Exception as e:
            session.clear()
            print(f"[DISCORD] OAuth erreur : {e}")
            return redirect("/?error=discord_oauth_echec")

        if str(user_data.get("id")) != DISCORD_OWNER_ID:
            session.clear()
            return redirect("/?error=discord_acces_refuse")

        session["discord_user"] = {
            "id": str(user_data.get("id", "")),
            "username": user_data.get("username", ""),
            "global_name": user_data.get("global_name", ""),
        }
        return redirect("/?dashboard=1")

    @app.get("/auth/logout")
    def auth_logout():
        session.clear()
        return redirect("/")

    @app.get("/assets/<path:filename>")
    def serve_assets(filename):
        return send_from_directory(os.path.join(interface_dir, "assets"), filename)

    @app.get("/<path:filename>")
    def serve_other(filename):
        file_path = os.path.join(interface_dir, filename)
        if os.path.exists(file_path):
            return send_from_directory(interface_dir, filename)
        return send_from_directory(interface_dir, "index.html")

    label = "WEB" if JARVIS_HEADLESS else "MOBILE"
    if HTTPS_PORT:
        try:
            cert_path, key_path = ensure_local_https_certificate(base_dir)
            threading.Thread(
                target=lambda: app.run(
                    host=SERVER_HOST,
                    port=HTTPS_PORT,
                    debug=False,
                    use_reloader=False,
                    threaded=True,
                    ssl_context=(cert_path, key_path),
                ),
                daemon=True,
            ).start()
            print(f"[{label}] Serveur HTTPS demarre sur https://{LOCAL_IP}:{HTTPS_PORT}")
        except Exception as e:
            print(f"[{label}] HTTPS indisponible : {e}")
    print(f"[{label}] Serveur HTTP demarre sur http://{LOCAL_IP}:{HTTP_PORT}")
    app.run(host=SERVER_HOST, port=HTTP_PORT, debug=False, use_reloader=False, threaded=True)

def liberer_port(port):
    """Tue le processus qui occupe le port donné (Linux)."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True
        )
        for pid_str in result.stdout.strip().splitlines():
            pid = int(pid_str.strip())
            if pid != os.getpid():
                os.kill(pid, _signal.SIGKILL)
                print(f"[DÉMARRAGE] Port {port} libéré (PID {pid} terminé).")
    except Exception as e:
        print(f"[DÉMARRAGE] Impossible de libérer le port {port} : {e}")

def main():
    print()
    print("=" * 60)
    print("   J.A.R.V.I.S — Mode Console + Interface Web")
    print("=" * 60)
    print()
    print("  Backend   : actif (terminal)")
    print(f"  WebSocket : ws://localhost:{WS_PORT}  (LAN: ws://{LOCAL_IP}:{WS_PORT})")
    if JARVIS_HEADLESS:
        print("  Frontend  : page web actuelle")
        print(f"  Interface : ouvrir http://{LOCAL_IP}:{HTTP_PORT}")
        if HTTPS_PORT:
            print(f"  iPhone    : ouvrir https://{LOCAL_IP}:{HTTPS_PORT}")
    else:
        print("  Frontend  : ouvrir http://localhost:5173")
        print(f"  Mobile    : ouvrir http://{LOCAL_IP}:{HTTP_PORT} sur votre tel/tablette")
    print()
    if JARVIS_HEADLESS:
        print("  Mode      : serveur headless pour VM")
        print("  Commandes : texte/micro depuis la page web")
    else:
        print("  Commandes vocales actives.")
        print("  Dites 'Jarvis' pour activer la session.")
    print("=" * 60)
    print()

    # Libérer les ports si une instance précédente tourne encore
    liberer_port(WS_PORT)
    liberer_port(HTTP_PORT)
    if HTTPS_PORT:
        liberer_port(HTTPS_PORT)

    # Lancer le serveur Frontend
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    frontend_process = None
    if not JARVIS_HEADLESS and os.path.exists(frontend_dir):
        print("[J.A.R.V.I.S] Lancement automatique de l'interface Web (Vite)...")
        frontend_process = subprocess.Popen(["npm", "run", "dev"], cwd=frontend_dir)
        time.sleep(2.5)  # Laisser le temps a Vite de demarrer

    # Ouvrir le navigateur vers le frontend
    if not JARVIS_HEADLESS:
        try:
            webbrowser.open("http://localhost:5173")
        except Exception:
            pass

    # Lancer le serveur HTTP de l'interface dans un thread
    threading.Thread(target=start_http_interface_server, daemon=True).start()

    # Lancer le backend IA dans un thread
    threading.Thread(target=start_ia, daemon=True).start()

    # Garder le processus en vie et s'arreter si le navigateur est ferme
    try:
        while True:
            time.sleep(1)
            if not JARVIS_HEADLESS and interface_deja_connectee and len(CONNECTED_CLIENTS) == 0:
                print("\n[J.A.R.V.I.S] Interface déconnectée. Attente de reconnexion (60s)...")
                time.sleep(60)
                if len(CONNECTED_CLIENTS) == 0:
                    print("[J.A.R.V.I.S] Aucune reconnexion. Extinction automatique...")
                    break
                else:
                    print("[J.A.R.V.I.S] Reconnexion détectée. Reprise.")
    except KeyboardInterrupt:
        print("\n[J.A.R.V.I.S] Arret du systeme demande manuellement.")
        
    if frontend_process:
        print("[J.A.R.V.I.S] Arret du serveur Web...")
        frontend_process.terminate()

if __name__ == "__main__":
    main()
try:
    import pyautogui
except Exception:
    pyautogui = None

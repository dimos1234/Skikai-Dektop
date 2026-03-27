"""
Central configuration for Skikai.
Single source of truth for env vars, ports, paths, feature flags, and LLM endpoints.
All modules should import from here instead of calling load_dotenv() individually.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool = True) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


# ── Environment profile ────────────────────────────────────────────────
# "desktop" (full setup), "portable" (laptop/no TTS/Warudo), "headless" (brain only)
ENV = _env("SKIKAI_ENV", "desktop")


# ── LLM endpoints ──────────────────────────────────────────────────────
class _LLM:
    openai_key  = _env("OPENAI_API_KEY")
    ollama_url  = _env("MAC_OLLAMA_URL", "http://192.168.1.100:11434")
    groq_key    = _env("GROQ_API_KEY")

llm = _LLM()


# ── Network ports ──────────────────────────────────────────────────────
class _Ports:
    discord_in    = _env_int("SKIKAI_PORT_DISCORD_IN", 5005)
    discord_out   = _env_int("SKIKAI_PORT_DISCORD_OUT", 5006)
    sensory       = _env_int("SKIKAI_PORT_SENSORY", 5007)
    minecraft_bot = _env_int("SKIKAI_PORT_MINECRAFT", 5008)
    tts           = _env_int("SKIKAI_PORT_TTS", 9880)
    warudo        = _env_int("SKIKAI_PORT_WARUDO", 19190)

ports = _Ports()

HOST = _env("SKIKAI_HOST", "127.0.0.1")


# ── File paths ─────────────────────────────────────────────────────────
class _Paths:
    chroma      = _env("SKIKAI_CHROMA_PATH", "./chroma_memory")
    workspace   = _env("SKIKAI_WORKSPACE", "skikai_workspace")
    goals       = _env("SKIKAI_GOALS_FILE", "skikai_goals.json")
    ref_audio   = _env("SKIKAI_REF_AUDIO", "skikai_ref.wav")

paths = _Paths()


# ── Feature flags ──────────────────────────────────────────────────────
# Each can be overridden by env var; defaults depend on ENV profile.
_DESKTOP_DEFAULTS = {
    "tts": True, "warudo": True, "screen_capture": True,
    "discord": True, "minecraft": True, "weather": True,
}
_PORTABLE_DEFAULTS = {
    "tts": False, "warudo": False, "screen_capture": False,
    "discord": True, "minecraft": False, "weather": True,
}
_HEADLESS_DEFAULTS = {
    "tts": False, "warudo": False, "screen_capture": False,
    "discord": False, "minecraft": False, "weather": False,
}

_PROFILE_DEFAULTS = {
    "desktop": _DESKTOP_DEFAULTS,
    "portable": _PORTABLE_DEFAULTS,
    "headless": _HEADLESS_DEFAULTS,
}


class _Features:
    def __init__(self):
        base = _PROFILE_DEFAULTS.get(ENV, _DESKTOP_DEFAULTS)
        self.tts            = _env_bool("SKIKAI_TTS", base["tts"])
        self.warudo         = _env_bool("SKIKAI_WARUDO", base["warudo"])
        self.screen_capture = _env_bool("SKIKAI_SCREEN_CAPTURE", base["screen_capture"])
        self.discord        = _env_bool("SKIKAI_DISCORD", base["discord"])
        self.minecraft      = _env_bool("SKIKAI_MINECRAFT", base["minecraft"])
        self.weather        = _env_bool("SKIKAI_WEATHER", base["weather"])

features = _Features()

IS_WINDOWS = sys.platform == "win32"

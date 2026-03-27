"""
Capabilities abstraction for Skikai.
Provides platform-safe wrappers and feature gates so the system can run
in different environments (desktop, portable, headless) without code changes.
"""
import config


# ── Platform-safe active window ────────────────────────────────────────

def get_active_window() -> str:
    """Return the title of the foreground window, or a stub on non-Windows / when disabled."""
    if not config.features.screen_capture or not config.IS_WINDOWS:
        return "Unknown (disabled)"
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value if buf.value else "Unknown Application"
    except Exception:
        return "Unknown Application"


# ── Convenience booleans (re-exported from config.features) ────────────

tts           = config.features.tts
warudo        = config.features.warudo
screen_capture = config.features.screen_capture
discord       = config.features.discord
minecraft     = config.features.minecraft
weather       = config.features.weather

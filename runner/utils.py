import time

from runner import state


KEY_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "esc": "esc",
    "escape": "esc",
    "home": "home",
    "end": "end",
    "pgup": "page up",
    "pgdn": "page down",
    "pageup": "page up",
    "pagedown": "page down",
    "space": "space",
    "enter": "enter",
    "return": "enter",
}


def normalize_key_name(k: str) -> str:
    """Map script.json key names to keyboard library scan names."""
    k = str(k).strip()
    lower = k.lower()
    if lower in KEY_ALIASES:
        return KEY_ALIASES[lower]
    if lower.startswith("f") and lower[1:].isdigit():
        return lower
    if len(k) == 1:
        return k.lower()
    return lower


def expand_key_sequence(key_text: str) -> list[str]:
    """Expand key args like '1111' into ['1', '1', '1', '1']."""
    raw = str(key_text).strip()
    if not raw:
        return []

    lower = raw.lower()
    if lower in KEY_ALIASES:
        return [KEY_ALIASES[lower]]
    if lower.startswith("f") and lower[1:].isdigit():
        return [lower]
    if len(raw) == 1:
        return [normalize_key_name(raw)]
    if all(len(ch) == 1 for ch in raw):
        return [normalize_key_name(ch) for ch in raw]

    return [normalize_key_name(raw)]


def to_int(value, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def sleep_interruptible(seconds: float):
    """Sleep for seconds, stopping early if automation is toggled off."""
    if seconds <= 0:
        return

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        with state.state_lock:
            if state.exiting or not state.running:
                return
        time.sleep(min(0.05, end - time.monotonic()))


def normalize_mouse_button(button: str) -> str:
    name = str(button).strip().lower()
    aliases = {
        "left": "left",
        "right": "right",
        "middle": "middle",
        "mid": "middle",
        "wheel": "middle",
    }
    return aliases.get(name, "left")

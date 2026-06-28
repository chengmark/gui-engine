import threading
from typing import Callable, Optional

import keyboard
from pynput import mouse as ms

from runner.utils import normalize_key_name

_mouse_listener: Optional[ms.Listener] = None
_mouse_handlers: dict[str, list[Callable[[], None]]] = {}
_mouse_lock = threading.Lock()

MOUSE_TRIGGER_NAMES = {
    "mb1": "left",
    "lbutton": "left",
    "left": "left",
    "mb2": "right",
    "rbutton": "right",
    "right": "right",
    "mb3": "middle",
    "mbutton": "middle",
    "middle": "middle",
    "wheel": "middle",
    "mb4": "x1",
    "x1": "x1",
    "back": "x1",
    "mb5": "x2",
    "x2": "x2",
    "forward": "x2",
}

PYNPUT_BUTTONS = {
    "left": ms.Button.left,
    "right": ms.Button.right,
    "middle": ms.Button.middle,
    "x1": ms.Button.x1,
    "x2": ms.Button.x2,
}


def normalize_mouse_trigger(name: str) -> str:
    key = str(name).strip().lower()
    return MOUSE_TRIGGER_NAMES.get(key, key)


def is_mouse_trigger(name: str) -> bool:
    return normalize_mouse_trigger(name) in PYNPUT_BUTTONS


def _button_name(button: ms.Button) -> Optional[str]:
    for name, value in PYNPUT_BUTTONS.items():
        if button == value:
            return name
    return None


def _on_mouse_click(x, y, button, pressed):
    if not pressed:
        return
    name = _button_name(button)
    if not name:
        return
    with _mouse_lock:
        callbacks = list(_mouse_handlers.get(name, []))
    for callback in callbacks:
        try:
            callback()
        except Exception:
            pass


def _ensure_mouse_listener():
    global _mouse_listener
    if _mouse_listener is not None:
        return
    _mouse_listener = ms.Listener(on_click=_on_mouse_click)
    _mouse_listener.start()


def _stop_mouse_listener():
    global _mouse_listener
    if _mouse_listener is None:
        return
    _mouse_listener.stop()
    _mouse_listener = None


def register_mouse_trigger(button_name: str, callback: Callable[[], None]) -> Callable[[], None]:
    btn = normalize_mouse_trigger(button_name)
    if btn not in PYNPUT_BUTTONS:
        raise ValueError(f"Unsupported mouse trigger '{button_name}'.")

    with _mouse_lock:
        _mouse_handlers.setdefault(btn, []).append(callback)
        _ensure_mouse_listener()

    def cleanup():
        with _mouse_lock:
            handlers = _mouse_handlers.get(btn, [])
            if callback in handlers:
                handlers.remove(callback)
            if not any(_mouse_handlers.values()):
                _stop_mouse_listener()

    return cleanup


def register_key_trigger(key_name: str, callback: Callable[[], None]) -> Callable[[], None]:
    hotkey = normalize_key_name(key_name)
    remove = keyboard.add_hotkey(
        hotkey,
        callback,
        suppress=False,
        trigger_on_release=False,
    )

    def cleanup():
        try:
            remove()
        except Exception:
            pass

    return cleanup

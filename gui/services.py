"""Optional backend services loaded lazily by the GUI."""

from __future__ import annotations

import importlib
import sys
from typing import Any, Optional

_warned: set[str] = set()


def _warn_once(service: str, action: str, detail: str) -> None:
    key = f"{service}:{action}"
    if key in _warned:
        return
    _warned.add(key)
    print(f"[gui] {service} unavailable ({action}): {detail}", file=sys.stderr)


def _import_optional(module_name: str) -> Any | None:
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        _warn_once(module_name, "import", str(exc))
        return None


class _StubLock:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class StubScriptRunner:
    script_path: Optional[str] = None

    def __init__(self, on_status_change=None):
        self._on_status_change = on_status_change

    @property
    def is_loaded(self) -> bool:
        return False

    @property
    def is_running(self) -> bool:
        return False

    def load(self, *_args, **_kwargs):
        _warn_once("run", "ScriptRunner.load", "run.py / runner package not found")
        raise RuntimeError("Script runner service is not available.")

    def toggle(self):
        _warn_once("run", "ScriptRunner.toggle", "run.py / runner package not found")

    def unload(self):
        pass


class StubInputRecorder:
    lock = _StubLock()
    events: list = []

    def start_listeners(self):
        _warn_once("record", "InputRecorder.start_listeners", "record.py not found")
        raise RuntimeError("Recording service is not available.")

    def start(self):
        _warn_once("record", "InputRecorder.start", "record.py not found")
        raise RuntimeError("Recording service is not available.")

    def stop(self):
        _warn_once("record", "InputRecorder.stop", "record.py not found")
        return []

    def stop_listeners(self):
        pass


def stub_script_runner(on_status_change=None) -> StubScriptRunner:
    return StubScriptRunner(on_status_change)


def stub_input_recorder() -> StubInputRecorder:
    return StubInputRecorder()


class StubBackgroundManager:
    def is_loaded(self, filename: str) -> bool:
        return False

    def loaded_filenames(self) -> set:
        return set()

    def load(self, script_path: str):
        _warn_once("runner.background", "BackgroundScriptManager.load", "runner.background not found")
        raise RuntimeError("Background script service is not available.")

    def unload(self, filename: str):
        pass

    def unload_all(self):
        pass


def stub_background_manager() -> StubBackgroundManager:
    return StubBackgroundManager()


def create_background_manager():
    module = _import_optional("runner.background")
    if module is None:
        return StubBackgroundManager()
    return module.BackgroundScriptManager()


def create_script_runner(on_status_change=None):
    module = _import_optional("run")
    if module is None:
        return StubScriptRunner(on_status_change)
    return module.ScriptRunner(on_status_change=on_status_change)


def create_input_recorder():
    module = _import_optional("record")
    if module is None:
        return StubInputRecorder()
    return module.InputRecorder()


def get_cursor_sample() -> tuple[int, int, int, int, int]:
    """Return cursor x, y and RGB components. Raises if coord_helper is missing."""
    module = _import_optional("coord_helper")
    if module is None:
        _warn_once("coord_helper", "get_cursor_pos/get_pixel_rgb", "coord_helper.py not found")
        raise RuntimeError("Cursor service is not available.")
    x, y = module.get_cursor_pos()
    r, g, b = module.get_pixel_rgb(x, y)
    return x, y, r, g, b


def events_to_steps(events) -> list:
    module = _import_optional("record")
    if module is None:
        _warn_once("record", "events_to_steps", "record.py not found")
        raise RuntimeError("Recording service is not available.")
    return module.events_to_steps(events)


def build_script(steps, description: str, toggle_key: str = "home") -> dict:
    module = _import_optional("record")
    if module is None:
        _warn_once("record", "build_script", "record.py not found")
        raise RuntimeError("Recording service is not available.")
    return module.build_script(steps, description, toggle_key)

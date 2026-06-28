import threading
import time
import traceback
from typing import Callable, Optional

import keyboard

from handlers import perform_step
from runner import state
from runner.script_io import apply_limit_download_pid, load_script
from runner.subroutines import SubroutineManager
from runner.utils import normalize_key_name


UNLOAD_HOTKEY = "shift+esc"


def run_steps(steps):
    for step in steps:
        if not step or not step.get("command"):
            continue
        with state.state_lock:
            if state.exiting or not state.running:
                return False
        try:
            perform_step(step)
        except Exception:
            cmd = step.get("command", "?")
            print(f"Step error ({cmd} {step.get('args', [])}):")
            traceback.print_exc()
    return True


def worker_loop(initial, loop):
    while not state.exiting:
        with state.state_lock:
            if not state.running:
                time.sleep(0.05)
                continue

        try:
            if initial and not run_steps(initial):
                continue

            while not state.exiting:
                with state.state_lock:
                    if not state.running:
                        break
                if not run_steps(loop):
                    break
        except Exception:
            print("Worker loop error:")
            traceback.print_exc()
            time.sleep(0.1)


def toggle_automation():
    with state.state_lock:
        state.running = not state.running
        status = "ON" if state.running else "OFF"
    print(f"Automation toggled {status}.")
    if state.subroutine_manager:
        state.subroutine_manager.toggle_all()


def request_exit():
    with state.state_lock:
        state.exiting = True
        state.running = False
    print("Ctrl+Esc pressed. Exiting script...")
    if state.subroutine_manager:
        state.subroutine_manager.shutdown_all()
    state.exit_event.set()


def unload_active_script():
    """Stop the active script without exiting the runner process."""
    with state.state_lock:
        state.running = False
    if state.subroutine_manager:
        state.subroutine_manager.shutdown_all()
        state.subroutine_manager = None
    print("Script unloaded (Shift+Esc).")


class ScriptRunner:
    """Programmatic script runner for GUI and other controllers."""

    def __init__(self, on_status_change=None):
        self.script_path: Optional[str] = None
        self.toggle_key_norm = "home"
        self.worker: Optional[threading.Thread] = None
        self._initial: list = []
        self._loop: list = []
        self._on_status_change = on_status_change
        self._hotkey_remove: Optional[Callable[[], None]] = None
        self._shift_esc_remove: Optional[Callable[[], None]] = None

    @property
    def is_loaded(self) -> bool:
        return self.script_path is not None

    @property
    def is_worker_alive(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    @property
    def is_running(self) -> bool:
        with state.state_lock:
            return state.running and not state.exiting

    def _notify(self):
        if self._on_status_change:
            self._on_status_change()

    def _remove_hotkey(self):
        if self._hotkey_remove is not None:
            try:
                self._hotkey_remove()
            except Exception:
                pass
            self._hotkey_remove = None

    def _register_hotkey(self):
        self._remove_hotkey()
        self._hotkey_remove = keyboard.add_hotkey(
            self.toggle_key_norm,
            self._on_toggle_hotkey,
            suppress=False,
            trigger_on_release=False,
        )

    def _register_shift_esc(self):
        self._remove_shift_esc()
        self._shift_esc_remove = keyboard.add_hotkey(
            UNLOAD_HOTKEY,
            self._on_shift_esc,
            suppress=False,
            trigger_on_release=False,
        )

    def _remove_shift_esc(self):
        if self._shift_esc_remove is not None:
            try:
                self._shift_esc_remove()
            except Exception:
                pass
            self._shift_esc_remove = None

    def _on_shift_esc(self):
        if not self.is_loaded:
            return
        print("Shift+Esc pressed. Unloading script...")
        self.unload()

    def _start_worker(self):
        if self.is_worker_alive:
            return
        state.exiting = False
        self.worker = threading.Thread(
            target=worker_loop,
            args=(self._initial, self._loop),
            daemon=True,
        )
        self.worker.start()

    def _on_toggle_hotkey(self):
        self._handle_toggle()

    def _handle_toggle(self):
        with state.state_lock:
            turning_on = not state.running
        toggle_automation()
        if turning_on:
            self._start_worker()
        self._notify()

    def load(self, script_path: str, pid_override: Optional[int] = None):
        import os

        if self.is_loaded:
            self.unload()

        script_path = os.path.abspath(script_path)
        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"Script file not found: {script_path}")

        state.script_base_dir = os.path.dirname(script_path)
        state.exiting = False
        state.running = False
        state.exit_event.clear()

        toggle_key, initial, loop, scripts, _background = load_script(script_path)
        if pid_override is not None:
            scripts = apply_limit_download_pid(scripts, pid_override)
        self.toggle_key_norm = normalize_key_name(toggle_key)
        self.script_path = script_path
        self._initial = initial
        self._loop = loop

        state.subroutine_manager = SubroutineManager(scripts, state.script_base_dir)
        state.subroutine_manager.start_all(parent_running=False)

        self._register_hotkey()
        self._register_shift_esc()
        self._start_worker()
        self._notify()

    def toggle(self):
        if not self.is_loaded:
            return
        self._handle_toggle()

    def unload(self):
        if not self.is_loaded:
            return

        with state.state_lock:
            state.running = False
            state.exiting = True

        if state.subroutine_manager:
            state.subroutine_manager.shutdown_all()
            state.subroutine_manager = None

        self._remove_hotkey()
        self._remove_shift_esc()

        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=2.0)
        self.worker = None
        self.script_path = None
        self._initial = []
        self._loop = []

        state.exiting = False
        state.exit_event.clear()
        state.running = False
        self._notify()

import os
import traceback
from typing import Callable, Optional

from handlers import perform_step
from runner import state
from runner.script_io import load_script


def run_background_steps(steps: list) -> list[Callable[[], None]]:
    state.background_cleanups = []
    for step in steps:
        if not step or not step.get("command"):
            continue
        try:
            perform_step(step)
        except Exception:
            cmd = step.get("command", "?")
            print(f"Background step error ({cmd} {step.get('args', [])}):")
            traceback.print_exc()

    cleanups = list(state.background_cleanups)
    state.background_cleanups = []
    return cleanups


class BackgroundScriptManager:
    """Load/unload scripts that define a background step list."""

    def __init__(self):
        self._cleanups: dict[str, list[Callable[[], None]]] = {}

    def is_loaded(self, filename: str) -> bool:
        return filename in self._cleanups

    def loaded_filenames(self) -> set[str]:
        return set(self._cleanups.keys())

    def load(self, script_path: str):
        script_path = os.path.abspath(script_path)
        filename = os.path.basename(script_path)
        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"Script file not found: {script_path}")

        self.unload(filename)

        _, _, _, _, background = load_script(script_path)
        if not background:
            raise ValueError(f"Script has no background steps: {filename}")

        print(f"Loading background script: {filename}")
        cleanups = run_background_steps(background)
        self._cleanups[filename] = cleanups

    def unload(self, filename: str):
        cleanups = self._cleanups.pop(filename, [])
        if not cleanups:
            return
        print(f"Unloading background script: {filename}")
        for cleanup in cleanups:
            try:
                cleanup()
            except Exception:
                pass

    def unload_all(self):
        for filename in list(self._cleanups.keys()):
            self.unload(filename)

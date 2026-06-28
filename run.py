"""Backward-compatible entry point for the automation runner."""

from runner.cli import main, parse_args, run_controlled_mode
from runner.constants import APP_ROOT, DEFAULT_SCRIPT, RUN_PY
from runner.engine import ScriptRunner, request_exit, run_steps, toggle_automation, unload_active_script, worker_loop
from runner.background import BackgroundScriptManager
from runner.script_io import apply_limit_download_pid, load_script, resolve_script_path, run_imported_script
from runner.subroutines import SubroutineManager
from runner.utils import normalize_key_name, normalize_mouse_button, sleep_interruptible, to_float, to_int

__all__ = [
    "APP_ROOT",
    "DEFAULT_SCRIPT",
    "RUN_PY",
    "ScriptRunner",
    "SubroutineManager",
    "apply_limit_download_pid",
    "load_script",
    "main",
    "normalize_key_name",
    "parse_args",
    "request_exit",
    "resolve_script_path",
    "run_controlled_mode",
    "run_imported_script",
    "run_steps",
    "toggle_automation",
    "worker_loop",
]

if __name__ == "__main__":
    main()

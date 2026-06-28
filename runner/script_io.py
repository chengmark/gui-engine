import json
import os

from runner import state


def load_script(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    toggle_key = data.get("toggle", "home")
    initial = data.get("initial", [])
    loop = data.get("loop", data.get("steps", []))
    scripts = data.get("scripts", [])
    background = data.get("background", [])
    return toggle_key, initial, loop, scripts, background


def script_has_background(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(data.get("background"))
    except (OSError, json.JSONDecodeError):
        return False


def apply_limit_download_pid(scripts: list, pid: int) -> list:
    """Return a copy of script subroutines with limit_download.py PID overridden."""
    patched = []
    for entry in scripts:
        entry = dict(entry)
        file_name = os.path.basename(str(entry.get("file", ""))).lower()
        if file_name == "limit_download.py":
            args = list(entry.get("args", []))
            if args:
                args[0] = pid
            else:
                args = [pid]
            entry["args"] = args
        patched.append(entry)
    return patched


def resolve_script_path(file_name: str) -> str:
    if os.path.isabs(file_name):
        return file_name
    return os.path.join(state.script_base_dir, file_name)


def run_imported_script(file_name: str):
    """Run another script's initial and loop steps inline."""
    from runner.engine import run_steps

    path = os.path.abspath(resolve_script_path(file_name))
    if not os.path.isfile(path):
        print(f"ImportScript: file not found: {path}")
        return

    print(f"ImportScript: running {path}")
    _, initial, loop, _, _ = load_script(path)
    if initial and not run_steps(initial):
        return
    run_steps(loop)

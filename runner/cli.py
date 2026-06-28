import argparse
import os
import sys
import threading

import keyboard

from runner.constants import DEFAULT_SCRIPT
from runner import state
from runner.engine import ScriptRunner, request_exit, run_steps, toggle_automation, unload_active_script, worker_loop
from runner.script_io import load_script
from runner.subroutines import SubroutineManager
from runner.utils import normalize_key_name


def parse_args():
    parser = argparse.ArgumentParser(description="Run automation steps from a JSON script file.")
    parser.add_argument(
        "script",
        nargs="?",
        default=DEFAULT_SCRIPT,
        help="Path to script JSON file (default: script.json in this directory)",
    )
    parser.add_argument(
        "--controlled",
        action="store_true",
        help="Run without keyboard hooks; receive toggle/exit commands on stdin.",
    )
    return parser.parse_args()


def run_controlled_mode(script_path: str):
    script_path = os.path.abspath(script_path)
    state.script_base_dir = os.path.dirname(script_path)
    toggle_key, initial, loop, scripts, _background = load_script(script_path)
    toggle_key_norm = normalize_key_name(toggle_key)

    state.subroutine_manager = SubroutineManager(scripts, state.script_base_dir)
    state.subroutine_manager.start_all(parent_running=False)

    print(f"Controlled subroutine loaded from {script_path}")
    print(f"Toggle key: {toggle_key_norm}")
    print("Listening for stdin commands: toggle, exit")

    worker = threading.Thread(target=worker_loop, args=(initial, loop), daemon=True)
    worker.start()

    try:
        for line in sys.stdin:
            cmd = line.strip().lower()
            if cmd == "toggle":
                toggle_automation()
            elif cmd == "exit":
                request_exit()
                break
    finally:
        if state.subroutine_manager:
            state.subroutine_manager.shutdown_all()
        worker.join(timeout=2.0)


def main():
    args = parse_args()
    script_path = os.path.abspath(args.script)
    if not os.path.isfile(script_path):
        raise SystemExit(f"Script file not found: {script_path}")

    state.script_base_dir = os.path.dirname(script_path)

    if args.controlled:
        run_controlled_mode(script_path)
        return

    toggle_key, initial, loop, scripts, _background = load_script(script_path)
    toggle_key_norm = normalize_key_name(toggle_key)

    state.subroutine_manager = SubroutineManager(scripts, state.script_base_dir)
    state.subroutine_manager.start_all(parent_running=False)

    print(f"Loaded script from {script_path}")
    print(f"Toggle key: {toggle_key_norm} (works globally)")
    if initial:
        print(f"Initial steps: {len(initial)}")
    print(f"Loop steps: {len(loop)}")
    if scripts:
        print(f"Subroutines: {', '.join(state.subroutine_manager.subroutines.keys())}")
    print("Press toggle key to start/stop running steps and subroutines.")
    print("Press Shift+Esc to unload the script.")
    print("Press Ctrl+Esc to exit.")
    if sys.platform == "win32":
        print("Tip: run the terminal as Administrator if hotkeys fail in some games.")

    keyboard.add_hotkey(toggle_key_norm, toggle_automation, suppress=False, trigger_on_release=False)
    keyboard.add_hotkey("shift+esc", unload_active_script, suppress=False, trigger_on_release=False)
    keyboard.add_hotkey("ctrl+esc", request_exit, suppress=False, trigger_on_release=False)

    worker = threading.Thread(target=worker_loop, args=(initial, loop), daemon=True)
    worker.start()

    try:
        state.exit_event.wait()
    except KeyboardInterrupt:
        request_exit()
    finally:
        keyboard.unhook_all_hotkeys()
        if state.subroutine_manager:
            state.subroutine_manager.shutdown_all()
        worker.join(timeout=2.0)
        print("Script terminated.")

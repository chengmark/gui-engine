"""
Record keyboard and mouse input, then save a run.py-compatible JSON script.

Hotkeys:
  F9       - start recording
  F10      - stop recording and save
  Ctrl+Esc - exit without saving
"""

import argparse
import json
import os
import sys
import threading
import time
from typing import Any, Optional

import keyboard
from pynput import keyboard as kb
from pynput import mouse as ms

HOLD_THRESHOLD_SEC = 0.2
MIN_DELAY_MS = 50
MOUSE_MOVE_THRESHOLD = 3
RECORDER_HOTKEYS = {"f9", "f10"}


def format_key(key) -> Optional[str]:
    if key is None:
        return None
    if isinstance(key, kb.KeyCode):
        if key.char:
            ch = key.char
            if ch.isalpha() and len(ch) == 1:
                return ch.upper()
            if ch.isdigit():
                return ch
            return ch
        vk = getattr(key, "vk", None)
        if vk is not None and 65 <= vk <= 90:
            return chr(vk)
        if vk is not None and 48 <= vk <= 57:
            return chr(vk)
        return None
    if isinstance(key, kb.Key):
        aliases = {
            "space": "Space",
            "esc": "ESC",
            "enter": "Enter",
            "tab": "Tab",
            "backspace": "Backspace",
            "delete": "Delete",
            "home": "Home",
            "end": "End",
            "page_up": "PageUp",
            "page_down": "PageDown",
            "up": "Up",
            "down": "Down",
            "left": "Left",
            "right": "Right",
            "shift": "Shift",
            "shift_l": "Shift",
            "shift_r": "Shift",
            "ctrl": "Ctrl",
            "ctrl_l": "Ctrl",
            "ctrl_r": "Ctrl",
            "alt": "Alt",
            "alt_l": "Alt",
            "alt_r": "Alt",
        }
        if key.name in aliases:
            return aliases[key.name]
        if key.name and key.name.startswith("f") and key.name[1:].isdigit():
            return key.name.upper()
        return key.name.upper() if key.name else None
    return str(key)


def format_button(button) -> str:
    if button == ms.Button.left:
        return "Left"
    if button == ms.Button.right:
        return "Right"
    if button == ms.Button.middle:
        return "Middle"
    return "Left"


class InputRecorder:
    def __init__(self):
        self.lock = threading.Lock()
        self.recording = False
        self.events: list[dict[str, Any]] = []
        self.record_start = 0.0
        self._key_listener: Optional[kb.Listener] = None
        self._mouse_listener: Optional[ms.Listener] = None

    def _event_time(self) -> float:
        return time.monotonic() - self.record_start

    def _append_event(self, event: dict[str, Any]):
        with self.lock:
            if self.recording:
                self.events.append(event)

    def start(self):
        with self.lock:
            self.recording = True
            self.events = []
            self.record_start = time.monotonic()
        print("Recording started. Press F10 to stop and save.")

    def stop(self) -> list[dict[str, Any]]:
        with self.lock:
            self.recording = False
            return list(self.events)

    def _on_key_press(self, key):
        name = format_key(key)
        if not name or name.lower() in RECORDER_HOTKEYS:
            return
        self._append_event({"type": "key_down", "key": name, "t": self._event_time()})

    def _on_key_release(self, key):
        name = format_key(key)
        if not name or name.lower() in RECORDER_HOTKEYS:
            return
        self._append_event({"type": "key_up", "key": name, "t": self._event_time()})

    def _on_mouse_move(self, x, y):
        self._append_event({"type": "mouse_move", "x": x, "y": y, "t": self._event_time()})

    def _on_mouse_click(self, x, y, button, pressed):
        self._append_event(
            {
                "type": "mouse_down" if pressed else "mouse_up",
                "button": format_button(button),
                "x": x,
                "y": y,
                "t": self._event_time(),
            }
        )

    def start_listeners(self):
        self._key_listener = kb.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener = ms.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
        )
        self._key_listener.start()
        self._mouse_listener.start()

    def stop_listeners(self):
        if self._key_listener:
            self._key_listener.stop()
            self._key_listener = None
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None


def events_to_steps(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []

    steps: list[dict[str, Any]] = []
    last_t = events[0]["t"]
    last_pos: Optional[tuple[int, int]] = None
    pending_dx = 0
    pending_dy = 0
    key_down_times: dict[str, float] = {}

    def add_delay(current_t: float):
        nonlocal last_t
        delay_ms = int(round((current_t - last_t) * 1000))
        if delay_ms >= MIN_DELAY_MS:
            steps.append({"command": "Delay", "args": [delay_ms]})
        last_t = current_t

    def flush_mouse_move(current_t: float):
        nonlocal pending_dx, pending_dy, last_t
        if pending_dx == 0 and pending_dy == 0:
            return
        add_delay(current_t)
        args = [pending_dx]
        if pending_dy != 0:
            args.append(pending_dy)
        steps.append({"command": "MouseMove", "args": args})
        pending_dx = 0
        pending_dy = 0
        last_t = current_t

    for event in events:
        event_type = event["type"]
        current_t = event["t"]

        if event_type == "mouse_move":
            x = int(event["x"])
            y = int(event["y"])
            if last_pos is None:
                last_pos = (x, y)
                continue
            dx = x - last_pos[0]
            dy = y - last_pos[1]
            last_pos = (x, y)
            if dx == 0 and dy == 0:
                continue
            pending_dx += dx
            pending_dy += dy
            if abs(pending_dx) >= MOUSE_MOVE_THRESHOLD or abs(pending_dy) >= MOUSE_MOVE_THRESHOLD:
                flush_mouse_move(current_t)
            continue

        if event_type == "key_down":
            key_down_times[event["key"]] = current_t
            continue

        if event_type == "key_up":
            key = event["key"]
            down_t = key_down_times.pop(key, current_t)
            duration = max(current_t - down_t, 0.0)
            flush_mouse_move(current_t)
            add_delay(current_t)
            if duration >= HOLD_THRESHOLD_SEC:
                hold_seconds = round(duration, 2)
                if hold_seconds <= 0:
                    hold_seconds = 0.01
                steps.append({"command": "KeyHoldAndRelease", "args": [key, hold_seconds]})
            else:
                steps.append({"command": "KeyPress", "args": [key, 1]})
            last_t = current_t
            continue

        if event_type == "mouse_down":
            last_pos = (int(event["x"]), int(event["y"]))
            continue

        if event_type == "mouse_up":
            x = int(event["x"])
            y = int(event["y"])
            button = event.get("button", "Left")
            last_pos = (x, y)
            flush_mouse_move(current_t)
            add_delay(current_t)
            if button == "Left":
                steps.append({"command": "ClickOn", "args": [x, y]})
            else:
                steps.append({"command": "ClickOn", "args": [x, y, button]})
            last_t = current_t

    flush_mouse_move(events[-1]["t"])
    return steps


def build_script(steps: list[dict[str, Any]], description: str, toggle: str) -> dict[str, Any]:
    return {
        "description": description,
        "toggle": toggle,
        "scripts": [],
        "initial": [],
        "loop": steps,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Record keyboard/mouse input to a run.py JSON script.")
    parser.add_argument(
        "output",
        nargs="?",
        default="recorded.json",
        help="Output JSON file path (default: recorded.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_flag",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--description",
        default="Recorded script",
        help="Description field for the output JSON",
    )
    parser.add_argument(
        "--toggle",
        default="home",
        help="Toggle key written into the output JSON (default: home)",
    )
    return parser.parse_args()


def resolve_output_path(args: argparse.Namespace) -> str:
    path = args.output_flag if args.output_flag else args.output
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    return path


def main():
    if sys.platform != "win32":
        print("Warning: record.py is intended for Windows.")

    args = parse_args()
    output_path = resolve_output_path(args)
    recorder = InputRecorder()
    exit_event = threading.Event()
    saved = False

    def start_recording():
        if recorder.recording:
            print("Already recording.")
            return
        recorder.start()

    def stop_and_save():
        nonlocal saved
        if not recorder.recording:
            print("Not recording.")
            return
        events = recorder.stop()
        steps = events_to_steps(events)
        script = build_script(steps, args.description, args.toggle)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=4, ensure_ascii=False)
            f.write("\n")
        saved = True
        print(f"Saved {len(steps)} steps to {output_path}")
        print(f"Run with: python run.py {output_path}")

    def request_exit():
        if recorder.recording:
            recorder.stop()
        exit_event.set()

    recorder.start_listeners()

    print("Input recorder ready.")
    print("F9       - start recording")
    print("F10      - stop recording and save")
    print("Ctrl+Esc - exit")
    print(f"Output: {output_path}")

    keyboard.add_hotkey("f9", start_recording, suppress=False, trigger_on_release=False)
    keyboard.add_hotkey("f10", stop_and_save, suppress=False, trigger_on_release=False)
    keyboard.add_hotkey("ctrl+esc", request_exit, suppress=False, trigger_on_release=False)

    try:
        exit_event.wait()
    except KeyboardInterrupt:
        request_exit()
    finally:
        keyboard.unhook_all_hotkeys()
        recorder.stop_listeners()
        if not saved and recorder.recording:
            recorder.stop()
        print("Exited.")


if __name__ == "__main__":
    main()

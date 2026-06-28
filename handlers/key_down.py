import keyboard

from runner import state
from runner.utils import normalize_key_name, to_int


def handle(args, _step):
    if len(args) < 1:
        return
    key = normalize_key_name(args[0])
    times = to_int(args[1]) if len(args) >= 2 else 1

    for _ in range(times):
        with state.state_lock:
            if state.exiting or not state.running:
                return
        keyboard.press(key)

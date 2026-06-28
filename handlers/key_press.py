import keyboard

from runner import state
from runner.utils import expand_key_sequence, to_int


def handle(args, _step):
    if len(args) < 1:
        return
    keys = expand_key_sequence(args[0])
    times = to_int(args[1]) if len(args) >= 2 else 1

    for _ in range(times):
        for key in keys:
            with state.state_lock:
                if state.exiting or not state.running:
                    return
            keyboard.press_and_release(key)

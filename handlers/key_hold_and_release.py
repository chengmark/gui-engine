import keyboard

from runner.utils import normalize_key_name, sleep_interruptible, to_float


def handle(args, _step):
    if len(args) < 2:
        return
    key = normalize_key_name(args[0])
    hold_seconds = to_float(args[1], 0.0)
    keyboard.press(key)
    try:
        sleep_interruptible(hold_seconds)
    finally:
        keyboard.release(key)

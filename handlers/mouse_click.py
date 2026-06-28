from runner import state
from runner.mouse import mouse_click
from runner.utils import normalize_mouse_button, to_int


def handle(args, _step):
    if len(args) < 1:
        return
    button = normalize_mouse_button(args[0])
    times = to_int(args[1]) if len(args) >= 2 else 1

    for _ in range(times):
        with state.state_lock:
            if state.exiting or not state.running:
                return
        mouse_click(button)

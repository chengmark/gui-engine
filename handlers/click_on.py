from runner.mouse import click_on
from runner.utils import normalize_mouse_button, to_int


def handle(args, _step):
    if len(args) < 2:
        return
    x = to_int(args[0], 0)
    y = to_int(args[1], 0)
    button = normalize_mouse_button(args[2]) if len(args) >= 3 else "left"
    click_on(x, y, button)

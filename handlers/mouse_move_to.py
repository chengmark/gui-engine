from runner.mouse import mouse_move_to
from runner.utils import to_int


def handle(args, _step):
    if len(args) < 2:
        return
    x = to_int(args[0], 0)
    y = to_int(args[1], 0)
    mouse_move_to(x, y)

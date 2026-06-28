from runner.mouse import mouse_move
from runner.utils import to_int


def handle(args, _step):
    dx = to_int(args[0], 0) if len(args) >= 1 else 0
    dy = to_int(args[1], 0) if len(args) >= 2 else 0
    mouse_move(dx, dy)

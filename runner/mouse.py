import ctypes
import ctypes.wintypes as wintypes
import math
import sys

from runner import state

_MOUSE_BUTTON_EVENTS = {
    "left": (0x0002, 0x0004),
    "right": (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
}

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUT(ctypes.Structure):
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION),
    ]


def _user32():
    if sys.platform != "win32":
        raise NotImplementedError("Mouse commands are only supported on Windows.")
    return ctypes.windll.user32


def get_cursor_pos() -> tuple[int, int]:
    pt = _POINT()
    _user32().GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor_pos(x: int, y: int):
    _user32().SetCursorPos(int(x), int(y))


def send_mouse_relative(dx: int, dy: int):
    if dx == 0 and dy == 0:
        return

    user32 = _user32()
    inp = _INPUT(type=INPUT_MOUSE)
    inp.mi = _MOUSEINPUT(dx=dx, dy=dy, dwFlags=MOUSEEVENTF_MOVE)
    if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT)) != 1:
        user32.mouse_event(MOUSEEVENTF_MOVE, dx, dy, 0, 0)


def mouse_click(button: str):
    down, up = _MOUSE_BUTTON_EVENTS.get(button, _MOUSE_BUTTON_EVENTS["left"])
    user32 = _user32()
    user32.mouse_event(down, 0, 0, 0, 0)
    user32.mouse_event(up, 0, 0, 0, 0)


def click_on(x: int, y: int, button: str = "left"):
    set_cursor_pos(x, y)
    mouse_click(button)


def mouse_move(dx: int, dy: int):
    if dx == 0 and dy == 0:
        return

    distance = math.hypot(dx, dy)
    steps = max(1, int(round(distance)))
    prev_x = 0
    prev_y = 0

    for i in range(1, steps + 1):
        with state.state_lock:
            if state.exiting or not state.running:
                return
        t = i / steps
        cur_x = round(dx * t)
        cur_y = round(dy * t)
        step_dx = cur_x - prev_x
        step_dy = cur_y - prev_y
        prev_x, prev_y = cur_x, cur_y
        send_mouse_relative(step_dx, step_dy)


def mouse_move_to(x: int, y: int):
    start_x, start_y = get_cursor_pos()
    dx = x - start_x
    dy = y - start_y
    if dx == 0 and dy == 0:
        return

    distance = math.hypot(dx, dy)
    steps = max(1, int(round(distance)))

    for i in range(1, steps + 1):
        with state.state_lock:
            if state.exiting or not state.running:
                return
        t = i / steps
        set_cursor_pos(round(start_x + dx * t), round(start_y + dy * t))

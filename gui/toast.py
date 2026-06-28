import sys
import tkinter as tk
from typing import Optional, Tuple


def _monitor_work_area_for_window(root: tk.Misc) -> Tuple[int, int, int, int]:
    """Return (x, y, width, height) of the work area on the monitor containing root."""
    root.update_idletasks()
    center_x = root.winfo_rootx() + max(root.winfo_width(), 1) // 2
    center_y = root.winfo_rooty() + max(root.winfo_height(), 1) // 2

    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes as wintypes

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            monitor = ctypes.windll.user32.MonitorFromPoint(
                POINT(center_x, center_y),
                2,  # MONITOR_DEFAULTTONEAREST
            )
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                area = info.rcWork
                return (
                    area.left,
                    area.top,
                    area.right - area.left,
                    area.bottom - area.top,
                )
        except Exception:
            pass

    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class Toast:
    def __init__(self, parent: tk.Misc):
        self._parent = parent
        self._window: Optional[tk.Toplevel] = None
        self._after_id: Optional[str] = None

    def show(self, message: str, duration_ms: int = 2200, on: Optional[bool] = None):
        if self._after_id is not None:
            self._parent.after_cancel(self._after_id)
            self._after_id = None

        self._hide()

        if on is True:
            bg = "#2d6a4f"
        elif on is False:
            bg = "#6a2d2d"
        else:
            bg = "#444444"

        window = tk.Toplevel(self._parent)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg=bg)

        label = tk.Label(
            window,
            text=message,
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff",
            bg=bg,
            padx=16,
            pady=10,
        )
        label.pack()

        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        area_x, area_y, area_w, area_h = _monitor_work_area_for_window(self._parent)
        x = area_x + area_w - width - 24
        y = area_y + area_h - height - 24
        window.geometry(f"+{x}+{y}")

        self._window = window
        self._after_id = self._parent.after(duration_ms, self._hide)

    def _hide(self):
        self._after_id = None
        if self._window is not None:
            self._window.destroy()
            self._window = None

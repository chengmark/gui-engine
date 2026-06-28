"""
Display a live popup with the cursor position and RGB color under the cursor.

Press Ctrl+Esc to close.
"""

import ctypes
import sys
import tkinter as tk

EXIT_HOTKEY = "ctrl+esc"


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_pos() -> tuple[int, int]:
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def get_pixel_rgb(x: int, y: int) -> tuple[int, int, int]:
    hdc = ctypes.windll.user32.GetDC(0)
    try:
        colorref = ctypes.windll.gdi32.GetPixel(hdc, x, y)
        if colorref == -1:
            return 0, 0, 0
        r = colorref & 0xFF
        g = (colorref >> 8) & 0xFF
        b = (colorref >> 16) & 0xFF
        return r, g, b
    finally:
        ctypes.windll.user32.ReleaseDC(0, hdc)


class CoordHelperApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Coord Helper")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e1e")

        self.frame = tk.Frame(self.root, bg="#1e1e1e", padx=16, pady=12)
        self.frame.pack()

        self.pos_label = tk.Label(
            self.frame,
            text="X: 0   Y: 0",
            font=("Consolas", 14),
            fg="#ffffff",
            bg="#1e1e1e",
            anchor="w",
        )
        self.pos_label.pack(fill="x", pady=(0, 8))

        color_row = tk.Frame(self.frame, bg="#1e1e1e")
        color_row.pack(fill="x", pady=(0, 8))

        self.swatch = tk.Label(
            color_row,
            width=4,
            height=2,
            bg="#000000",
            relief="solid",
            borderwidth=1,
        )
        self.swatch.pack(side="left", padx=(0, 10))

        self.rgb_label = tk.Label(
            color_row,
            text="RGB: 0, 0, 0",
            font=("Consolas", 14),
            fg="#ffffff",
            bg="#1e1e1e",
            anchor="w",
        )
        self.rgb_label.pack(side="left")

        self.hex_label = tk.Label(
            self.frame,
            text="#000000",
            font=("Consolas", 12),
            fg="#aaaaaa",
            bg="#1e1e1e",
            anchor="w",
        )
        self.hex_label.pack(fill="x")

        self.hint_label = tk.Label(
            self.frame,
            text="Ctrl+Esc to close",
            font=("Segoe UI", 9),
            fg="#888888",
            bg="#1e1e1e",
            anchor="w",
        )
        self.hint_label.pack(fill="x", pady=(10, 0))

        self._poll_interval_ms = 50
        self._hotkey_registered = False
        self._schedule_poll()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _schedule_poll(self):
        self._update()
        self.root.after(self._poll_interval_ms, self._schedule_poll)

    def _update(self):
        x, y = get_cursor_pos()
        r, g, b = get_pixel_rgb(x, y)
        hex_color = f"#{r:02X}{g:02X}{b:02X}"

        self.pos_label.config(text=f"X: {x}   Y: {y}")
        self.rgb_label.config(text=f"RGB: {r}, {g}, {b}")
        self.hex_label.config(text=hex_color)
        self.swatch.config(bg=hex_color)

    def register_hotkey(self):
        if self._hotkey_registered:
            return
        try:
            import keyboard

            keyboard.add_hotkey(EXIT_HOTKEY, self.close, suppress=False, trigger_on_release=False)
            self._hotkey_registered = True
        except Exception:
            pass

    def close(self):
        if self._hotkey_registered:
            try:
                import keyboard

                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
        self.root.after(0, self.root.destroy)

    def run(self):
        self.register_hotkey()
        self.root.mainloop()


def main():
    if sys.platform != "win32":
        raise SystemExit("coord_helper.py only supports Windows.")

    app = CoordHelperApp()
    app.run()


if __name__ == "__main__":
    main()

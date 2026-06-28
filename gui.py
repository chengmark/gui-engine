"""
Automation control panel GUI.

Launch:
    python gui.py
"""

import json
import os
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, Optional

from gui.services import (
    StubBackgroundManager,
    StubInputRecorder,
    StubScriptRunner,
    build_script,
    create_background_manager,
    create_input_recorder,
    create_script_runner,
    events_to_steps,
    get_cursor_sample,
    stub_background_manager,
    stub_input_recorder,
    stub_script_runner,
)
from gui.toast import Toast

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(APP_DIR, "scripts")

POLL_MS = 200
SCRIPT_SCAN_MS = 500
WINDOW_WIDTH = 760
WINDOW_HEIGHT = 680
SCRIPTS_PANEL_WIDTH = 520
CURSOR_PANEL_WIDTH = 200
BG_COLUMN = "#2"


class ScriptCatalog:
    def __init__(self, scripts_dir: str):
        self.scripts_dir = scripts_dir
        self._cache: Dict[str, dict] = {}

    def scan(self) -> Dict[str, dict]:
        if not os.path.isdir(self.scripts_dir):
            os.makedirs(self.scripts_dir, exist_ok=True)

        current_files = set()
        updated: Dict[str, dict] = {}

        for name in sorted(os.listdir(self.scripts_dir)):
            if not name.lower().endswith(".json"):
                continue
            path = os.path.join(self.scripts_dir, name)
            if not os.path.isfile(path):
                continue
            current_files.add(name)

            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue

            cached = self._cache.get(name)
            if cached and cached["mtime"] == mtime:
                if "has_background" not in cached:
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            cached = dict(cached)
                            cached["has_background"] = bool(json.load(f).get("background"))
                    except (OSError, json.JSONDecodeError):
                        cached = dict(cached)
                        cached["has_background"] = False
                updated[name] = cached
                continue

            description = name
            has_background = False
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                description = data.get("description") or name
                has_background = bool(data.get("background"))
            except (OSError, json.JSONDecodeError):
                pass

            updated[name] = {
                "filename": name,
                "path": path,
                "description": description,
                "mtime": mtime,
                "has_background": has_background,
            }

        for stale in list(self._cache.keys()):
            if stale not in current_files:
                self._cache.pop(stale, None)

        self._cache = updated
        return updated


class AutomationGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Automation Control Panel")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(680, 460)
        self.root.configure(bg="#1e1e1e")

        self.catalog = ScriptCatalog(SCRIPTS_DIR)
        self.runner = stub_script_runner(on_status_change=self._on_runner_status)
        self.background_manager = stub_background_manager()
        self.recorder = stub_input_recorder()
        self.recording_active = False
        self.toast = Toast(self.root)

        self._selected_filename: Optional[str] = None
        self._background_checked: set[str] = set()
        self._last_running: Optional[bool] = None
        self._was_script_loaded = False
        self._last_script_name: Optional[str] = None
        self.pid_var = tk.StringVar(value="")

        self._build_ui()
        self._refresh_script_list()
        self._update_controls()
        self._poll_cursor()
        self._poll_scripts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TLabel", background="#1e1e1e", foreground="#ffffff")
        style.configure("TLabelframe", background="#1e1e1e", foreground="#ffffff")
        style.configure("TLabelframe.Label", background="#1e1e1e", foreground="#ffffff")
        style.configure("TButton", padding=6)
        style.configure(
            "Scripts.Treeview",
            background="#2b2b2b",
            foreground="#ffffff",
            fieldbackground="#2b2b2b",
            rowheight=24,
        )
        style.configure(
            "Scripts.Treeview.Heading",
            background="#333333",
            foreground="#ffffff",
            relief="flat",
        )
        style.map(
            "Scripts.Treeview",
            background=[("selected", "#3d6ea8")],
            foreground=[("selected", "#ffffff")],
        )

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main)
        top.pack(fill="both", expand=True)

        left = ttk.LabelFrame(top, text="Scripts", padding=8, width=SCRIPTS_PANEL_WIDTH)
        left.pack(side="left", fill="both", padx=(0, 8))
        left.pack_propagate(False)

        table_frame = ttk.Frame(left)
        table_frame.pack(fill="both", expand=True)

        columns = ("no", "bg", "description", "filename")
        self.script_table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            style="Scripts.Treeview",
        )
        self.script_table.heading("no", text="#")
        self.script_table.heading("bg", text="BG")
        self.script_table.heading("description", text="Description")
        self.script_table.heading("filename", text="Filename")
        self.script_table.column("no", width=36, anchor="center", stretch=False)
        self.script_table.column("bg", width=36, anchor="center", stretch=False)
        self.script_table.column("description", width=200, anchor="w")
        self.script_table.column("filename", width=150, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.script_table.yview)
        self.script_table.configure(yscrollcommand=scrollbar.set)
        self.script_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.script_table.bind("<<TreeviewSelect>>", self._on_script_select)
        self.script_table.bind("<Button-1>", self._on_script_table_click, add=True)

        right = ttk.LabelFrame(top, text="Cursor", padding=8, width=CURSOR_PANEL_WIDTH)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self.pos_label = tk.Label(
            right,
            text="X: 0   Y: 0",
            font=("Consolas", 13),
            fg="#ffffff",
            bg="#1e1e1e",
            anchor="w",
            width=20,
        )
        self.pos_label.pack(fill="x", pady=(0, 8))

        color_row = tk.Frame(right, bg="#1e1e1e")
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
            font=("Consolas", 13),
            fg="#ffffff",
            bg="#1e1e1e",
            anchor="w",
            width=16,
        )
        self.rgb_label.pack(side="left")

        self.hex_label = tk.Label(
            right,
            text="#000000",
            font=("Consolas", 11),
            fg="#aaaaaa",
            bg="#1e1e1e",
            anchor="w",
            width=20,
        )
        self.hex_label.pack(fill="x")

        status_frame = ttk.LabelFrame(main, text="Status", padding=8)
        status_frame.pack(fill="x", pady=(10, 8))

        self.selected_label = ttk.Label(status_frame, text="Selected: none")
        self.selected_label.pack(anchor="w")

        pid_row = ttk.Frame(status_frame)
        pid_row.pack(anchor="w", pady=(4, 0))
        ttk.Label(pid_row, text="PID:").pack(side="left")
        self.pid_entry = ttk.Entry(pid_row, textvariable=self.pid_var, width=12)
        self.pid_entry.pack(side="left", padx=(6, 0))
        ttk.Label(
            pid_row,
            text="(for limit_download.py; blank uses script default)",
            foreground="#888888",
        ).pack(side="left", padx=(8, 0))

        self.script_status_label = ttk.Label(status_frame, text="Script: Idle")
        self.script_status_label.pack(anchor="w", pady=(4, 0))
        self.record_status_label = ttk.Label(status_frame, text="Recording: Idle")
        self.record_status_label.pack(anchor="w", pady=(4, 0))

        script_btns = ttk.Frame(main)
        script_btns.pack(fill="x", pady=(0, 6))

        self.load_btn = ttk.Button(script_btns, text="Load Script", command=self._load_script)
        self.load_btn.pack(side="left", padx=(0, 6))

        self.toggle_btn = ttk.Button(script_btns, text="Toggle Script", command=self._toggle_script)
        self.toggle_btn.pack(side="left", padx=(0, 6))

        self.stop_script_btn = ttk.Button(script_btns, text="Stop Script", command=self._stop_script)
        self.stop_script_btn.pack(side="left")

        record_btns = ttk.Frame(main)
        record_btns.pack(fill="x")

        self.start_record_btn = ttk.Button(
            record_btns, text="Start Recording", command=self._start_recording
        )
        self.start_record_btn.pack(side="left", padx=(0, 6))

        self.stop_record_btn = ttk.Button(
            record_btns, text="Stop & Save Recording", command=self._stop_recording
        )
        self.stop_record_btn.pack(side="left")

        hint = ttk.Label(
            main,
            text="Shift+Esc unloads the active script. Background (BG) scripts run when checked.",
            foreground="#888888",
        )
        hint.pack(anchor="w", pady=(10, 0))

    def _ensure_runner(self):
        if not isinstance(self.runner, StubScriptRunner):
            return
        self.runner = create_script_runner(on_status_change=self._on_runner_status)

    def _ensure_background_manager(self):
        if not isinstance(self.background_manager, StubBackgroundManager):
            return
        self.background_manager = create_background_manager()

    def _ensure_recorder(self):
        if not isinstance(self.recorder, StubInputRecorder):
            return
        self.recorder = create_input_recorder()

    def _busy(self) -> Optional[str]:
        if self.recording_active:
            return "recording"
        if self.runner.is_loaded:
            return "script"
        return None

    def _on_runner_status(self):
        def update():
            was_loaded = self._was_script_loaded
            is_loaded = self.runner.is_loaded
            is_running = self.runner.is_running if is_loaded else False

            if is_loaded and self._last_running is not None and is_running != self._last_running:
                name = os.path.splitext(os.path.basename(self.runner.script_path or "script"))[0]
                self.toast.show(f"{name}: {'ON' if is_running else 'OFF'}", on=is_running)

            if was_loaded and not is_loaded and self._last_script_name:
                name = os.path.splitext(os.path.basename(self._last_script_name))[0]
                self.toast.show(f"{name}: unloaded")

            self._was_script_loaded = is_loaded
            if is_loaded:
                self._last_running = is_running
                self._last_script_name = self.runner.script_path
            else:
                self._last_running = None

            self._update_status_labels()

        self.root.after(0, update)

    def _bg_checkbox_text(self, filename: str, entry: dict) -> str:
        if not entry.get("has_background"):
            return ""
        return "☑" if filename in self._background_checked else "☐"

    def _update_bg_checkbox(self, filename: str):
        entry = self.catalog._cache.get(filename)
        if not entry or filename not in self.script_table.get_children():
            return
        values = self.script_table.item(filename, "values")
        if not values:
            return
        mark = self._bg_checkbox_text(filename, entry)
        self.script_table.item(filename, values=(values[0], mark, values[2], values[3]))

    def _on_script_table_click(self, event):
        column = self.script_table.identify_column(event.x)
        if column != BG_COLUMN:
            return
        filename = self.script_table.identify_row(event.y)
        if not filename:
            return
        entry = self.catalog._cache.get(filename)
        if not entry or not entry.get("has_background"):
            return

        if filename in self._background_checked:
            self._background_checked.discard(filename)
            checked = False
        else:
            self._background_checked.add(filename)
            checked = True

        self._ensure_background_manager()
        try:
            if checked:
                self.background_manager.load(entry["path"])
            else:
                self.background_manager.unload(filename)
        except Exception as exc:
            if checked:
                self._background_checked.discard(filename)
            else:
                self._background_checked.add(filename)
            messagebox.showerror("Background Script", str(exc), parent=self.root)

        self._update_bg_checkbox(filename)
        return "break"

    def _sync_background_scripts(self):
        self._ensure_background_manager()
        loaded = self.background_manager.loaded_filenames()
        for filename in list(loaded):
            if filename not in self._background_checked:
                self.background_manager.unload(filename)
        for filename in list(self._background_checked):
            entry = self.catalog._cache.get(filename)
            if not entry or not entry.get("has_background"):
                self._background_checked.discard(filename)
                continue
            if not self.background_manager.is_loaded(filename):
                try:
                    self.background_manager.load(entry["path"])
                except Exception as exc:
                    print(f"Background load failed ({filename}): {exc}")
                    self._background_checked.discard(filename)

    def _on_script_select(self, _event=None):
        selection = self.script_table.selection()
        if not selection:
            if self._selected_filename is not None:
                self._selected_filename = None
                self.pid_var.set("")
                self._update_status_labels()
            return

        filename = selection[0]
        if filename == self._selected_filename:
            return

        self._selected_filename = filename
        self._sync_pid_from_script()
        self._update_status_labels()

    def _default_limit_download_pid(self, script_path: str) -> Optional[int]:
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

        for entry in data.get("scripts", []):
            file_name = os.path.basename(str(entry.get("file", ""))).lower()
            if file_name != "limit_download.py":
                continue
            args = entry.get("args", [])
            if args and isinstance(args[0], (int, float)):
                return int(args[0])
        return None

    def _sync_pid_from_script(self):
        path = self._selected_path()
        if not path:
            self.pid_var.set("")
            return
        default_pid = self._default_limit_download_pid(path)
        self.pid_var.set(str(default_pid) if default_pid is not None else "")

    def _refresh_script_list(self):
        entries = self.catalog.scan()
        previous_selection = self._selected_filename

        for item in self.script_table.get_children():
            self.script_table.delete(item)

        sorted_entries = sorted(
            entries.items(),
            key=lambda item: (item[1]["description"].lower(), item[1]["filename"].lower()),
        )

        for index, (filename, entry) in enumerate(sorted_entries, start=1):
            bg_mark = self._bg_checkbox_text(filename, entry)
            self.script_table.insert(
                "",
                "end",
                iid=filename,
                values=(index, bg_mark, entry["description"], entry["filename"]),
            )
            if filename == previous_selection:
                self.script_table.selection_set(filename)
                self.script_table.see(filename)

        if previous_selection and previous_selection not in entries:
            self._selected_filename = None
            self.pid_var.set("")

        self._sync_background_scripts()
        self._update_status_labels()

    def _poll_scripts(self):
        self._refresh_script_list()
        self.root.after(SCRIPT_SCAN_MS, self._poll_scripts)

    def _poll_cursor(self):
        try:
            x, y, r, g, b = get_cursor_sample()
            hex_color = f"#{r:02X}{g:02X}{b:02X}"
            self.pos_label.config(text=f"X: {x}   Y: {y}")
            self.rgb_label.config(text=f"RGB: {r}, {g}, {b}")
            self.hex_label.config(text=hex_color)
            self.swatch.config(bg=hex_color)
        except RuntimeError:
            pass
        except Exception:
            pass
        self.root.after(POLL_MS, self._poll_cursor)

    def _update_status_labels(self):
        if self._selected_filename:
            entry = self.catalog._cache.get(self._selected_filename)
            if entry:
                self.selected_label.config(
                    text=f"Selected: {entry['description']} (file: {entry['filename']})"
                )
            else:
                self.selected_label.config(text=f"Selected: {self._selected_filename}")
        else:
            self.selected_label.config(text="Selected: none")

        if not self.runner.is_loaded:
            script_text = "Script: Idle"
        elif self.runner.is_running:
            script_text = f"Script: Running ON ({os.path.basename(self.runner.script_path or '')})"
        else:
            script_text = f"Script: Loaded OFF ({os.path.basename(self.runner.script_path or '')})"

        self.script_status_label.config(text=script_text)

        if self.recording_active:
            with self.recorder.lock:
                event_count = len(self.recorder.events)
            self.record_status_label.config(text=f"Recording: Active ({event_count} events)")
        else:
            self.record_status_label.config(text="Recording: Idle")

        self._update_controls()

    def _update_controls(self):
        busy = self._busy()

        can_use_scripts = busy is None
        can_load = can_use_scripts and self._selected_filename is not None
        can_toggle = busy == "script"
        can_stop_script = busy == "script"
        can_start_record = busy is None
        can_stop_record = busy == "recording"

        if can_use_scripts:
            self.script_table.state(())
        else:
            self.script_table.state(("disabled",))
        self.load_btn.config(state="normal" if can_load else "disabled")
        self.toggle_btn.config(state="normal" if can_toggle else "disabled")
        self.stop_script_btn.config(state="normal" if can_stop_script else "disabled")
        self.start_record_btn.config(state="normal" if can_start_record else "disabled")
        self.stop_record_btn.config(state="normal" if can_stop_record else "disabled")
        self.pid_entry.config(state="normal" if can_use_scripts else "disabled")

    def _selected_path(self) -> Optional[str]:
        if not self._selected_filename:
            return None
        return os.path.join(SCRIPTS_DIR, self._selected_filename)

    def _load_script(self):
        if self._busy():
            messagebox.showwarning("Busy", "Stop the current script or recording first.")
            return

        path = self._selected_path()
        if not path:
            messagebox.showinfo("Select Script", "Select a script from the list first.")
            return

        pid_override = None
        pid_text = self.pid_var.get().strip()
        if pid_text:
            try:
                pid_override = int(pid_text)
                if pid_override <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Invalid PID",
                    "Enter a positive integer PID, or leave the field blank to use the script default.",
                )
                return

        try:
            self._ensure_runner()
            self.runner.load(path, pid_override=pid_override)
            self._last_running = False
            self._was_script_loaded = True
            self._last_script_name = path
        except Exception as exc:
            messagebox.showerror("Load Failed", str(exc))
            return

        self._update_status_labels()

    def _toggle_script(self):
        if self._busy() != "script":
            return
        self.runner.toggle()
        self._update_status_labels()

    def _stop_script(self):
        if not self.runner.is_loaded:
            return
        self.runner.unload()
        self._update_status_labels()

    def _start_recording(self):
        if self._busy():
            messagebox.showwarning("Busy", "Stop the current script or recording first.")
            return

        try:
            self._ensure_recorder()
            self.recorder.start_listeners()
            self.recorder.start()
        except RuntimeError as exc:
            messagebox.showerror("Recording Unavailable", str(exc))
            return

        self.recording_active = True
        self._update_status_labels()

    def _stop_recording(self):
        if not self.recording_active:
            return

        events = self.recorder.stop()
        self.recorder.stop_listeners()
        self.recording_active = False
        self._update_status_labels()

        default_name = f"recorded_{int(time.time())}.json"
        filename = simpledialog.askstring(
            "Save Recording",
            "Save as (in scripts/):",
            initialvalue=default_name,
            parent=self.root,
        )
        if not filename:
            messagebox.showinfo("Recording", "Recording discarded.")
            return

        filename = filename.strip()
        if not filename.lower().endswith(".json"):
            filename += ".json"

        description = simpledialog.askstring(
            "Description",
            "Script description:",
            initialvalue=os.path.splitext(filename)[0],
            parent=self.root,
        )
        if description is None:
            messagebox.showinfo("Recording", "Recording discarded.")
            return

        steps = events_to_steps(events)
        if not steps:
            messagebox.showwarning("Recording", "No events recorded.")
            return

        try:
            output_path = os.path.join(SCRIPTS_DIR, filename)
            script = build_script(steps, description.strip() or os.path.splitext(filename)[0], "home")
        except RuntimeError as exc:
            messagebox.showerror("Recording Unavailable", str(exc))
            return

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=4, ensure_ascii=False)
            f.write("\n")

        self._selected_filename = filename
        self._refresh_script_list()
        messagebox.showinfo("Recording", f"Saved {len(steps)} steps to {output_path}")

    def _on_close(self):
        if self.recording_active:
            self.recorder.stop()
            self.recorder.stop_listeners()
            self.recording_active = False
        if self.runner.is_loaded:
            self.runner.unload()
        self.background_manager.unload_all()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    if sys.platform != "win32":
        print("Warning: gui.py is intended for Windows.")
    app = AutomationGUI()
    app.run()


if __name__ == "__main__":
    main()

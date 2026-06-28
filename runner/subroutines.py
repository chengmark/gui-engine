import os
import subprocess
import sys
from typing import Optional

from runner.constants import APP_ROOT, RUN_PY


class ScriptSubroutine:
    def __init__(self, file: str, args: list, base_dir: str, key: Optional[str] = None):
        self.file = file
        self.args = args
        self.base_dir = base_dir
        self.key = key or file
        self.process = None
        self.synced_on = False

    def _resolve_path(self) -> str:
        if os.path.isabs(self.file):
            return self.file
        if self.file.lower().endswith(".py"):
            return os.path.join(APP_ROOT, self.file)
        return os.path.join(self.base_dir, self.file)

    def _working_dir(self, target: str) -> str:
        if target.lower().endswith(".py"):
            return APP_ROOT
        return self.base_dir

    def _build_command(self) -> list[str]:
        target = self._resolve_path()
        str_args = [str(arg) for arg in self.args]

        if target.lower().endswith(".json"):
            return [sys.executable, RUN_PY, target, *str_args, "--controlled"]

        if target.lower().endswith(".py"):
            return [sys.executable, target, *str_args, "--controlled"]

        raise ValueError(f"Unsupported script file type: {self.file}")

    def start(self, parent_running: bool = False):
        if self.process and self.process.poll() is None:
            return

        cmd = self._build_command()
        target = self._resolve_path()
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=self._working_dir(target),
        )
        print(f"Started subroutine: {self.file} {' '.join(str(a) for a in self.args)}")

        if parent_running and not self.synced_on:
            self._send("toggle")
            self.synced_on = True

    def _send(self, command: str):
        if not self.process or self.process.poll() is not None:
            return
        try:
            self.process.stdin.write(f"{command}\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass

    def toggle(self):
        self._send("toggle")
        self.synced_on = not self.synced_on

    def shutdown(self):
        self._send("exit")
        if not self.process:
            return
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.process = None
        self.synced_on = False


class SubroutineManager:
    def __init__(self, scripts: list, base_dir: str):
        self.base_dir = base_dir
        self.subroutines: dict[str, ScriptSubroutine] = {}
        for entry in scripts:
            file_name = entry.get("file")
            if not file_name:
                continue
            args = entry.get("args", [])
            key = entry.get("key", file_name)
            self.subroutines[key] = ScriptSubroutine(file_name, args, base_dir, key)

    def start_all(self, parent_running: bool = False):
        for subroutine in self.subroutines.values():
            subroutine.start(parent_running=parent_running)

    def start_script(self, file_name: str, args: list, parent_running: bool = False):
        key = file_name
        if key not in self.subroutines:
            self.subroutines[key] = ScriptSubroutine(file_name, args, self.base_dir, key)
        self.subroutines[key].start(parent_running=parent_running)

    def toggle_all(self):
        for subroutine in self.subroutines.values():
            subroutine.toggle()

    def shutdown_all(self):
        for subroutine in self.subroutines.values():
            subroutine.shutdown()

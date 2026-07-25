import os
import sys


def _app_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


APP_ROOT = _app_root()
DEFAULT_SCRIPT = os.path.join(APP_ROOT, "scripts", "script.json")
RUN_PY = os.path.join(APP_ROOT, "run.py")

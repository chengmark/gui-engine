import os
import sys

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SCRIPT = os.path.join(APP_ROOT, "scripts", "script.json")
RUN_PY = os.path.join(APP_ROOT, "run.py")

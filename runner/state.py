import threading
from typing import TYPE_CHECKING, Optional

from runner.constants import APP_ROOT

if TYPE_CHECKING:
    from runner.subroutines import SubroutineManager

running = False
exiting = False
state_lock = threading.Lock()
exit_event = threading.Event()
script_base_dir = APP_ROOT
subroutine_manager: Optional["SubroutineManager"] = None
background_cleanups: list = []

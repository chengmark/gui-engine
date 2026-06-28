from typing import Optional

from runner import state
from runner.triggers import is_mouse_trigger, register_key_trigger, register_mouse_trigger
from runner.volume import get_master_volume, set_master_volume


class _MuteToggle:
    def __init__(self):
        self.muted = False
        self.saved_volume: Optional[float] = None

    def toggle(self):
        try:
            if not self.muted:
                self.saved_volume = get_master_volume()
                set_master_volume(0.0)
                self.muted = True
                print(f"ToggleMute ON (saved volume {self.saved_volume:.2f})")
            else:
                restore = self.saved_volume if self.saved_volume is not None else 1.0
                set_master_volume(restore)
                print(f"ToggleMute OFF (restored volume {restore:.2f})")
                self.muted = False
                self.saved_volume = None
        except Exception as exc:
            print(f"ToggleMute failed: {exc}")

    def restore_if_muted(self):
        if not self.muted or self.saved_volume is None:
            return
        try:
            set_master_volume(self.saved_volume)
            print(f"ToggleMute cleanup (restored volume {self.saved_volume:.2f})")
        except Exception as exc:
            print(f"ToggleMute cleanup failed: {exc}")
        finally:
            self.muted = False
            self.saved_volume = None


def handle(args, _step):
    if len(args) < 1:
        print("ToggleMute requires a trigger key or mouse button.")
        return

    trigger = str(args[0]).strip()
    toggler = _MuteToggle()

    if is_mouse_trigger(trigger):
        remove_trigger = register_mouse_trigger(trigger, toggler.toggle)
    else:
        remove_trigger = register_key_trigger(trigger, toggler.toggle)

    def cleanup():
        toggler.restore_if_muted()
        remove_trigger()

    state.background_cleanups.append(cleanup)

from runner import state
from runner.triggers import is_mouse_trigger, register_key_trigger, register_mouse_trigger
from runner.utils import to_float
from runner.volume import set_master_volume


def _make_callback(volume: float):
    def on_trigger():
        try:
            set_master_volume(volume)
            print(f"SetVolume -> {volume:.2f}")
        except Exception as exc:
            print(f"SetVolume failed: {exc}")

    return on_trigger


def handle(args, _step):
    if len(args) < 2:
        print("SetVolume requires trigger and volume (0-1).")
        return

    trigger = str(args[0]).strip()
    volume = to_float(args[1], 0.0)
    volume = max(0.0, min(1.0, volume))
    callback = _make_callback(volume)

    if is_mouse_trigger(trigger):
        cleanup = register_mouse_trigger(trigger, callback)
    else:
        cleanup = register_key_trigger(trigger, callback)

    state.background_cleanups.append(cleanup)

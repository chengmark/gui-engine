from handlers.set_volume import handle as handle_set_volume
from handlers.toggle_mute import handle as handle_toggle_mute
from handlers.click_on import handle as handle_click_on
from handlers.delay import handle as handle_delay
from handlers.import_script import handle as handle_import_script
from handlers.key_down import handle as handle_key_down
from handlers.key_hold_and_release import handle as handle_key_hold_and_release
from handlers.key_press import handle as handle_key_press
from handlers.key_up import handle as handle_key_up
from handlers.mouse_click import handle as handle_mouse_click
from handlers.mouse_move import handle as handle_mouse_move
from handlers.mouse_move_to import handle as handle_mouse_move_to
from handlers.script import handle as handle_script

HANDLERS = {
    "Script": handle_script,
    "ImportScript": handle_import_script,
    "Delay": handle_delay,
    "KeyHoldAndRelease": handle_key_hold_and_release,
    "KeyDown": handle_key_down,
    "KeyUp": handle_key_up,
    "KeyPress": handle_key_press,
    "MouseClick": handle_mouse_click,
    "MouseMove": handle_mouse_move,
    "MouseMoveTo": handle_mouse_move_to,
    "ClickOn": handle_click_on,
    "SetVolume": handle_set_volume,
    "ToggleMute": handle_toggle_mute,
}


def perform_step(step):
    cmd = step.get("command")
    handler = HANDLERS.get(cmd)
    if handler is None:
        print(f"Unknown command: {cmd}")
        return
    handler(step.get("args", []), step)

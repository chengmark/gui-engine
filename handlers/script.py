from runner import state


def handle(args, _step):
    if len(args) < 1:
        return
    file_name = args[0]
    script_args = args[1:]
    with state.state_lock:
        parent_running = state.running
    if state.subroutine_manager:
        state.subroutine_manager.start_script(file_name, script_args, parent_running=parent_running)

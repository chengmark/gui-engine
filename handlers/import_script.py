from runner.script_io import run_imported_script


def handle(args, _step):
    if len(args) < 1:
        return
    run_imported_script(args[0])

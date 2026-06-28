from runner.utils import sleep_interruptible, to_float


def handle(args, _step):
    ms = args[0] if args else 0
    sleep_interruptible(to_float(ms) / 1000.0)

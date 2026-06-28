"""
Limit inbound (download) bandwidth for a specific process on Windows.

Requires Administrator privileges (WinDivert driver).
Upload traffic is not modified.
When enabled, alternates: limit 1 min -> normal 30s -> repeat.
Press Home to toggle the cycle on/off.
Press Ctrl+Esc to exit.
"""

import argparse
import ctypes
import re
import sys
import threading
import time

import keyboard
import psutil
import pydivert

TOGGLE_KEY = "home"
EXIT_HOTKEY = "ctrl+esc"
LIMIT_DURATION_SEC = 60.0
RESUME_DURATION_SEC = 30.0

UNIT_MULTIPLIERS = {
    "B": 1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
}

RATE_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(B|KB|MB|GB)?\s*$",
    re.IGNORECASE,
)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def parse_rate(rate_text: str) -> int:
    """Parse a rate string like '5 MB', '1024KB', or '1.5 GB' into bytes/sec."""
    match = RATE_PATTERN.match(rate_text)
    if not match:
        raise ValueError(
            f"Invalid rate '{rate_text}'. Use formats like 512 B, 10 KB, 5 MB, or 1 GB."
        )

    value = float(match.group(1))
    unit = (match.group(2) or "B").upper()
    multiplier = UNIT_MULTIPLIERS[unit]
    rate = int(value * multiplier)
    if rate <= 0:
        raise ValueError("Rate must be greater than zero.")
    return rate


def format_rate(bytes_per_sec: float) -> str:
    if bytes_per_sec >= UNIT_MULTIPLIERS["GB"]:
        return f"{bytes_per_sec / UNIT_MULTIPLIERS['GB']:.2f} GB/s"
    if bytes_per_sec >= UNIT_MULTIPLIERS["MB"]:
        return f"{bytes_per_sec / UNIT_MULTIPLIERS['MB']:.2f} MB/s"
    if bytes_per_sec >= UNIT_MULTIPLIERS["KB"]:
        return f"{bytes_per_sec / UNIT_MULTIPLIERS['KB']:.2f} KB/s"
    return f"{bytes_per_sec:.0f} B/s"


class TokenBucket:
    def __init__(self, rate_bytes_per_sec: int, burst_seconds: float = 1.0):
        self.rate = rate_bytes_per_sec
        self.capacity = max(rate_bytes_per_sec, int(rate_bytes_per_sec * burst_seconds))
        self.tokens = float(self.capacity)
        self.updated_at = time.monotonic()
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.tokens = float(self.capacity)
            self.updated_at = time.monotonic()

    def consume(self, amount: int) -> float:
        """Return seconds to wait before this amount can be sent."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.updated_at
            self.updated_at = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if amount <= self.tokens:
                self.tokens -= amount
                return 0.0

            deficit = amount - self.tokens
            self.tokens = 0.0
            return deficit / self.rate


class ProcessDownloadLimiter:
    def __init__(self, pid: int, rate_bytes_per_sec: int):
        self.pid = pid
        self.rate_bytes_per_sec = rate_bytes_per_sec
        self.enabled = False
        self.app_stopping = False

        self.endpoints = set()
        self.endpoints_lock = threading.Lock()

        self.bucket = TokenBucket(rate_bytes_per_sec)
        self.state_lock = threading.Lock()

        self.divert_thread = None
        self.divert_handle = None
        self.divert_lock = threading.Lock()
        self.endpoint_thread = None
        self.stats_thread = None
        self.workers_started = False

        self.bytes_allowed = 0
        self.stats_lock = threading.Lock()

        self.cycle_active = False
        self.cycle_thread = None

        self._validate_process()

    def _validate_process(self):
        if not psutil.pid_exists(self.pid):
            raise ProcessLookupError(f"No process with PID {self.pid}.")
        proc = psutil.Process(self.pid)
        print(f"Target process: PID {self.pid} ({proc.name()})")
        print(f"Download limit: {format_rate(self.rate_bytes_per_sec)} (upload unchanged)")
        print(
            f"Cycle: limit {LIMIT_DURATION_SEC:.0f}s, "
            f"normal {RESUME_DURATION_SEC:.0f}s, repeat"
        )

    def _refresh_endpoints(self):
        endpoints = set()
        try:
            proc = psutil.Process(self.pid)
            for conn in proc.net_connections(kind="inet"):
                if not conn.laddr:
                    continue
                local_ip = conn.laddr.ip
                local_port = conn.laddr.port
                endpoints.add((local_ip, local_port))
                if local_ip in ("0.0.0.0", "::"):
                    endpoints.add(("", local_port))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        with self.endpoints_lock:
            self.endpoints = endpoints

    def _packet_belongs_to_process(self, packet: pydivert.Packet) -> bool:
        with self.endpoints_lock:
            endpoints = self.endpoints

        dst_addr = packet.dst_addr
        dst_port = packet.dst_port

        for local_ip, local_port in endpoints:
            if local_port != dst_port:
                continue
            if not local_ip or local_ip in ("0.0.0.0", "::") or local_ip == dst_addr:
                return True
        return False

    def _should_stop_divert(self) -> bool:
        with self.state_lock:
            return self.app_stopping or not self.enabled

    def _close_handle(self, handle: pydivert.WinDivert):
        with self.divert_lock:
            if self.divert_handle is handle:
                self.divert_handle = None
        try:
            handle.close()
        except OSError:
            pass

    def _send_packet(self, handle: pydivert.WinDivert, packet: pydivert.Packet) -> bool:
        try:
            handle.send(packet)
            return True
        except OSError:
            return False

    def _sleep_interruptible(self, seconds: float) -> bool:
        """Sleep in short chunks. Returns False if limiting was disabled."""
        if seconds <= 0:
            return True

        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._should_stop_divert():
                return False
            time.sleep(min(0.05, end - time.monotonic()))
        return True

    def _endpoint_loop(self):
        while not self.app_stopping:
            self._refresh_endpoints()
            time.sleep(0.25)

    def _stats_loop(self):
        last_bytes = 0
        last_time = time.monotonic()

        while not self.app_stopping:
            time.sleep(1.0)
            now = time.monotonic()
            with self.stats_lock:
                current_bytes = self.bytes_allowed
            elapsed = max(now - last_time, 0.001)
            delta = current_bytes - last_bytes
            speed = delta / elapsed

            with self.state_lock:
                enabled = self.enabled

            status = "ON" if enabled else "OFF"
            print(
                f"[{status}] PID {self.pid} download: {format_rate(speed)} "
                f"(cap {format_rate(self.rate_bytes_per_sec)})"
            )

            last_bytes = current_bytes
            last_time = now

    def _divert_loop(self):
        packet_filter = "inbound and (tcp or udp)"
        handle = pydivert.WinDivert(packet_filter)

        with self.divert_lock:
            self.divert_handle = handle

        try:
            handle.open()
            while not self._should_stop_divert():
                try:
                    packet = handle.recv()
                except OSError:
                    break

                if self._should_stop_divert():
                    self._send_packet(handle, packet)
                    break

                if not self._packet_belongs_to_process(packet):
                    if not self._send_packet(handle, packet):
                        break
                    continue

                packet_size = len(packet.raw)
                wait_seconds = self.bucket.consume(packet_size)
                if wait_seconds > 0:
                    self._sleep_interruptible(wait_seconds)

                if not self._send_packet(handle, packet):
                    break

                with self.stats_lock:
                    self.bytes_allowed += packet_size
        finally:
            self._close_handle(handle)

    def _start_background_workers(self):
        if self.workers_started:
            return

        self.endpoint_thread = threading.Thread(target=self._endpoint_loop, daemon=True)
        self.stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
        self.endpoint_thread.start()
        self.stats_thread.start()
        self.workers_started = True

    def _stop_divert(self):
        with self.divert_lock:
            handle = self.divert_handle

        if handle is not None:
            # Closing unblocks recv(); divert loop catches OSError on send/recv.
            self._close_handle(handle)

        if self.divert_thread and self.divert_thread.is_alive():
            self.divert_thread.join(timeout=3.0)
        self.divert_thread = None

    def start_limiting(self):
        with self.state_lock:
            if self.enabled:
                return
            self.enabled = True

        self.bucket.reset()
        self._start_background_workers()
        self._stop_divert()

        self.divert_thread = threading.Thread(target=self._divert_loop, daemon=True)
        self.divert_thread.start()
        print("Download limiting enabled.")

    def stop_limiting(self):
        with self.state_lock:
            if not self.enabled:
                return
            self.enabled = False

        self._stop_divert()
        print("Download limiting disabled.")

    def _wait_phase(self, seconds: float) -> bool:
        """Wait for a cycle phase. Returns False if the cycle should stop."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            with self.state_lock:
                if self.app_stopping or not self.cycle_active:
                    return False
            time.sleep(min(0.1, end - time.monotonic()))
        return True

    def _cycle_loop(self):
        self._start_background_workers()
        print(
            f"Download cycle started: limit {LIMIT_DURATION_SEC:.0f}s, "
            f"normal {RESUME_DURATION_SEC:.0f}s."
        )

        while not self.app_stopping:
            with self.state_lock:
                if not self.cycle_active:
                    break

            print(f"Cycle phase: limiting for {LIMIT_DURATION_SEC:.0f}s...")
            self.start_limiting()
            if not self._wait_phase(LIMIT_DURATION_SEC):
                break

            print(f"Cycle phase: normal speed for {RESUME_DURATION_SEC:.0f}s...")
            self.stop_limiting()
            if not self._wait_phase(RESUME_DURATION_SEC):
                break

        self.stop_limiting()

    def start_cycle(self):
        with self.state_lock:
            if self.cycle_active:
                return
            self.cycle_active = True

        self.cycle_thread = threading.Thread(target=self._cycle_loop, daemon=True)
        self.cycle_thread.start()

    def stop_cycle(self):
        with self.state_lock:
            if not self.cycle_active:
                return
            self.cycle_active = False

        self.stop_limiting()
        if self.cycle_thread and self.cycle_thread.is_alive():
            self.cycle_thread.join(timeout=2.0)
        self.cycle_thread = None
        print("Download cycle stopped.")

    def toggle(self):
        with self.state_lock:
            should_start = not self.cycle_active
        if should_start:
            self.start_cycle()
        else:
            self.stop_cycle()

    def shutdown(self):
        if self.app_stopping:
            return
        self.app_stopping = True
        self.stop_cycle()
        if self.endpoint_thread:
            self.endpoint_thread.join(timeout=1.0)
        if self.stats_thread:
            self.stats_thread.join(timeout=1.0)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Limit download speed for a Windows process by PID."
    )
    parser.add_argument("pid", type=int, nargs="?", help="Process ID to limit")
    parser.add_argument(
        "rate",
        nargs="?",
        help="Download speed cap, e.g. 512 KB, 5 MB, 1.5 GB",
    )
    parser.add_argument("--pid", dest="pid_flag", type=int, help="Process ID to limit")
    parser.add_argument(
        "--rate",
        dest="rate_flag",
        help="Download speed cap, e.g. '512 KB', '5 MB', '1.5 GB'",
    )
    return parser


def resolve_args(args: argparse.Namespace) -> tuple[int, str]:
    pid = args.pid_flag if args.pid_flag is not None else args.pid
    rate = args.rate_flag if args.rate_flag is not None else args.rate
    if pid is None or rate is None:
        raise SystemExit("Usage: python limit_download.py <pid> <rate>  OR  --pid PID --rate '5 MB'")
    return pid, rate


def run_controlled_mode(pid: int, rate_bytes_per_sec: int):
    limiter = ProcessDownloadLimiter(pid, rate_bytes_per_sec)
    exit_event = threading.Event()

    print(f"Controlled subroutine: PID {pid}, cap {format_rate(rate_bytes_per_sec)}")
    print(
        f"Cycle: limit {LIMIT_DURATION_SEC:.0f}s, normal {RESUME_DURATION_SEC:.0f}s, repeat"
    )
    print("Listening for stdin commands: toggle, exit")

    try:
        for line in sys.stdin:
            cmd = line.strip().lower()
            if cmd == "toggle":
                limiter.toggle()
            elif cmd == "exit":
                limiter.shutdown()
                break
    finally:
        limiter.shutdown()
        print("Exited.")


def main():
    if sys.platform != "win32":
        raise SystemExit("This script only supports Windows.")

    if not is_admin():
        print("Warning: Administrator privileges are required for global packet capture.")
        print("Restart your terminal as Administrator if limiting does not work.")

    parser = build_arg_parser()
    parser.add_argument(
        "--controlled",
        action="store_true",
        help="Run without keyboard hooks; receive toggle/exit commands on stdin.",
    )
    args = parser.parse_args()
    pid, rate_text = resolve_args(args)
    rate_bytes_per_sec = parse_rate(rate_text)

    if args.controlled:
        run_controlled_mode(pid, rate_bytes_per_sec)
        return

    limiter = ProcessDownloadLimiter(pid, rate_bytes_per_sec)

    print(f"Press {TOGGLE_KEY} to toggle the download limit cycle (starts OFF).")
    print(
        f"Cycle pattern: limit {LIMIT_DURATION_SEC:.0f}s, "
        f"normal {RESUME_DURATION_SEC:.0f}s, repeat."
    )
    print(f"Press {EXIT_HOTKEY} to exit.")

    exit_event = threading.Event()

    def request_exit():
        limiter.shutdown()
        exit_event.set()

    keyboard.add_hotkey(TOGGLE_KEY, limiter.toggle, suppress=False, trigger_on_release=False)
    keyboard.add_hotkey(EXIT_HOTKEY, request_exit, suppress=False, trigger_on_release=False)

    try:
        exit_event.wait()
    except KeyboardInterrupt:
        limiter.shutdown()
    finally:
        keyboard.unhook_all_hotkeys()
        limiter.shutdown()
        print("Exited.")


if __name__ == "__main__":
    main()

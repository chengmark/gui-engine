import sys


def _get_endpoint_volume():
    try:
        from pycaw.pycaw import AudioUtilities
    except ImportError as exc:
        raise RuntimeError(
            "Volume control requires pycaw and comtypes. Install with: pip install pycaw comtypes"
        ) from exc

    device = AudioUtilities.GetSpeakers()
    volume = getattr(device, "EndpointVolume", None)
    if volume is not None:
        return volume

    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import IAudioEndpointVolume

    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_master_volume() -> float:
    """Return system master volume scalar 0.0 to 1.0. Windows only."""
    if sys.platform != "win32":
        raise OSError("Volume control is only supported on Windows.")

    volume = _get_endpoint_volume()
    return float(volume.GetMasterVolumeLevelScalar())


def set_master_volume(level: float) -> None:
    """Set system master volume. level: 0.0 (mute) to 1.0 (max). Windows only."""
    level = max(0.0, min(1.0, float(level)))
    if sys.platform != "win32":
        raise OSError("SetVolume is only supported on Windows.")

    volume = _get_endpoint_volume()
    volume.SetMasterVolumeLevelScalar(level, None)

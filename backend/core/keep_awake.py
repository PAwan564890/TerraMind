"""Stops Windows from idle-sleeping while a long job runs.

A training run that sleeps mid-way is not lost, but it stalls for as long as
the machine sleeps: one 15-minute run in this project took 12 hours that way.

This asks the operating system not to idle-sleep while THIS process is alive,
the same request a video player makes. It changes no power setting, ends when
the process exits, and does nothing on other platforms.

The display is kept on as well, on purpose. Laptops with Modern Standby enter
standby as soon as the screen turns off, and a request that only says "the
system is needed" did not prevent that here: training still stalled for up to
an hour at a time. Keeping the display on does.

What this cannot prevent: closing the lid, pressing the power button, or
choosing Sleep. For a long run, leave the lid open and the charger connected.
"""

import ctypes
import logging
import sys

log = logging.getLogger(__name__)

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


def keep_awake() -> bool:
    """Request no idle sleep for the life of this process. True if it took effect."""
    if sys.platform != "win32":
        return False
    try:
        result = ctypes.windll.kernel32.SetThreadExecutionState(
            _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
        )
    except (AttributeError, OSError):
        return False
    if result == 0:
        return False
    log.info("idle sleep and display-off are held off while this process runs")
    return True

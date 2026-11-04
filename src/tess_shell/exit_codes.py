"""Process exit codes (Shell Start and Stop, Exit Codes). Leaf module: standard library only."""

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    CONFIG = 1
    ENVIRONMENT = 2
    ALREADY_RUNNING = 4
    INTERNAL = 70
    FORCED = 130

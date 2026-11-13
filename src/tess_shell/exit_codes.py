"""Process exit codes (Shell Start and Stop, Exit Codes). Leaf module: standard library only."""

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    CONFIG = 1
    ENVIRONMENT = 2
    NOT_RUNNING = 3  # a control command found no shell: the bus name has no owner
    ALREADY_RUNNING = 4
    TIMEOUT = 5  # a control command timed out
    INTERNAL = 70
    FORCED = 130


class ShellError(Exception):
    """A failure that ends the process with ``exit_code`` and a one line message."""

    exit_code: ExitCode = ExitCode.INTERNAL


class EnvironmentFailure(ShellError):
    """The machine cannot run the shell (no compositor, bad runtime directory, ...)."""

    exit_code = ExitCode.ENVIRONMENT


class AlreadyRunning(ShellError):
    exit_code = ExitCode.ALREADY_RUNNING

    def __init__(self, pid: int | None) -> None:
        self.pid = pid
        who = f" (pid {pid})" if pid is not None else ""
        super().__init__(f"another tesserae-shell is already running{who}")

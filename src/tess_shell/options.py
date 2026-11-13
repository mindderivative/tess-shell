"""Global command line options shared by every subcommand."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Options:
    config_dir: Path | None = None
    json: bool = False
    quiet: bool = False
    timeout: float = 5.0  # seconds a control command waits for the shell

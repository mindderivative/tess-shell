import json
import re
import stat
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from loguru import logger

from tess_shell.config.settings import LoggingSettings
from tess_shell.logging import (
    apply_retention,
    configure_logging,
    log_finding,
    log_path,
    seconds_until_midnight,
    shutdown_logging,
    swap_file_sink,
)
from tess_shell.schema.findings import Finding


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    yield
    shutdown_logging()


def today_file(directory: Path) -> Path:
    return log_path(directory, datetime.now())


def test_line_shape_and_default_source(tmp_path: Path) -> None:
    configure_logging(LoggingSettings(console=False), default_directory=tmp_path / "logs")
    logger.info("hello")
    shutdown_logging()
    (line,) = today_file(tmp_path / "logs").read_text().splitlines()
    assert re.fullmatch(
        r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} \| INFO     \| shell \| - \| hello", line
    )


def test_level_filter_and_bound_source(tmp_path: Path) -> None:
    configure_logging(LoggingSettings(level="WARNING", console=False), default_directory=tmp_path)
    logger.info("dropped")
    logger.bind(source="module:Clock").warning("kept")
    shutdown_logging()
    text = today_file(tmp_path).read_text()
    assert "dropped" not in text and "| module:Clock | - | kept" in text


def test_modes(tmp_path: Path) -> None:
    configure_logging(LoggingSettings(console=False), default_directory=tmp_path / "logs")
    shutdown_logging()
    assert stat.S_IMODE((tmp_path / "logs").stat().st_mode) == 0o700
    assert stat.S_IMODE(today_file(tmp_path / "logs").stat().st_mode) == 0o600


def test_json_format_carries_finding_fields(tmp_path: Path) -> None:
    configure_logging(LoggingSettings(format="JSON", console=False), default_directory=tmp_path)
    log_finding(Finding("a.tdl", 3, 4, "error", "unknown-key", "bad key"))
    shutdown_logging()
    record = json.loads(today_file(tmp_path).read_text().splitlines()[0])["record"]
    assert record["level"]["name"] == "ERROR"
    assert record["extra"]["rule"] == "unknown-key"
    assert record["extra"]["location"] == "a.tdl:3:4 unknown-key"


def test_quiet_console_shows_warnings_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(LoggingSettings(), quiet=True, default_directory=tmp_path)
    logger.info("chatter")
    logger.warning("careful")
    shutdown_logging()
    err = capsys.readouterr().err
    assert "careful" in err and "chatter" not in err


def test_unusable_directory_falls_back_to_console(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    state = configure_logging(LoggingSettings(console=False), default_directory=blocker / "logs")
    logger.info("still here")
    shutdown_logging()
    err = capsys.readouterr().err
    assert state.file_sink is None
    assert str(blocker / "logs") in err and "still here" in err


def test_retention_only_removes_old_log_files(tmp_path: Path) -> None:
    for name in ("log_2020-01-01.log", "log_2026-01-10.log", "notes.txt", "log_2020-01-01.log.bak"):
        (tmp_path / name).write_text("x")
    removed = apply_retention(tmp_path, 30, datetime(2026, 1, 15))
    assert [p.name for p in removed] == ["log_2020-01-01.log"]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "log_2020-01-01.log.bak",
        "log_2026-01-10.log",
        "notes.txt",
    ]


def test_seconds_until_midnight() -> None:
    assert seconds_until_midnight(datetime(2026, 1, 31, 23, 59, 0)) == 60.0
    assert seconds_until_midnight(datetime(2026, 1, 1, 0, 0, 0)) == 86400.0


def test_swap_starts_next_day_file_and_keeps_old_whole(tmp_path: Path) -> None:
    configure_logging(LoggingSettings(console=False), default_directory=tmp_path)
    logger.info("day one")
    swap_file_sink(datetime(2031, 5, 6, 0, 0, 1))
    logger.info("day two")
    shutdown_logging()
    first = today_file(tmp_path).read_text()
    second = (tmp_path / "log_2031-05-06.log").read_text()
    assert "day one" in first and "day two" not in first
    assert "day two" in second

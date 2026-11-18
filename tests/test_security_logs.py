"""No content in logs (Security Model, controls 7 and 8): starting an application logs its id and
never the values of its arguments, on a start that works, a fallback to a plain start and a start
that fails."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from loguru import logger

from tests.launcher_rig import FakeRunner
from tests.test_apps_launch import launched, make_apps

SECRET = "hunter2-not-for-the-log"
EXEC = f"fake-app --password={SECRET} --token {SECRET} --open %U"


@pytest.fixture
def lines() -> Iterator[list[str]]:
    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="DEBUG")
    yield seen
    logger.remove(sink)


@pytest.mark.parametrize(
    ("runner", "worked"),
    [
        (FakeRunner(scope=True), True),  # in a systemd scope
        (FakeRunner(scope=False), True),  # a plain start
        (FakeRunner(scope=True, fail_scope=True), True),  # the scope fails, the plain start works
        (FakeRunner(scope=False, fail_plain=True), False),  # the process cannot be started
    ],
    ids=["scope", "plain", "fallback", "failed"],
)
def test_an_application_start_logs_the_id_and_not_the_argument_values(
    tmp_path: Path, lines: list[str], runner: FakeRunner, worked: bool
) -> None:
    with make_apps(tmp_path, runner, **{"Secret App": {"Exec": EXEC}}) as (apps, loop, _r):
        result = launched(apps, loop, "secret-app.desktop")
    assert result.ok is worked
    if worked:  # the arguments really were passed on: the recorder has them
        assert any(SECRET in part for part in runner.started[-1].argv)
    text = "\n".join(lines)
    assert "secret-app.desktop" in text  # the id is what the log names
    assert SECRET not in text and "--password" not in text and "--token" not in text
    assert SECRET not in result.error


def test_an_announcement_that_reaches_no_window_is_logged_without_its_text(
    lines: list[str],
) -> None:
    """What a module says can be a window title or a track name: the log says that nothing was
    said, not what it was."""
    from tests.test_ctx_announce import Port, context

    private = "Inbox - a private window title"
    ctx, _ = context(None)  # a shell with no surfaces
    ctx.announce(private)
    ctx, _ = context(Port(result=False))  # no use of the module is on an open window
    ctx.announce(private)
    said = [ln for ln in lines if "ctx.announce" in ln]
    assert len(said) == 2 and not [ln for ln in said if "private" in ln or "Inbox" in ln]

"""The application service (Applications Module > The Application Index, Search): the list the
launcher searches, on TEMPORARY ``applications`` folders of made-up entries. Nothing here reads
the user's applications or starts a process: the starter is the recorder of
``tests/launcher_rig.py``."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tess_shell.services.apps import AppService, fold
from tess_shell.services.desktop_entries import ApplicationIndex
from tests.launcher_rig import FakeRunner, Loop, write_entry


def settle(loop: Loop, predicate: Any, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        loop.drain()
        if predicate():
            return True
        if time.monotonic() > deadline:
            return False
        time.sleep(0.005)


@contextmanager
def service(
    folders: Sequence[Path],
    *,
    locale: str = "",
    desktops: Sequence[str] = (),
    counts: Path | None = None,
    runner: FakeRunner | None = None,
    which: Any = lambda p: f"/usr/bin/{p}",
) -> Iterator[tuple[AppService, Loop, FakeRunner]]:
    index = ApplicationIndex(folders=folders, locale=locale, desktops=desktops, which=which)
    loop, runner = Loop(), runner or FakeRunner()
    apps = AppService(index, runner=runner, counts=counts, call_soon=loop.call_soon, env={})
    apps.start()
    try:
        assert settle(loop, lambda: apps.ready)
        yield apps, loop, runner
    finally:
        apps.stop()


def folder_with(tmp_path: Path, entries: Mapping[str, Mapping[str, str]]) -> Path:
    folder = tmp_path / "applications"
    folder.mkdir()
    for name, keys in entries.items():
        write_entry(folder, name, **keys)
    return folder


def names(found: Sequence[Any]) -> list[str]:
    return [a.name for a in found]


# -- the list: which entries ---------------------------------------------------------------------


def test_hidden_nodisplay_other_type_excluded_and_tryexec_missing_entries_are_not_listed(
    tmp_path: Path,
) -> None:
    folder = folder_with(
        tmp_path,
        {
            "Plain": {},
            "Hidden One": {"Hidden": "true"},
            "No Display": {"NoDisplay": "true"},
            "Only Gnome": {"OnlyShowIn": "GNOME;"},
            "Not Here": {"NotShowIn": "KDE;"},
            "Needs Program": {"TryExec": "program-that-is-not-there"},
            "Has Program": {"TryExec": "present"},
        },
    )
    (folder / "a-link.desktop").write_text(
        "[Desktop Entry]\nType=Link\nName=A Link\nURL=https://example.org\n"
    )
    which = lambda p: "/usr/bin/present" if p == "present" else None  # noqa: E731
    with service([folder], desktops=("KDE",), which=which) as (apps, _loop, _runner):
        assert sorted(names(apps.search("", 50))) == ["Has Program", "Plain"]
        assert apps.get("plain") is not None and apps.get("hidden-one") is None
        assert apps.get("a-link") is None


def test_an_entry_of_the_users_folder_hides_the_same_id_in_a_system_folder(tmp_path: Path) -> None:
    user, system = tmp_path / "user", tmp_path / "system"
    write_entry(system, "Editor", Comment="the system's")
    write_entry(system, "Viewer")
    write_entry(user, "Editor", Comment="the user's")
    write_entry(user, "Viewer", Hidden="true")  # how a user deletes an entry the system ships
    with service([user, system]) as (apps, _loop, _runner):
        found = apps.search("", 10)
        assert names(found) == ["Editor"] and found[0].comment == "the user's"


def test_a_localised_name_is_used_for_the_matching_locale_and_the_plain_name_otherwise(
    tmp_path: Path,
) -> None:
    folder = folder_with(tmp_path, {"Web Browser": {"Name[de]": "Netzleser"}})
    with service([folder], locale="de_DE.UTF-8") as (apps, _loop, _runner):
        assert names(apps.search("leser")) == ["Netzleser"]
        assert apps.search("browser") == []  # the German name is the one the user sees
    with service([folder], locale="fr_FR.UTF-8") as (apps, _loop, _runner):
        assert names(apps.search("browser")) == ["Web Browser"]
        assert apps.search("leser") == []


# -- search --------------------------------------------------------------------------------------


def test_the_five_rank_levels_order_the_results_as_the_table_says(tmp_path: Path) -> None:
    folder = folder_with(
        tmp_path,
        {
            # 5: anywhere in the comment ("splinter")
            "Aardvark": {"Comment": "Removes a splinter"},
            # 5: anywhere in a keyword
            "Badger": {"Keywords": "winter;"},
            # 4: the start of a word of the generic name
            "Cobra": {"GenericName": "Remote Terminal"},
            # 4: the start of a keyword
            "Dingo": {"Keywords": "terminal;shell;"},
            # 3: anywhere in the name
            "Xterm": {},
            "Alterego": {},
            # 2: the start of a word of the name
            "Gnome Terminal": {},
            # 1: the start of the name
            "Terminal": {},
            "Terrace": {},
        },
    )
    with service([folder]) as (apps, _loop, _runner):
        assert names(apps.search("ter", 20)) == [
            "Terminal",  # 1, then by name
            "Terrace",
            "Gnome Terminal",  # 2
            "Alterego",  # 3, by name
            "Xterm",
            "Cobra",  # 4, by name
            "Dingo",
            "Aardvark",  # 5, by name
            "Badger",
        ]


def test_every_word_of_the_query_must_match_and_case_and_accents_do_not_matter(
    tmp_path: Path,
) -> None:
    folder = folder_with(
        tmp_path,
        {
            "Écran Capture": {"Comment": "Takes pictures"},
            "Screen Ruler": {},
            "Zoomer": {"Keywords": "ecran;"},
        },
    )
    with service([folder]) as (apps, _loop, _runner):
        assert names(apps.search("ECRAN")) == ["Écran Capture", "Zoomer"]
        assert names(apps.search("ecran pict")) == ["Écran Capture"]
        assert apps.search("ecran ruler") == []  # one word matches nothing of Écran Capture
        assert names(apps.search("  screen   ruler ")) == ["Screen Ruler"]
        assert fold("Écran ÀÉÎ") == "ecran aei"


def test_the_most_started_wins_a_tie_and_an_empty_query_lists_the_most_started_first(
    tmp_path: Path,
) -> None:
    run = {"Exec": "fake-app"}
    folder = folder_with(
        tmp_path,
        {"Alpha Editor": run, "Beta Editor": run, "Gamma Editor": run, "Delta": run},
    )
    counts = tmp_path / "counts.json"
    with service([folder], counts=counts) as (apps, loop, runner):
        assert names(apps.search("editor")) == ["Alpha Editor", "Beta Editor", "Gamma Editor"]
        assert names(apps.search("")) == ["Alpha Editor", "Beta Editor", "Delta", "Gamma Editor"]
        results: list[Any] = []
        for entry in ("gamma-editor", "gamma-editor", "delta"):
            apps.launch(f"{entry}.desktop", None, results.append)
        assert settle(loop, lambda: len(results) == 3)
        assert all(r.ok for r in results), results
        assert len(runner.started) == 3
        assert names(apps.search("editor")) == ["Gamma Editor", "Alpha Editor", "Beta Editor"]
        assert names(apps.search("")) == ["Gamma Editor", "Delta", "Alpha Editor", "Beta Editor"]
        assert names(apps.search("", 2)) == ["Gamma Editor", "Delta"]  # at most `limit`
        assert apps.search("", 0) == []
    # the count was written to the file and a later service reads it
    assert json.loads(counts.read_text()) == {"delta.desktop": 1, "gamma-editor.desktop": 2}
    with service([folder], counts=counts) as (again, _loop, _runner):
        assert names(again.search("", 1)) == ["Gamma Editor"]


def test_a_count_file_is_replaced_whole_a_broken_one_counts_anew_and_an_unwritable_one_warns_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from loguru import logger

    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(str(m)), level="WARNING")
    try:
        folder = folder_with(tmp_path, {"One": {"Exec": "fake-app"}, "Two": {"Exec": "fake-app"}})
        broken = tmp_path / "broken.json"
        broken.write_text("{ not json")
        with service([folder], counts=broken) as (apps, loop, _runner):
            assert any("not readable" in line for line in seen)
            done: list[Any] = []
            apps.launch("one.desktop", None, done.append)
            assert settle(loop, lambda: done)
        assert json.loads(broken.read_text()) == {"one.desktop": 1}
        assert not list(tmp_path.glob("*.tmp"))  # the temporary file was renamed over it
        # a count file that is a folder cannot be written: one warning, the counts stay in memory
        seen.clear()
        blocked = tmp_path / "blocked.json"
        blocked.mkdir()
        with service([folder], counts=blocked) as (apps, loop, _runner):
            done = []
            for entry in ("one.desktop", "two.desktop", "one.desktop"):
                apps.launch(entry, None, done.append)
            assert settle(loop, lambda: len(done) == 3)
            assert names(apps.search("")) == ["One", "Two"]  # ranked by the counts in memory
            assert apps.count("one.desktop") == 2
        assert sum("cannot write" in line for line in seen) == 1
    finally:
        logger.remove(sink)


# -- following the folders -----------------------------------------------------------------------


def test_adding_and_removing_an_entry_file_changes_the_list_without_a_restart(
    tmp_path: Path,
) -> None:
    folder = folder_with(tmp_path, {"First": {}})
    with service([folder]) as (apps, loop, _runner):
        apps.index.watch(debounce=0.05)
        try:
            assert apps.watching
            heard: list[int] = []
            apps.on_changed(lambda: heard.append(1))
            assert names(apps.search("")) == ["First"]
            added = write_entry(folder, "Second")
            assert settle(loop, lambda: names(apps.search("")) == ["First", "Second"])
            assert settle(loop, lambda: bool(heard))  # the callback comes after the list
            added.unlink()
            assert settle(loop, lambda: names(apps.search("")) == ["First"])
        finally:
            apps.index.unwatch()


def test_no_folder_gives_an_empty_list_and_a_service_that_is_not_started_is_not_ready(
    tmp_path: Path,
) -> None:
    index = ApplicationIndex(folders=[tmp_path / "missing"], locale="", desktops=())
    apps = AppService(index, runner=FakeRunner(), call_soon=Loop().call_soon, env={})
    assert not apps.ready and apps.search("anything") == []
    with service([tmp_path / "missing"]) as (apps, _loop, _runner):
        assert apps.ready and apps.search("") == []


def test_one_search_over_500_entries_is_far_inside_its_budget_and_the_build_is_off_the_loop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Applications Module > Performance Budget: the build of 500 entries (150 ms) runs on the
    worker, a search (2 ms) on the loop. The bounds here are ten times the budget: the machine that
    runs the suite is not the one the budget is for; the measurement is printed."""
    folder = tmp_path / "applications"
    for n in range(500):
        write_entry(
            folder,
            f"Application number {n}",
            GenericName="Generic name",
            Comment=f"Does thing {n} well",
            Keywords="one;two;three;",
            Exec="fake-app",
        )
    index = ApplicationIndex(folders=[folder], locale="", desktops=())
    loop = Loop()
    apps = AppService(index, runner=FakeRunner(), call_soon=loop.call_soon, env={})
    started = time.perf_counter()
    apps.start()
    assert time.perf_counter() - started < 0.05  # start() only hands the work to the worker
    assert settle(loop, lambda: apps.ready, 30)
    build_ms = apps.stats.build_ms[-1]
    started = time.perf_counter()
    found: list[Any] = []
    for _ in range(50):
        found = apps.search("number 4 well", 8)
    search_ms = (time.perf_counter() - started) / 50 * 1000
    apps.stop()
    with capsys.disabled():
        print(f"\n500 entries: build {build_ms:.0f} ms (worker), one search {search_ms:.2f} ms")
    assert len(found) == 8
    assert build_ms < 1500 and search_ms < 20

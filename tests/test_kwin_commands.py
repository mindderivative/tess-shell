"""``tesserae-shell kwin script`` and ``kwin rule`` (IPC and CLI > The Command Line; KWin
Integration > Loading the script, Window rules). Every file is a temporary copy: the rule file,
``kwinrc`` and the scripts folder are named with ``--rules-file``, ``--kwinrc`` and
``--scripts-dir``, and the bus is a private one with a fake KWin. The real ``kwinrulesrc`` is never
read or written."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tess_shell import cli
from tess_shell.services.kwin_package import (
    PACKAGE_ID,
    RULE_ID,
    RefusedInTest,
    ini_get,
    ini_group,
    ini_remove_group,
    ini_set,
    install_package,
    refuse_real_path,
    rule_group,
    rule_ids,
    rule_installed,
    with_rule,
    without_rule,
)
from tests.fake_dbus import HAVE_DAEMON, fake_bus, wait_for
from tests.fake_kwin import FakeKWin, Loaded

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

# what System Settings writes for two rules of the user's own (the shell must never touch them)
USER = """\
[General]
count=2
rules=aaaa-1111,bbbb-2222

[aaaa-1111]
Description=Chrome on desktop 2
desktops=desktop-2
desktopsrule=2
wmclass=google-chrome
wmclassmatch=1

# a comment the user wrote
[bbbb-2222]
Description=Terminal without a border
noborder=true
noborderrule=2
wmclass=konsole
"""


# -- the file editing: one group, nothing else -------------------------------------------------


def test_the_group_the_shell_writes_is_what_show_prints() -> None:
    group = rule_group()
    assert group.startswith(f"[{RULE_ID}]\n") and "layer=4\n" in group and "layerrule=2\n" in group
    assert "wmclass=tesserae-shell.\n" in group and "wmclassmatch=2\n" in group


def test_install_adds_one_group_and_its_id_and_changes_nothing_else() -> None:
    after = with_rule(USER)
    assert rule_installed(after) and rule_ids(after) == ["aaaa-1111", "bbbb-2222", RULE_ID]
    assert ini_get(after, "General", "count") == "3"
    for group in ("aaaa-1111", "bbbb-2222"):
        assert ini_group(after, group) == ini_group(USER, group)  # every user group, as it was
    assert ini_group(after, RULE_ID) == rule_group()
    assert "# a comment the user wrote" in after  # a comment is kept
    assert with_rule(after) == after  # installing again changes nothing


def test_remove_restores_the_earlier_content_of_every_other_group() -> None:
    assert without_rule(with_rule(USER)) == USER


@pytest.mark.parametrize(
    "original",
    [
        "",  # no file
        "[General]\ncount=0\nrules=\n",  # an empty book
        "[General]\ncount=1\nrules=x\n\n[x]\nDescription=x",  # no newline at the end
        "[Other]\nkey=value\n",  # no [General] at all
        USER,
        USER + "\n\n\n",
    ],
)
def test_install_then_remove_leaves_every_other_line_where_it_was(original: str) -> None:
    after = without_rule(with_rule(original))
    assert rule_ids(after) == rule_ids(original)
    assert ini_group(after, RULE_ID) is None
    for name in ("aaaa-1111", "bbbb-2222", "x", "Other"):
        assert ini_group(after, name) == ini_group(original, name)


def test_a_group_with_a_similar_name_is_never_touched() -> None:
    text = f"[{RULE_ID}-mine]\nDescription=mine\n\n[General]\ncount=1\nrules={RULE_ID}-mine\n"
    after = without_rule(with_rule(text))
    mine = f"[{RULE_ID}-mine]\nDescription=mine\n"
    assert ini_group(after, f"{RULE_ID}-mine") == mine
    assert rule_ids(after) == [f"{RULE_ID}-mine"]


def test_ini_helpers_keep_unrelated_lines() -> None:
    text = "[A]\nx=1\n\n[B]\ny=2\n"
    assert ini_set(text, "A", "z", "3") == "[A]\nx=1\nz=3\n\n[B]\ny=2\n"
    assert ini_set(text, "A", "x", "9") == "[A]\nx=9\n\n[B]\ny=2\n"
    assert ini_set(text, "C", "k", "v") == text + "\n[C]\nk=v\n"
    assert ini_remove_group(text, "A") == "[B]\ny=2\n"
    assert ini_get(text, "B", "y") == "2" and ini_get(text, "B", "nope") is None


# -- the guards --------------------------------------------------------------------------------


def test_a_path_under_the_real_home_is_refused_in_a_test(tmp_path: Path) -> None:
    refuse_real_path(tmp_path / "kwinrulesrc", "x")  # a temporary one is fine
    with pytest.raises(RefusedInTest):
        refuse_real_path(Path.home() / ".config" / "kwinrulesrc", "x")
    with pytest.raises(RefusedInTest):
        refuse_real_path(Path("~/.config/kwinrulesrc"), "x")


def test_the_commands_refuse_the_real_files_and_write_nothing_there(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real ``kwinrulesrc`` is never named by a test; a path under the real home that does not
    exist stands for it, and it must still not be made."""
    ghost = Path.home() / ".tess-shell-never-made" / "kwinrulesrc"
    try:
        for argv in (
            ["kwin", "rule", "install", "--yes", "--rules-file", str(ghost)],
            ["kwin", "rule", "remove", "--rules-file", str(ghost)],
            ["kwin", "script", "install", "--kwinrc", str(ghost), "--no-reload"],
            ["kwin", "script", "remove", "--scripts-dir", str(ghost.parent), "--no-reload"],
        ):
            assert cli.main(argv) == 1, argv
            assert "this process is a test" in capsys.readouterr().err
        assert not ghost.parent.exists()
    finally:
        if ghost.parent.exists():  # a guard that failed: do not leave it behind
            import shutil

            shutil.rmtree(ghost.parent)


def test_rule_show_only_reads_so_it_may_name_any_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules = tmp_path / "kwinrulesrc"
    assert cli.main(["kwin", "rule", "show", "--rules-file", str(rules)]) == 0
    out = capsys.readouterr().out
    assert "not installed" in out and rule_group() in out and not rules.exists()
    rules.write_text(with_rule(USER))
    assert cli.main(["kwin", "rule", "show", "--rules-file", str(rules), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["installed"] is True and data["group"] == rule_group() and data["id"] == RULE_ID


# -- the rule commands on a temporary copy -----------------------------------------------------


def test_rule_install_asks_and_writes_one_group_then_remove_restores_the_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = tmp_path / "kwinrulesrc"
    rules.write_text(USER)
    # no terminal and no --yes: it will not write
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert cli.main(["kwin", "rule", "install", "--rules-file", str(rules), "--no-reload"]) == 1
    assert "--yes" in capsys.readouterr().err and rules.read_text() == USER
    # a terminal, and the user says no
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert cli.main(["kwin", "rule", "install", "--rules-file", str(rules), "--no-reload"]) == 1
    assert rules.read_text() == USER
    # and says yes
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert cli.main(["kwin", "rule", "install", "--rules-file", str(rules), "--no-reload"]) == 0
    assert rule_installed(rules.read_text()) and "written" in capsys.readouterr().out
    assert cli.main(["kwin", "rule", "install", "--yes", "--rules-file", str(rules)]) == 0
    assert "already" in capsys.readouterr().out  # installing twice is one group
    assert rules.read_text().count(f"[{RULE_ID}]") == 1
    assert cli.main(["kwin", "rule", "remove", "--rules-file", str(rules), "--no-reload"]) == 0
    assert rules.read_text() == USER  # exactly as it was
    assert cli.main(["kwin", "rule", "remove", "--rules-file", str(rules), "--no-reload"]) == 0
    assert "nothing to remove" in capsys.readouterr().out.splitlines()[-1]


def test_a_new_rule_file_is_made_when_there_is_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rules = tmp_path / "config" / "kwinrulesrc"
    args = ["kwin", "rule", "install", "--yes", "--no-reload", "--rules-file", str(rules)]
    assert cli.main(args) == 0
    text = rules.read_text()
    assert ini_get(text, "General", "rules") == RULE_ID and ini_get(text, "General", "count") == "1"


@needs_daemon
def test_install_asks_kwin_to_reload_and_a_kwin_that_is_not_there_puts_the_file_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = tmp_path / "kwinrulesrc"
    rules.write_text(USER)
    with fake_bus() as bus:
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", bus.address)
        args = ["kwin", "rule", "install", "--yes", "--rules-file", str(rules)]
        # no KWin on the bus: the write is undone and the cause is said
        assert cli.main(args) != 0
        err = capsys.readouterr().err
        assert "org.kde.KWin is not on the session bus" in err and "left as it was" in err
        assert rules.read_text() == USER
        # KWin is there: written, and asked to reconfigure
        fake = FakeKWin(bus)
        fake.up()
        try:
            assert cli.main(args) == 0
            assert rule_installed(rules.read_text())
            assert wait_for(lambda: fake.names("reconfigure") == [()])
            assert cli.main(["kwin", "rule", "remove", "--rules-file", str(rules)]) == 0
            assert rules.read_text() == USER
            assert wait_for(lambda: len(fake.names("reconfigure")) == 2)
        finally:
            fake.close()


# -- the script commands on temporary folders --------------------------------------------------


@needs_daemon
def test_script_install_copies_the_package_enables_it_and_asks_kwin_and_remove_undoes_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts, kwinrc = tmp_path / "data" / "kwin" / "scripts", tmp_path / "kwinrc"
    kwinrc.write_text("[Plugins]\nkzonesEnabled=true\n\n[Windows]\nFocusPolicy=1\n")
    flags = ["--scripts-dir", str(scripts), "--kwinrc", str(kwinrc)]
    with fake_bus() as bus:
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", bus.address)
        fake = FakeKWin(bus)
        fake.up()
        try:
            assert cli.main(["kwin", "script", "install", *flags]) == 0
            assert (scripts / PACKAGE_ID / "metadata.json").is_file()
            assert (scripts / PACKAGE_ID / "contents" / "code" / "main.js").is_file()
            text = kwinrc.read_text()
            assert ini_get(text, "Plugins", f"{PACKAGE_ID}Enabled") == "true"
            assert ini_get(text, "Plugins", "kzonesEnabled") == "true"  # another script: kept
            assert ini_get(text, "Windows", "FocusPolicy") == "1"
            assert wait_for(lambda: fake.names("reconfigure") == [()])
            capsys.readouterr()
            # status: the package, the switch, KWin's version, and whether KWin has it loaded
            assert cli.main(["kwin", "script", "status", *flags, "--json"]) == 0
            status = json.loads(capsys.readouterr().out)
            assert status["installed"] and status["enabled"] and status["reachable"]
            assert status["kwin"] == "6.8.2" and status["loaded"] is False
            fake.scripts[PACKAGE_ID] = Loaded(PACKAGE_ID, "x", "")
            assert cli.main(["kwin", "script", "status", *flags]) == 0
            out = capsys.readouterr().out
            assert "installed at" in out and "KWin 6.8.2" in out
            assert "loaded in KWin now: yes" in out
            # remove: the files, the switch, the running script and one reload
            assert cli.main(["kwin", "script", "remove", *flags]) == 0
            assert not (scripts / PACKAGE_ID).exists()
            assert ini_get(kwinrc.read_text(), "Plugins", f"{PACKAGE_ID}Enabled") is None
            assert ini_get(kwinrc.read_text(), "Plugins", "kzonesEnabled") == "true"
            assert fake.names("unloadScript") == [(PACKAGE_ID,)]
        finally:
            fake.close()


@needs_daemon
def test_script_status_with_no_kwin_reports_it_and_still_answers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    with fake_bus() as bus:
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", bus.address)
        flags = ["--scripts-dir", str(tmp_path / "s"), "--kwinrc", str(tmp_path / "kwinrc")]
        assert cli.main(["kwin", "script", "status", *flags]) == 0
        out = capsys.readouterr().out
        assert "not installed" in out and "enabled in kwinrc" in out and "KWin: not reached" in out


def test_a_test_never_reaches_a_bus_that_is_not_private(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")  # the real one
    flags = ["--scripts-dir", str(tmp_path / "s"), "--kwinrc", str(tmp_path / "kwinrc")]
    assert cli.main(["kwin", "script", "status", *flags, "--json"]) == 0  # reported, not reached
    data = json.loads(capsys.readouterr().out)
    assert data["reachable"] is False and "not a private one" in data["error"]
    rules = tmp_path / "kwinrulesrc"
    args = ["kwin", "rule", "install", "--yes", "--rules-file", str(rules)]
    assert cli.main(args) == 1  # the reload would reach it: refused, and the file is put back
    assert not rules.exists() or rules.read_text() == ""


def test_the_packages_files_survive_a_second_install(tmp_path: Path) -> None:
    first = install_package(tmp_path / "scripts")
    (first / "stale.txt").write_text("left over")
    second = install_package(tmp_path / "scripts")
    assert second == first and not (second / "stale.txt").exists()
    assert (second / "contents" / "code" / "main.js").is_file()

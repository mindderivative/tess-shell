"""The recorded command outputs of ``tests/fixtures/cli/`` still equal what the commands print."""

import json

import pytest

from tests.cli_fixtures import FIXTURES, RECORDED, available


@pytest.mark.parametrize("name", sorted(RECORDED))
def test_the_fixture_equals_what_the_command_prints(name: str) -> None:
    if name.startswith("status_") and not available():
        pytest.skip("sway and dbus-daemon record the status fixtures")
    recorded = (FIXTURES / name).read_text(encoding="utf-8")
    assert recorded == RECORDED[name](), (
        f"{name} is stale: run `env -u WAYLAND_DISPLAY -u DISPLAY python -m tests.cli_fixtures`"
    )


def test_every_json_fixture_on_disk_is_recorded() -> None:
    on_disk = {p.name for p in FIXTURES.glob("*.json")}
    assert on_disk == set(RECORDED)


def test_the_findings_fixture_has_a_located_finding_and_the_clean_one_none() -> None:
    clean = json.loads((FIXTURES / "check_clean.json").read_text())
    findings = json.loads((FIXTURES / "check_findings.json").read_text())
    assert clean["ok"] is True and clean["errors"] == [] and clean["config_dir"] == "<config_dir>"
    assert findings["ok"] is False
    (error,) = findings["errors"]
    assert (error["file"], error["line"]) == ("Shells/Foo_Shell.tdl", 5)


def test_version_and_check_json_name_the_folder_they_are_about(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from tests.cli_fixtures import run

    for argv in (("version", "--json"), ("check", "--json")):
        _, out = run(*argv, "--config-dir", str(tmp_path))
        assert json.loads(out)["config_dir"] == str(tmp_path)


def test_the_status_fixtures_show_what_a_tool_has_to_handle() -> None:
    running = json.loads((FIXTURES / "status_running.json").read_text())
    assert running["state"] == "running"
    assert set(running) == {
        "state",
        "api_version",
        "version",
        "monitors",
        "surfaces",
        "modules",
        "errors",
    }
    assert {s["name"]: s["kind"] for s in running["surfaces"]} == {
        "Launcher": "panel",
        "Top_Bar": "bar",
    }
    assert running["modules"] == ["Clock"]
    assert running["version"]["shell"] == "<shell>"
    assert "/home" not in json.dumps(running) and "/tmp" not in json.dumps(running)
    gone = json.loads((FIXTURES / "status_not_running.json").read_text())
    assert gone["ok"] is False and gone["exit"] == 3 and "no shell is running" in gone["error"]

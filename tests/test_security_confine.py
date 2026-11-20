"""A path a file writes may not leave the configured folders (Security Model, control 3): ``..`` and
symbolic links are resolved first, the error carries ``file:line:column``, the package's own files
are the one exception, and every kind of path-valued key goes through the same check."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tess_shell.cli import main
from tess_shell.config.confine import Confinement, PathOutsideConfig
from tess_shell.config.discovery import shipped_dir
from tests.test_module_import import HEAD, LABEL, check, module, rules, shell


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    """A configuration folder with a real file outside it, ``tmp_path/outside/Out_Module.tdl``."""
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "Out_Module.tdl").write_text(HEAD.format(name="Out") + LABEL)
    (tmp_path / "outside" / "Out_Module.py").write_text(
        "from tess_shell import Module\n\nclass O(Module):\n    pass\n"
    )
    (tmp_path / "outside" / "pic.png").write_bytes(b"not really a png")
    (tmp_path / "outside" / "dot.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    (tmp_path / "cfg").mkdir()
    return tmp_path / "cfg"


def errors(report: dict[str, object]) -> list[dict[str, Any]]:
    found = report["errors"]
    assert isinstance(found, list)
    return found


def position(path: Path, needle: str) -> tuple[int, int]:
    for number, text in enumerate(path.read_text().splitlines(), 1):
        if needle in text:
            return number, text.index(needle) + 1
    raise AssertionError(needle)


def test_an_import_that_climbs_out_by_dotdot_is_refused_with_its_position(
    cfg: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module(cfg, "Label", LABEL)
    path = shell(cfg, "Import: ../../outside/Out_Module.tdl")
    code, report = check(cfg, capsys)
    assert code == 1 and rules(report) == ["path-outside-config"]
    (error,) = errors(report)
    line, column = position(path, "../../outside")
    assert (error["file"], error["line"], error["column"]) == (
        "Shells/Main_Shell.tdl",
        line,
        column,
    )
    assert "../../outside/Out_Module.tdl" in error["message"]


def test_an_import_through_a_symbolic_link_to_another_folder_is_refused(
    cfg: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # the written path stays inside the configuration folder; only the link takes it out
    (cfg / "Modules").mkdir()
    (cfg / "Modules" / "Elsewhere").symlink_to(cfg.parent / "outside", target_is_directory=True)
    shell(cfg, "Import: ../Modules/Elsewhere/Out_Module.tdl")
    code, report = check(cfg, capsys)
    assert code == 1 and rules(report) == ["path-outside-config"]
    (error,) = errors(report)
    assert str(cfg.parent / "outside") in error["message"]  # says where the link really goes


def test_a_link_that_stays_inside_and_a_folder_added_by_directories_are_fine(
    cfg: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module(cfg, "Label", LABEL)
    (cfg / "Modules" / "Same").symlink_to(cfg / "Modules" / "Label", target_is_directory=True)
    shell(cfg, "Import: ../Modules/Same/Label_Module.tdl")
    assert check(cfg, capsys)[0] == 0
    # a folder the settings add is a configured folder: its files may be named
    extra = cfg.parent / "outside"
    (cfg / "settings.tdl").write_text(
        HEAD.format(name="S") + f'Settings {{ Directories {{ Modules: "{extra}" }} }}\n'
    )
    shell(cfg, "Import: ../../outside/Out_Module.tdl")
    code, report = check(cfg, capsys)
    assert code == 0, report


def test_every_path_valued_key_goes_through_the_same_check(
    cfg: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Bitmap's and an SVG's ``Source``, a ``path`` param given by a call and the default of one,
    and a module's ``Style:`` each name a file outside the folder: each is ``path-outside-config``
    at its own line and column (and not the old not-found message)."""
    folder = cfg / "Modules" / "Pic"
    folder.mkdir(parents=True)
    (folder / "Pic_Module.py").write_text(
        "from tess_shell import Module\n\nclass P(Module):\n    pass\n"
    )
    layout = folder / "Pic_Module.tdl"
    layout.write_text(
        HEAD.format(name="Pic")
        + "Module {\n"
        + "    Style: ../../../outside/Out_Style.tdl\n"
        + "    Params { where { Type: path, Default: ../../../outside/pic.png } }\n"
        + "    Text { Text: hi }\n}\n"
    )
    module(  # a sound module: the call below gives its path param a file outside
        cfg,
        "Img",
        'Module {\n    Params { where { Type: path, Default: "" } }\n    Text { Text: hi }\n}\n',
    )
    path = shell(
        cfg,
        "Bitmap { Source: ../../outside/pic.png }\n"
        "SVG { Source: ../../outside/dot.svg, Width: 8, Height: 8 }\n"
        "Img { where: ../../outside/pic.png }\n",
    )
    code, report = check(cfg, capsys)
    assert code == 1
    found = {(e["file"], e["line"], e["column"]): e["rule"] for e in errors(report)}
    image = position(path, "../../outside/pic.png")
    svg = position(path, "../../outside/dot.svg")
    call = position(path, "where: ../../outside/pic.png")
    style = position(layout, "../../../outside/Out_Style.tdl")
    default = position(layout, "../../../outside/pic.png")
    wanted = {
        ("Shells/Main_Shell.tdl", *image),
        ("Shells/Main_Shell.tdl", *svg),
        ("Shells/Main_Shell.tdl", call[0], call[1] + len("where: ")),
        ("Modules/Pic/Pic_Module.tdl", *style),
        ("Modules/Pic/Pic_Module.tdl", *default),
    }
    assert {k for k, rule in found.items() if rule == "path-outside-config"} == wanted, found
    assert "image-not-found" not in found.values() and "style-not-found" not in found.values()


def test_a_file_inside_the_folder_is_still_read_and_a_missing_one_is_not_a_confinement_error(
    cfg: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (cfg / "Shells").mkdir()
    (cfg / "Shells" / "dot.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    shell(cfg, "SVG { Source: dot.svg, Width: 8, Height: 8 }\nBitmap { Source: gone.png }")
    code, report = check(cfg, capsys)
    assert code == 0 and rules(report) == ["image-not-found"]  # the old warning, not the new error


def test_confinement_by_hand(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / "inside").mkdir(parents=True)
    (tmp_path / "other").mkdir()
    (home / "link").symlink_to(tmp_path / "other", target_is_directory=True)
    confine = Confinement.of([home], shipped_dir())
    file = home / "inside" / "A_Module.tdl"
    assert confine.target(file, "../b/c.png") == home / "b" / "c.png"  # not there: still inside
    assert confine.target(file, "x/../y.png") == home / "inside" / "y.png"
    for text in ("../../other/f", "../link/f", "/etc/passwd", "~/nothing-here"):
        with pytest.raises(PathOutsideConfig):
            confine.target(file, text)
    # the one exception: a file of the package, found by where it is
    assert confine.target(file, str(shipped_dir() / "Clock" / "Clock_Module.tdl"))
    # the name of a sibling folder is not "inside" by prefix alone
    (tmp_path / "home-evil").mkdir()
    with pytest.raises(PathOutsideConfig):
        confine.target(file, "../../home-evil/x")


def test_the_json_of_check_carries_the_rule_so_a_tool_can_act_on_it(
    cfg: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shell(cfg, "Import: ../../outside/Out_Module.tdl")
    assert main(["check", "--json", "--config-dir", str(cfg)]) == 1
    (error,) = json.loads(capsys.readouterr().out)["errors"]
    assert error["rule"] == "path-outside-config" and error["severity"] == "error"
    assert "configuration folder" in error["hint"]

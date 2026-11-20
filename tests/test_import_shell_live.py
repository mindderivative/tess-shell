"""A shell split over files, running on a private headless sway: both files' Bars open, and saving
an imported file reloads the shell (Hot Reload > acceptance; Shell File > Structure, D22)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.sway import PrivateSway
from tests.test_import_shell import bar, main_shell, surfaces
from tests.test_reload_live import SETTINGS, Live
from tests.test_run import Shell

pytestmark = pytest.mark.tre


class Split(Live):
    """A running shell whose top Bar is in ``Main_Shell.tdl`` and whose bottom Bar is in
    ``Parts/Bottom_Shell.tdl``, a folder no shell folder watches."""

    def __init__(self, sway: PrivateSway, cfg: Path) -> None:
        self.cfg = cfg
        (cfg / "settings.tdl").write_text(SETTINGS.format(extra=""))
        self.shell_file = main_shell(cfg, f"{bar('Top_Bar')}\nImport: ../Parts/Bottom_Shell.tdl")
        self.part = surfaces(
            cfg, bar("Bottom_Bar", "BOTTOM", 24), relative="Parts/Bottom_Shell.tdl"
        )
        self.process = Shell(cfg, sway.env)


@pytest.fixture
def split(private_sway: PrivateSway, tmp_path: Path) -> Iterator[Split]:
    run = Split(private_sway, tmp_path)
    run.wait(r"step 12 \(modules\): started")
    run.wait("running")
    yield run
    run.close()


def test_both_files_surfaces_open_and_saving_the_imported_file_reloads_the_shell(
    split: Split,
) -> None:
    assert "step 11 (surfaces): 2 opened" in split.text()
    split.part.write_text(split.part.read_text().replace("Height: 24", "Height: 40"))
    split.wait(r"reloaded \(Bottom_Shell\.tdl\)")
    assert "size (0, 40) zone 40" in split.text()
    # the shell's own UID write into the imported file is not a second reload
    assert split.part.read_text().count("UID:") == 1
    assert split.stop() == 0


def test_a_mistake_saved_in_the_imported_file_is_refused_at_that_file_and_the_fix_is_taken(
    split: Split,
) -> None:
    good = split.part.read_text()
    split.part.write_text(good.replace("Edge: BOTTOM", "Edge: bottom"))
    split.wait("reload refused")
    assert "Parts/Bottom_Shell.tdl:" in split.text() and "write BOTTOM" in split.text()
    assert split.count(r"reloaded \(") == 0
    split.part.write_text(good)
    split.wait(r"reloaded \(Bottom_Shell\.tdl\)", timeout=5)
    assert split.stop() == 0


def test_a_file_the_main_shell_starts_to_import_is_watched_from_then_on(split: Split) -> None:
    extra = surfaces(split.cfg, bar("Left_Bar", "LEFT", 20), relative="More/Extra_Shell.tdl")
    split.edit_shell(
        "Import: ../Parts/Bottom_Shell.tdl",
        "Import: [../Parts/Bottom_Shell.tdl, ../More/Extra_Shell.tdl]",
    )
    split.wait(r"reloaded \(Main_Shell\.tdl\)")
    extra.write_text(extra.read_text().replace("Height: 20", "Height: 36"))
    split.wait(r"reloaded \(Extra_Shell\.tdl\)")
    assert split.stop() == 0


def test_a_file_that_is_wrong_when_it_is_first_imported_reloads_once_it_is_fixed(
    split: Split,
) -> None:
    extra = surfaces(
        split.cfg, "Bar { Name: Left_Bar, Edge: left }", relative="More/Extra_Shell.tdl"
    )
    split.edit_shell(
        "Import: ../Parts/Bottom_Shell.tdl",
        "Import: [../Parts/Bottom_Shell.tdl, ../More/Extra_Shell.tdl]",
    )
    split.wait("reload refused")
    assert "More/Extra_Shell.tdl:" in split.text()
    extra.write_text(
        extra.read_text().replace("Edge: left }", "Edge: LEFT, Width: 20, Height: 20 }")
    )
    split.wait(r"reloaded \(Extra_Shell\.tdl\)")
    assert split.stop() == 0

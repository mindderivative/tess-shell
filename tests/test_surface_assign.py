"""Which outputs a Monitor block applies to (Shell File > Monitors)."""

from __future__ import annotations

from dataclasses import dataclass

from tess_shell.binder.model import NO_ORIGIN
from tess_shell.schema.model import MonitorDef
from tess_shell.surfaces.manager import assign


@dataclass
class Out:
    name: str
    description: str


OUTS = [Out("DP-1", "Dell A"), Out("HDMI-A-1", "LG B"), Out("DP-2", "Dell C")]


def mon(name: str, **kw: object) -> MonitorDef:
    base: dict[str, object] = {"index": None, "connector": None, "description": None}
    base.update(kw)
    return MonitorDef(name=name, origin=NO_ORIGIN, **base)  # type: ignore[arg-type]


def result(monitors: list[MonitorDef]) -> dict[str, list[int]]:
    return {m.name: idx for m, idx in assign(monitors, OUTS)}


def test_index_is_a_position() -> None:
    assert result([mon("A", index=0), mon("B", index=1)]) == {"A": [0], "B": [1]}


def test_connector_beats_description_beats_index() -> None:
    m = mon("A", index=0, description="LG B", connector="DP-2")
    assert result([m]) == {"A": [2]}
    assert result([mon("A", index=0, description="LG B")]) == {"A": [1]}


def test_a_selector_that_matches_nothing_gives_no_outputs() -> None:
    assert result([mon("A", index=7), mon("B", connector="eDP-1")]) == {"A": [], "B": []}


def test_default_takes_every_output_no_other_block_names() -> None:
    got = result([mon("Rest", index="default"), mon("Main", connector="HDMI-A-1")])
    assert got == {"Main": [1], "Rest": [0, 2]}


def test_the_first_block_wins_when_two_name_the_same_output() -> None:
    got = result([mon("A", index=0), mon("B", connector="DP-1")])
    assert got == {"A": [0], "B": []}


def test_a_block_with_no_selector_is_ignored() -> None:
    assert result([mon("A")]) == {}

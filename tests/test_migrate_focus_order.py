"""Step 0003: a positive ``Tab_Index`` becomes the file's order and ``Focus_Order``."""

from __future__ import annotations

import tess_dl

from tess_shell.migrate.focus_order import move_tab_index
from tess_shell.schema.shell import read_shell
from tess_shell.surfaces.focus import surface_order
from tests.shell_samples import HEADER

BEFORE = """Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 32
                Tab_Index: 3
                Children { FlexBox { Children {
                    Button { Name: Save, Tab_Index: 2 }
                    Button { Name: Cancel, Tab_Index: 1, Width: 40 }
                    Button { Name: Keep, Tab_Index: 0 }
                } } }
            }
            Panel { Name: Dock, Anchor: LEFT, Width: 50, Height: 50, Tab_Index: 1 }
            Frame {
                Name: Ring
                Thickness: 8
                Edges { Top { Thickness: 30, Tab_Index: 2, Children { FlexBox { } } } }
            }
        }
    }
}
"""


def moved(text: str = BEFORE) -> tuple[str, list]:  # type: ignore[type-arg]
    return move_tab_index(HEADER + text, path="Shells/Main_Shell.tdl")


def test_the_surfaces_that_had_a_tab_index_are_listed_in_its_order_and_lose_it() -> None:
    out, changes = moved()
    assert "Focus_Order: [Dock, Ring.top, Top_Bar]" in out
    assert "Tab_Index: 3" not in out and "Tab_Index: 1 }" not in out
    assert sorted(c.kind for c in changes).count("focus-order") == 1


def test_a_block_loses_a_positive_tab_index_alone_or_among_other_keys_and_keeps_a_zero() -> None:
    out, _ = moved()
    assert "Button { Name: Save }" in out
    assert "Button { Name: Cancel, Width: 40 }" in out
    assert "Button { Name: Keep, Tab_Index: 0 }" in out


def test_a_key_alone_on_its_line_takes_the_line_with_it() -> None:
    out, _ = moved()
    assert "\n                \n" not in out and "Tab_Index" not in out.replace("Tab_Index: 0", "")
    assert "Height: 32\n                Children" in out


def test_the_result_loads_and_orders_the_surfaces_as_the_numbers_did() -> None:
    out, _ = moved(BEFORE.replace("Button {", "FlexBox { Role: BUTTON,"))
    result = tess_dl.parse(out, path="Shells/Main_Shell.tdl")
    assert result.document is not None and not result.errors
    shell, findings = read_shell(result.document, "Shells/Main_Shell.tdl", lambda p: "")
    assert shell is not None and [f for f in findings if f.severity == "error"] == [], findings
    assert surface_order(shell)[:3] == ["Dock", "Ring.top", "Top_Bar"]


def test_the_step_is_idempotent_and_leaves_a_file_with_nothing_to_move_alone() -> None:
    once, _ = moved()
    twice, again = move_tab_index(once, path="Shells/Main_Shell.tdl")
    assert twice == once and again == []
    plain = HEADER + "Shell { Monitor { Name: Main, Index: 0, Children { } } }\n"
    assert move_tab_index(plain, path="x.tdl") == (plain, [])


def test_a_module_file_loses_a_positive_tab_index_and_no_focus_order_is_made() -> None:
    text = "Module { FlexBox { Children { Button { Name: A, Tab_Index: 4 } } } }\n"
    out, changes = move_tab_index(HEADER + text, path="Modules/M/M_Module.tdl")
    assert "Tab_Index" not in out and "Focus_Order" not in out
    assert [c.kind for c in changes] == ["tab-index"]


def test_a_file_of_surfaces_made_to_be_imported_keeps_its_surfaces_tab_index() -> None:
    text = "Shell { Bar { Name: A, Edge: TOP, Width: EXPAND, Height: 10, Tab_Index: 2 } }\n"
    out, changes = move_tab_index(HEADER + text, path="Shells/Top_Shell.tdl")
    assert "Tab_Index: 2" in out and changes == []

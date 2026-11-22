"""The Peek handle's ink where no border gives it is a theme role, the one of ``on_surface`` and
``surface`` that reads better on the Frame's fill (Peek > Tokens used, AC-PEK-14)."""

from __future__ import annotations

import pytest

from tess_shell.surfaces.frame import _contrast, resolve_paint
from tests.test_frame import look, shell_of


def paint_of(frame: str):  # type: ignore[no-untyped-def]
    (frame_def,) = shell_of(frame).monitors[0].frames
    paint, errors = resolve_paint(frame_def, look())
    assert errors == []
    return paint


@pytest.mark.parametrize("fill", ['"#101418"', '"#F6F8FA"', "$color.surface"])
def test_the_handle_reaches_3_to_1_on_any_fill_it_is_drawn_on(fill: str) -> None:
    paint = paint_of(f"Frame {{ Name: F, Thickness: 20, Style {{ Background: {fill} }} }}")
    assert paint.handle is not None and paint.fill is not None
    assert _contrast(paint.handle, paint.fill) >= 3.0

"""``Appearance { Scheme: LIGHT | DARK }`` of settings.tdl (TSH-061): the user's own choice,
which the desktop's colour scheme does not change."""

from __future__ import annotations

from pathlib import Path

from tess_shell.appearance import Appearance
from tess_shell.scanner import build_look, scan
from tests.shell_samples import write_example


def test_a_scheme_set_in_settings_is_kept_when_the_desktop_changes_its_own(tmp_path: Path) -> None:
    from tess_shell.config.settings import load_settings as load

    write_example(tmp_path)
    (tmp_path / "settings.tdl").write_text(
        "---\nTDL: 0.2\nName: Settings\n---\nSettings { Appearance { Scheme: LIGHT } }\n"
    )
    settings, _ = load(tmp_path)
    assert settings is not None
    look = build_look(scan(settings, tmp_path), settings, Appearance(scheme="dark"))
    assert look.appearance.scheme == "light"
    after = look.with_appearance(Appearance(scheme="dark"))  # the portal says dark
    assert after.appearance.scheme == "light" and after.appearance.scheme_override == "light"
    from dataclasses import replace

    free = replace(settings, appearance=replace(settings.appearance, scheme="DEFAULT"))
    again = build_look(scan(free, tmp_path), free, after.appearance)
    assert again.appearance.scheme == "default" and again.appearance.scheme_override is None

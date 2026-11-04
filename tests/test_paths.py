from pathlib import Path

import pytest

from tess_shell.config.paths import FOLDERS, PathError, config_dir, ensure_config_dir, expand_path


def test_override_wins_and_is_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert config_dir(Path("rel")) == tmp_path / "rel"


@pytest.mark.parametrize("xdg", ["", "relative/dir"])
def test_unusable_xdg_falls_back_to_home(xdg: str) -> None:
    assert config_dir(environ={"XDG_CONFIG_HOME": xdg}) == Path.home() / ".config/tesserae-shell"


def test_xdg_config_home_used() -> None:
    assert config_dir(environ={"XDG_CONFIG_HOME": "/x/cfg"}) == Path("/x/cfg/tesserae-shell")


def test_ensure_creates_folders(tmp_path: Path) -> None:
    ensure_config_dir(tmp_path / "c")
    assert all((tmp_path / "c" / f).is_dir() for f in FOLDERS)


def test_expand_home_and_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/u")
    monkeypatch.setenv("FOO", "bar")
    assert expand_path("~/x") == "/home/u/x"
    assert expand_path("$HOME/x") == "/home/u/x"
    assert expand_path("/a/${FOO}/b") == "/a/bar/b"


def test_unset_variable_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOPE_NOT_SET", raising=False)
    with pytest.raises(PathError, match="NOPE_NOT_SET"):
        expand_path("/a/$NOPE_NOT_SET")

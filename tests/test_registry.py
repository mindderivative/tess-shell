import json
import os
import stat
from pathlib import Path

import pytest

from tess_shell.config.registry import Registry, RegistryError


def test_missing_file_is_created(tmp_path: Path) -> None:
    reg = Registry.open(tmp_path / "registry.json")
    assert json.loads((tmp_path / "registry.json").read_text()) == {"registry": 1, "entries": {}}
    assert stat.S_IMODE((tmp_path / "registry.json").stat().st_mode) == 0o600
    assert reg.data["entries"] == {}


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ('{"registry": 1,\n "entries": }', "registry-invalid-json"),
        ("[]", "registry-bad-shape"),
        ('{"registry": "1", "entries": {}}', "registry-bad-shape"),
        ('{"registry": 1, "entries": []}', "registry-bad-shape"),
        ('{"registry": 2, "entries": {}}', "registry-too-new"),
    ],
)
def test_bad_file_is_reported_and_left_untouched(tmp_path: Path, text: str, rule: str) -> None:
    path = tmp_path / "registry.json"
    path.write_text(text)
    with pytest.raises(RegistryError) as info:
        Registry.open(path)
    assert info.value.finding.rule == rule
    assert path.read_text() == text


def test_invalid_json_position(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text('{\n  "registry": 1,\n  "entries": }')
    with pytest.raises(RegistryError) as info:
        Registry.open(path)
    assert info.value.finding.line == 3


def test_save_keeps_old_file_whole_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = Registry.open(tmp_path / "registry.json")
    before = (tmp_path / "registry.json").read_text()
    reg.data["entries"]["x"] = {"a": 1}

    def boom(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        reg.save()
    assert (tmp_path / "registry.json").read_text() == before
    assert [p.name for p in tmp_path.iterdir()] == ["registry.json"]


def test_save_roundtrip_and_preserves_mode(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    reg = Registry.open(path)
    path.chmod(0o640)
    reg.data["entries"]["x"] = {"a": 1}
    reg.save()
    assert Registry.open(path).data["entries"] == {"x": {"a": 1}}
    assert stat.S_IMODE(path.stat().st_mode) == 0o640

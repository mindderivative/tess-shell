"""The carried tess_utils: the files match their stamp, the compiled module works through the
shell's converters, and the sync tool's checks refuse a bad release (Shell Package Layout)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sysconfig
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tess_shell._vendor import tess_utils
from tess_shell.binder import convert
from tess_shell.binder.model import (
    BindError,
    Color,
    Enum,
    Length,
    Number,
    Origin,
    Seq,
    Sides,
)

ROOT = Path(__file__).resolve().parents[1]
AT = Origin("t.tdl", 3, 5)


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "vendor_utils", ROOT / "tools" / "vendor_utils.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_carried_files_match_their_stamp() -> None:
    """The drift check: an edited or swapped file, or one missing from the stamp, fails here."""
    assert load_tool().check() == []


def test_the_carried_version_is_the_stamped_one() -> None:
    record = json.loads((ROOT / "src/tess_shell/_vendor/VENDORED.json").read_text())
    assert record["version"] == tess_utils.__version__
    assert record["tag"] == f"v{tess_utils.__version__}"
    assert "tess_utils.pyi" in record["files"]


def test_a_changed_carried_file_is_reported(tmp_path: Path) -> None:
    tool: Any = load_tool()
    target = tmp_path / "_vendor"
    shutil.copytree(ROOT / "src/tess_shell/_vendor", target)
    tool.TARGET = target
    so = next(target.glob("tess_utils.*.so"))
    so.write_bytes(so.read_bytes() + b"\0")
    problems = tool.check()
    assert any(so.name in p and "differs" in p for p in problems), problems
    (target / "tess_utils.pyi").unlink()
    assert any("tess_utils.pyi is missing" in p for p in tool.check())
    (target / "tess_utils.extra").write_text("x")
    assert any("tess_utils.extra is carried but not in" in p for p in tool.check())


def stamped(folder: Path, python: str | None = None, **hashes: str) -> dict[str, object]:
    stamp: dict[str, object] = {
        "version": "9.9.9",
        "python": python or sysconfig.get_config_var("SOABI"),
        "platform": __import__("platform").machine(),
        "files": {"tess_utils.pyi": __import__("hashlib").sha256(b"stub").hexdigest(), **hashes},
    }
    (folder / "stamp.json").write_text(json.dumps(stamp))
    (folder / "tess_utils.pyi").write_bytes(b"stub")
    return stamp


def test_a_release_that_matches_its_stamp_is_accepted(tmp_path: Path) -> None:
    stamped(tmp_path)
    assert (
        load_tool().verify_download(tmp_path, "stamp.json", ["tess_utils.pyi"])["version"]
        == "9.9.9"
    )


def test_a_release_with_a_wrong_hash_or_for_another_python_is_refused(tmp_path: Path) -> None:
    tool = load_tool()
    stamped(tmp_path, **{"tess_utils.pyi": "0" * 64})
    with pytest.raises(tool.VendorError, match="does not match the SHA-256"):
        tool.verify_download(tmp_path, "stamp.json", ["tess_utils.pyi"])
    stamped(tmp_path, python="cpython-313-x86_64-linux-gnu")
    with pytest.raises(tool.VendorError, match="built for cpython-313"):
        tool.verify_download(tmp_path, "stamp.json", ["tess_utils.pyi"])
    (tmp_path / "tess_utils.pyi").unlink()
    stamped(tmp_path)
    (tmp_path / "tess_utils.pyi").unlink()
    with pytest.raises(tool.VendorError, match="has no tess_utils.pyi"):
        tool.verify_download(tmp_path, "stamp.json", ["tess_utils.pyi"])


# -- the shell's converters over the compiled module ---------------------------------------------


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("#102030", (16, 32, 48, 255)),
        ("#10203040", (16, 32, 48, 64)),
        ("#fa0", (255, 170, 0, 255)),
        ("rgba(0 0 0 0.5)", (0, 0, 0, 128)),
        ("rgb(1, 2, 3)", (1, 2, 3, 255)),
        ("transparent", (0, 0, 0, 0)),
    ],
)
def test_the_shell_reads_colours_through_tess_utils(
    written: str, expected: tuple[int, int, int, int]
) -> None:
    c = convert.parse_color(written, AT)
    assert (c.r, c.g, c.b, c.a) == expected and c.origin == AT


def test_a_bad_colour_is_a_bind_error_at_the_written_position() -> None:
    with pytest.raises(BindError) as exc:
        convert.parse_color("#12", AT)
    assert exc.value.origin == AT and "'#12'" in exc.value.message and exc.value.hint


def test_sides_radius_and_enum_words_take_tres_forms() -> None:
    assert convert.sides(Sides(1, 2, 3, 4, origin=AT), ("t", "r", "b", "l")) == {
        "t": 2,
        "r": 3,
        "b": 4,
        "l": 1,
    }
    assert convert.sides(Number(5, origin=AT), ("t", "r", "b", "l")) == {
        "t": 5,
        "r": 5,
        "b": 5,
        "l": 5,
    }
    items = tuple(Length(n, origin=AT) for n in (1, 2, 3, 4))
    assert convert.radius(Seq(items, origin=AT), ("corner_radius",)) == {
        "corner_radius": (1, 2, 3, 4)
    }
    assert convert.enum(Enum("SPACE_BETWEEN", origin=AT), ("justify",), ("SPACE_BETWEEN",)) == {
        "justify": "space_between"
    }
    with pytest.raises(BindError, match="negative"):
        convert.sides(Sides(1, -2, 3, 4, origin=AT), ("t", "r", "b", "l"))


def test_the_carried_module_is_the_compiled_one() -> None:
    assert str(tess_utils.__file__).endswith(".so")
    assert isinstance(Color(0, 0, 0, 0, origin=AT), Color)

"""The NOTICE file lists every third-party asset and dependency, and the built package carries it.

NOTICE is written by hand (a licence is read by a person), so these tests make it complete by
construction of a check, from the three places a new third-party thing can come in:

- a file in the package that is not source code (an icon, an image, a font, a licence text) must be
  named in NOTICE by its path;
- a runtime dependency, direct (pyproject.toml) or transitive (the installed metadata of the
  dependency closure), must have an entry in NOTICE section 3 with its version range and the
  licence its installed release declares, and a native library a dependency's wheel bundles
  (``*.libs/``) must be named;
- the built wheel carries NOTICE in ``dist-info/licenses`` and the sdist at its root.

What no test can see is an asset embedded in a compiled extension (tesserae-engine's fonts are
bytes inside ``tess_re/_core*.so``). NOTICE section 2 lists them for the engine range of section 3;
the entry for tesserae-engine therefore has to carry that range, and a person re-checks section 2
when the range moves.
"""

from __future__ import annotations

import importlib.metadata as md
import os
import re
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from collections.abc import Iterable
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "src" / "tess_shell"
NOTICE = REPO / "NOTICE"

# What this project writes itself and ships as source: everything else in the package is an asset
# (or the licence text of one) and NOTICE has to name it.
SOURCE_SUFFIXES = {".py", ".tdl", ".js", ".desktop", ".service"}
SOURCE_FILES = {"py.typed", "kwin/TesseraeShell/metadata.json"}


def notice_text() -> str:
    return NOTICE.read_text(encoding="utf-8")


def section(text: str, number: int) -> str:
    """The text of the numbered section ("3. Runtime dependencies ...") up to the next one."""
    parts = re.split(r"^(?=\d+\. )", text, flags=re.MULTILINE)
    (found,) = [p for p in parts if p.startswith(f"{number}. ")]
    return found


def entries(text: str) -> dict[str, str]:
    """The "* " entries of a text by their first word (a dependency name, canonicalised if it is
    one), with their continuation lines."""
    found: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("* "):
            word = re.match(r"\* ([^\s:]+)", line)
            assert word is not None, line
            current = str(word.group(1))
            found[current] = line
        elif current is not None and line.startswith("  "):
            found[current] += "\n" + line
        else:
            current = None
    return found


def asset_files(relative_paths: Iterable[str]) -> list[str]:
    """The paths (relative to the package folder) that are not this project's own source."""
    return sorted(
        path
        for path in relative_paths
        if "__pycache__" not in path.split("/")
        and not path.endswith(".pyc")
        and Path(path).suffix not in SOURCE_SUFFIXES
        and path not in SOURCE_FILES
    )


def package_files() -> list[str]:
    return [p.relative_to(PACKAGE).as_posix() for p in sorted(PACKAGE.rglob("*")) if p.is_file()]


# -- the runtime dependency closure --------------------------------------------------------------


def direct_requirements() -> list[Requirement]:
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return [Requirement(text) for text in data["project"]["dependencies"]]


def runtime_closure() -> tuple[dict[str, md.Distribution], list[str]]:
    """Every runtime dependency by canonical name, from pyproject.toml's list and the installed
    metadata of each one (its ``Requires-Dist`` with the extras that were asked for, markers
    evaluated here); and the names that are not installed (their own requirements are unknown)."""
    found: dict[str, md.Distribution] = {}
    absent: list[str] = []
    extras_of: dict[str, set[str]] = {}
    queue = list(direct_requirements())
    while queue:
        req = queue.pop()
        name = canonicalize_name(req.name)
        asked = extras_of.setdefault(name, set())
        new_extras = {canonicalize_name(e) for e in req.extras} - asked
        if name in found and not new_extras:
            continue
        asked |= new_extras
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            if name not in absent:
                absent.append(name)
            continue
        found[name] = dist
        for text in dist.requires or []:
            child = Requirement(text)
            if child.marker is None or any(
                child.marker.evaluate({"extra": extra}) for extra in ("", *asked)
            ):
                queue.append(child)
    return found, sorted(absent)


def declared_license(dist: md.Distribution) -> str | None:
    """The licence an installed release declares: ``License-Expression``, a short ``License``
    field, or the "License ::" classifier (without its trailing " License")."""
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return str(expression)
    short = meta.get("License")
    if short and len(short) < 100 and "\n" not in short:
        return str(short)
    classifiers = [
        c.split(" :: ")[-1] for c in meta.get_all("Classifier", []) if c.startswith("License ::")
    ]
    if classifiers:
        return str(classifiers[-1]).removesuffix(" License")
    return None


def dependency_entries() -> dict[str, str]:
    return {
        canonicalize_name(word.split("[")[0]): text
        for word, text in entries(section(notice_text(), 3)).items()
    }


# -- NOTICE against what is in the package and what it needs -------------------------------------


def test_every_asset_file_of_the_package_is_named_in_notice() -> None:
    text = notice_text()
    assets = asset_files(package_files())
    assert "shipped/Icons/mdi.json" in assets  # the walk finds the set it exists for
    missing = [path for path in assets if path not in text]
    assert not missing, f"not named in NOTICE section 1 (with licence and source): {missing}"


def test_every_asset_path_notice_names_exists() -> None:
    """A renamed or removed asset leaves a wrong line in NOTICE, which the test above cannot see."""
    named = [word.rstrip(":") for word in entries(section(notice_text(), 1))]
    gone = [path for path in named if not (PACKAGE / path).is_file()]
    assert not gone, f"NOTICE section 1 names files the package does not have: {gone}"


def test_the_dependency_closure_is_found() -> None:
    """The walk must not come back empty or short: the extra of tesserae-utils needs pillow."""
    closure, absent = runtime_closure()
    assert not absent, f"installed environment lacks {absent}: run uv sync"
    direct = {canonicalize_name(r.name) for r in direct_requirements()}
    assert direct <= set(closure)
    assert {"tesserae-engine", "pillow", "tesserae-utils"} <= set(closure)


def test_every_runtime_dependency_has_an_entry_in_notice() -> None:
    closure, absent = runtime_closure()
    listed = set(dependency_entries())
    wanted = set(closure) | set(absent)
    assert wanted <= listed, f"no entry in NOTICE section 3 for: {sorted(wanted - listed)}"
    extra = sorted(listed - wanted)
    assert listed <= wanted, f"NOTICE section 3 lists what is not a dependency: {extra}"


def test_a_direct_dependency_entry_carries_its_version_range() -> None:
    entry = dependency_entries()
    for req in direct_requirements():
        text = entry.get(canonicalize_name(req.name))
        if text is None:
            continue  # test_every_runtime_dependency_has_an_entry_in_notice reports it
        for clause in str(req.specifier).split(","):
            assert clause in text, f"{req.name}: NOTICE does not carry {clause} of {req}"


def test_an_entry_names_the_licence_the_installed_release_declares() -> None:
    closure, _ = runtime_closure()
    entry = dependency_entries()
    wrong: list[str] = []
    for name, dist in closure.items():
        licence = declared_license(dist)
        assert licence is not None, (
            f"{name} declares no licence: say so in NOTICE, extend this test"
        )
        if name not in entry:
            continue  # test_every_runtime_dependency_has_an_entry_in_notice reports it
        # the entry reads "name range: LICENCE. url"; the licence must follow the colon, so the
        # same word elsewhere in the entry's prose does not count
        if not re.search(rf": {re.escape(licence)}(?![\w-])", entry[name]):
            wrong.append(f"{name} {dist.version} declares {licence!r}")
    assert not wrong, f"NOTICE section 3 does not carry the declared licence of: {wrong}"


def test_every_entry_carries_a_project_url_from_the_metadata() -> None:
    closure, _ = runtime_closure()
    entry = dependency_entries()
    for name, dist in closure.items():
        if name not in entry:
            continue  # test_every_runtime_dependency_has_an_entry_in_notice reports it
        urls = [
            part.split(",", 1)[1].strip()
            for part in dist.metadata.get_all("Project-URL", [])
            if "," in part
        ]
        urls.append(str(dist.metadata.get("Home-page") or ""))
        assert any(url and url.rstrip("/").removesuffix(".git") in entry[name] for url in urls), (
            f"{name}: NOTICE names none of its URLs {urls}"
        )


def test_every_native_library_a_dependency_bundles_is_named_in_notice() -> None:
    """``pillow.libs/libjpeg-6dc8d115.so.62.4.0`` is named by ``libjpeg``."""
    closure, _ = runtime_closure()
    text = notice_text()
    missing: list[str] = []
    found = 0
    for name, dist in closure.items():
        for file in dist.files or []:
            first = file.parts[0]
            if first.endswith(".libs"):
                found += 1
                stem = re.sub(r"(-[0-9a-f]{8})?\.so(\.\d+)*$", "", file.name)
                if not re.search(rf"(?<![\w-]){re.escape(stem)}(?![\w])", text):
                    missing.append(f"{name}: {file}")
    assert found, "no bundled native library found: the walk is wrong"
    assert not missing, f"bundled native libraries not named in NOTICE: {missing}"


# -- the built package carries NOTICE ------------------------------------------------------------


def uv_build(out: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not installed")
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTEST_CURRENT_TEST")}
    # `uv build` makes the sdist and then the wheel from it. --offline builds from uv's cache (the
    # build backend, hatchling); a cold cache falls back to the network.
    done = None
    for flags in (["--offline"], []):
        done = subprocess.run(
            [uv, "build", *flags, "--out-dir", str(out), str(REPO)],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if done.returncode == 0:
            return
    assert done is not None
    text = (done.stdout + done.stderr).lower()
    if "failed to fetch" in text or "failed to download" in text or "dns error" in text:
        pytest.skip("the build backend is neither in uv's cache nor reachable (no network)")
    pytest.fail(done.stdout + done.stderr)


def test_the_built_wheel_and_sdist_carry_notice(tmp_path: Path) -> None:
    uv_build(tmp_path)
    (wheel,) = tmp_path.glob("*.whl")
    (sdist,) = tmp_path.glob("*.tar.gz")
    wanted = NOTICE.read_bytes()
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        (member,) = [n for n in names if n.endswith(".dist-info/licenses/NOTICE")]
        assert archive.read(member) == wanted
        (metadata,) = [n for n in names if n.endswith(".dist-info/METADATA")]
        assert "License-File: NOTICE" in archive.read(metadata).decode()
        # whatever the wheel carries under tess_shell/ that is not source is named in NOTICE too
        shipped = [n.removeprefix("tess_shell/") for n in names if n.startswith("tess_shell/")]
        text = wanted.decode()
        unnamed = [p for p in asset_files(shipped) if p not in text]
        assert not unnamed, f"in the wheel, not named in NOTICE: {unnamed}"
    with tarfile.open(sdist) as tar:
        root = sdist.name.removesuffix(".tar.gz")
        member_file = tar.extractfile(f"{root}/NOTICE")
        assert member_file is not None
        assert member_file.read() == wanted

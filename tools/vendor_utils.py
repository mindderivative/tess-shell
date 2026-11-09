"""Carry the compiled ``tess_utils`` of the private tess-utils repository into this package.

    uv run python tools/vendor_utils.py sync                 # the latest release of tess-utils
    uv run python tools/vendor_utils.py sync --tag v0.1.1    # a named release
    uv run python tools/vendor_utils.py sync --from-dir ../tess-utils/build/so   # a local build
    uv run python tools/vendor_utils.py check                # no network: is the copy in step?

``sync`` reads ``vendor.json`` from the repository at the release tag, downloads the stamp and the
files it names (``{soabi}`` is this interpreter's Python tag) with ``gh`` (credentials for the
private repository), checks each file against the SHA-256 in the stamp and the stamp against this
interpreter, and copies them to ``src/tess_shell/_vendor/`` with ``VENDORED.json`` (the tag, the
version and the SHA-256 of each file). A release is reproducible, so a copy made from a local build
and the release of the same source have the same hashes. ``check`` is the drift check: it
recomputes the hashes of the carried files and compares them with ``VENDORED.json``.

Standard library only; the only external tool is ``gh``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "tess_shell" / "_vendor"
STAMP_NAME = "VENDORED.json"
DEFAULT_REPO = "mindderivative/tess-utils"


class VendorError(Exception):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gh(*args: str) -> str:
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise VendorError("gh is not installed (needed to read the private repository)") from None
    except subprocess.CalledProcessError as exc:
        raise VendorError(f"gh {' '.join(args)} failed: {exc.stderr.strip()}") from None
    return done.stdout


def latest_tag(repo: str) -> str:
    tag = gh("release", "view", "-R", repo, "--json", "tagName", "-q", ".tagName").strip()
    if not tag:
        raise VendorError(f"{repo} has no release")
    return tag


def manifest_at(repo: str, tag: str) -> dict[str, object]:
    text = gh(
        "api",
        f"repos/{repo}/contents/vendor.json?ref={tag}",
        "-H",
        "Accept: application/vnd.github.raw",
    )
    return json.loads(text)  # type: ignore[no-any-return]


def wanted_files(manifest: dict[str, object]) -> list[str]:
    soabi = sysconfig.get_config_var("SOABI") or ""
    names = manifest["files"]
    assert isinstance(names, list)
    return [str(n).replace("{soabi}", soabi) for n in names]


def verify_download(folder: Path, stamp_name: str, files: list[str]) -> dict[str, object]:
    """The stamp read from ``folder``, after every file in it matches the stamp's SHA-256 and the
    stamp names this interpreter's Python tag and platform."""
    stamp_path = folder / stamp_name
    if not stamp_path.is_file():
        raise VendorError(f"the release has no {stamp_name}")
    stamp = json.loads(stamp_path.read_text())
    soabi = sysconfig.get_config_var("SOABI")
    if stamp.get("python") != soabi or stamp.get("platform") != platform.machine():
        raise VendorError(
            f"the release is built for {stamp.get('python')} on {stamp.get('platform')}, "
            f"this is {soabi} on {platform.machine()}"
        )
    hashes = stamp.get("files", {})
    for name in files:
        path = folder / name
        if not path.is_file():
            raise VendorError(f"the release has no {name}")
        if hashes.get(name) != sha256(path):
            raise VendorError(f"{name} does not match the SHA-256 in {stamp_name}")
    return stamp  # type: ignore[no-any-return]


def install(
    folder: Path, files: list[str], stamp: dict[str, object], tag: str, source: str
) -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for old in TARGET.glob("tess_utils.*"):
        old.unlink()
    for name in files:
        shutil.copy2(folder / name, TARGET / name)
    record = {
        "package": "tess_utils",
        "tag": tag,
        "version": stamp["version"],
        "source": source,
        "files": {name: sha256(TARGET / name) for name in files},
    }
    (TARGET / STAMP_NAME).write_text(json.dumps(record, indent=2) + "\n")


def sync(repo: str, tag: str | None, from_dir: Path | None) -> None:
    if from_dir is not None:
        manifest = json.loads((ROOT.parent / "tess-utils" / "vendor.json").read_text())
        files = wanted_files(manifest)
        stamp = verify_download(from_dir, str(manifest["stamp"]), files)
        install(from_dir, files, stamp, f"v{stamp['version']}", f"local build {from_dir}")
        print(f"carried tess_utils {stamp['version']} from the local build {from_dir}")
        return
    tag = tag or latest_tag(repo)
    manifest = manifest_at(repo, tag)
    files = wanted_files(manifest)
    stamp_name = str(manifest["stamp"])
    with tempfile.TemporaryDirectory() as tmp:
        for pattern in (*files, stamp_name):
            gh("release", "download", tag, "-R", repo, "-p", pattern, "-D", tmp, "--clobber")
        folder = Path(tmp)
        stamp = verify_download(folder, stamp_name, files)
        install(folder, files, stamp, tag, f"{repo} release {tag}")
    print(f"carried tess_utils {stamp['version']} ({tag}) from {repo}")


def check() -> list[str]:
    """What differs between the carried files and ``VENDORED.json``; empty when it is in step."""
    stamp_path = TARGET / STAMP_NAME
    if not stamp_path.is_file():
        return [f"{STAMP_NAME} is missing: run tools/vendor_utils.py sync"]
    record = json.loads(stamp_path.read_text())
    problems: list[str] = []
    for name, expected in record["files"].items():
        path = TARGET / name
        if not path.is_file():
            problems.append(f"{name} is missing")
        elif sha256(path) != expected:
            problems.append(f"{name} differs from {STAMP_NAME} (edited, or a different build)")
    carried = {p.name for p in TARGET.glob("tess_utils.*")}
    for extra in sorted(carried - set(record["files"])):
        problems.append(f"{extra} is carried but not in {STAMP_NAME}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sync", help="copy a tess-utils release into the package")
    s.add_argument("--repo", default=DEFAULT_REPO)
    s.add_argument("--tag", help="a release tag (default: the latest release)")
    s.add_argument("--from-dir", type=Path, help="a local build directory instead of GitHub")
    sub.add_parser("check", help="compare the carried files with VENDORED.json (no network)")
    args = parser.parse_args(argv)
    try:
        if args.command == "sync":
            sync(args.repo, args.tag, args.from_dir)
            return 0
        problems = check()
    except VendorError as exc:
        print(f"vendor_utils: {exc}", file=sys.stderr)
        return 1
    for problem in problems:
        print(f"vendor_utils: {problem}", file=sys.stderr)
    if not problems:
        print("the carried tess_utils matches VENDORED.json")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

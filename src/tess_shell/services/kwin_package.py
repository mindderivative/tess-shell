"""The shell's KWin files: the script package, the one-shot action scripts, the window rule and the
guards that keep a test away from the real KWin (KWin Integration > The KWin script, Window rules;
Tasks Module > Acting on a Window).

Pure standard library: the loader (``services.kwin``, on the ``dbus`` thread) and the ``kwin``
commands (``tess_shell.kwin_commands``) both use it, and nothing here touches a bus or KWin.

The package is ``src/tess_shell/kwin/TesseraeShell/`` (``metadata.json`` and
``contents/code/main.js``), a KPackage of type ``KWin/Script`` with the id ``tesserae-shell-kwin``.
A one-shot script is a template of ``src/tess_shell/kwin/actions/`` whose ``__WINDOW_ID__`` is
replaced by a window id that is a UUID and nothing else: no script text is built from a window's
title.

The guards. A state-changing path must refuse to act on a real location when the process is a test
(``PYTEST_CURRENT_TEST``): a bus that is not private (a unix socket under the temporary folder), a
file under the real home. Tests name a temporary target; a bare default is refused.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path

PACKAGE_ID = "tesserae-shell-kwin"
RULE_ID = "tesserae-shell-surfaces"
RULE_DESCRIPTION = "Tesserae Shell: surfaces above Plasma panels"
ACTIONS = ("activate", "minimize", "close")
PLACEHOLDER = "__WINDOW_ID__"
_UUID = re.compile(r"^[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}$")
_VERSION = re.compile(r"^KWin version:\s*(\S+)", re.MULTILINE)


class RefusedInTest(RuntimeError):
    """A test tried to act on something real: the real session bus, a file under the real home."""


def parse_version(information: str) -> str | None:
    """The ``KWin version: ...`` line of ``/KWin supportInformation``."""
    found = _VERSION.search(information)
    return found.group(1) if found else None


# -- the guards -----------------------------------------------------------------------------


def in_test() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def under_real_home(path: Path) -> bool:
    try:
        path.expanduser().resolve().relative_to(Path(os.path.expanduser("~")).resolve())
    except ValueError:
        return False
    return True


def refuse_real_path(path: Path, what: str) -> None:
    """Raise :class:`RefusedInTest` when this is a test and ``path`` is under the real home."""
    if in_test() and under_real_home(path):
        raise RefusedInTest(
            f"{what}: {path} is under the real home and this process is a test; "
            "a test names a temporary path"
        )


def socket_path(address: str) -> Path | None:
    """The socket file of a ``unix:path=...`` bus address (``None`` for any other form)."""
    for part in address.split(";"):
        kind, _, rest = part.partition(":")
        if kind != "unix":
            continue
        for item in rest.split(","):
            key, _, value = item.partition("=")
            if key == "path" and value:
                return Path(value)
    return None


def private_address(address: str | None) -> bool:
    """Is ``address`` a bus a test made: a unix socket under the temporary folder (the private
    ``dbus-daemon`` of ``tests/fake_dbus.py``)? ``None`` (the bus as the environment gives it) is
    not known to be private."""
    if not address:
        return False
    path = socket_path(address)
    if path is None:
        return False
    try:
        path.resolve().relative_to(Path(tempfile.gettempdir()).resolve())
    except ValueError:
        return False
    return True


def refuse_real_bus(address: str | None) -> None:
    """Raise :class:`RefusedInTest` when this is a test and the bus ``address`` is not private. A
    test that loads a script passes the address of its private bus; the environment's session bus
    is the real one."""
    if in_test() and not private_address(address):
        raise RefusedInTest(
            "this process is a test and the bus is not a private one: nothing is loaded into KWin"
        )


# -- the package and the one-shot scripts ------------------------------------------------------


def kwin_folder() -> Path:
    """The ``kwin`` data folder of the shell (the package and the action templates)."""
    return Path(str(resources.files("tess_shell") / "kwin"))


def package_folder() -> Path:
    return kwin_folder() / "TesseraeShell"


def main_script() -> Path:
    """The script a run-time load (mode R) gives to ``loadScript``."""
    return package_folder() / "contents" / "code" / "main.js"


def valid_window_id(window_id: object) -> bool:
    """Is ``window_id`` a UUID (bare, without braces)? Only such an id goes into a script."""
    return isinstance(window_id, str) and _UUID.match(window_id) is not None


def action_script(kind: str, window_id: str) -> str:
    """The text of the one-shot script for ``kind`` on the window ``window_id``."""
    if kind not in ACTIONS:
        raise ValueError(f"no such window action: {kind!r}")
    if not valid_window_id(window_id):
        raise ValueError("the window id is not a UUID")
    template = (kwin_folder() / "actions" / f"{kind}.js").read_text(encoding="utf-8")
    assert PLACEHOLDER in template
    return template.replace(PLACEHOLDER, window_id.lower())


# -- the persistent install (mode P) ------------------------------------------------------------


def _home(env: Mapping[str, str]) -> Path:
    return Path(env.get("HOME") or "~").expanduser()


def data_home(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(env.get("XDG_DATA_HOME") or _home(env) / ".local" / "share")


def config_home(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(env.get("XDG_CONFIG_HOME") or _home(env) / ".config")


def installed_folder(scripts: Path) -> Path:
    """Where mode P puts the package below KWin's scripts folder (``<data>/kwin/scripts``)."""
    return scripts / PACKAGE_ID


def scripts_folder(data: Path | None = None) -> Path:
    return (data or data_home()) / "kwin" / "scripts"


def installed_main(scripts: Path) -> Path:
    return installed_folder(scripts) / "contents" / "code" / "main.js"


def install_package(scripts: Path) -> Path:
    """Copy the package to ``<scripts>/tesserae-shell-kwin`` (replacing what is there). Returns the
    folder. Refuses a real target in a test."""
    refuse_real_path(scripts, "kwin script install")
    target = installed_folder(scripts)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(package_folder(), target)
    return target


def remove_package(scripts: Path) -> bool:
    """Delete the installed package; ``False`` when there was none."""
    refuse_real_path(scripts, "kwin script remove")
    target = installed_folder(scripts)
    if not target.exists():
        return False
    shutil.rmtree(target)
    return True


# -- KConfig files: a group and a key at a time, everything else untouched -----------------------


def _header(line: str) -> str | None:
    text = line.strip()
    if text.startswith("[") and text.endswith("]") and "][" not in text:
        return text[1:-1]
    return None


def _span(lines: Sequence[str], group: str) -> tuple[int, int] | None:
    """The line range ``[start, end)`` of ``group`` (its header and the lines below it up to the
    next header), or ``None``."""
    start: int | None = None
    for i, line in enumerate(lines):
        name = _header(line)
        if name is None:
            continue
        if start is not None:
            return start, i
        if name == group:
            start = i
    return None if start is None else (start, len(lines))


def ini_get(text: str, group: str, key: str) -> str | None:
    lines = text.splitlines()
    span = _span(lines, group)
    if span is None:
        return None
    for line in lines[span[0] + 1 : span[1]]:
        name, equals, value = line.partition("=")
        if equals and name.strip() == key:
            return value.strip()
    return None


def ini_set(text: str, group: str, key: str, value: str) -> str:
    """``text`` with ``key=value`` in ``[group]``: the key is replaced in place or added at the end
    of the group, the group is added at the end of the file when it is missing. Every other line is
    kept as it was."""
    lines = text.splitlines()
    span = _span(lines, group)
    if span is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"[{group}]", f"{key}={value}"]
        return "\n".join(lines) + "\n"
    start, end = span
    for i in range(start + 1, end):
        name, equals, _ = lines[i].partition("=")
        if equals and name.strip() == key:
            lines[i] = f"{key}={value}"
            return "\n".join(lines) + "\n"
    last = end
    while last > start + 1 and not lines[last - 1].strip():
        last -= 1  # keep the blank line that separates this group from the next
    lines.insert(last, f"{key}={value}")
    return "\n".join(lines) + "\n"


def ini_remove_key(text: str, group: str, key: str) -> str:
    """``text`` without the line ``key=...`` of ``[group]``; every other line is kept. A group
    that is left empty stays (KWin writes its own groups; it is not ours to delete)."""
    lines = text.splitlines()
    span = _span(lines, group)
    if span is None:
        return text
    for i in range(span[0] + 1, span[1]):
        name, equals, _ = lines[i].partition("=")
        if equals and name.strip() == key:
            del lines[i]
            return "\n".join(lines) + "\n"
    return text


def ini_remove_group(text: str, group: str) -> str:
    """``text`` without ``[group]`` and its lines (and the blank line that followed it)."""
    lines = text.splitlines()
    span = _span(lines, group)
    if span is None:
        return text if text.endswith("\n") or not text else text + "\n"
    start, end = span
    del lines[start:end]
    if start == len(lines) and lines and not lines[-1].strip():
        lines.pop()  # the group was the last one: the blank line that parted it goes too
    return "\n".join(lines) + "\n" if lines else ""


def ini_group(text: str, group: str) -> str | None:
    """The lines of ``[group]`` as written, header included, with no trailing blank line."""
    lines = text.splitlines()
    span = _span(lines, group)
    if span is None:
        return None
    body = lines[span[0] : span[1]]
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body) + "\n"


def write_text_atomically(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` through a temporary file in the same folder and a rename, so a
    failure leaves the file as it was."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(text)
        if path.exists():
            shutil.copymode(path, temp)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


# -- the window rule (KWin Integration > Window rules) -----------------------------------------

# KWin's layer enum (``effect/globals.h``): Desktop 0, Below 1, Normal 2, Above 3, Notification 4,
# Active 5, Popup 6, ... A plasma panel is in Above; Notification is above it and below an active
# fullscreen window. The rule's other values are KWin's ``Rules`` enums (``rules.h``): the layer
# rule ``Force`` is 2 and the window class match ``SubstringMatch`` is 2.
RULE_LAYER = 4
RULE_FORCE = 2
RULE_SUBSTRING = 2
RULE_MATCH = "tesserae-shell."  # every surface's resource class starts with this namespace


def rule_group() -> str:
    """The one group the shell owns in ``kwinrulesrc``, as ``kwin rule show`` prints it."""
    return (
        f"[{RULE_ID}]\n"
        f"Description={RULE_DESCRIPTION}\n"
        f"layer={RULE_LAYER}\n"
        f"layerrule={RULE_FORCE}\n"
        f"wmclass={RULE_MATCH}\n"
        "wmclasscomplete=false\n"
        f"wmclassmatch={RULE_SUBSTRING}\n"
    )


def rule_ids(text: str) -> list[str]:
    """The ids in ``[General]`` ``rules``."""
    value = ini_get(text, "General", "rules") or ""
    return [item.strip() for item in value.split(",") if item.strip()]


def rule_installed(text: str) -> bool:
    return RULE_ID in rule_ids(text) and ini_group(text, RULE_ID) is not None


def with_rule(text: str) -> str:
    """``text`` with the shell's group written and its id in the list of ``[General]``; no other
    group is touched."""
    group = ini_remove_group(text, RULE_ID)
    lines = group.splitlines()
    if lines and lines[-1].strip():
        lines.append("")
    lines += rule_group().splitlines()
    out = "\n".join(lines) + "\n"
    ids = [i for i in rule_ids(out) if i != RULE_ID] + [RULE_ID]
    out = ini_set(out, "General", "rules", ",".join(ids))
    return ini_set(out, "General", "count", str(len(ids)))


def without_rule(text: str) -> str:
    """``text`` without the shell's group and without its id in the list; no other group is
    touched."""
    ids = [i for i in rule_ids(text) if i != RULE_ID]
    out = ini_remove_group(text, RULE_ID)
    if ini_get(out, "General", "rules") is not None:
        out = ini_set(out, "General", "rules", ",".join(ids))
        out = ini_set(out, "General", "count", str(len(ids)))
    return out

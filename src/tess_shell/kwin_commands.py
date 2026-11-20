"""The ``kwin`` commands (IPC and CLI > The Command Line, KWin Integration > Loading the script and
Window rules): ``kwin script install | remove | status`` and ``kwin rule show | install | remove``.

None needs a running shell. They read and write KWin's own files (``kwinrc``, ``kwinrulesrc``, the
scripts folder) and ask KWin to reload its configuration over D-Bus, the way the shell's other
control commands talk to the shell: standard library and ``jeepney`` only.

* ``script install`` copies the package to ``<data>/kwin/scripts/tesserae-shell-kwin/``, sets
  ``tesserae-shell-kwinEnabled=true`` under ``[Plugins]`` in ``kwinrc`` and asks KWin to
  reconfigure (mode P: KWin runs the script from login). ``remove`` undoes exactly that.
  ``status`` reports the package, the ``kwinrc`` switch and whether KWin has the script loaded now
  (the answer of a shell that loaded it in mode R, or of mode P).
* ``rule show`` prints the one group the shell owns in ``kwinrulesrc``; ``install`` shows it, asks
  (or takes ``--yes``) and writes that group and its id in ``[General]``; ``remove`` takes exactly
  that group and id out. No other group is ever touched. If KWin cannot be asked to reload after
  the write, the file is put back as it was and the command says why (``--no-reload`` skips the
  call).

Safety. Every path is an argument that defaults from the real XDG folders; a process that is a test
(``PYTEST_CURRENT_TEST``) refuses a path under the real home and a bus that is not private
(``services.kwin_package``), so a test names temporary files and a private bus.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tess_shell.client import Failure, session_address
from tess_shell.exit_codes import ExitCode
from tess_shell.options import Options
from tess_shell.services.kwin_package import (
    PACKAGE_ID,
    RULE_ID,
    RefusedInTest,
    config_home,
    ini_get,
    ini_group,
    ini_remove_key,
    ini_set,
    install_package,
    installed_folder,
    installed_main,
    parse_version,
    refuse_real_bus,
    refuse_real_path,
    remove_package,
    rule_group,
    rule_installed,
    scripts_folder,
    with_rule,
    without_rule,
    write_text_atomically,
)

KWIN = "org.kde.KWin"
SCRIPTING_INTERFACE = "org.kde.kwin.Scripting"  # lower case ``kwin``: libkwin's adaptor name
ENABLED_KEY = f"{PACKAGE_ID}Enabled"


class Paths:
    """The files the commands act on; each defaults from the real XDG folders."""

    def __init__(
        self,
        rules: Path | None = None,
        kwinrc: Path | None = None,
        scripts: Path | None = None,
    ) -> None:
        self.rules = rules or config_home() / "kwinrulesrc"
        self.kwinrc = kwinrc or config_home() / "kwinrc"
        self.scripts = scripts or scripts_folder()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise Failure(ExitCode.ENVIRONMENT, f"cannot read {path}: {exc.strerror}") from exc


def _write(path: Path, text: str) -> None:
    try:
        write_text_atomically(path, text)
    except OSError as exc:
        raise Failure(ExitCode.ENVIRONMENT, f"cannot write {path}: {exc.strerror}") from exc


def _guard_path(path: Path, what: str) -> None:
    try:
        refuse_real_path(path, what)
    except RefusedInTest as exc:
        raise Failure(ExitCode.CONFIG, str(exc)) from exc


# -- KWin over D-Bus (blocking jeepney, like the control commands) ------------------------------


class KWinBus:
    """One connection to the session bus for the calls of one command."""

    def __init__(self, timeout: float) -> None:
        from jeepney.io.blocking import open_dbus_connection

        self.timeout = timeout
        address = session_address()
        try:
            refuse_real_bus(address)
        except RefusedInTest as exc:
            raise Failure(ExitCode.CONFIG, str(exc)) from exc
        try:
            self.connection = open_dbus_connection(bus=address, enable_fds=False)
        except (OSError, KeyError, ValueError) as exc:
            raise Failure(ExitCode.ENVIRONMENT, f"cannot reach the session bus ({exc})") from exc

    def close(self) -> None:
        self.connection.close()

    def call(
        self,
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: Sequence[Any] = (),
        *,
        reply: bool = True,
    ) -> tuple[Any, ...]:
        """The reply's values. Raises :class:`Failure` when KWin is not on the bus, answers with an
        error or does not answer. ``reply=False`` is a call KWin does not answer."""
        from jeepney import DBusAddress, HeaderFields, MessageType, new_method_call
        from jeepney.low_level import MessageFlag

        message = new_method_call(
            DBusAddress(path, bus_name=KWIN, interface=interface), member, signature, tuple(body)
        )
        try:
            if not reply:
                message.header.flags |= MessageFlag.no_reply_expected
                self.connection.send(message)
                return ()
            got = self.connection.send_and_get_reply(message, timeout=self.timeout)
        except TimeoutError as exc:
            raise Failure(
                ExitCode.TIMEOUT, f"KWin did not answer {member} within {self.timeout:g} s"
            ) from exc
        except OSError as exc:
            raise Failure(ExitCode.ENVIRONMENT, f"lost the session bus ({exc})") from exc
        if got.header.message_type == MessageType.error:
            name = got.header.fields.get(HeaderFields.error_name, "")
            if name.endswith(("ServiceUnknown", "NameHasNoOwner")):
                raise Failure(ExitCode.NOT_RUNNING, f"{KWIN} is not on the session bus")
            text = str(got.body[0]) if got.body else ""
            raise Failure(ExitCode.CONFIG, f"KWin answered {member} with {name}: {text}")
        return tuple(got.body)

    def reconfigure(self) -> None:
        """Ask KWin to read its configuration again (``/KWin reconfigure``, a call with no
        answer)."""
        self.call("/KWin", KWIN, "reconfigure", reply=False)

    def version(self) -> str | None:
        (text,) = self.call("/KWin", KWIN, "supportInformation")
        return parse_version(str(text))

    def loaded(self) -> bool:
        (value,) = self.call("/Scripting", SCRIPTING_INTERFACE, "isScriptLoaded", "s", [PACKAGE_ID])
        return bool(value)

    def unload(self) -> bool:
        (value,) = self.call("/Scripting", SCRIPTING_INTERFACE, "unloadScript", "s", [PACKAGE_ID])
        return bool(value)


def _emit(options: Options, text: str, data: dict[str, Any]) -> None:
    print(json.dumps(data) if options.json else text)


def _ask(question: str, yes: bool) -> bool:
    if yes:
        return True
    if not sys.stdin.isatty():
        raise Failure(
            ExitCode.CONFIG, "this changes KWin's files: ask from a terminal or add --yes"
        )
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


# -- kwin rule ----------------------------------------------------------------------------------


def rule_show(paths: Paths, options: Options) -> int:
    text = _read(paths.rules)
    installed = rule_installed(text)
    group = rule_group()
    _emit(
        options,
        f"# {paths.rules}: {'installed' if installed else 'not installed'}\n"
        "# this group, and its id in the [General] 'rules' list, is what 'kwin rule install'"
        f" writes:\n{group}",
        {"file": str(paths.rules), "installed": installed, "group": group, "id": RULE_ID},
    )
    return int(ExitCode.OK)


def _reload_or_restore(path: Path, before: str, options: Options, reload: bool) -> str:
    """Ask KWin to reload; on failure put ``path`` back as it was. The words about the reload."""
    if not reload:
        return "KWin was not asked to reload (--no-reload)"
    bus: KWinBus | None = None
    try:
        bus = KWinBus(options.timeout)
        bus.version()  # a call that is answered: KWin is on the bus (a reconfigure is not answered)
        bus.reconfigure()
    except Failure as failure:
        _write(path, before)
        raise Failure(
            failure.code,
            f"{failure.message}; {path.name} was left as it was (--no-reload writes it anyway)",
        ) from failure
    finally:
        if bus is not None:
            bus.close()
    return "KWin was asked to reload its configuration"


def rule_install(paths: Paths, options: Options, yes: bool, reload: bool) -> int:
    _guard_path(paths.rules, "kwin rule install")
    before = _read(paths.rules)
    if not _ask(f"Write this rule to {paths.rules}?\n{rule_group()}", yes):
        raise Failure(ExitCode.CONFIG, "nothing written")
    after = with_rule(before)
    changed = after != before
    if changed:
        _write(paths.rules, after)
    note = _reload_or_restore(paths.rules, before, options, reload and changed)
    message = (
        f"the rule {RULE_ID} is {'written' if changed else 'already'} in {paths.rules}; {note}"
    )
    _emit(options, message, {"ok": True, "file": str(paths.rules), "changed": changed})
    return int(ExitCode.OK)


def rule_remove(paths: Paths, options: Options, reload: bool) -> int:
    _guard_path(paths.rules, "kwin rule remove")
    before = _read(paths.rules)
    if not rule_installed(before) and ini_group(before, RULE_ID) is None:
        _emit(
            options,
            f"the rule {RULE_ID} is not in {paths.rules}; nothing to remove",
            {"ok": True, "file": str(paths.rules), "changed": False},
        )
        return int(ExitCode.OK)
    _write(paths.rules, without_rule(before))
    note = _reload_or_restore(paths.rules, before, options, reload)
    _emit(
        options,
        f"the rule {RULE_ID} is removed from {paths.rules}; {note}",
        {"ok": True, "file": str(paths.rules), "changed": True},
    )
    return int(ExitCode.OK)


# -- kwin script --------------------------------------------------------------------------------


def script_status(paths: Paths, options: Options) -> int:
    installed = installed_main(paths.scripts).is_file()
    enabled = ini_get(_read(paths.kwinrc), "Plugins", ENABLED_KEY) == "true"
    data: dict[str, Any] = {
        "package": str(installed_folder(paths.scripts)),
        "installed": installed,
        "enabled": enabled,
        "kwin": None,
        "loaded": None,
        "reachable": False,
    }
    lines = [
        f"package: {'installed at ' + data['package'] if installed else 'not installed'}",
        f"enabled in kwinrc ({paths.kwinrc}): {'yes' if enabled else 'no'}",
    ]
    bus: KWinBus | None = None
    try:
        bus = KWinBus(options.timeout)
        data["kwin"], data["loaded"], data["reachable"] = bus.version(), bus.loaded(), True
        lines.append(f"KWin {data['kwin'] or '(version unknown)'} on the session bus")
        lines.append(
            "loaded in KWin now: "
            + ("yes" if data["loaded"] else "no (a running shell in mode R loads it at start)")
        )
    except Failure as failure:
        data["error"] = failure.message
        lines.append(f"KWin: not reached ({failure.message})")
    finally:
        if bus is not None:
            bus.close()
    _emit(options, "\n".join(lines), data)
    return int(ExitCode.OK)


def script_install(paths: Paths, options: Options, reload: bool) -> int:
    _guard_path(paths.scripts, "kwin script install")
    _guard_path(paths.kwinrc, "kwin script install")
    before = _read(paths.kwinrc)
    folder = install_package(paths.scripts)
    after = ini_set(before, "Plugins", ENABLED_KEY, "true")
    if after != before:
        _write(paths.kwinrc, after)
    note = _reload_or_restore(paths.kwinrc, before, options, reload)
    _emit(
        options,
        f"the script is installed at {folder} and enabled in {paths.kwinrc}; {note}. "
        "'tesserae-shell kwin script status' says whether KWin has it loaded",
        {"ok": True, "package": str(folder), "kwinrc": str(paths.kwinrc)},
    )
    return int(ExitCode.OK)


def script_remove(paths: Paths, options: Options, reload: bool) -> int:
    _guard_path(paths.scripts, "kwin script remove")
    _guard_path(paths.kwinrc, "kwin script remove")
    before = _read(paths.kwinrc)
    after = ini_remove_key(before, "Plugins", ENABLED_KEY)
    if after != before:
        _write(paths.kwinrc, after)
    removed = remove_package(paths.scripts)
    note = "KWin was not asked to reload (--no-reload)"
    if reload:
        bus: KWinBus | None = None
        try:
            bus = KWinBus(options.timeout)
            try:
                bus.unload()  # a script KWin runs now stops at once
            except Failure:
                pass
            bus.reconfigure()
            note = "KWin was asked to unload it and to reload its configuration"
        except Failure as failure:
            note = f"KWin was not reached ({failure.message}); the script stops at the next login"
        finally:
            if bus is not None:
                bus.close()
    _emit(
        options,
        f"the script is {'removed' if removed else 'not installed'}; {ENABLED_KEY} is out of "
        f"{paths.kwinrc}; {note}",
        {"ok": True, "removed": removed, "kwinrc": str(paths.kwinrc)},
    )
    return int(ExitCode.OK)


# -- the entry point ----------------------------------------------------------------------------


def run(args: Any, options: Options) -> int:
    """``args`` is the parsed command line: ``group`` (``script`` or ``rule``), ``action`` and the
    flags ``rules_file``, ``kwinrc``, ``scripts_dir``, ``yes``, ``no_reload``."""
    paths = Paths(args.rules_file, args.kwinrc, args.scripts_dir)
    reload = not args.no_reload
    try:
        if args.group == "rule":
            if args.action == "show":
                return rule_show(paths, options)
            if args.action == "install":
                return rule_install(paths, options, args.yes, reload)
            return rule_remove(paths, options, reload)
        if args.action == "status":
            return script_status(paths, options)
        if args.action == "install":
            return script_install(paths, options, reload)
        return script_remove(paths, options, reload)
    except Failure as failure:
        if options.json:
            print(json.dumps({"ok": False, "error": failure.message, "exit": int(failure.code)}))
        else:
            print(f"tesserae-shell: {failure.message}", file=sys.stderr)
        return int(failure.code)

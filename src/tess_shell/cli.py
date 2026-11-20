"""The ``tesserae-shell`` command line.

Heavy imports (the engine, Loguru, the loader) happen inside the commands that need them so that
``version`` and the control commands stay light: a control command imports only the standard
library and ``jeepney`` (``tess_shell.client``).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from tess_shell.exit_codes import ExitCode
from tess_shell.options import Options

if TYPE_CHECKING:
    from tess_shell.session import Runner

# the control commands: name -> (help, positional arguments as (name, nargs)); each is a client of
# the running shell's D-Bus interface (``tess_shell.client``)
_CONTROL: dict[str, tuple[str, list[tuple[str, str | None]]]] = {
    "reload": ("reload the running shell and report the errors", []),
    "quit": ("stop the running shell", []),
    "status": ("show the running shell's state (--json: the shell's own JSON)", []),
    "show": ("show a Panel or a Frame by its Name", [("name", None)]),
    "hide": ("hide a Panel or a Frame by its Name", [("name", None)]),
    "toggle": ("toggle a Panel or a Frame by its Name", [("name", None)]),
    "call": (
        "call a module's @action (each ARG a JSON value, or text)",
        [("module", None), ("action", None), ("args", "*")],
    ),
    "log-level": ("change the log level until the next reload of settings.tdl", [("level", None)]),
}
# the ``kwin`` commands (``tess_shell.kwin_commands``): group, then action
_KWIN: dict[str, tuple[str, dict[str, str]]] = {
    "script": (
        "the shell's KWin script, installed for KWin to run from login (mode P)",
        {
            "install": "copy the script to KWin's scripts folder and enable it in kwinrc",
            "remove": "take the script and its kwinrc switch away",
            "status": "report the package, the kwinrc switch and whether KWin has it loaded",
        },
    ),
    "rule": (
        "the one window rule that keeps the shell's surfaces above Plasma panels (opt-in)",
        {
            "show": "print the rule group the shell would write to kwinrulesrc",
            "install": "write that group (shows it and asks first, or takes --yes)",
            "remove": "take exactly that group out of kwinrulesrc",
        },
    ),
}


def _parent() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--config-dir", type=Path, metavar="PATH", help="configuration directory")
    parent.add_argument("--json", action="store_true", help="machine readable output")
    parent.add_argument("--quiet", action="store_true", help="only warnings and errors")
    parent.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="how long a control command waits for the shell (default 5)",
    )
    return parent


def _build_parser() -> argparse.ArgumentParser:
    # Options are defined once and attached to the main parser and every subparser. Subparser
    # defaults are SUPPRESS so a value given before the subcommand is not overwritten.
    parent = _parent()
    parser = argparse.ArgumentParser(prog="tesserae-shell", parents=[parent])
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    def add(name: str, help_: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_, parents=[parent])
        for action in p._actions:
            if action.dest in {"config_dir", "json", "quiet", "timeout"}:
                action.default = argparse.SUPPRESS
        return p

    add("run", "start the shell (default)")
    migrate = add(
        "migrate",
        "bring the configuration files to the current format (--check lists what would change)",
    )
    migrate.add_argument(
        "--check", action="store_true", help="change nothing; exit 1 if any file would change"
    )
    migrate.add_argument(
        "--force", action="store_true", help="migrate even while a shell is running"
    )
    check = add("check", "validate settings and shell files")
    check.add_argument(
        "--strict", action="store_true", help="a warning fails the check too (exit code 1)"
    )
    check.add_argument(
        "--import-modules",
        action="store_true",
        help="also import your modules' Python in throwaway processes (runs its top-level code)",
    )
    add("version", "print versions")
    schema = add("schema", "print the schema of the shell's files as JSON (with --json)")
    schema.add_argument(
        "--out", type=Path, metavar="FILE", help="write the JSON to FILE, not to standard output"
    )
    install = add(
        "install-session",
        "write the desktop file and the systemd user unit (--enable, --remove, --print)",
    )
    what = install.add_mutually_exclusive_group()
    what.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="show both files and their paths, write nothing",
    )
    what.add_argument(
        "--enable",
        action="store_true",
        help="also run systemctl --user enable tesserae-shell.service",
    )
    what.add_argument(
        "--remove",
        action="store_true",
        help="disable the unit if it is enabled and remove both files",
    )
    install.add_argument(
        "--force", action="store_true", help="replace an existing file that has other content"
    )
    for name, (control_help, control_positionals) in _CONTROL.items():
        p = add(name, control_help)
        for arg, nargs in control_positionals:
            if nargs is None:
                p.add_argument(arg)
            else:
                p.add_argument(arg, nargs=nargs)
    kwin = add("kwin", "KWin helpers: the script and the window rule (no shell needs to run)")
    groups = kwin.add_subparsers(dest="group", metavar="GROUP", required=True)
    for group, (group_help, actions) in _KWIN.items():
        group_parser = groups.add_parser(group, help=group_help)
        action_parsers = group_parser.add_subparsers(dest="action", metavar="ACTION", required=True)
        for action_name, action_help in actions.items():
            p = action_parsers.add_parser(action_name, help=action_help, parents=[parent])
            for option in p._actions:
                if option.dest in {"config_dir", "json", "quiet", "timeout"}:
                    option.default = argparse.SUPPRESS
            p.set_defaults(
                rules_file=None, kwinrc=None, scripts_dir=None, yes=False, no_reload=False
            )
            if group == "rule":
                p.add_argument(
                    "--rules-file", type=Path, metavar="PATH", help="the rule file (kwinrulesrc)"
                )
            else:
                p.add_argument("--kwinrc", type=Path, metavar="PATH", help="KWin's kwinrc")
                p.add_argument(
                    "--scripts-dir", type=Path, metavar="PATH", help="KWin's scripts folder"
                )
            if action_name != "show" and action_name != "status":
                p.add_argument(
                    "--no-reload", action="store_true", help="do not ask KWin to reload afterwards"
                )
            if (group, action_name) == ("rule", "install"):
                p.add_argument("--yes", action="store_true", help="write without asking")
    return parser


def _versions() -> dict[str, str]:
    from tess_shell.commands import versions

    return versions()


def _version(options: Options) -> int:
    try:
        versions = _versions()
    except Exception as exc:  # an import or metadata failure
        print(f"tesserae-shell: dependency unavailable ({exc})", file=sys.stderr)
        return ExitCode.ENVIRONMENT
    if options.json:
        from tess_shell.config.paths import config_dir

        # the folder the shell would read (``--config-dir``, else the XDG one), so a tool that
        # drives the command knows which folder its answer is about
        print(json.dumps({**versions, "config_dir": str(config_dir(options.config_dir))}))
    else:
        names = {"shell": "tesserae-shell"}
        for key, value in versions.items():
            print(f"{names.get(key, key)} {value}")
    return ExitCode.OK


def _schema(options: Options, out: Path | None) -> int:
    """The shell's schema as JSON on standard output, or in the file ``--out`` names. JSON is the
    only form, so ``--json`` is asked for; a bare ``schema`` is kept for another form."""
    if not options.json:
        print("tesserae-shell: schema writes JSON only; add --json", file=sys.stderr)
        return ExitCode.CONFIG
    from tess_shell.schema.export import schema_json

    text = schema_json()
    if out is None:
        sys.stdout.write(text)
        return ExitCode.OK
    try:
        out.write_text(text, encoding="utf-8")
    except OSError as exc:
        print(f"tesserae-shell: cannot write {out}: {exc.strerror}", file=sys.stderr)
        return ExitCode.ENVIRONMENT
    return ExitCode.OK


def _install_session(args: argparse.Namespace, options: Options, runner: Runner | None) -> int:
    from tess_shell import session

    return session.run_command(
        print_only=args.print_only,
        enable=args.enable,
        remove_files=args.remove,
        force=args.force,
        json_out=options.json,
        config_dir=options.config_dir,
        runner=runner,
    )


def _migrate(args: argparse.Namespace, options: Options) -> int:
    from tess_shell.migrate import run as migrate_run

    return migrate_run.run(options, check=args.check, force=args.force)


def main(argv: Sequence[str] | None = None, *, runner: Runner | None = None) -> int:
    """``runner`` is the hook of ``install-session``: what would run ``systemctl --user ...``.
    Tests pass a recording one; a run from the command line uses the real one."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    options = Options(
        config_dir=getattr(args, "config_dir", None),
        json=getattr(args, "json", False),
        quiet=getattr(args, "quiet", False),
        timeout=getattr(args, "timeout", 5.0),
        strict=getattr(args, "strict", False),
        import_modules=getattr(args, "import_modules", False),
    )
    command = args.command or "run"
    from tess_shell.schema.deprecations import command_warning

    warning = command_warning(command)
    if warning is not None:
        print(warning, file=sys.stderr)
    if command == "version":
        return _version(options)
    if command == "schema":
        return _schema(options, getattr(args, "out", None))
    if command == "migrate":
        return _migrate(args, options)
    if command == "install-session":
        return _install_session(args, options, runner)
    if command in _CONTROL:
        from tess_shell import client

        return client.run(command, args, options)
    if command == "kwin":
        from tess_shell import kwin_commands

        return kwin_commands.run(args, options)
    from tess_shell import app

    return app.check(options) if command == "check" else app.run(options)

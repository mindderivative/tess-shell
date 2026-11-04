"""The ``tesserae-shell`` command line.

Heavy imports (the engine, Loguru, the loader) happen inside the commands that need them so that
``version`` stays light.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tess_shell import __version__
from tess_shell.exit_codes import ExitCode
from tess_shell.options import Options

# name -> (help, positional arguments as (name, nargs), optional flags)
_STUBS: dict[str, tuple[str, list[tuple[str, str | None]], list[str]]] = {
    "schema": ("write the JSON schemas", [], ["--out"]),
    "reload": ("reload the running shell", [], []),
    "quit": ("stop the running shell", [], []),
    "status": ("show the running shell's state", [], []),
    "show": ("show a surface", [("name", None)], []),
    "hide": ("hide a surface", [("name", None)], []),
    "toggle": ("toggle a surface", [("name", None)], []),
    "call": (
        "call a module action",
        [("module", None), ("action", None), ("args", "*")],
        [],
    ),
    "log-level": ("change the log level", [("level", None)], []),
    "kwin": ("KWin helpers", [("args", "*")], []),
}


def _parent() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--config-dir", type=Path, metavar="PATH", help="configuration directory")
    parent.add_argument("--json", action="store_true", help="machine readable output")
    parent.add_argument("--quiet", action="store_true", help="only warnings and errors")
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
            if action.dest in {"config_dir", "json", "quiet"}:
                action.default = argparse.SUPPRESS
        return p

    add("run", "start the shell (default)")
    add("check", "validate settings and shell files")
    add("version", "print versions")
    for name, (help_, positionals, flags) in _STUBS.items():
        p = add(name, help_)
        for arg, nargs in positionals:
            if nargs is None:
                p.add_argument(arg)
            else:
                p.add_argument(arg, nargs=nargs)
        for flag in flags:
            p.add_argument(flag)
    return parser


def _versions() -> dict[str, str]:
    from importlib.metadata import version

    import tess_dl
    import tess_el

    return {
        "shell": __version__,
        "tess_re": version("tesserae-engine"),
        "tess_el": tess_el.__version__,
        "tess_dl": tess_dl.__version__,
        "python": ".".join(map(str, sys.version_info[:3])),
    }


def _version(options: Options) -> int:
    try:
        versions = _versions()
    except Exception as exc:  # an import or metadata failure
        print(f"tesserae-shell: dependency unavailable ({exc})", file=sys.stderr)
        return ExitCode.ENVIRONMENT
    if options.json:
        print(json.dumps(versions))
    else:
        names = {"shell": "tesserae-shell"}
        for key, value in versions.items():
            print(f"{names.get(key, key)} {value}")
    return ExitCode.OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    options = Options(
        config_dir=getattr(args, "config_dir", None),
        json=getattr(args, "json", False),
        quiet=getattr(args, "quiet", False),
    )
    command = args.command or "run"
    if command == "version":
        return _version(options)
    if command in _STUBS:
        print(f"tesserae-shell: '{command}' is not implemented in M0", file=sys.stderr)
        return ExitCode.CONFIG
    from tess_shell import app

    return app.check(options) if command == "check" else app.run(options)

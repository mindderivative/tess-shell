import json
import subprocess
import sys

import pytest

from tess_shell.cli import main


def _module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tess_shell", *args], capture_output=True, text=True, check=False
    )


def test_version_script_and_module_agree() -> None:
    script = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from tess_shell.cli import main; sys.exit(main())",
            "version",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    module = _module("version")
    assert script.returncode == module.returncode == 0
    assert script.stdout == module.stdout
    assert len(module.stdout.splitlines()) == 5


def test_version_json_keys() -> None:
    out = _module("version", "--json").stdout
    assert set(json.loads(out)) == {
        "shell",
        "tess_re",
        "tess_el",
        "tess_dl",
        "python",
        "config_dir",
    }


def test_stub_command_reports_not_implemented(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["kwin"]) == 1
    assert "'kwin' is not implemented in M0" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--json", "version"], ["version", "--json"]])
def test_global_options_before_or_after_subcommand(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["shell"]

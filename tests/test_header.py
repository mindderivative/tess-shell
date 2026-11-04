import tess_dl

from tess_shell.files.header import check_header, parse_version

INSTALLED = {"Shell": "0.1.0.dev0", "TRE": "0.6.1", "TEL": "0.1.2"}


def doc(meta: str, root: str = "Shell") -> tess_dl.Document:
    result = tess_dl.parse(f"---\nTDL: 0.1\nName: X\n{meta}---\n{root} {{\n}}\n")
    assert result.document is not None
    return result.document


def test_version_parsing_ignores_dev_suffixes() -> None:
    assert parse_version("0.1.0.dev0") == (0, 1, 0)
    assert parse_version("0.6.1") == (0, 6, 1)
    assert parse_version("0.5.9") < parse_version("0.6.0")


def test_pins_that_are_met_pass() -> None:
    assert check_header(doc("Shell: 0.1\nTRE: 0.5.9\nTEL: 0.1\n"), "a_Shell.tdl", INSTALLED) == []


def test_a_pin_above_the_installed_version_is_an_error() -> None:
    (f,) = check_header(doc("TRE: 0.7.0\n"), "a_Shell.tdl", INSTALLED)
    assert f.rule == "version-pin" and "TRE 0.7.0" in f.message and "0.6.1" in f.message


def test_root_block_must_agree_with_the_suffix() -> None:
    (f,) = check_header(doc("", root="Module"), "Shells/Clock_Shell.tdl", INSTALLED)
    assert f.rule == "shell-root-suffix"
    assert "Module" in f.message and "_Shell.tdl" in f.message
    assert (f.line, f.column) == (5, 1)


def test_a_matching_root_passes() -> None:
    assert check_header(doc("", root="Shell"), "Shells/Main_Shell.tdl", INSTALLED) == []

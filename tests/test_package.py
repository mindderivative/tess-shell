from importlib.metadata import version

import tess_shell


def test_version_matches_metadata() -> None:
    assert tess_shell.__version__ == version("tesserae-shell")

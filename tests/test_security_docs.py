"""The user-facing statement of the Security Model is in the guide and the README word for word,
and every finding code the security controls add is explained in the troubleshooting page."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# the wording decided with posture A (Security Model > The User-Facing Statement)
STATEMENT = (
    "A module is Python that runs inside the shell with your rights. It can read your files and "
    "start programs. Write modules yourself or read them before you add them. TDL files cannot "
    "run code. Keep your configuration folder writable by you only: the shell warns if it is not."
)


@pytest.mark.parametrize("page", ["guide/02-configuration-folder.md", "README.md"])
def test_the_statement_is_in_the_guide_and_the_readme_word_for_word(page: str) -> None:
    text = " ".join((ROOT / page).read_text(encoding="utf-8").split())
    assert STATEMENT in text


@pytest.mark.parametrize(
    "code", ["insecure-permissions", "path-outside-config", "slow-module", "many-threads"]
)
def test_every_security_code_is_explained_in_the_troubleshooting_page(code: str) -> None:
    page = (ROOT / "guide" / "10-troubleshooting.md").read_text(encoding="utf-8")
    assert f"`{code}`" in page

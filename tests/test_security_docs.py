"""The user-facing statement of the Security Model is in the guide and the README word for word,
and every finding code the security controls add is explained in the troubleshooting page."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# the wording of posture C, decided 2026-11-19 (Security Model > The User-Facing Statement): the
# shell's own modules run in it, a user module in a process of its own, which is not a sandbox
STATEMENT = (
    "A module is Python that runs with your rights. The modules that ship with the shell run "
    "inside it; a module you write or add runs in a process of its own, so a module that hangs "
    "or crashes does not freeze your bars. That is not a sandbox: it can still read your files "
    "and start programs. Write modules yourself or read them before you add them. TDL files "
    "cannot run code. Keep your configuration folder writable by you only: the shell warns if "
    "it is not."
)


@pytest.mark.parametrize("page", ["guide/02-configuration-folder.md", "README.md"])
def test_the_statement_is_in_the_guide_and_the_readme_word_for_word(page: str) -> None:
    text = " ".join((ROOT / page).read_text(encoding="utf-8").split())
    assert STATEMENT in text


@pytest.mark.parametrize(
    "code",
    [
        "insecure-permissions",
        "path-outside-config",
        "slow-module",
        "many-threads",
        "module-process",
        "module-actions",
    ],
)
def test_every_security_code_is_explained_in_the_troubleshooting_page(code: str) -> None:
    page = (ROOT / "guide" / "10-troubleshooting.md").read_text(encoding="utf-8")
    assert f"`{code}`" in page

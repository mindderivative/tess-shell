"""Build hook: the wheel carries a compiled ``tess_utils`` (``src/tess_shell/_vendor``), so it is a
platform wheel (CPython 3.14, x86-64 Linux), not a pure-Python one (maintainer, 2026-11-08).

The tag is ``manylinux_2_36``, not the ``linux_x86_64`` that hatchling infers from the build
machine, because PyPI accepts only manylinux tags. ``auditwheel show`` on the built wheel (2026-11-15)
says the compiled file is consistent with ``manylinux_2_36`` and no older one: it asks for glibc
2.14 symbols at most but also for ``GLIBC_ABI_DT_RELR`` (packed relative relocations, glibc 2.36),
which the toolchain that built it emits. The release workflow runs ``auditwheel show`` and fails
when the wheel is consistent with nothing as old as its tag, so a mislabelled wheel is never
uploaded. A lower tag (more users) needs tess_utils rebuilt in an older manylinux image: tess-utils
is the maintainer's repository.
"""

from __future__ import annotations

from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class PlatformWheelHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        build_data["pure_python"] = False
        build_data["tag"] = "cp314-cp314-manylinux_2_36_x86_64"

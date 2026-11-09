"""Build hook: the wheel carries a compiled ``tess_utils`` (``src/tess_shell/_vendor``), so it is a
platform wheel (CPython 3.14, this platform), not a pure-Python one (maintainer, 2026-11-08)."""

from __future__ import annotations

from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class PlatformWheelHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        build_data["pure_python"] = False
        build_data["infer_tag"] = True

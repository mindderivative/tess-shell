"""What the desktop says about its look (Portals > The Settings Portal): one small value type
shared by the portal reader, which fills it, and the theme resolver, which reads it. Standard
library only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Scheme = Literal["default", "dark", "light"]


@dataclass(frozen=True, slots=True)
class Appearance:
    scheme: Scheme = "default"  # no preference: the theme's default variant
    accent: tuple[int, int, int] | None = None  # sRGB, 0 to 255
    high_contrast: bool = False
    reduced_motion: bool = False

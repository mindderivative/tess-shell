"""What the desktop says about its look (Portals > The Settings Portal): one small value type
shared by the portal reader, which fills it, and the theme resolver, which reads it. Standard
library only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Scheme = Literal["default", "dark", "light"]
Density = Literal["default", "compact", "dense"]  # Spacing and Density (ADR-0002)


@dataclass(frozen=True, slots=True)
class Appearance:
    scheme: Scheme = "default"  # no preference: the theme's default variant
    accent: tuple[int, int, int] | None = None  # sRGB, 0 to 255
    high_contrast: bool = False
    _reduced_motion_key: bool = False  # the portal's ``reduced-motion`` is 1 (portal reader only)
    animations: bool = True  # ``org.gnome.desktop.interface`` ``enable-animations``
    icon_theme: str | None = None  # ``org.gnome.desktop.interface`` ``icon-theme``
    font_family: str | None = None  # the family of ``org.gnome.desktop.interface`` ``font-name``
    # the density level of the sizes a module reads (``density.*`` tokens): the shell's own setting
    # (``Appearance.Density``), never the desktop's, so it is kept when the portal speaks
    density: Density = "compact"
    # ``Appearance.Scheme`` of settings.tdl when it is LIGHT or DARK: the user's own choice, which
    # the desktop's colour scheme does not change (``scheme`` above is then this)
    scheme_override: Scheme | None = None

    @property
    def reduced_motion(self) -> bool:
        """No animation: either the desktop's reduced-motion preference or its animations switch
        says so (Portals > Settings Read in M5h). The one public flag; the portal's single key
        behind it is private."""
        return self._reduced_motion_key or not self.animations

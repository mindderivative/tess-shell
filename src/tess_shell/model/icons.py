"""Icon names that arrive at run time (Standard Modules > Icon; Battery Module).

``Icon: "mdi:home"`` written in a file is looked up when the file is read. ``Icon: {{ icon }}``
is a name a module sends: it is looked up here each time the slot is evaluated, through the same
icon sets, so a name that works written works sent. A name no set has shows the
``image-broken-variant`` icon, with one warning naming it (once for each name, however often it is
sent); an empty name shows nothing. A document (text that starts with ``<``) is used as it is.

Imports nothing but the schema's ``IconSource`` protocol and ``loguru``; never ``tess_re``.
"""

from __future__ import annotations

from loguru import logger

from tess_shell.schema.model import IconSource

FALLBACK = "mdi:image-broken-variant"
EMPTY = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'></svg>"


class RuntimeIcons:
    def __init__(self, source: IconSource) -> None:
        self._source = source
        self._warned: set[str] = set()

    def document(self, name: str, *, blank: str = EMPTY) -> str:
        """The SVG document for ``name``. ``blank`` is what an empty name gives."""
        if not name:
            return blank
        if name.startswith("<"):
            return name
        found = self._source.lookup(name)
        if found is not None:
            return found
        if name not in self._warned:
            self._warned.add(name)
            close = self._source.nearest(name)
            hint = f" (did you mean {', '.join(close)}?)" if close else ""
            logger.warning(f"no icon named {name}{hint}; showing the broken-image icon")
        return self._source.lookup(FALLBACK) or blank

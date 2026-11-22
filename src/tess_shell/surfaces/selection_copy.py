"""Ctrl+C on a selectable Text (Text Selection > Keyboard, AC-SEL-1, AC-SEL-4).

The engine selects the text of a ``Selectable`` Text with the pointer and keeps the selection
(``selection``: a pair of byte offsets). The shell copies it: the pieces of every selected text of
the surface, in tree order and joined with a newline, go to the clipboard. A text input keeps its
own selection and its own copy, so nothing is copied while one has the focus.
"""

from __future__ import annotations

from typing import Any

from loguru import logger


def selected_text(root: Any) -> str:
    """What is selected in the selectable texts under ``root``, in tree order, one per line."""
    pieces: list[str] = []
    stack = [root]
    while stack:
        node = stack.pop()
        try:
            kind = node.get("kind")
            if kind == "text_input" and node.get("focused"):
                return ""  # the input's selection and copy come first
            selection = node.get("selection") if kind == "text" else None
            if selection is not None:
                start, end = selection
                raw = str(node.get("text")).encode("utf-8")
                piece = raw[start:end].decode("utf-8", errors="ignore")
                if piece:
                    pieces.append(piece)
            stack.extend(reversed(node.children()))
        except ValueError:  # a node that is gone
            continue
    return "\n".join(pieces)


def copy_selection(window: Any, event: Any) -> bool:
    """Ctrl+C: put the selected text of ``window`` on the clipboard. True when it did (the key is
    then used); False for any other key, with nothing selected, or while a text input has focus."""
    if getattr(event, "key", None) != "c" or not getattr(event, "ctrl", False):
        return False
    if any(getattr(event, name, False) for name in ("shift", "alt", "meta")):
        return False
    try:
        text = selected_text(window.root)
        if not text:
            return False
        copied = bool(window.write_clipboard(text))
    except ValueError:
        return False
    logger.debug(f"Ctrl+C copied {len(text)} characters ({'ok' if copied else 'no clipboard'})")
    return copied

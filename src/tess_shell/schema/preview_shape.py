"""The shape of the preview model (``tess_shell.preview``), as data: the schema export carries it
and the preview module returns it from ``describe()``. Bump ``PREVIEW_VERSION`` when a key of the
model is changed or removed."""

from __future__ import annotations

from typing import Any

Json = dict[str, Any]
PREVIEW_VERSION = "1"


def describe() -> Json:
    """The shape of ``PreviewModel.to_dict()``, as the schema export carries it."""
    return {
        "version": PREVIEW_VERSION,
        "entry": "tess_shell.preview.preview(config, overrides=None, outputs=(VirtualOutput(),), "
        "appearance=None)",
        "doc": "What the shell would show for a configuration, as plain data, with the shell's "
        "own pipeline. Nothing opens a window. A configuration with errors still gives what "
        "resolves; `findings` says what did not.",
        "keys": {
            "preview_version": "the version of this shape",
            "findings": "what `check` prints: file, line, column, severity, rule, message, hint",
            "outputs": "name, width, height (logical pixels), scale, description",
            "appearance": "scheme, density, theme (a name or null), stylesheets",
            "tokens": "the theme's tokens by dotted path (colours as #RRGGBB, numbers, words)",
            "shell": "name and file of the main shell, or null when there is none",
            "monitors": "each Monitor block: name, index, connector, description, outputs it "
            "lands on, status",
            "surfaces": "bar, panel and frame, one per Monitor and output: placement, status "
            "(ok or `skipped: reason`), style, blocks",
            "popups": "each Popup of a Monitor as a static card: placement rules, blocks",
            "desktop": "per output, the rectangle windows get after the exclusive zones",
        },
        "block_types": {
            "block": "kind, name, classes, part, props, style, tooltip, children",
            "module": "module, name, label (a placeholder), params (defaults and written, "
            "slots as {slot: text}), common, tooltip, children",
            "if": "condition, children, else",
            "for": "items, children",
        },
        "values": "a length is a number of pixels; auto, expand and enum words are lower-case "
        "text; a percentage is text (`50%`); a colour is #RRGGBB or #RRGGBBAA; a token reference "
        "is {token, value}; a slot is {slot: text}",
    }

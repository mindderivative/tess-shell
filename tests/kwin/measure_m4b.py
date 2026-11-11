"""Frames drawn by the M4b animations on a private sway (not collected by pytest): idle with a Marquee
that fits, an Expander at rest, a Marquee that scrolls (cost per frame) and an Expander opening.

    env -u WAYLAND_DISPLAY -u DISPLAY <PrivateSway env> uv run python tests/kwin/measure_m4b.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import tess_re  # noqa: E402

from tess_shell.binder import model as m  # noqa: E402
from tess_shell.binder.build import build  # noqa: E402
from tess_shell.model.marquee import compose  # noqa: E402
from tests.sway import PrivateSway  # noqa: E402


def run() -> None:
    app = tess_re.App()
    window = tess_re.Window(width=420, height=200)
    app.add_window(window)
    look = {
        "Foreground": m.Color(255, 255, 255, 255),
        "Font_Size": m.Number(14),
    }
    fits = compose(
        m.Node(m.MARQUEE, props={"Text": m.Text("fits"), "Width": m.Length(200)}, style=look)
    )
    text = "a very long text " * 6 if "active" in sys.argv else "short"
    long = compose(
        m.Node(m.MARQUEE, props={"Text": m.Text(text), "Width": m.Length(120)}, style=look)
    )
    body = m.Node(
        "Box",
        name="Fold",
        props={"Height": m.Length(0), "Clip_Children": m.Bool(True)},
        style={"Transition": m.Seq((m.Text("Height"),)), "Duration": m.Number(400)},
        children=(m.Node("Rectangle", props={"Width": m.Length(100), "Height": m.Length(60)}),),
    )
    root = m.Node("FlexBox", props={"Flex": m.Enum("VERTICAL")}, children=(fits, long, body))
    view = build([root], window)
    out: dict[str, object] = {}
    handle = app.thread_handle()

    def stat(label: str) -> None:
        s = window.frame_stats(reset=True)
        out[label] = s["frames"]

    window.after(1500, lambda: stat("settle"))
    window.after(4500, lambda: stat("3 s: Marquees that fit and an Expander at rest"))
    window.after(4600, lambda: view.update([("Fold", "Height", m.Auto())]))
    window.after(5500, lambda: stat("0.9 s: an Expander opening over 0.4 s"))
    window.after(8500, lambda: stat("3 s after it: at rest again"))
    window.after(9000, handle.stop)
    app.run(keep_alive=True)
    for k, v in out.items():
        print(f"{k}: {v} frames drawn")


if __name__ == "__main__":
    sway = PrivateSway().start()
    import os

    os.environ.update(sway.env)
    try:
        run()
    finally:
        sway.stop()

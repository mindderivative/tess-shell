"""Repro (not collected by pytest): a light line on a dark ground looks thinner on a curve than on
a straight, because tre blends the anti-aliased edge in sRGB.

    uv run python tests/kwin/repro_srgb_edge_blend.py

A 2 px band (outer corner radius 16, inner 14: the shape of the Frame's inner border) in #89b4fa
is drawn on #1e1e2e. On the straight sides the band covers whole pixels. On the corner the
band's edges cut pixels: the coverage tre computes is right (the sum of coverage across the band
is 2.0 on both), but an edge pixel is the *sRGB-encoded* mix ``dark + a * (light - dark)``, which
in linear light is much darker than ``a`` of the way to the light colour (a = 0.5 gives 0.31 of
the light). So the band's visible width, measured as the sum of linear-light brightness across
it, is 2.00 on the straight and less on the curve (this script's ray at 45 degrees: 1.63 at
scale 1.0, 1.84 at 1.5; the mean over the whole corner is 1.70 and 1.80): "the border looks
thinner where it rounds". Wanted (a request, not a defect of the coverage): blend
the anti-aliased edge in linear light, or an option for it (colours and the surface format are
8-bit sRGB throughout, tre docs/design/gaps.md).
"""

from __future__ import annotations

import math

import tess_re

SIZE = 80
LIGHT, DARK = (0x89, 0xB4, 0xFA), (0x1E, 0x1E, 0x2E)
# outer rounded rectangle clockwise (radius 16), inner (radius 14, 2 px in) the other way
BAND = (
    "M26,10 L54,10 A16,16 0 0 1 70,26 L70,54 A16,16 0 0 1 54,70 L26,70 A16,16 0 0 1 10,54 "
    "L10,26 A16,16 0 0 1 26,10 Z "
    "M26,12 A14,14 0 0 0 12,26 L12,54 A14,14 0 0 0 26,68 L54,68 A14,14 0 0 0 68,54 "
    "L68,26 A14,14 0 0 0 54,12 Z"
)


def lin(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(c: tuple[int, int, int]) -> float:
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def across(
    rgba: bytes, width: int, scale: float, start: tuple[float, float], d: tuple[float, float]
) -> tuple[float, float]:
    """(sum of coverage, sum of linear-light fraction) along a ray over the band, in logical px;
    the coverage is read from the green channel (linear in the blend), samples are bilinear."""
    span = luminance(LIGHT) - luminance(DARK)
    cov = lum = 0.0
    step = 0.015
    for k in range(int(6 / step)):
        t = -3 + (k + 0.5) * step
        x, y = (start[0] + d[0] * t) * scale - 0.5, (start[1] + d[1] * t) * scale - 0.5
        i, j = math.floor(x), math.floor(y)
        u, v = x - i, y - j
        for di, dj, wt in (
            (0, 0, (1 - u) * (1 - v)),
            (1, 0, u * (1 - v)),
            (0, 1, (1 - u) * v),
            (1, 1, u * v),
        ):
            o = ((j + dj) * width + i + di) * 4
            c = (rgba[o], rgba[o + 1], rgba[o + 2])
            cov += wt * step * (c[1] - DARK[1]) / (LIGHT[1] - DARK[1])
            lum += wt * step * (luminance(c) - luminance(DARK)) / span
    return cov, lum


def main() -> None:
    for scale in (1.0, 1.5):
        window = tess_re.Window(width=SIZE, height=SIZE)
        window.root.set(fill=(*DARK, 255))
        window.root.add_child(
            window.create(
                "path",
                data=BAND,
                fill=(*LIGHT, 255),
                position="absolute",
                left=0,
                top=0,
                width=SIZE,
                height=SIZE,
            )
        )
        rgba, width, _ = window.snapshot(scale=scale)
        side = across(rgba, width, scale, (11, 40), (1, 0))
        # the 45 degree point of the corner whose centre is (26, 26): radius 15 from it
        c = 26 - 15 * math.sqrt(0.5)
        corner = across(rgba, width, scale, (c, c), (math.sqrt(0.5), math.sqrt(0.5)))
        print(
            f"scale {scale}: straight: coverage {side[0]:.2f}, linear light {side[1]:.2f}; "
            f"corner at 45 degrees: coverage {corner[0]:.2f}, linear light {corner[1]:.2f}"
        )
    print("expected if the edge were blended in linear light: linear light equals coverage")


if __name__ == "__main__":
    main()

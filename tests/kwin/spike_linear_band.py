"""Spike (not collected by pytest): does a fill shader that blends a band in linear light make the
band read as wide on a curve as on a straight? (TRE-REQ-015, the option 2 recipe.)

    uv run python tests/kwin/spike_linear_band.py

The shape of ``repro_srgb_edge_blend.py``: a 2 px band (outer corner radius 16, inner 14) in
#89b4fa on #1e1e2e, snapshotted at scale 1.0 and 1.5, drawn two ways: as a ``path`` node (tre's own
blend, in sRGB) and as one opaque box painted by a WGSL fill shader that mixes the two colours in
linear light and writes the encoded result. Measured as the repro does: the sum, along a ray over
the band, of the linear-light brightness (0 at the dark, 1 at the light) in logical pixels; 2.00 is
a 2 px band. Rays: a straight side, the 45 degree ray of the corner, and the mean of rays over the
whole corner (every 5 degrees); the 45 degree ray averaged over 8 phases along the tangent (one
ray alone depends on where it falls on the pixel grid); and the sum over the corner's pixels
against the exact area of the quarter ring, as 2 px times that area (2.000 is exact).

The second table is the band as the real Frame has it: the ring dark on the outside, the opening
open (transparent), composited over a desktop the way a compositor does (straight alpha, in the
encoded values). The border's outer edge is then between two colours the shader paints, the inner
edge against the desktop, which the compositor blends in sRGB whatever the shader writes: only the
outer half of the band is corrected (the rays show the path's inner half at 1.0 because vello's
edge pixels reach further than ``sd_coverage``'s; the area sum, which is the measure that counts,
is 1.69 for the paths and 1.88 for the shader at 1x, 1.79 and 1.93 at 1.5x:
``tests/test_frame_linear.py``).
"""

from __future__ import annotations

import math

import tess_re

SIZE = 80
LIGHT, DARK = (0x89, 0xB4, 0xFA), (0x1E, 0x1E, 0x2E)
BAND = (
    "M26,10 L54,10 A16,16 0 0 1 70,26 L70,54 A16,16 0 0 1 54,70 L26,70 A16,16 0 0 1 10,54 "
    "L10,26 A16,16 0 0 1 26,10 Z "
    "M26,12 A14,14 0 0 0 12,26 L12,54 A14,14 0 0 0 26,68 L54,68 A14,14 0 0 0 68,54 "
    "L68,26 A14,14 0 0 0 54,12 Z"
)
WGSL = """
fn to_lin(c: vec3<f32>) -> vec3<f32> {
    return select(pow((c + 0.055) / 1.055, vec3<f32>(2.4)), c / 12.92, c <= vec3<f32>(0.04045));
}

fn to_srgb(c: vec3<f32>) -> vec3<f32> {
    return select(1.055 * pow(c, vec3<f32>(1.0 / 2.4)) - 0.055, c * 12.92,
                  c <= vec3<f32>(0.0031308));
}

fn shade(p: Pixel) -> vec4<f32> {
    let q = p.px / frame.scale - u.centre;
    let d_centre = sd_round_box(q, u.half_size, u.radius);
    let d_band = (abs(d_centre) - u.half_width) * frame.scale;
    let a = sd_coverage(d_band);
    let lin = mix(to_lin(u.ring.rgb), to_lin(u.band.rgb), a);
    return vec4<f32>(to_srgb(lin), 1.0);
}
"""


def lin(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(c: tuple[int, int, int]) -> float:
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def across(
    rgba: bytes, width: int, scale: float, start: tuple[float, float], d: tuple[float, float]
) -> float:
    """The sum of linear-light fraction along a ray over the band, in logical px (bilinear)."""
    span = luminance(LIGHT) - luminance(DARK)
    total = 0.0
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
            total += wt * step * (luminance(c) - luminance(DARK)) / span
    return total


def window_sum(rgba: bytes, width: int, scale: float) -> float:
    """The linear-light fraction summed over the corner's quarter of the band (the pixels of the
    logical square 10..26) in logical px squared, over the exact area of the quarter ring
    (pi / 4 * (16 ** 2 - 14 ** 2)): 1.0 is a band of exactly 2 px."""
    span = luminance(LIGHT) - luminance(DARK)
    total = 0.0
    for y in range(round(10 * scale), round(26 * scale)):
        for x in range(round(10 * scale), round(26 * scale)):
            o = (y * width + x) * 4
            c = (rgba[o], rgba[o + 1], rgba[o + 2])
            total += (luminance(c) - luminance(DARK)) / span
    return total / scale**2 / (math.pi / 4 * (16**2 - 14**2))


def measure(rgba: bytes, width: int, scale: float) -> tuple[float, float, float, float]:
    """(straight, corner at 45 degrees averaged over a pixel of phases, mean over the corner's
    rays, the corner's area sum over the exact area)."""
    side = across(rgba, width, scale, (11, 40), (1, 0))
    rays = []
    for degrees in range(0, 91, 5):
        a = math.radians(degrees)
        d = (-math.cos(a), -math.sin(a))  # outwards from the corner's centre (26, 26)
        rays.append(across(rgba, width, scale, (26 + 15 * d[0], 26 + 15 * d[1]), d))
    c = 26 - 15 * math.sqrt(0.5)
    r = math.sqrt(0.5)
    phases = [
        across(rgba, width, scale, (c + r * (k / 8 - 0.5), c - r * (k / 8 - 0.5)), (-r, -r))
        for k in range(8)
    ]
    return side, sum(phases) / len(phases), sum(rays) / len(rays), window_sum(rgba, width, scale)


def snapshot(mode: str, scale: float) -> tuple[bytes, int]:
    window = tess_re.Window(width=SIZE, height=SIZE)
    window.root.set(fill=(*DARK, 255))
    if mode == "path":
        node = window.create(
            "path",
            data=BAND,
            fill=(*LIGHT, 255),
            position="absolute",
            left=0,
            top=0,
            width=SIZE,
            height=SIZE,
        )
    else:
        shader = tess_re.Shader(
            WGSL,
            uniforms={
                "centre": (SIZE / 2, SIZE / 2),
                "half_size": (29.0, 29.0),  # the band's centre line: 1 px inside the outer edge
                "radius": 15.0,
                "half_width": 1.0,
                "ring": (*(c / 255 for c in DARK), 1.0),
                "band": (*(c / 255 for c in LIGHT), 1.0),
            },
        )
        node = window.create(
            "box", position="absolute", left=0, top=0, width=SIZE, height=SIZE, shader=shader
        )
    window.root.add_child(node)
    rgba, width, _ = window.snapshot(scale=scale)
    return rgba, width


FRAME_WGSL = """
fn to_lin(c: vec3<f32>) -> vec3<f32> {
    return select(pow((c + 0.055) / 1.055, vec3<f32>(2.4)), c / 12.92, c <= vec3<f32>(0.04045));
}

fn to_srgb(c: vec3<f32>) -> vec3<f32> {
    return select(1.055 * pow(c, vec3<f32>(1.0 / 2.4)) - 0.055, c * 12.92,
                  c <= vec3<f32>(0.0031308));
}

fn shade(p: Pixel) -> vec4<f32> {
    let q = p.px / frame.scale - u.centre;
    let o2 = sd_round_box(q, u.half2, u.r2);        // the opening: where the band starts
    let o3 = sd_round_box(q, u.half3, u.r3);        // inside the band
    let os = sd_round_box(q, u.halfs, u.rs);        // the fill's hole: it runs under the band
    let a_fill = sd_coverage(-os * frame.scale);
    let a_band = sd_coverage(max(o2, -o3) * frame.scale);
    let lin_fill = to_lin(u.ring.rgb);
    let lin_band = to_lin(u.band.rgb);
    // band over fill over nothing, premultiplied in linear light
    let a = a_band + a_fill * (1.0 - a_band);
    let pm = lin_band * a_band + lin_fill * a_fill * (1.0 - a_band);
    return vec4<f32>(to_srgb(pm / max(a, 0.00001)), a);
}
"""
FILL = "M0,0 L80,0 L80,80 L0,80 Z M26,11 A15,15 0 0 0 11,26 L11,54 A15,15 0 0 0 26,69 L54,69 A15,15 0 0 0 69,54 L69,26 A15,15 0 0 0 54,11 Z"


def over(rgba: bytes, backdrop: tuple[int, int, int]) -> bytes:
    """The snapshot composited over ``backdrop`` the way a compositor does: straight alpha, in
    the encoded values."""
    out = bytearray(len(rgba))
    for o in range(0, len(rgba), 4):
        a = rgba[o + 3] / 255
        for k in range(3):
            out[o + k] = round(rgba[o + k] * a + backdrop[k] * (1 - a))
        out[o + 3] = 255
    return bytes(out)


def width_across(
    rgba: bytes,
    width: int,
    scale: float,
    start: tuple[float, float],
    d: tuple[float, float],
    backdrop: tuple[int, int, int],
) -> tuple[float, float]:
    """(outer half, inner half) of the band's apparent width along a ray towards the opening, in
    logical px: each half is the linear-light fraction summed from the middle of the band to the
    dark ring (outer) or to the backdrop (inner); 1.0 each is a 2 px band."""
    halves = [0.0, 0.0]
    base = (DARK, backdrop)
    step = 0.015
    for k in range(int(3 / step)):
        for half, sign in ((0, -1), (1, 1)):
            t = sign * (k + 0.5) * step
            x, y = (start[0] + d[0] * t) * scale - 0.5, (start[1] + d[1] * t) * scale - 0.5
            i, j = math.floor(x), math.floor(y)
            u, v = x - i, y - j
            span = luminance(LIGHT) - luminance(base[half])
            for di, dj, wt in (
                (0, 0, (1 - u) * (1 - v)),
                (1, 0, u * (1 - v)),
                (0, 1, (1 - u) * v),
                (1, 1, u * v),
            ):
                o = ((j + dj) * width + i + di) * 4
                c = (rgba[o], rgba[o + 1], rgba[o + 2])
                halves[half] += wt * step * (luminance(c) - luminance(base[half])) / span
    return halves[0], halves[1]


def frame_snapshot(mode: str, scale: float) -> tuple[bytes, int]:
    window = tess_re.Window(width=SIZE, height=SIZE)
    if mode == "path":
        for data, colour in ((FILL, DARK), (BAND, LIGHT)):
            window.root.add_child(
                window.create(
                    "path",
                    data=data,
                    fill=(*colour, 255),
                    position="absolute",
                    left=0,
                    top=0,
                    width=SIZE,
                    height=SIZE,
                )
            )
    else:
        shader = tess_re.Shader(
            FRAME_WGSL,
            uniforms={
                "centre": (SIZE / 2, SIZE / 2),
                "half2": (30.0, 30.0),
                "r2": 16.0,
                "half3": (28.0, 28.0),
                "r3": 14.0,
                "halfs": (29.0, 29.0),
                "rs": 15.0,
                "ring": (*(c / 255 for c in DARK), 1.0),
                "band": (*(c / 255 for c in LIGHT), 1.0),
            },
        )
        window.root.add_child(
            window.create(
                "box", position="absolute", left=0, top=0, width=SIZE, height=SIZE, shader=shader
            )
        )
    rgba, width, _ = window.snapshot(scale=scale)
    return rgba, width


def frame_main() -> None:
    print("\nthe band on a ring with the opening open (the real Frame), over a backdrop;")
    print("apparent width = outer half + inner half (2.000 is exact), 45 degree ray (8 phases):")
    for scale in (1.0, 1.5):
        for backdrop in (DARK, (0, 0, 0), (128, 128, 128)):
            for mode in ("path", "shader"):
                rgba, width = frame_snapshot(mode, scale)
                flat = over(rgba, backdrop)
                r = math.sqrt(0.5)
                c = 26 - 15 * r
                halves = [
                    width_across(
                        flat,
                        width,
                        scale,
                        (c + r * (k / 8 - 0.5), c - r * (k / 8 - 0.5)),
                        (r, r),
                        backdrop,
                    )
                    for k in range(8)
                ]
                outer = sum(h[0] for h in halves) / 8
                inner = sum(h[1] for h in halves) / 8
                side = width_across(flat, width, scale, (11, 40), (1, 0), backdrop)
                print(
                    f"scale {scale} backdrop {backdrop!s:15} {mode:6}: straight "
                    f"{side[0] + side[1]:.3f}; corner 45 deg outer half {outer:.3f} + inner half "
                    f"{inner:.3f} = {outer + inner:.3f}"
                )


def main() -> None:
    for scale in (1.0, 1.5):
        for mode in ("path", "shader"):
            rgba, width = snapshot(mode, scale)
            side, corner, mean, area = measure(rgba, width, scale)
            print(
                f"scale {scale} {mode:6}: straight {side:.3f}, corner 45 deg (mean of 8 phases) "
                f"{corner:.3f}, mean over the corner's rays {mean:.3f}, corner area sum "
                f"{2 * area:.3f}"
            )
        for name, x, y in (("band", 10.5 * scale, 40 * scale), ("ring", 40 * scale, 40 * scale)):
            i = (int(y) * width + int(x)) * 4
            print(f"    shader pixel in the {name}: {tuple(rgba[i : i + 4])}")


if __name__ == "__main__":
    main()
    frame_main()

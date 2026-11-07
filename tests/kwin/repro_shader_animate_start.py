"""Repro (not collected by pytest): ``Shader.animate`` starts on the NEXT ``advance`` step in a
headless window, ``Node.animate`` (and ``animate_param``, and an animated path ``data``) in the
same one.

    uv run python tests/kwin/repro_shader_animate_start.py

A shader uniform and a node's opacity are both asked to go from 0 to 1 in 100 ms with the same
linear easing, in the same call. After ``advance(50)`` the opacity is 0.5 and the uniform still 0;
every later step is half a step behind. In the shell this shows as a lag of one step in the
tests (the Join tests prime with a 1 ms ``advance``); live the lag is at most one frame, which the
docs describe ("starts on the next frame of a window that draws the shader"). Wanted: the same
start as ``Node.animate``, so a test that steps time sees the same frames for either, or a line
in docs/reference/shader.md that says so.
"""

from __future__ import annotations

import tess_re

window = tess_re.Window(width=100, height=100)
shader = tess_re.Shader(
    "fn shade(p: Pixel) -> vec4<f32> { return vec4<f32>(u.k, 0.0, 0.0, 1.0); }",
    uniforms={"k": 0.0},
)
shaded = window.create("box", width=50, height=50, shader=shader)
faded = window.create("box", width=50, height=50, fill=(255, 0, 0, 255), opacity=0.0)
window.root.add_child(shaded)
window.root.add_child(faded)
window.advance(0)  # pin the clock
shader.animate("k", 1.0, 100, "linear")
faded.animate("opacity", 1.0, 100, "linear")
for step in (50, 50, 50):
    window.advance(step)
    print(f"uniform k = {shader.uniforms['k']:.2f}   opacity = {faded.get('opacity'):.2f}")
print(
    "expected: 0.50 0.50 / 1.00 1.00 / 1.00 1.00; a shader that is one step behind: 0.00 0.50 / ..."
)

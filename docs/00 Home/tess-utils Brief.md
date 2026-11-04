---
title: tess-utils Brief
aliases: [tess-utils, tess_utils, Shared Utilities Brief]
type: moc
status: draft
owner: phil
created: 2026-11-03
updated: 2026-11-03
tags: [moc, brief, tess-utils]
---

# tess-utils Brief

> [!NOTE]
> The first slice of `tess-utils`: a small, dependency-free Python package of converters shared by the Tesserae projects, so that tre stays a rendering engine with one entry form ([ADR-0018 One Entry Form in tre](../30%20Decisions/ADR-0018%20One%20Entry%20Form%20in%20tre.md)). It is its own project with a GitHub repository, it is not released on PyPI, and a project may add to it when a need spans more than one project ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md), maintainer, 2026-11-03). This brief is for the maintainer to hand to whoever builds it; the vault sends nothing to another project.

## Purpose and Scope

- Turn the value forms that TDL writes into the single form tre takes, in one place: colour, four-sided values, corner radii, enum words.
- Not in scope: schema, typing, UI meaning, and anything that imports `tess_re`, `tess_el`, `tess_dl`, `tess_ui` or `tess_shell`. A third-party dependency is allowed where every consumer needs it (Pillow, for image decoding).

## Names and Rules

| Item | Value |
|---|---|
| Repository | `github.com/mindderivative/tess-utils`, private (maintainer, 2026-11-03); to be created by the maintainer; the name was free on 2026-11-03 |
| Import name | `tess_utils` |
| PyPI | Not released |
| Licence | MIT |
| Python | 3.14 or later; no dependencies |
| Tooling | The house style of [Shell Package Layout > Tooling](../20%20Architecture/Shell%20Package%20Layout.md#tooling): src layout, `hatchling`, `uv`, `ruff`, `mypy`, `pytest` |
| Versions | Git tags (`v0.1.0`), a `CHANGELOG.md`; consumers vendor a tagged copy ([ADR-0017 Shared Utilities > Distribution (Decided by the Maintainer 2026-11-03; Details Proposed)](../30%20Decisions/ADR-0017%20Shared%20Utilities.md#distribution-decided-by-the-maintainer-2026-11-03-details-proposed)) |
| Adding a function | At least two projects use it, it is a few lines of our own code (or a mapped library only for work that would be a project of its own, [ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md)), it has no Tesserae-package import, no dependency and no UI or schema meaning, and it has tests |

## The First Slice (0.1)

Illustrative signatures; the builder settles the final names.

| Module | Function | Does |
|---|---|---|
| `color` | `parse_color(text: str) -> tuple[int, int, int, int]` | Reads the forms TDL writes: `#RRGGBB`, `#RRGGBBAA` (alpha last), `rgba(r g b a)` with spaces, red to blue 0 to 255 and alpha 0.0 to 1.0, and `transparent`. Returns tre's `(r, g, b, a)` of 0 to 255 integers. Raises `ValueError` naming the bad part |
| `sides` | `expand_sides(value) -> tuple[float, float, float, float]` | One number, or four numbers or named sides, to `(left, top, right, bottom)`; raises `ValueError` for a list of two or three ([ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) D72) |
| `sides` | `to_tre_order(sides) -> tuple[float, float, float, float]` | `(left, top, right, bottom)` to `(top, right, bottom, left)`, the order tre's margins use |
| `radius` | `expand_radius(value) -> tuple[float, float, float, float]` | One number or four from the top-left corner clockwise to `(top_left, top_right, bottom_right, bottom_left)`, the form tre takes |
| `enums` | `to_tre_word(name: str) -> str` | `SPACE_BETWEEN` to `space_between`, `HORIZONTAL` to `horizontal` |

Planned for when the shell's `Bitmap` block and Tesserae UI both need it (not 0.1): an `image` module that decodes PNG, JPEG, GIF and WebP bytes to `(width, height, rgba_bytes)`, the decoded pixels tre takes. It is where the library choice in [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) R8 lands: Pillow (maintainer, 2026-11-03).

More forms (`#RGB`, comma syntax, CSS names, `hsl()`) are added when a second project needs them. Tesserae UI keeps its own wider `parse_color` until then ([ADR-0017 Shared Utilities > Context](../30%20Decisions/ADR-0017%20Shared%20Utilities.md#context)).

## Tests and Done Criteria

- [ ] Table-driven tests for every function, including each error case; the colour cases include `#ffffff10`, `rgba(0 0 0 0.5)` and a bad hex digit.
- [ ] `ruff` and `mypy` pass; the package has `py.typed`.
- [ ] No import outside the standard library in the 0.1 modules; Pillow is imported lazily and only by the image module, once it exists.
- [ ] A tag `v0.1.0`, a `CHANGELOG.md` and a short `README.md` saying what belongs here and the rule for adding a function.
- [ ] A sync script and a drift check ready for the first consumer (the shell), or a note saying the shell writes them.

## The Maintainer's Sketch

The maintainer's sketch of 2026-11-03 (a `tess_utils` package that re-exports Pillow as `tess_utils.Pillow` and installs it through `install_requires`) is examined in [ADR-0017 Shared Utilities > The Maintainer's Sketch (2026-11-03)](../30%20Decisions/ADR-0017%20Shared%20Utilities.md#the-maintainers-sketch-2026-11-03), with the adjustments proposed there. The first slice follows the adjusted form unless the maintainer says otherwise.

## Answers of 2026-11-03

| # | Question | Answer |
|---|---|---|
| 1 | Public or private | Private (maintainer: "I dont think we need it public"). The repository `mindderivative/tess-utils` is created by the maintainer |
| 2 | Who builds it | The shell's code session starts the build; any project adds to it when it has something to add, under the rule in "Names and Rules" |
| 3 | Where the sync script lives | Open; options below |
| 4 | How a PyPI-released project gets it | Bundled: `tess-ui` and `tess-shell` pull the latest `tess-utils` when they build a release and carry the copy in the package (maintainer) |

### Where the Sync Script Could Live

The script copies a version of `tess_utils` from the private repository into a consumer's `_vendor/` folder and writes a stamp of the version. It runs at the start of a release, and in a CI check that fails if the copy differs from the stamped version.

| Option | For | Against |
|---|---|---|
| A. A script in each consumer (`tools/vendor_utils.py`) | Each repository is self-contained; the release does not depend on tooling in `tess-utils` | The script exists twice and can drift |
| B. One script in `tess-utils` (`tools/vendor.py`), run from a local clone | Written and fixed once; it knows what to copy and what to leave out | A release needs a local clone of the private repository next to the consumer, and the consumer's build depends on it |
| C. A manifest in `tess-utils` (`vendor.json`: the files to copy, the target name) and a short script in each consumer that reads it (recommended) | The layout knowledge lives once, in `tess-utils`; each script is about 30 lines and rarely changes | Still two small scripts |
| D. `git subtree` or a submodule | No custom script; git records the source | A subtree brings the whole repository (tests, docs) under the prefix, so the import path gets an extra level; a submodule is not in a built wheel unless the build copies it; both need extra care with a private repository |

Recommendation: C. Two points apply to every option: the private repository needs credentials wherever the release is built (the maintainer's machine has them; a CI release job would need a deploy key or token), and "latest" should mean the latest tag, not the tip of `main`, so a release records exactly which version it carries.

### How a Release Pulls It (Proposal)

1. The release starts by running the sync script, which fetches the latest tag of `tess-utils`, copies it into `src/<package>/_vendor/tess_utils/` and writes `VENDORED.json` (tag and commit).
2. The tests run against that copy. The copy and the stamp are committed, so the release is reproducible and the drift check can compare them.
3. The build (`uv build`) packages the vendored folder with the project.
4. During development, the project imports `tess_utils` from an editable or git install of the private repository, so work in `tess-utils` is seen at once.

## Idea: Build It as a Compiled Extension (2026-11-03)

The maintainer suggested building `tess-utils` as a `.so` with everything in it, so people do not download 100+ packages. Examined here; not decided.

- **The count today.** The shell's planned dependencies (`tesserae-engine`, `tesserae-el`, `tesserae-dl`, `loguru`, `dbus-fast`, `jsonschema`, `Pillow`, before `jsonschema` was dropped in ADR-0020) resolve to 11 packages on Python 3.14 (checked with `uv pip compile`, 2026-11-03): the seven plus `attrs`, `jsonschema-specifications`, `referencing` and `rpds-py`, which `jsonschema` brings. Tesserae UI declares six direct dependencies (`tesserae-engine`, `pyyaml`, `Pillow`, `watchfiles`, `loguru`, `materialyoucolor`). Neither is near 100.
- **What a single file can hold.** A compiled extension (for example Rust with PyO3 and maturin, as the other Tesserae engine is) holds its own code and the libraries compiled into it. Pillow cannot be folded into it: it is a Python package with several C modules and bundled image libraries. To have "everything in" one file, the image decoding would be done by a Rust library (the `image` crate decodes PNG, JPEG, GIF and WebP) in place of Pillow, which changes behaviour and coverage, and Tesserae UI uses Pillow for more than decoding.

| For | Against |
|---|---|
| One file; no Pillow import (about 22 ms on first use); fast decoding | A platform-specific binary: a wheel per platform and Python (or one per platform with the stable ABI), so `tesserae-shell` and `tesserae-ui` stop being pure-Python wheels |
| Fewer packages for a user to install, if the decoder replaces Pillow | A Rust toolchain on every machine and CI job that builds a release; harder to debug and to vendor (a binary, not source) |
| Fits the engine's own approach | The converters (colour, sides, radius, enums) are about thirty lines and microseconds; compiling them gains nothing |

Recommendation: start 0.1 in pure Python with a stable API, so a compiled backend can replace the internals later without any consumer changing. Revisit when the `image` module is built: measure Pillow against a Rust decoder, and decide then whether the saved import time and packages are worth platform wheels. If the answer is yes, the distribution question changes (a binary is distributed as a wheel, not vendored source).

## Open Questions

1. [x] Private repository (maintainer, 2026-11-03).
2. [x] The shell's code session starts the build; any project may add (maintainer, 2026-11-03).
3. [ ] Where the sync script lives (options A to D above; recommendation C).
4. [x] Bundled by each PyPI-released project at release time, pulling the latest from `tess-utils` (maintainer, 2026-11-03).
5. [ ] Whether "latest" means the latest tag (recommended) or `main`.
6. [ ] Credentials for a CI release job, if one is ever used.
7. [x] The "100+" was an example of where a project could go over a long time, not a present count (maintainer, 2026-11-03). A compiled extension is not wanted now; the dependency rule is [ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md): a library only for what would be a project of its own, otherwise a few lines of our own code.

## Links

- [ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md) · [ADR-0018 One Entry Form in tre](../30%20Decisions/ADR-0018%20One%20Entry%20Form%20in%20tre.md) · [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) · [M1 Brief](M1%20Brief.md) · [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md)

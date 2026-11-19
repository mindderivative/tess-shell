---
title: tess-utils Brief
aliases: [tess-utils, tess_utils, Shared Utilities Brief]
type: moc
status: draft
owner: phil
created: 2026-11-03
updated: 2026-11-15
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
| Repository | `github.com/mindderivative/tess-utils`, private (maintainer, 2026-11-03), public since 2026-11-15 (maintainer, checked on GitHub); to be created by the maintainer; the name was free on 2026-11-03 |
| Import name | `tess_utils` |
| PyPI | Not released as of 2026-11-15; the maintainer set up the name `tesserae-utils` with a Trusted Publisher that day, released: `tesserae-utils` 0.2.1 is on PyPI since 2026-11-15, and `tess-shell` depends on it from there instead of vendoring the compiled file (its report, same day) ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md)) |
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
| 2 | Who builds it | The shell's code session starts the build; any project adds to it when it has something to add, under the rule in "Names and Rules". Confirmed by the maintainer on 2026-11-08: "Shell will have to start the tess-utils as there is no dedicated session for tess-utils" |
| 3 | Where the sync script lives | Open; options below |
| 4 | How a PyPI-released project gets it | Bundled: `tess-ui` and `tess-shell` pull the latest `tess-utils` when they build a release and carry the copy in the package (maintainer) |

### Built: 0.1 (code session's report, 2026-11-08; the vault checked the repository, not the tests)

The shell's code session built 0.1 after the maintainer told it to start. Seen by the vault in `~/Projects/pyDev/projects/tess-utils`: one commit `b7cb229` ("tess-utils 0.1: colour, sides, radius and enum converters; mypyc build of one .so"), the tag `v0.1.0` (local), `origin` set to `github.com/mindderivative/tess-utils.git`, and nothing pushed (the shell session pushes only on the maintainer's word). `build/so/` holds one file, `tess_utils.cpython-314-x86_64-linux-gnu.so` (444 KB), and `tess_utils.stamp.json` (version 0.1.0, python tag, platform, SHA-256).

Reported, not run by the vault: `parse_color` (hex of 3, 4, 6 or 8 digits with alpha last, `rgb()` and `rgba()` with spaces or commas, `transparent`; a `ValueError` names the bad part), `expand_sides`, `to_tre_order`, `expand_radius` (never negative) and `to_tre_word`; 101 tests, `ruff` and `mypy` strict clean, a test that no module imports outside the standard library or a Tesserae package, and the same 101 tests passing against the `.so`. The code session added `#RGB`, `#RGBA` and comma syntax beyond the first-slice list because the shell already reads them.

Two findings:

1. A literal single file needs a single module. `mypyc` compiles several modules into one shared library plus a small shim `.so` per module, so the build tool merges the four modules into one `tess_utils.py` before compiling. Consequence: `tess_utils.color` and the other submodules are not importable from the compiled file, only the top-level names (`from tess_utils import parse_color`). That matches how the brief and the ADR write the imports.
2. A compiled function raises `TypeError` for a wrongly typed argument and accepts `True` as a float, where the source raised `ValueError`. The public functions therefore take `object` and validate, so source and `.so` behave alike.

The shell already has these converters in `src/tess_shell/binder/convert.py` (colour, sides, radius, enum), wrapped in typed `Value`, `Origin` and `BindError` types. They are not replaced by `tess_utils` yet: that needs the sync script (open question 3) and the wheel and platform decisions. Not built: the `image` module, the `abi3` settings, the sync script. The file is built for `cpython-314`, not the stable ABI.

### Built: 0.1.1 and the shell's use of it (code session's report, 2026-11-10; repository state checked by the vault, tests not run)

The code session reports it did steps 1 to 4 at the maintainer's word (the vault has not heard this from the maintainer in chat; the report is a peer message): `tess-utils` `main` and the tag `v0.1.0` pushed, and a GitHub release `v0.1.0` made with the `.so` and its stamp. The vault cannot see GitHub; it saw locally that the tags `v0.1.0` and `v0.1.1` exist and that `v0.1.1` is commit `3de783c` in `tess-utils`, and that the shell's commit `8127852` exists with `tools/vendor_utils.py` and `src/tess_shell/_vendor/` holding `tess_utils.cpython-314-x86_64-linux-gnu.so`, `tess_utils.pyi` and `VENDORED.json`.

Reported: `v0.1.1` adds a type stub `tess_utils.pyi` beside the `.so`, a `vendor.json` manifest (package, repository, stamp, files with `{soabi}`) and a stamp listing both files' SHA-256. It is committed with a local tag only: not pushed and no release yet. In `tess-shell` (1624 tests reported): `tools/vendor_utils.py sync` reads `vendor.json` at the tag through `gh`, checks each file against the stamp and the stamp against this Python, and copies into `src/tess_shell/_vendor/` with `VENDORED.json`; `check` is the no-network drift check, also `tests/test_vendor.py`. `binder/convert.py` now takes colour, sides, order, radius and enum words from the carried `tess_utils` and keeps the `Value`, `Origin` and `BindError` wrappers (it reads `rgb()` and `transparent` now). The wheel is a platform wheel through `hatch_build.py`; PyPI needs a manylinux tag, which is M7.

Not tested: the sync from GitHub, until `v0.1.1` is pushed and released. That waits for the maintainer. Open questions 3 (option C), 13 (the shell replaces its converters, keeping its wrappers) and 14 (top-level imports only) were acted on by the code session; the vault has no maintainer answer for them in chat and records them as proposed and in use. Still not built: the `image` module and `abi3`.

### State on 2026-11-08, Before 0.1 (Superseded by the Section Above)

The local directory `~/Projects/pyDev/projects/tess-utils` was empty when the vault checked it. The maintainer says (2026-11-08) that `https://github.com/mindderivative/tess-utils.git` exists and has never had a commit or a push, so there is no code and no tag. He is not sure whether `tess-shell` already has the converters in `binder/convert.py`; the code session reports that (it was asked on 2026-11-08). Since the shell session owns the project, it keeps the rules of "Names and Rules" (two users, no Tesserae imports, tests) and lists what it adds in `CHANGELOG.md`. The next planned addition is the `image` module, which [M4 Brief](M4%20Brief.md) needs by M4b ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md): Pillow is imported only there). The release form is a single compiled `.so` ([Decision Direction: One Compiled `.so` per Release (2026-11-08)](#decision-direction-one-compiled-so-per-release-2026-11-08)).

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

## Decision Direction: One Compiled `.so` per Release (2026-11-08)

> [!IMPORTANT]
> **The maintainer's direction (2026-11-08)**
> "tess-utils is a private project for Tesserae projects and not open to the public. I want tess-utils releases to be a single compiled `.so` file that the tesserae projects use." There is no PyPI release and no PyPI tag. The repository `https://github.com/mindderivative/tess-utils.git` exists and has never had a commit or a push. This replaces the earlier view (open question 7, 2026-11-03: "a compiled extension is not wanted now") and the vendored-source distribution proposal below; the examination that follows stays as the reasoning it rests on.

What follows from it, as the vault sees it (proposals, not decisions, unless marked):

| Point | Consequence | Proposal |
|---|---|---|
| Build tool | A single `.so` needs a compiled language or a compiler for typed Python. The vault has not chosen. Candidates: Rust with PyO3 and maturin (the engine's own approach), or the existing typed Python compiled with `mypyc` into one shared object, or Cython | Recommended: write 0.1 as typed pure Python with tests, then compile it with `mypyc` into one `.so`: no Rust toolchain, no behaviour change, and the pure source stays for tests and for development. Move to Rust only if the `image` decoder replaces Pillow (see below). The maintainer decides the tool |
| What one file holds | It holds our own code and what is compiled into it. Pillow cannot be folded in: it is a Python package with its own C modules and bundled libraries | Keep Pillow outside, imported inside the image function when first called ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md)), and listed in each consumer's `pyproject.toml`; or decode with a compiled Rust library and drop Pillow, which changes behaviour and coverage and is the maintainer's choice |
| One file per platform | A compiled extension is tied to a Python version and a platform. This machine is Linux x86_64 on Python 3.14 | Build for CPython 3.14 on Linux x86_64 first; use the stable ABI (`abi3`) if the tool allows it, so one file serves later 3.x versions. Other platforms only when a consumer needs them (Linux/Wayland is the shell's only target, [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md)) |
| Distribution | The consumers no longer vendor source. Each carries the built `.so` and a stamp (version, build date, SHA-256), and a check fails if the carried file differs from the stamp | The release is a file attached to a GitHub release of the private repository (no PyPI); the consumers' sync script downloads it with credentials, verifies the SHA-256 and copies it into `_vendor/` (option C above, with a binary in place of source) |
| The consumers' own wheels | `tesserae-shell` and `tesserae-ui` are released on PyPI. A wheel that carries a compiled `.so` is no longer a pure-Python wheel: it has a platform tag | They build a platform wheel (Linux x86_64, CPython 3.14), or a wheel tagged for the stable ABI. The `.so` then travels inside public PyPI wheels, so "not open to the public" protects the source and not the binary |
| Debugging | A compiled file is harder to step through | The pure source stays in the repository and the tests run against both the source and the compiled file |
| Versions | There is no PyPI tag; a version is still needed to say which build a consumer carries | Proposed: git tags `v0.1.0` on the private repository, used only as the version of the `.so`; the maintainer says if he wants no tags at all |

### The Maintainer's Answers of 2026-11-08

| # | Point | Answer |
|---|---|---|
| 1 | Build tool | Typed Python, compiled to one `.so` with `mypyc`: "that is as I see it" (maintainer, 2026-11-08, confirming the vault's reading). Rust only for a compelling need |
| 2 | Pillow | Decided (maintainer, 2026-11-08: "Use your recommendation as a lazy import"): Pillow stays outside the `.so` and `tess_utils.image` imports it lazily, inside the function that decodes. The explanation of why it is not one library is in the next subsection |
| 3 | Platforms | Linux x86_64 first. macOS and Windows binaries wait until there is a strong way of testing on them |
| 4 | Distribution | Agreed: the release is a file on a GitHub release of the private repository; each consumer's sync script downloads it with credentials, checks the SHA-256 and carries it in `_vendor/` with a stamp |
| 5 | The consumers' PyPI wheels | Accepted: `tesserae-shell` and `tesserae-ui` become platform wheels |
| 6 | Tags | Git tags are fine (the version of each `.so`; not a PyPI tag) |

### Why Pillow Is Not One Library (for the Maintainer's Question)

I said Pillow "cannot be folded" into the file. That was too strong. What is true, read on the Pillow 13.0.0 install in `~/Projects/pyDev/pyEnvs/global-base` (CPython 3.14, Linux x86_64), is this:

- Pillow is not one file. The install has 8 compiled extension modules (`_imaging`, `_imagingft`, `_imagingcms`, `_imagingmath`, `_imagingmorph`, `_imagingtk`, `_webp` and `_avif`, each `.cpython-314-x86_64-linux-gnu.so`) and 18 more shared libraries in `pillow.libs` (libjpeg, libpng, libwebp, libtiff, freetype, harfbuzz, lcms2, openjp2, avif, zstd, lzma and others), 7.4 MB for `PIL` and 15 MB for the libraries.
- `mypyc` compiles our own typed Python. It does not merge a third-party package, with its C modules and its libraries, into our file.
- A single file that decodes images therefore means building our own extension that links the codec libraries statically: libpng, libjpeg, libwebp and a GIF reader, which is what Pillow's wheel does for those formats, written and kept by us. That is a project of its own, in C or in Rust (the `image` crate), and it is the compelling need for Rust the maintainer set as the test. It changes behaviour and coverage, and Tesserae UI uses Pillow for more than decoding ([ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md): build only what would otherwise be a project of its own).
- Keeping Pillow outside costs one import (about 22 ms on first use, measured on 2026-11-03) and one line in each consumer's `pyproject.toml`; `tess_utils` still hides it, so consumers never import Pillow ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md)).

Recommendation: Pillow outside the `.so`. If the maintainer wants one self-contained file for images too, the decoder becomes its own task: the formats it must read (PNG, JPEG, GIF, WebP, and which of them Tesserae UI needs), then a build with static codecs. Licences of the codec libraries were not checked. #needs-verification

Decided on 2026-11-08: the compiler is `mypyc`, and Pillow stays outside the `.so`, imported lazily by `tess_utils.image` (so a consumer that only needs colours never loads it, and each consumer lists Pillow in its own `pyproject.toml`). Still open: the stable ABI (`abi3`) when the compiler is set up. The release file is a GitHub release asset (agreed). The shell's code session starts the project ([Answers of 2026-11-03](#answers-of-2026-11-03), confirmed 2026-11-08), once the maintainer says go.

## Earlier Examination: Build It as a Compiled Extension (2026-11-03)

The maintainer suggested building `tess-utils` as a `.so` with everything in it, so people do not download 100+ packages. Examined here on 2026-11-03.

- **The count today.** The shell's planned dependencies (`tesserae-engine`, `tesserae-el`, `tesserae-dl`, `loguru`, `dbus-fast`, `jsonschema`, `Pillow`, before `jsonschema` was dropped in ADR-0020) resolve to 11 packages on Python 3.14 (checked with `uv pip compile`, 2026-11-03): the seven plus `attrs`, `jsonschema-specifications`, `referencing` and `rpds-py`, which `jsonschema` brings. Tesserae UI declares six direct dependencies (`tesserae-engine`, `pyyaml`, `Pillow`, `watchfiles`, `loguru`, `materialyoucolor`). Neither is near 100.
- **What a single file can hold.** A compiled extension (for example Rust with PyO3 and maturin, as the other Tesserae engine is) holds its own code and the libraries compiled into it. Pillow cannot be folded into it by a compiler such as `mypyc`: it is a Python package with several C modules and bundled image libraries (see "Why Pillow Is Not One Library" above). To have "everything in" one file, the image decoding would be done by a Rust library (the `image` crate decodes PNG, JPEG, GIF and WebP) or an own C extension in place of Pillow, which changes behaviour and coverage, and Tesserae UI uses Pillow for more than decoding.

| For | Against |
|---|---|
| One file; no Pillow import (about 22 ms on first use); fast decoding | A platform-specific binary: a wheel per platform and Python (or one per platform with the stable ABI), so `tesserae-shell` and `tesserae-ui` stop being pure-Python wheels |
| Fewer packages for a user to install, if the decoder replaces Pillow | A Rust toolchain on every machine and CI job that builds a release; harder to debug and to vendor (a binary, not source) |
| Fits the engine's own approach | The converters (colour, sides, radius, enums) are about thirty lines and microseconds; compiling them gains nothing |

Recommendation: start 0.1 in pure Python with a stable API, so a compiled backend can replace the internals later without any consumer changing. Revisit when the `image` module is built: measure Pillow against a Rust decoder, and decide then whether the saved import time and packages are worth platform wheels. If the answer is yes, the distribution question changes (a binary is distributed as a wheel, not vendored source).

## Notes

`decode_image` (`tess_utils` 0.2.0), for the Image and Bitmap of M4b: the code session reports (peer message, 2026-11-11, not confirmed here) four local commits in the tess-utils repository and a local build carried in the shell. The push, the tag and the GitHub release have not happened; they follow when the maintainer directs them.

## Open Questions

1. [x] Private repository (maintainer, 2026-11-03).
2. [x] The shell's code session starts the build; any project may add (maintainer, 2026-11-03).
3. [x] Where the sync script lives: option C, a manifest `vendor.json` in `tess-utils` and a short script in each consumer, the shell writing the first (maintainer, 2026-11-10, as recommended).
4. [x] Bundled by each PyPI-released project at release time, pulling the latest from `tess-utils` (maintainer, 2026-11-03).
5. [x] "Latest" means the latest tag, not `main` (maintainer, 2026-11-10).
6. [x] Credentials: the maintainer's standard GitHub credentials (2026-11-10). No separate deploy key for now; a CI release job, if one is ever made, is a new question.
7. [x] The "100+" was an example of where a project could go over a long time, not a present count (maintainer, 2026-11-03). On 2026-11-03 a compiled extension was not wanted yet; on 2026-11-08 the maintainer wants releases as a single compiled `.so` ([Decision Direction: One Compiled `.so` per Release (2026-11-08)](#decision-direction-one-compiled-so-per-release-2026-11-08)). The dependency rule is still [ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md): a library only for what would be a project of its own, otherwise a few lines of our own code.
8. [x] The compiled build tool: typed Python compiled with `mypyc`; Rust only for a compelling need (maintainer, 2026-11-08).
9. [x] Pillow stays outside the `.so` and is imported lazily by `tess_utils.image` (maintainer, 2026-11-08, as recommended).
10. [x] Linux x86_64 on CPython 3.14 first; macOS and Windows when there is a strong way to test them (maintainer, 2026-11-08). The stable ABI (`abi3`) is still to be settled when the compiler is chosen.
11. [x] Git tags for the `.so` versions, and the release file as a GitHub release asset on the private repository (maintainer, 2026-11-08: "Agreed" and "git tags are fine"). The wheels of the consumers are platform wheels (accepted).
12. [x] `tess-utils` pushed and the `v0.1.0` release exists on GitHub (maintainer, 2026-11-10: the repository shows the 0.1.0 release). The code session reports (peer message, 2026-11-10) that `v0.1.1` is pushed and released on the private repository at the maintainer's word, and that the real `tools/vendor_utils.py sync` from GitHub works and the shell carries it (D111); the vault cannot see GitHub.
13. [x] The shell replaces its own converters in `binder/convert.py` with `tess_utils`, keeping the typed `Value`, `Origin` and `BindError` wrappers in the shell (maintainer, 2026-11-10, as recommended; done by the code session).
14. [x] The compiled file has no submodule imports (`tess_utils.color`); the public API is the top-level names (maintainer, 2026-11-10, as recommended).

## Questions After Testing

Answered by: the first `mypyc` build of `tess_utils` (see question 10 above).

1. [ ] Should the compiled `.so` target the stable ABI (`abi3`) or a CPython 3.14 specific build? Context: question 10 left it open until the compiler is chosen; `mypyc` output may not support `abi3`, which only a build shows. Recommendation: the CPython 3.14 specific build unless `mypyc` produces `abi3` without cost.

## Links

- [ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md) · [ADR-0018 One Entry Form in tre](../30%20Decisions/ADR-0018%20One%20Entry%20Form%20in%20tre.md) · [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) · [M1 Brief](M1%20Brief.md) · [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md)

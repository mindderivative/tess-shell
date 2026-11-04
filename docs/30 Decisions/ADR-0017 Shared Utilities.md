---
title: ADR-0017 Shared Utilities
aliases: [ADR-0017, tess-utils, Shared Helpers]
type: adr
status: accepted
owner: phil
created: 2026-11-03
updated: 2026-11-03
tags: [adr, architecture]
---

# ADR-0017: Shared Utilities

> [!NOTE]
> Should a `tess-utils` project hold small helpers that the shell and Tesserae UI both need, such as turning a hex colour string into the `(r, g, b, a)` tuple that tre takes? The maintainer ruled that tre does not do conversions ([ADR-0018 One Entry Form in tre](ADR-0018%20One%20Entry%20Form%20in%20tre.md)), so the frameworks must. That changes my recommendation: create a small, dependency-free `tess-utils` for the shared converters. Accepted by the maintainer in chat on 2026-11-03, with two terms of their own: it is not released on PyPI, and it is open to additions when a need spans more than one project.

## Context

The maintainer noted on 2026-11-03 that the shell's M1 needs converters (hex string to tuple, four-sided values to four properties, lengths) that Tesserae UI also needs, and suggested a `tess-utils` project. Facts:

- Tesserae UI already has `parse_color` in `tess_ui/tokens.py`, covering hex, CSS names and the CSS colour functions, and depending on Pillow's `ImageColor`.
- tre takes colours only as `(r, g, b, a)` tuples. The maintainer declined to have tre accept colour strings: one entry form per kind of value, and the framework converts ([ADR-0018 One Entry Form in tre](ADR-0018%20One%20Entry%20Form%20in%20tre.md); [TRE-REQ-010 Colour Strings](../80%20Requests/TRE-REQ-010%20Colour%20Strings.md) was withdrawn).
- The binder is designed to be split out ([ADR-0015 Render Binder](ADR-0015%20Render%20Binder.md)); its converters have no dependencies ([Render Binder Design > Converters](../20%20Architecture/Render%20Binder%20Design.md#converters)).
- A new project costs a repository, a release process, version ranges in every consumer and a session or a maintainer's attention.

## Options

### Option A — Create `tess-utils` Now, Small and Dependency-Free (Recommended)

- A package of converters, starting with the forms TDL writes: colour (`#RGB`, `#RGBA`, `#RRGGBB`, `#RRGGBBAA`, `rgba(r g b a)`, `transparent`) to the tuple tre takes, a four-sided value to four values, a length or percentage to what tre takes, and enum words to tre's lower-case words.
- The shell's binder imports it; Tesserae UI can replace its Pillow-based `parse_color` with it when it chooses, keeping its extras (CSS names, `hsl()`, wide-gamut) locally until the shared package covers them.
- **For:** the converters exist once; tre stays minimal; it removes the duplication that exists today.
- **Against:** a sixth project (repository, releases, version ranges); its API is set by the shell's M1 needs before Tesserae UI has weighed in.

### Option B — Keep the Converters in the Binder; Create `tess-utils` on a Trigger

- Pure, standard-library-only functions in `binder/convert.py`, so they can move unchanged; create `tess-utils` when a second project adopts them.
- **For:** no new project until it is clearly needed; the move is a file copy.
- **Against:** Tesserae UI keeps its own converter in the meantime.

### Option C — Put Helpers in an Existing Library (`tess_dl` or `tess_el`)

- **Against:** wrong layer. `tess_dl` is structure-only and `tess_el` is expressions; neither should know about tre's value forms.

## Decision

Accepted 2026-11-03 by the maintainer in chat: **Option A**, with these terms: "tess-utils will be its own project but not a pypi released one as it is geared specifically for tesserae projects. It will have a github but again it will be a utility tool for tesserae projects which will leave it open for other projects to add to it when the needs are more then just one project."

- Repository `mindderivative/tess-utils` on GitHub, private (maintainer, 2026-11-03); import name `tess_utils`; no PyPI release.
- Dependencies are allowed where every consumer needs them (maintainer, 2026-11-03: "I don't mind it having dependencies like Pillow because both tess-ui and tess-shell will use them for image decoding"). This also lets the image decoding that tre does not do ([ADR-0018 One Entry Form in tre](ADR-0018%20One%20Entry%20Form%20in%20tre.md)) live in one place: only `tess_utils` imports Pillow, and the shell and Tesserae UI call its image functions instead of importing Pillow themselves (maintainer, 2026-11-03: "that way tess-ui and tess-shell dont have to import Pillow themselves").
- It serves the Tesserae projects only. Another project may add to it when a need spans more than one project (the "at least two users" rule below).
- How a project that is released on PyPI gets it is a consequence with a proposed answer, in "Distribution" below.

## Consequences

If Option A is accepted:

- `tess-utils` is created before M1's converter task (T2 in [M1 Brief](../00%20Home/M1%20Brief.md)), small enough to publish in one session; the binder depends on it and still imports nothing from the shell.
- The binder's import rule becomes `tess_re`, `tess_utils` and the standard library ([Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md)).
- Until it is published the code session may write the converters in `binder/convert.py` as pure functions and move them.

If Option B is accepted:

- The binder's converters are pure functions with no import outside the standard library, so they can move unchanged.
- The trigger to create `tess-utils` is written down: a second project adopts the helpers.

If `tess-utils` is ever created, these rules keep it small:

| Rule | Reason |
|---|---|
| Only functions with at least two users | No speculative helpers |
| Only `tess_utils` imports Pillow; a consumer's own code never does, and a test checks it | One place decodes images; the consumers stay free of the library's API |
| A consumer that vendors `tess_utils` still lists Pillow in its own `pyproject.toml`, because the vendored code imports it | A vendored copy brings no package metadata, so pip would not install Pillow otherwise |
| No import of `tess_re`, `tess_el`, `tess_dl`, `tess_ui` or `tess_shell` | It sits below all of them |
| A third-party dependency only when every consumer already needs it, building it would be a project of its own ([ADR-0019 Dependency Policy](ADR-0019%20Dependency%20Policy.md)), and it is imported inside the function that uses it | Today that is Pillow, which both the shell and Tesserae UI use to decode images; a consumer that only needs colours never imports it |
| No schema, UI or shell meaning | It converts forms, it does not interpret them |
| Pure, typed Python; semantic versioning | Safe to share |
| Names: repository `tess-utils`, import `tess_utils`; not on PyPI | The maintainer's term; the repository name was free on 2026-11-03 |

## The Maintainer's Sketch (2026-11-03)

The maintainer sketched how `tess-utils` could map external libraries once for all projects: a `tess-utils/` repository with `setup.py` and a `tess_utils/` package; `install_requires=["Pillow"]` so installing `tess-utils` installs Pillow; an `__init__.py` that re-exports the library (`import PIL as Pillow`) so a project writes `from tess_utils import Pillow`; and own helpers beside it (`image_helpers.py` with a `custom_resize`). The aim: "a centralized external library without the need for each project installing 3rd party libraries separately". It is an example, not yet a decision.

What it gets right, and what to adjust:

| Point | Finding | Proposed adjustment |
|---|---|---|
| One place maps each external library; projects reach it through `tess_utils` | Matches the rule that only `tess_utils` imports Pillow | Keep. Add a short module per mapped library (`tess_utils.image` for Pillow) |
| `import PIL as Pillow` | Tested with Pillow 13.0.0: a bare `import PIL` takes 1 ms and does not load `PIL.Image`, so `Pillow.Image` is missing until some module runs `from PIL import Image`, which costs about 22 ms. The sketch works only because `image_helpers.py` imports `Image` as a side effect | Import lazily: expose `Pillow` through a module-level `__getattr__` that imports `PIL.Image` on first use, so `tess_utils` costs nothing for callers that only need colours. This keeps `from tess_utils import Pillow` working |
| Re-exporting the whole library | Consumers can use all of Pillow's API through it, which couples them to Pillow's API | Recommend the supported API be the `tess_utils.image` functions (decode to `(width, height, rgba_bytes)`), with `Pillow` as an escape hatch for the Tesserae projects only |
| `install_requires=["Pillow"]` pulls Pillow in | True only when `tess-utils` is installed as a package. PyPI rejects a URL dependency ([pypa/warehouse #9404](https://github.com/pypi/warehouse/issues/9404)), so `tesserae-shell` and `tesserae-ui` released on PyPI cannot depend on an unpublished `tess-utils` | See "Distribution" below: vendoring needs Pillow listed in each consumer, or the install route changes |
| `setup.py`, `python_requires=">=3.7"`, unpinned `Pillow` | Does not match the house style or the projects' needs | `pyproject.toml` with `hatchling`, `requires-python >=3.14`, `Pillow>=10.0` (Tesserae UI's floor) |
| `custom_resize` prints and writes files | A utility that prints is awkward for a library; file paths are the caller's I/O | Return the image or bytes; no printing |

## Distribution (Decided by the Maintainer 2026-11-03; Details Proposed)

The maintainer's answer: `tess-ui` and `tess-shell` bundle `tess-utils`, pulling the latest version from the `tess-utils` repository when they build a release. That is the vendoring option below; the details (what "latest" means, where the sync script lives, how the copy is stamped and checked) are in [tess-utils Brief > Answers of 2026-11-03](../00%20Home/tess-utils%20Brief.md#answers-of-2026-11-03). The shell's code session starts the build; any project may add to it.

PyPI rejects an upload whose dependencies are given by URL, such as a `git+https` link ([pypa/warehouse #9404](https://github.com/pypi/warehouse/issues/9404); the maintainers said they have no plans to change it). So `tesserae-shell` and `tesserae-ui`, which are released on PyPI, cannot declare an unpublished `tess-utils` as a dependency. Options:

| Option | How | For | Against |
|---|---|---|---|
| Vendor a tagged copy (recommended) | Each consumer carries `tess_utils` in a private folder (`src/tess_shell/_vendor/tess_utils/`), copied from a tag of the `tess-utils` repository by a small sync script that records the tag; a CI check fails if the copy differs from the tag | Works with PyPI; no extra install; tess-utils stays a plain repository | A copy per consumer; the sync script and the drift check |
| Git subtree or submodule | The same folder, kept by git | Git tracks the source | More friction in each repository; a submodule does not reach a built wheel unless copied |
| Development dependency by URL only | `[tool.uv.sources]` points at the repository for local work; the release build vendors | Easy local edits | Two routes to keep in step |
| Publish it after all | PyPI `tesserae-utils` | Simplest | Against the maintainer's term |

Recommendation: vendor a tagged copy. The binder's import rule becomes `tess_re`, `tess_utils` (the vendored copy) and the standard library; to a reader of the code it is the module `tess_utils`, reached as `from tess_shell._vendor import tess_utils`.

## Links

- [ADR-0015 Render Binder](ADR-0015%20Render%20Binder.md) · [ADR-0018 One Entry Form in tre](ADR-0018%20One%20Entry%20Form%20in%20tre.md) · [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) · [TRE-REQ-010 Colour Strings](../80%20Requests/TRE-REQ-010%20Colour%20Strings.md) · [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) · [30 Decisions](30%20Decisions.md)

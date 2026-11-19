# Contributing

How the repository is laid out and how to build, test and document a change. Tesserae Shell is pre-alpha and has one maintainer; talk to the maintainer before you spend time on a large change.

## Repository layout

| Path | What is in it |
|---|---|
| `src/tess_shell/` | The package. `cli.py` is the command line, `app.py` the start and stop sequences, `config/` the configuration folder, settings and registry, `files/` and `schema/` the reading and checking of TDL files, `model/` and `binder/` the typed tree and its binding to tre, `surfaces/` Bar, Panel, Popup and Frame, `modules/` the module host, `services/` D-Bus, audio, KWin and the portal, `migrate/` the `migrate` command, `shipped/` the modules, themes, stylesheets and icons the package ships. |
| `tests/` | The test suite, with fakes of the desktop services (`fake_*.py`), the private compositor helper (`sway.py`), the guide's table generator (`guide_tables.py`) and, in `kwin/` and `perf/`, hand-check kits and measurements that the default run leaves out. |
| `docs/` | This site, written by hand: the overview, `guide/`, `reference/` and the other pages. |
| `docs/design/` | The design notes, **generated**; see below. |
| `tools/` | `sync_docs.py` (the export into `docs/design/`) and the maintainer's repository helpers. |
| `.github/workflows/` | `ci.yml`, `docs.yml` and `release.yml`. |
| `pyproject.toml`, `uv.lock` | The package, its dependency ranges, and the locked environment. |
| `CHANGELOG.md`, `README.md`, `NOTICE` | Release notes, the front page, and the licences of what is shipped or required. |

`AGENTS.md` holds the standing instructions of the project. Its layering rules are tested: `tests/test_imports.py` fails when a package imports what it must not (the binder imports only the engine, a module never imports the engine).

## Set up

You need Python 3.14 (the regular build with the GIL, which `pyproject.toml` asks `uv` to use) and [`uv`](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/mindderivative/tess-shell
cd tess-shell
uv sync --locked --python 3.14
```

Commands run through `uv run`: `uv run tesserae-shell version` is the command from your checkout.

## Run what CI runs

CI (`.github/workflows/ci.yml`) has four checks on a pull request: lint and types, the tests in four shards, a clean install of the wheel, and the docs build. For a change to code, run the first two locally:

```sh
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy
env -u WAYLAND_DISPLAY -u DISPLAY uv run pytest -q
```

* Ruff covers `src` and `tests` (`docs` and `tools` are excluded) and mypy covers `src`. The line length is 100, mypy is `strict`, and everything is typed.
* The suite runs on a private headless `sway`, private D-Bus daemons and a virtual keyboard, so it needs `sway`, `wtype`, `grim`, `dbus-daemon` and a software Vulkan driver (the list is in the "Install system dependencies" step of `ci.yml`). It refuses to run with `WAYLAND_DISPLAY` or `DISPLAY` set, so that it never touches your desktop: hence the `env -u` prefix.
* By default the run leaves out tests marked `perf`, `manual`, `compositor`, `dbus` and `audio_sandbox` (the `addopts` of `pyproject.toml`). Run one by name with `-m`.
* The tests that need a real compositor or a person (`tests/kwin/`) are checklists the maintainer runs by hand; nothing in a normal run registers global shortcuts or opens surfaces on your own session.
* The wheel check is `uv build --out-dir dist`, then installing the wheel alone in a clean environment and running `tesserae-shell version`.

A change is done when the changelog says so: add a line under *Unreleased* in `CHANGELOG.md` for anything a user can see (a key, a command, a message, a fix).

## The documentation

There are two kinds of page under `docs/`:

* **Hand-written pages** (everything outside `docs/design/`) describe what the code does today. The guide's pages (`docs/guide/`) take their tables of keys, defaults, tokens, settings, commands and exit codes from the code. They sit between `<!-- BEGIN generated: NAME -->` and `<!-- END generated: NAME -->` markers, and every example under `docs/guide/examples/` is a real configuration folder that a test runs through `check`. After a change that affects them, regenerate:

  ```sh
  env -u WAYLAND_DISPLAY -u DISPLAY uv run python -m tests.guide_tables
  ```

  `tests/test_guide_tables.py` and `tests/test_guide_examples.py` fail if a page or an example is out of date. Do not edit between the markers; the marker names are listed in the docstring of `tests/guide_tables.py`. The [examples](examples.md) page lists the example folders.
* **The design notes** (`docs/design/`) are the maintainer's Obsidian vault, exported by `tools/sync_docs.py` and replaced each time. Edit nothing there: a change to a design belongs in the vault, so tell the maintainer what is wrong or missing. The vault is the design record, and the code is the source of what is true today; where they differ, the pages outside `docs/design/` say what the code does.

Build the site as CI does (a broken link or anchor fails it):

```sh
uv sync --locked --only-group docs
NO_MKDOCS_2_WARNING=1 uv run --no-sync mkdocs build --strict
uv run --no-sync mkdocs serve        # to read it while you write
```

## Engine requests

The shell never works around the engine. When it needs something tre (`tesserae-engine`), the expression language or the TDL reader does not offer, that is a numbered request to that project (`TRE-REQ-###`, `TEL-REQ-###`, `TDL-REQ-###`), written up with a reproduction and carried to the project by the maintainer. Do not file issues upstream for it yourself. Examples of requests, with their reproductions, are in `tests/kwin/`.

## Releases

Releases are the maintainer's. A release is a version bump in `src/tess_shell/__init__.py` and a `## X.Y.Z` section in `CHANGELOG.md`, merged to `main`, then a tag `vX.Y.Z`. The tag starts `release.yml`, which:

1. runs the whole of CI on the tagged commit;
2. builds the package and checks that the tag, the built version and a changelog section all agree, and that the wheel imports in a clean environment as that version;
3. publishes to PyPI (the `pypi` environment of the repository) and creates the GitHub release, with that version's changelog section as its notes.

A pull request does not bump the version or add a tag. The site is rebuilt and deployed by `docs.yml` when `docs/` or `mkdocs.yml` change on `main`.

# Changelog

## Unreleased

- Package skeleton: `pyproject.toml`, `src/tess_shell`, tooling (ruff, mypy, pytest).
- Command line `tesserae-shell` with `version`; `run` and `check` are wired in later tasks; the other subcommands report "not implemented in M0".
- Config directory lookup (`--config-dir`, `$XDG_CONFIG_HOME`, `~/.config`) and `settings.tdl` reading: every key of the Settings File note, one finding per problem with `file:line:column`.
- Loguru setup: console sink and a daily `log_YYYY-MM-DD.log` (directory 0o700, file 0o600), JSON option, midnight file swap, retention, console-only fallback.
- Instance lock (`flock` on `$XDG_RUNTIME_DIR/tesserae-shell/lock`, exit 4 naming the holder's pid) and `$XDG_RUNTIME_DIR` checks (exit 2).
- `tesserae-shell run`: pre-flight, settings, logging, instance lock, registry (`registry.json`, created and saved atomically), then the engine loop with `keep_alive`; SIGTERM and SIGINT stop it cleanly (exit 0), a second signal forces exit 130. Steps 7 to 12 of the start sequence that need later milestones are logged as not built.
- `tesserae-shell check`: settings, then a syntax check of every `*_Shell.tdl`, `*_Module.tdl`, `*_Style.tdl`, `*_Theme.tdl` and `*_Stylesheet.tdl` under the search directories, with `file:line:column`, `--json`, exit 0, 1 or 2. `run` step 7 does the same scan.
- Idle measurement script `tests/perf/measure_idle.py` and its first result (`tests/perf/idle-results.md`): 0.000 % of one core and about 3 wake-ups per second over 60 s, within the budgets.
- Import rules of the package layout are enforced by `tests/test_imports.py`.
- M1 binder (`tess_shell.binder`): the typed tree and `BindError` (`model.py`).
- M1 binder converters (`convert.py`): length, bound, number, whole, positive, bool, text, color, enum, wrap flag, sides, radius, font family, plus a colour parser; table-driven tests.
- M1 binder tables (`tables.py`) for `Box`, `FlexBox`, `Text`, `Rectangle`, `Spacer` and `SVG`, guarded by a test that builds a node for every row on a headless tre window; `build.py` binds a typed tree through `Window.build`, collects every error with its `file:line:column`, translates tre's errors back to the key, refuses `If` and `For`, and returns a `View` with `dispose`.
- M1 Bar geometry (`surfaces/bar.py`): `bar_geometry(spec, output, content)` computes tre's `anchor`, `size`, `margin`, `exclusive_zone` and `exclusive_edge` as a pure function; every row of the worked-examples table is a test, with `ZeroSize` for a Bar that is not created.
- Text `Width`/`Height` `AUTO` becomes tre's `"fit-content"`; a test pins that a headless `LayerWindow` accepts the Bar geometry of every worked example.
- Binder: a key written both in a block and in its Style is an error naming both places (D2); a Font_Family list is joined with ", " (D5).
- M1 schema (`tess_shell.schema`): `read_shell` checks a parsed `*_Shell.tdl` against the `Shell`, `Monitor`, `Bar` and block key declarations and types it into the binder's model; unknown keys with nearest names, wrong types, missing keys, duplicate names and monitors, `style-duplicate`, `bad-sides`, `Border { }` flattened, forms not built in M1 refused (`not-built`; Bar keys M1 does not build are warnings). `tree.py` moved from `files` to `schema`.
- M1 files: stage 3 header checks (`version-pin`, `shell-root-suffix`); `check` and `run` step 7 now type every `*_Shell.tdl`, print warnings without failing, and a test pins that the schema's key declaration matches the binder tables.
- M1 surfaces (`surfaces/manager.py`): `assign` matches `Monitor` blocks to outputs (Connector, then Description, then Index; `Index: default` takes the rest), `SurfaceManager` opens one `LayerWindow` per Bar (namespace `tesserae-shell.bar.<name>`, geometry from `bar_geometry`, inline `Fill`), binds its children and logs every bind error while leaving that Bar empty; `run` steps 10 and 11 call it. Tests on a private headless sway: the Bar is configured at 1280x32, the output's usable area shrinks by the reserved zone and is restored when the shell stops.
- M1 measurements: `tests/perf/measure_bind.py` (`bind-results.md`) and `measure_idle.py --bar` (`idle-results-bar.md`): 3,101 nodes bind in about 12.6 ms, the example in 0.03 ms; idle with the Bar shown is 0.000 % of one core and about 2.7 wake-ups per second.
- A Monitor block that names an output an earlier block already took logs a warning naming both blocks at start; the first wins (D11).
- A reference image of the M1 example (`tests/snapshots/m1_example.png`, 400x32) compared with a tolerance of 0.2 % of the pixels (a recoloured icon fails it); `UPDATE_SNAPSHOTS=1` regenerates it, written by `tess_re.snapshot.write_png`. The sample SVG now uses `currentColor`, so its `Color` is visible.

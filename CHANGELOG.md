# Changelog

## Unreleased

- Package skeleton: `pyproject.toml`, `src/tess_shell`, tooling (ruff, mypy, pytest).
- Command line `tesserae-shell` with `version`; `run` and `check` are wired in later tasks; the other subcommands report "not implemented in M0".
- Config directory lookup (`--config-dir`, `$XDG_CONFIG_HOME`, `~/.config`) and `settings.tdl` reading: every key of the Settings File note, one finding per problem with `file:line:column`.
- Loguru setup: console sink and a daily `log_YYYY-MM-DD.log` (directory 0o700, file 0o600), JSON option, midnight file swap, retention, console-only fallback.
- Instance lock (`flock` on `$XDG_RUNTIME_DIR/tesserae-shell/lock`, exit 4 naming the holder's pid) and `$XDG_RUNTIME_DIR` checks (exit 2).
- `tesserae-shell run`: pre-flight, settings, logging, instance lock, registry (`registry.json`, created and saved atomically), then the engine loop with `keep_alive`; SIGTERM and SIGINT stop it cleanly (exit 0), a second signal forces exit 130. Steps 7 to 12 of the start sequence that need later milestones are logged as not built.
- `tesserae-shell check`: settings, then a syntax check of every `*_Shell.tdl`, `*_Module.tdl`, `*_Style.tdl`, `*_Theme.tdl` and `*_Stylesheet.tdl` under the search directories, with `file:line:column`, `--json`, exit 0, 1 or 2. `run` step 7 does the same scan.

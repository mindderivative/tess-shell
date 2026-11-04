# Changelog

## Unreleased

- Package skeleton: `pyproject.toml`, `src/tess_shell`, tooling (ruff, mypy, pytest).
- Command line `tesserae-shell` with `version`; `run` and `check` are wired in later tasks; the other subcommands report "not implemented in M0".
- Config directory lookup (`--config-dir`, `$XDG_CONFIG_HOME`, `~/.config`) and `settings.tdl` reading: every key of the Settings File note, one finding per problem with `file:line:column`.
- Loguru setup: console sink and a daily `log_YYYY-MM-DD.log` (directory 0o700, file 0o600), JSON option, midnight file swap, retention, console-only fallback.
- Instance lock (`flock` on `$XDG_RUNTIME_DIR/tesserae-shell/lock`, exit 4 naming the holder's pid) and `$XDG_RUNTIME_DIR` checks (exit 2).

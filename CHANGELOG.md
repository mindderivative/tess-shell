# Changelog

## Unreleased

- Package skeleton: `pyproject.toml`, `src/tess_shell`, tooling (ruff, mypy, pytest).
- Command line `tesserae-shell` with `version`; `run` and `check` are wired in later tasks; the other subcommands report "not implemented in M0".
- Config directory lookup (`--config-dir`, `$XDG_CONFIG_HOME`, `~/.config`) and `settings.tdl` reading: every key of the Settings File note, one finding per problem with `file:line:column`.

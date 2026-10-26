---
title: Logging with Loguru
aliases: [Loguru, Shell Logging Option]
type: research
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [research, spec/runtime, needs-verification]
related: ["[[ADR-0007 Shell UI Layer]]", "[[ADR-0008 Tesserae Expression Language]]", "[[40 Specifications]]"]
depends_on: []
---

# Logging with Loguru

> [!summary]
> The maintainer noted (2026-10-25) that Loguru is a great option for logging and for providing warnings and errors. This note records it as the leading candidate for the shell's logging, with what is known and what to check. It is not an accepted decision: no ADR chooses it.

## Why it fits

The shell reports load errors with `file:line:column` and warnings while running (an unresolved reference, a missing module file, a refused file) ([[ADR-0007 Shell UI Layer#Monitors, names and errors (2026-10-25)]]). Loguru gives:

| Need | Loguru |
|---|---|
| Levels for warnings and errors | Standard method per level (`debug`, `info`, `warning`, `error`), and custom levels ([migration guide](https://loguru.readthedocs.io/en/stable/resources/migration.html)) |
| Several destinations | Sinks added with `logger.add`, each with its own level and filter |
| Context on each message | `logger.bind(...)` adds keys such as the file, UID and name to a record's `extra` |
| Threads | The docs say thread safety is managed automatically ([migration guide](https://loguru.readthedocs.io/en/stable/resources/migration.html)). The shell has module threads and a loop thread ([[ADR-0003 Process Model]]) |
| Readable exceptions | `logger.opt(exception=True)` includes a stack trace and variables |
| Redirecting `warnings` | The docs show routing `warnings.showwarning` to Loguru |

The maintainer's earlier Edge Shell design already lists `loguru` in its environment ([design spec §2](file:///home/phil/Projects/pyDev/projects/myShell/docs/superpowers/specs/2026-10-11-edge-shell-design.md)).

## What to check

- **Python 3.14.** PyPI lists `loguru` 0.7.3, uploaded 2024-12-06, with `requires_python` `>=3.5,<4.0`. Its classifiers stop at Python 3.9. The shell's minimum is Python 3.14 ([[ADR-0007 Shell UI Layer#UIDs and the registry (2026-10-25)]]). #needs-verification: that it runs on 3.14 and that it is still maintained (the last release is about ten months old).
- **Variables in tracebacks.** The exception formatting shows variable values. The docs say it can be turned off with `backtrace=False` and `diagnose=False` on a sink. A configuration with module data could leak values into a log file. Decide the defaults. #needs-verification: exact option behaviour against the current docs.
- **Libraries stay quiet.** TEL is a standalone library ([[ADR-0008 Tesserae Expression Language]]). A library should not configure a program's logging. Recommendation: TEL raises errors that carry file, line and column, or uses the standard `logging` module, and the shell turns them into Loguru messages. TEL does not depend on Loguru. #needs-verification: Loguru's guidance for libraries.
- **Standard library records.** Output from other libraries that use `logging` needs routing into Loguru. The pages read do not describe it.
- **Where the log goes.** The shell's config directory is `$HOME/.config/tesserae-shell/` ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]]); the log location, rotation and retention are not decided.

## Open

- [ ] Choose a logger in an ADR or the runtime spec (`40 Specifications/Runtime/`). Candidate: Loguru.
- [ ] Verify Python 3.14 support and maintenance.
- [ ] Decide the log file location, rotation and retention.
- [ ] Decide the defaults for variable display in tracebacks.
- [ ] Decide how TEL reports problems without depending on the shell's logger.

## Links

- [Loguru on GitHub](https://github.com/Delgan/loguru) · [documentation](https://loguru.readthedocs.io/en/stable/index.html) · [PyPI](https://pypi.org/project/loguru)
- [[ADR-0007 Shell UI Layer]] · [[ADR-0008 Tesserae Expression Language]] · [[90 Research]]

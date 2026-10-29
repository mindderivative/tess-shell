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
> The maintainer noted (2026-10-25) that Loguru is a great option for logging and for providing warnings and errors. This note records it as the leading candidate for the shell's logging, with what is known and what to check. The maintainer reports it is stable, actively supported and works on Python 3.14. It is not an accepted decision: no ADR chooses it.

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

- **Python 3.14 and maintenance (resolved).** The maintainer reports Loguru is in stable release mode, considered feature complete with consistent updates, actively supported, works on Python 3.14, and that its last official release is two years old while package maintainers keep building and signing updated package iterations (2026-10-25). Checked against the repository: the newest commit is dated 2026-10-25 19:46 UTC (documentation, about ten hours before the check); the newest release is 0.7.3, published 2024-12-06 (PyPI's latest too); and `pyproject.toml` on the main branch lists Python 3.10 to 3.15 classifiers and `requires-python >=3.5` ([GitHub](https://github.com/Delgan/loguru)). The PyPI release's own classifiers stop at 3.9, so 3.14 support is in the repository's main branch and the maintainer's report, not in a published release's metadata. The shell's minimum is Python 3.14 ([[ADR-0007 Shell UI Layer#UIDs and the registry (2026-10-25)]]). Because the last published release is old, pin the version and check that 0.7.3 imports and runs on 3.14 in the first build. #needs-verification
- **Variables in tracebacks.** The exception formatting shows variable values. The docs say it can be turned off with `backtrace=False` and `diagnose=False` on a sink. A configuration with module data could leak values into a log file. Decide the defaults. #needs-verification: exact option behaviour against the current docs.
- **Libraries stay quiet.** TEL is a standalone library ([[ADR-0008 Tesserae Expression Language]]). A library should not configure a program's logging. Recommendation: TEL raises errors that carry file, line and column, or uses the standard `logging` module, and the shell turns them into Loguru messages. TEL does not depend on Loguru. #needs-verification: Loguru's guidance for libraries.
- **Standard library records.** Output from other libraries that use `logging` needs routing into Loguru. The pages read do not describe it.
- **Where the log goes.** The shell's config directory is `$HOME/.config/tesserae-shell/` ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]]); the log location, rotation and retention are not decided.

## Open

- [ ] Choose a logger in an ADR or the runtime spec (`40 Specifications/Runtime/`). Candidate: Loguru; the choice is question 1 of [[Logging#Open questions]] (written 2026-10-28).
- [x] Python 3.14 support and maintenance: confirmed by the maintainer and the repository (see above). Still to test: that the pinned release runs on 3.14.
- [x] Default log location: `$HOME/.config/tesserae-shell/logs/`, configurable in `settings.yaml` (decided 2026-10-27, [[Settings File]]).
- [x] Log file naming `log_yyyy-mm-dd.log`, a new file each local day, retention left to the user (decided 2026-10-27, [[Settings File#Log files]]). A Loguru 0.7.3 test showed the `{time:YYYY-MM-DD}` path field works and a restart appends, but rotation adds a timestamp suffix to the finished file, so the shell swaps the sink itself at midnight.
- [ ] Decide the defaults for variable display in tracebacks: proposed `diagnose` off, tested 2026-10-28 ([[Logging#Safety]]).
- [ ] Decide how TEL reports problems without depending on the shell's logger.

## Links

- [Loguru on GitHub](https://github.com/Delgan/loguru) · [documentation](https://loguru.readthedocs.io/en/stable/index.html) · [PyPI](https://pypi.org/project/loguru)
- [[ADR-0007 Shell UI Layer]] · [[ADR-0008 Tesserae Expression Language]] · [[90 Research]]

---
title: Runtime
aliases: [Runtime Specs]
type: moc
status: review
owner: phil
created: 2026-10-25
updated: 2026-11-03
tags: [moc, spec/runtime]
---

# Runtime

| Note                                    | Purpose                                                                                   | Status |
|-----------------------------------------|-------------------------------------------------------------------------------------------|--------|
| [Shell Start and Stop](Shell%20Start%20and%20Stop.md) | The start sequence, running with no windows, the stop sequence, one instance, exit codes  | draft  |
| [Config Discovery and Registry](Config%20Discovery%20and%20Registry.md) | Finding files, names, UIDs, `registry.json`, the UID write, references                    | draft  |
| [Validation and Errors](Validation%20and%20Errors.md) | The validation pipeline, the error record, `file:line:column`, severities                 | draft  |
| [Logging](Logging.md) | The logger, sinks, levels, the record, who writes, safety, cost                           | draft  |
| [IPC and CLI](IPC%20and%20CLI.md) | The D-Bus interface the shell exports, the `tesserae-shell` command, exit codes, security | draft  |
| [Hot Reload](Hot%20Reload.md) | Watching files, the reload pipeline, the diff, what applies live, what reopens            | draft  |
| [Expression Language Requirements](Expression%20Language%20Requirements.md) | What the shell needs from the Tesserae Expression Language                                | draft  |

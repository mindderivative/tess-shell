---
title: Runtime
aliases: [Runtime Specs]
type: moc
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [moc, spec/runtime]
related: ["[[40 Specifications]]", "[[Index]]"]
depends_on: []
---

# Runtime

| Note | Purpose | Status |
|---|---|---|
| [[Shell Start and Stop]] | The start sequence, running with no windows, the stop sequence, one instance, exit codes | draft |
| [[Config Discovery and Registry]] | Finding files, names, UIDs, `registry.json`, the UID write, references | draft |
| [[Validation and Errors]] | The validation pipeline, the error record, `file:line:column`, severities | draft |
| [[IPC and CLI]] | The D-Bus interface the shell exports, the `tesserae-shell` command, exit codes, security | draft |
| [[Hot Reload]] | Watching files, the reload pipeline, the diff, what applies live, what reopens | draft |
| [[Expression Language Requirements]] | What the shell needs from the Tesserae Expression Language | draft |

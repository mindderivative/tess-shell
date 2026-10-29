---
title: 42 Python API
aliases: [Python API]
type: moc
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [moc, api]
related: ["[[Index]]", "[[AGENTS]]"]
depends_on: []
---

# 42 Python API

What a module author, and a shell written in Python, can rely on. The shell is the only thing that touches tre; the Python API is how modules and Python-built shells reach it.

| Note                                    | Purpose                                                | Status |
|-----------------------------------------|--------------------------------------------------------|--------|
| [[Module Contract]] | The class, lifecycle, rules, failures                  | draft  |
| [[Module Context]] | `self.ctx`: config, send, uses, D-Bus, threads, timers | draft  |
| [[Value Types and Conversion]] | What a module sends and what the shell converts        | draft  |
| [[Python Builder]] | The Python form of a shell file; requirements stub     | draft  |

Parts marked **decided** come from the ADRs; names and signatures are proposals. Not started: the surface and widget API for Python-built shells, the registry API, the shell package layout and versioning.

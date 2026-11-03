---
title: 42 Python API
aliases: [Python API]
type: moc
status: draft
owner: phil
created: 2026-10-26
updated: 2026-11-03
tags: [moc, api]
---

# 42 Python API

What a module author, and a shell written in Python, can rely on. The shell is the only thing that touches tre; the Python API is how modules and Python-built shells reach it.

| Note                                    | Purpose                                                | Status |
|-----------------------------------------|--------------------------------------------------------|--------|
| [Module Contract](Module%20Contract.md) | The class, lifecycle, rules, failures                  | draft  |
| [Module Context](Module%20Context.md) | `self.ctx`: config, send, uses, D-Bus, threads, timers | draft  |
| [Value Types and Conversion](Value%20Types%20and%20Conversion.md) | What a module sends and what the shell converts        | draft  |
| [Python Builder](Python%20Builder.md) | The Python form of a shell file; requirements stub     | draft  |
| [TDL Library API](TDL%20Library%20API.md) | The public API of the `tess_dl` parser library (`tess-dl`) | draft  |

Parts marked **decided** come from the ADRs; names and signatures are proposals. Not started: the surface and widget API for Python-built shells, the registry API, the shell package layout and versioning.

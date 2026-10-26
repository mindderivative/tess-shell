---
title: Python Builder
aliases: [Python Front-End, Shell in Python]
type: api
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [api, needs-verification]
related: ["[[42 Python API]]", "[[ADR-0007 Shell UI Layer]]", "[[ADR-0008 Tesserae Expression Language]]", "[[Expression Language Requirements]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# Python builder

> [!summary]
> A shell can be written in YAML or in Python with the same result (maintainer, 2026-10-25). This note holds the requirements for the Python form of the shell file and what is open. It is a requirements stub: the design waits on the shell model and the TEL Python form, neither of which exists yet.

## What is decided

- Python and YAML give the same result. A shell written in Python builds the same tree as one written in YAML ([[ADR-0007 Shell UI Layer#View format: a full expression language, and Python as an equal front-end (2026-10-25)]]).
- Python is for what YAML should not do: major logic, heavy calculation, terminal and system access. That is the module's job ([[Module Contract]]).
- TEL has a Python form so expressions can be built as code ([[Expression Language Requirements]] T7). TEL is an expression language only ([[ADR-0008 Tesserae Expression Language]]).
- The shell file format is the shell's: `shell:`, `type:`, `kind:`, `children:`, `import:`, names and UIDs ([[ADR-0007 Shell UI Layer]]).

## Requirements

| # | Requirement |
|---|---|
| P1 | Every construct in a shell file has a Python equivalent: roots, surfaces (`kind`), widgets, styles, modules, imports, monitors |
| P2 | A parity test shows the same shell written both ways builds the same model |
| P3 | The Python form goes through the same validation, with the same errors; a position is a Python source line where there is no YAML file |
| P4 | Names, UIDs and the registry work the same. A Python shell still needs a file for the UID to be written into; where is open |
| P5 | Expressions written as TEL strings or as TEL's Python form give the same compiled expression |
| P6 | Python-built shells hot-reload as files do (a changed `.py` rebuilds the model), or they are static and say so |
| P7 | A shell can mix: a YAML shell importing a Python-defined part, or the reverse |

## Open questions

- [ ] What is the entry point: a function that returns the model, a class, or a script that calls the shell API.
- [ ] How a Python-defined shell is found and where its UID is stored (P4).
- [ ] Whether the Python form is a separate package or part of the shell package.
- [ ] How errors point to Python source lines (P3).
- [ ] Whether imports between Python and YAML are v1 (P7).
- [ ] The TEL Python form: owned by the TEL project; the shell side needs it before this note can be designed.

## Acceptance criteria

- [ ] A bar with a clock, workspaces and tray written in Python builds the same tree as its YAML.
- [ ] The same validation error appears for the same mistake in both forms.
- [ ] A Python shell hot-reloads or states that it does not.

## Links

- [[42 Python API]] · [[ADR-0007 Shell UI Layer]] · [[Expression Language Requirements]]

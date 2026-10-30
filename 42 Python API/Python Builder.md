---
title: Python Builder
aliases: [Python Front-End, Shell in Python]
type: api
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-29
tags: [api, needs-verification]
related: ["[[42 Python API]]", "[[ADR-0007 Shell UI Layer]]", "[[ADR-0008 Tesserae Expression Language]]", "[[ADR-0014 Shell File Language]]", "[[Expression Language Requirements]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# Python Builder

> [!summary]
> A shell can be written in TDL or in Python with the same result (maintainer, 2026-10-25, said of YAML before [[ADR-0014 Shell File Language]]). This note holds the requirements for the Python form of the shell file and what is open. It is a requirements stub: the design waits on the shell model and the TEL Python form, neither of which exists yet.

## What is Decided

- Python and the file form give the same result. A shell written in Python builds the same tree as one written in TDL. The TDL parser and the Python builder produce the same tree, and the parity test stands ([[ADR-0014 Shell File Language#What TDL Is (Decided)]], item 13; the original decision, for YAML: [[ADR-0007 Shell UI Layer#View format: a full expression language, and Python as an equal front-end (2026-10-25)]]).
- Python is for what a shell file should not do: major logic, heavy calculation, terminal and system access. That is the module's job ([[Module Contract]]).
- TEL has a Python form so expressions can be built as code ([[Expression Language Requirements]] T7). TEL is an expression language only ([[ADR-0008 Tesserae Expression Language]]).
- The shell file format is the shell's: `shell:`, `type:`, `kind:`, `children:`, `import:`, names and UIDs ([[ADR-0007 Shell UI Layer]]).

## Requirements

| #  | Requirement                                                                                                                            |
|----|----------------------------------------------------------------------------------------------------------------------------------------|
| P1 | Every construct in a shell file has a Python equivalent: roots, surfaces (`kind`), widgets, styles, modules, imports, monitors, and `if` and `for` blocks ([[#If and For (Proposed Signature Sketch)]]) |
| P2 | A parity test shows the same shell written both ways (Python and TDL) builds the same tree, including `if` and `for`                    |
| P3 | The Python form goes through the same validation, with the same errors; a position is a Python source line where there is no TDL file  |
| P4 | Names, UIDs and the registry work the same. A Python shell still needs a file for the UID to be written into; where is open            |
| P5 | Expressions written as TEL strings or as TEL's Python form give the same compiled expression                                           |
| P6 | Python-built shells hot-reload as files do (a changed `.py` rebuilds the model), or they are static and say so                         |
| P7 | A shell can mix: a TDL shell importing a Python-defined part, or the reverse                                                           |

## If and For (Proposed Signature Sketch)

[[ADR-0014 Shell File Language#Conditions and Repeats (Decided)]] gives the file form two structure keywords, `if` (with an optional `else`) and `for` (with a required `key`), and says the builder gets the same two constructs so the parity test covers them. The ADR fixes no Python signature. The sketch below is proposed: names, argument order and the way a block takes children are not decided, and nothing here is TEL's Python form (owned by the TEL project).

```python
# Illustration only. Each line pairs with the TDL form above it.

# if {{ battery.present }} { Label { text: ... } } else { Icon { svg: battery-missing } }
If(expr("battery.present"),
   then=[Label(text=tpl("Battery {{ battery.percent }}%"))],
   otherwise=[Icon(svg="battery-missing")])      # "else" is a Python keyword

# for item in {{ tray.items }} key {{ item.id }} { Icon { svg: {{ item.icon }} } }
For("item", expr("tray.items"),
    key=expr("item.id"),
    body=[Icon(svg=expr("item.icon"))])
```

- `expr(...)` and `tpl(...)` stand for a TEL expression and a TEL template, however the TEL Python form builds them (P5).
- `If` and `For` carry structure only and run no code, as in the file form. `For` binds one name; its `key` is required; `else if` does not exist (nest an `If` in `otherwise`). The reserved words `if`, `else`, `for`, `in` and `key` apply to block names in both forms.
- `then`, `otherwise` and `body` take the same children a `children { }` block takes.

## Open Questions

- [ ] What is the entry point: a function that returns the model, a class, or a script that calls the shell API.
- [ ] How a Python-defined shell is found and where its UID is stored (P4).
- [ ] Whether the Python form is a separate package or part of the shell package.
- [ ] How errors point to Python source lines (P3).
- [ ] Whether imports between Python and TDL are v1 (P7).
- [ ] The signatures of `If` and `For` ([[#If and For (Proposed Signature Sketch)]]) and whether the builder tree keeps comments as the TDL tree does (the parity test compares trees; comments may not count).
- [ ] The TEL Python form: owned by the TEL project; the shell side needs it before this note can be designed.

## Acceptance Criteria

- [ ] A bar with a clock, workspaces and tray written in Python builds the same tree as its TDL file.
- [ ] A shell with an `if`/`else` and a `for` written in Python builds the same tree as the same shell in TDL.
- [ ] The same validation error appears for the same mistake in both forms.
- [ ] A Python shell hot-reloads or states that it does not.

## Links

- [[42 Python API]] · [[ADR-0007 Shell UI Layer]] · [[ADR-0014 Shell File Language]] · [[Expression Language Requirements]]

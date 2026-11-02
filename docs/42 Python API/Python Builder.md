---
title: Python Builder
aliases: [Python Front-End, Shell in Python]
type: api
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-30
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
- The shell file format is the shell's: the metadata block (`TDL`, the version pins, `Name`, `UID`), one root block that names the file type (`Shell`, `Module`, `Style`, `Stylesheet`, `Theme`, `Settings`), block heads as types (`Monitor`, `Bar`, `Text`, `Clock`), `Name:`, `Children`, `Import` and UIDs ([[TDL Language]], [[ADR-0014 Shell File Language#Second-Sketch Decisions (2026-10-30)]], [[ADR-0007 Shell UI Layer]]). The builder produces the same tree as the parser, including the metadata block and the root block: a builder call creates a `Shell`, `Module` or other root, and the root must agree with the file suffix when the tree is written to a file. The loader's tree is an ordered list of entries (head, properties, children) that keeps repeated names, and the builder produces the same (D12, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).

## Requirements

| #  | Requirement                                                                                                                            |
|----|----------------------------------------------------------------------------------------------------------------------------------------|
| P1 | Every construct in a shell file has a Python equivalent: the metadata block, the root block, `Monitor` blocks, surfaces (`Bar`, `Frame`, `Panel`, `Popup`), blocks, styles, module uses, imports, and `If` and `For` blocks ([[#Metadata and Heads (Proposed Signature Sketch)]], [[#If and For (Decided Sketch)]]) |
| P2 | A parity test shows the same shell written both ways (Python and TDL) builds the same tree, including the metadata block, the root block, `If` and `For` |
| P3 | The Python form goes through the same validation, with the same errors; a position is a Python source line where there is no TDL file  |
| P4 | Names, UIDs and the registry work the same. A Python shell still needs a file for the UID to be written into; where is open            |
| P5 | Expressions written as TEL strings or as TEL's Python form give the same compiled expression                                           |
| P6 | Python-built shells hot-reload as files do (a changed `.py` rebuilds the model), or they are static and say so                         |
| P7 | A shell can mix: a TDL shell importing a Python-defined part, or the reverse                                                           |
| P8 | The builder can set the metadata block: the `TDL:` version, the version pins (`TEL`, `TRE`, `Shell`), the required `Name:`, `UID:` and any extra metadata keys ([[TDL Language#The Metadata Block]]) |

## Metadata and Heads (Proposed Signature Sketch)

The file form starts with a metadata block, then one root block, and a block's head is its type ([[TDL Language]]). The builder needs a way to set the metadata, a root constructor per file type and a constructor per head. No signature is decided; the sketch shows the idea and nothing more.

```python
# Illustration only. Each line pairs with the TDL form above it.

# ---
# TDL: 0.1
# TEL: 0.1
# TRE: 0.5.9
# Shell: 0.1
# Name: Root_Shell
# ---
# Shell {
#   Monitor { Name: Main, Index: 0, Children { Bar { Name: Top_Bar, Edge: TOP, Height: 32 } } }
# }
shell = Shell(                                              # the root block: creates a Shell root
    meta={"TDL": "0.1", "TEL": "0.1", "TRE": "0.5.9", "Shell": "0.1",
          "Name": "Root_Shell"},                            # extra metadata keys go in the same mapping
    children=[
        Monitor(name="Main", index=0, children=[            # Index, Connector or Description picks the monitor
            Bar(name="Top_Bar", edge="TOP", height=32),     # the head is the type: Bar, Frame, Panel, Popup
        ]),
    ])

# A module root: Module { Params { ... } Style ... layout ... }, metadata Name: Clock
clock = Module(meta={"TDL": "0.1", "TEL": "0.1", "TRE": "0.5.9", "Shell": "0.1", "Name": "Clock"},
               params={...}, children=[...])
```

- Python and tre identifiers keep their own case (`name=`, `index=`); the builder maps them to the Capitalised TDL keys (`Name`, `Index`), as it maps `exclusive_zone` to `Exclusive_Zone`.
- The root constructors (`Shell`, `Module`, `Style`, `Stylesheet`, `Theme`, `Settings`) each create the root block of that file type, so the file type is never a metadata key. A module's metadata `Name:` (its call name and the root of its path, `Root_Shell.Main.Top_Bar`) is set in `meta` the same way.
- The constructors take the TDL keys in Python spelling and the TDL enum values as upper-case strings (`edge="TOP"`, `layer="OVERLAY"`, `align="START"`, `flex="HORIZONTAL"`); `Monitor`, `Bar` and `Panel` use the keys of [[Shell File]], [[Bar]] and [[Panel]] (`Edge`, `Width`, `Height`, `Alignment`, `Offset`, `Gap` for a Bar; `Offset`, `Margin`, `Padding` for a Panel; four-sided values in the order left, top, right, bottom). #needs-verification: the constructor signatures are a sketch.
- A module use is a head too (`Clock(name="main_clock")`). Python keys it `Clock@<uid>` as with a parsed use, and passes that key back to name the use in an action (D23, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).

## If and For (Decided Sketch)

[[ADR-0014 Shell File Language#Conditions and Repeats (Decided)]] gives the file form two structure keywords, `If` (with an optional `Else`) and `For` (with a required `Key`), and says the builder gets the same two constructs so the parity test covers them. The sketched signatures `If(cond, then, otherwise)` and `For(name, iterable, key, body)` stand (D15, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]). Nothing here is TEL's Python form (owned by the TEL project).

```python
# Illustration only. Each line pairs with the TDL form above it.

# If {{ battery.present }} { Label { Text: ... } } Else { Icon { Svg: battery-missing } }
If(expr("battery.present"),
   then=[Label(text=tpl("Battery {{ battery.percent }}%"))],
   otherwise=[Icon(svg="battery-missing")])      # "else" is a Python keyword

# For item In {{ tray.items }} Key {{ item.id }} { Icon { Svg: {{ item.icon }} } }
For("item", expr("tray.items"),
    key=expr("item.id"),
    body=[Icon(svg=expr("item.icon"))])
```

- `expr(...)` and `tpl(...)` stand for a TEL expression and a TEL template, however the TEL Python form builds them (P5).
- `If` and `For` carry structure only and run no code, as in the file form. `For` binds one name; its `key` is required; `Else If` does not exist (nest an `If` in `otherwise`). The reserved words `If`, `Else`, `For`, `In` and `Key` apply to block names in both forms.
- `then`, `otherwise` and `body` take the same children a `Children { }` block takes.

## Open Questions

- [ ] What is the entry point: a function that returns the model, a class, or a script that calls the shell API.
- [ ] How a Python-defined shell is found and where its UID is stored (P4).
- [ ] Whether the Python form is a separate package or part of the shell package.
- [ ] How errors point to Python source lines (P3).
- [ ] Whether imports between Python and TDL are v1 (P7).
- [x] `If` and `For` signatures stand, and the parity test compares trees, including metadata, and ignores comments and layout (D15, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).
- [ ] The signatures of the metadata setter and the head constructors ([[#Metadata and Heads (Proposed Signature Sketch)]]).
- [ ] The TEL Python form: owned by the TEL project; the shell side needs it before this note can be designed.

## Acceptance Criteria

- [ ] A bar with a clock, workspaces and tray written in Python builds the same tree as its TDL file, including the metadata block.
- [ ] A shell with an `If`/`Else` and a `For` written in Python builds the same tree as the same shell in TDL.
- [ ] The same validation error appears for the same mistake in both forms.
- [ ] A Python shell hot-reloads or states that it does not.

## Links

- [[42 Python API]] · [[ADR-0007 Shell UI Layer]] · [[ADR-0014 Shell File Language]] · [[Expression Language Requirements]]

---
title: Expression Language Requirements
aliases: [TEL Requirements, Shell Requirements on TEL]
type: spec
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-30
tags: [spec/runtime, needs-verification]
related: ["[[ADR-0008 Tesserae Expression Language]]", "[[ADR-0007 Shell UI Layer]]", "[[Expression Languages for YAML]]"]
depends_on: ["[[ADR-0008 Tesserae Expression Language]]"]
---

# Expression Language Requirements

> [!summary]
> What the shell needs from the Tesserae Expression Language (TEL). The shell drives TEL from these needs; TEL does not depend on the shell. This note is the shell's side only. TEL's own grammar and design live in the TEL project.

## Purpose and Scope

TEL evaluates expressions written in shell files, which are written in TDL ([[ADR-0014 Shell File Language]]): an expression sits in a `{{ ... }}` slot on one line, and in TDL it needs no quotes, even when a value begins with `{{` (YAML needed quotes there). The slot holds values bound to module data. TEL evaluates expressions (values) only. TDL owns structure: its own `If`, `Else` and `For ... In ... Key` blocks decide whether an entry exists and how many copies there are, and the shell's model builder evaluates a condition or iterable through TEL and rebuilds that branch or entry (D11, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]). T3 and T8 below, from 2026-10-25, first gave TEL structure; D11 narrowed them to expression-level conditionals and comprehensions. Python is the front-end for everything TEL should not do: heavy calculation, terminal and system access ([[ADR-0007 Shell UI Layer#View format: a full expression language, and Python as an equal front-end (2026-10-25)]]).

## Requirements from the Shell

| #   | Requirement                                                                                                                                                                                                                                                                                                                                                                                   | Source                                                                       |
|-----|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| T1  | **Independent library.** Pure Python, installed like any library. It imports neither the shell, tre nor Tesserae UI.                                                                                                                                                                                                                                                                          | [[ADR-0008 Tesserae Expression Language]]                                      |
| T2  | **Safe.** Evaluates expressions (values) only. No file, process, network or system access, no `eval`, no attribute escape. Limits on steps, size and repeated or powered values, so a bad expression is an error and never a hang.                                                                                                                                                            | Runs from a configuration file                                               |
| T3  | **Values, one language.** Values (a number, text or colour), including an expression-level conditional (`a if c else b`). Structure (whether an entry exists, how many copies) is TDL's `If` and `For`, not TEL's; the shell evaluates the condition or iterable through TEL (narrowed 2026-10-30 by D11; first decided 2026-10-25 as "TEL owns both"). | [[Expression Languages for YAML#What the shell needs from it]]; [[ADR-0014 Shell File Language#Conditions and Repeats (Decided)]] |
| T4  | **Live.** Compile once, evaluate many times. The caller can re-run an expression when an input changes.                                                                                                                                                                                                                                                                                       | Clock, battery, volume change while the shell runs                           |
| T5  | **Name tracking.** After evaluation the caller can ask which names the expression read, so only expressions whose inputs changed are re-run. The name lookup is a plug-in point the caller supplies (a scope), so TEL needs no reactive types of its own.                                                                                                                                     | Python is never in layout or paint ([[AGENTS#3. Layering principle]]) |
| T6  | **Positions.** Every error carries file, line and column, with an origin the caller supplies so a column inside a `{{ }}` slot maps to the file. T17 adds the slot's origin from the TDL parser.                                                                                                                                                                                                                                               | [[AGENTS#3. Layering principle]]                                      |
| T7  | **Same result from Python.** The language has a Python form, so a shell written in Python builds the same tree as one written in TDL.                                                                                                                                                                                                                                                        | [[Goals and Non-Goals]] G1                                   |
| T8  | **Expression-level conditionals and comprehensions.** A conditional that yields a value, and a comprehension that builds a list value from a list (workspaces, tray items), inside one expression. A conditional entry (`If`) and a repeated entry (`For`) are TDL's, not TEL's; the `{if condition, a, b}` form is dropped (narrowed 2026-10-30 by D11). | Maintainer, 2026-10-25; D11 |
| T9  | **Values the renderer accepts.** Results match types tre accepts. Conversions (for example HEX to RGBA) are the shell's; TEL returns plain values.                                                                                                                                                                                                                                            | [[ADR-0007 Shell UI Layer#Module data reaches the view through shell entry points (2026-10-25)]]                                      |
| T10 | **Versioned.** A file can say which language version it uses, so later changes do not break old files.                                                                                                                                                                                                                                                                                        | The metadata block carries `TDL:` and a file-type version already ([[TDL Language#The Metadata Block]]) |
| T11 | **Python 3.14 or later**, no heavy dependencies.                                                                                                                                                                                                                                                                                                                                              | [[ADR-0007 Shell UI Layer]]                                      |
| T12 | **Testable headless.** Parse and evaluate without a display.                                                                                                                                                                                                                                                                                                                                  | [[AGENTS#12. Design completeness checklist]]                                      |
| T13 | **Standalone.** Anyone can use TEL in plain data files (YAML, or TDL) by importing its parser in a Python script, with no shell and no Tesserae UI.                                                                                                                                                                                                                                                                | [[ADR-0008 Tesserae Expression Language]]                                      |
| T15 | **Expression language only.** TEL has no statements, handlers or event handling; the shell does all of that and may use TEL to evaluate argument expressions at event time. If the shell puts an `event` name in the scope it supplies, TEL treats it as an ordinary name. Confirmed by the maintainer, 2026-10-26 (told to `tess-el`; `tess-el` records it as its D10, replacing D2 and D5). | [[ADR-0008 Tesserae Expression Language]]                                      |
| T16 | **Compile off the loop.** Compiling an expression is a self-contained computation: it takes its input and returns the compiled result, holding no state shared with other calls, so the shell can compile on a worker thread and hand the result to the loop.                                                                                                                                 | Maintainer, 2026-10-28; [[Hot Reload]]              |
| T17 | **Origin of each slot (proposed, not yet sent to the TEL project).** The TDL parser tells TEL where each `{{ }}` slot starts, as an `Origin`: file, line and column, 1-based. TEL adds the position inside the expression to it, so a TEL error points to the right place in the file and the shell does no offset arithmetic. The slot is on one line, so the column is a plain offset. TEL already takes an expression or a template with an `Origin(file, line, column)` (TEL project `docs/language.md` section 8 and `src/tel/origin.py`, read 2026-10-29); this item confirms the shell relies on it. Proposed. | [[ADR-0014 Shell File Language#Consequences]]; [[Validation and Errors]] |
| T18 | **Child scope for a loop body (proposed, not yet sent to the TEL project).** TEL accepts a child scope that adds the name a TDL `For` loop binds (for example `item`) for the body only, on top of the scope the caller supplies. The name is visible to expressions inside the body and nowhere else, and name tracking (T5) still reports the names read, including names read through the parent scope. Proposed. | [[ADR-0014 Shell File Language#Conditions and Repeats (Decided)]] |
| T19 | **Question-mark conditional (proposed, optional, not yet sent to the TEL project).** TEL accepts `cond ? a : b` as another spelling of `a if cond else b`, so a style value reads `Color: {{ hovered ? "#1e1e2e" : "#313244" }}`. The existing `a if c else b` stays. TEL parses with Python's `ast` (TEL project `docs/language.md`, section 4), and `?` is not Python, so this needs a read-time rewrite before the parse that skips strings and leaves slices, dict displays and `:` in f-strings alone; the cost and whether it fits TEL's whitelist principle are the TEL project's to judge. Without it the same value is `Color: {{ "#313244" if not hovered else "#1e1e2e" }}`, which works today. | Maintainer, 2026-10-29; [[ADR-0014 Shell File Language#Open Items]] |
| T14 | **Efficient.** Much more efficient than Tesserae's `expr.py`: parse once, cheap re-evaluation, nothing re-run unless an input changed. A target and a benchmark are set in the TEL project.                                                                                                                                                                                                   | Maintainer, 2026-10-25                                                       |

## What Tesserae's `expr.py` Shows

From the local clone (commit `0eda3fe`, read 2026-10-25). It already provides the sandbox by `ast` whitelist (T2), limits (T2), static against reactive expressions (T4, T5), a scope lookup (T5), and positions with a caret in errors (T6). It also parses handlers (short lists of statements); TEL will not (T15). Its gaps for TEL: it imports `tesserae.reactive` (against T1), and nothing in the module header covers a Python front-end that builds the same tree (T7). TEL is a redesign that starts from `expr.py` (decided 2026-10-25).

## Open Questions

- [x] TEL's name: Tesserae Expression Language, `tel` in code. PyPI: `tesserae-expression-language`, else `tel` (taken on 2026-10-25), else `tess-el`.
- [x] Redesign or extraction: a redesign starting from `expr.py`.
- [x] Who owns structure: TDL owns `If` and `For`; TEL evaluates expressions (values) only (D11, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]; first answered 2026-10-25 as TEL owning both).
- [x] TEL's repository and licence: [mindderivative/tess-el](https://github.com/mindderivative/tess-el), MIT (2026-10-25). Local project `/home/phil/Projects/pyDev/projects/tess-el`.
- [ ] TEL's versioning and release process (the maintainer's).
- [x] Statements and events: none in TEL. The maintainer told `tess-el` that TEL is an expression language only and that statements, events and handlers belong to the shell (2026-10-26, T15). Syntax and form are worked out in the TEL project (2026-10-25).
- [ ] How the shell and any other user share TEL's releases without blocking each other.
- [ ] T17 and T18 are proposed requirements from ADR-0014, not yet sent to the TEL project. The maintainer carries them; nobody has messaged the TEL project.
- [x] T3 and T8 are narrowed to expression-level conditionals and comprehensions; structure conditions and repeats are TDL's (D11, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]). T17, T18 and T19 are unchanged.

## Acceptance Criteria

- [ ] A TEL expression compiles once and evaluates against a caller-supplied scope.
- [ ] After evaluation, the caller can list the names it read.
- [ ] (T17, proposed) A TEL error in a slot reports the slot's file line and the column inside the expression, from the `Origin` the TDL parser supplied.
- [ ] (T18, proposed) A name added by a child scope resolves inside the `For` body and is unknown outside it.
- [ ] An expression with an error reports file, line and column inside the TDL file.
- [ ] An expression that tries file, process or attribute access is refused with a clear error.
- [ ] An expression over a limit fails with an error and returns promptly.
- [ ] The same shell written in Python and in TDL builds the same tree.
- [ ] TEL installs and runs on Python 3.14 with no import of the shell, tre or Tesserae UI.

## Links

- [[ADR-0008 Tesserae Expression Language]] · [[ADR-0007 Shell UI Layer]] · [[Expression Languages for YAML]] · [[40 Specifications]]

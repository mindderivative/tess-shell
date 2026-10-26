---
title: Expression Language Requirements
aliases: [TEL Requirements, Shell Requirements on TEL]
type: spec
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [spec/runtime, needs-verification]
related: ["[[ADR-0008 Tesserae Expression Language]]", "[[ADR-0007 Shell UI Layer]]", "[[Expression Languages for YAML]]"]
depends_on: ["[[ADR-0008 Tesserae Expression Language]]"]
---

# Expression language requirements

> [!summary]
> What the shell needs from the Tesserae Expression Language (TEL). The shell drives TEL from these needs; TEL does not depend on the shell. This note is the shell's side only. TEL's own grammar and design live in the TEL project.

## Purpose and scope

TEL evaluates expressions written in shell YAML files (`{if condition, ...}`, values bound to module data) and may express structure (`if`, repeat). Python is the front-end for everything TEL should not do: heavy calculation, terminal and system access ([[ADR-0007 Shell UI Layer#View format: a full expression language, and Python as an equal front-end (2026-10-25)]]).

## Requirements from the shell

| # | Requirement | Source |
|---|---|---|
| T1 | **Independent library.** Pure Python, installed like any library. It imports neither the shell, tre nor Tesserae UI. | [[ADR-0008 Tesserae Expression Language]] |
| T2 | **Safe.** Evaluates values and structure only. No file, process, network or system access, no `eval`, no attribute escape. Limits on steps, size and repeated or powered values, so a bad expression is an error and never a hang. | Runs from a configuration file |
| T3 | **Two jobs, one language.** Values (a number, text or colour) and structure (whether an entry exists, how many copies). TEL owns both (decided 2026-10-25). | [[Expression Languages for YAML#What the shell needs from it]] |
| T4 | **Live.** Compile once, evaluate many times. The caller can re-run an expression when an input changes. | Clock, battery, volume change while the shell runs |
| T5 | **Name tracking.** After evaluation the caller can ask which names the expression read, so only expressions whose inputs changed are re-run. The name lookup is a plug-in point the caller supplies (a scope), so TEL needs no reactive types of its own. | Python is never in layout or paint ([[AGENTS#3. Layering principle]]) |
| T6 | **Positions.** Every error carries file, line and column, with an origin the caller supplies so a column inside a YAML scalar maps to the file. | [[AGENTS#3. Layering principle]] |
| T7 | **Same result from Python.** The language has a Python form, so a shell written in Python builds the same tree as one written in YAML. | [[Goals and Non-Goals]] G1 |
| T8 | **Conditions and repeaters.** `{if condition, a, b}` is the maintainer's example. Repeaters make one entry per item of a list (workspaces, tray items). | Maintainer, 2026-10-25 |
| T9 | **Values the renderer accepts.** Results match types tre accepts. Conversions (for example HEX to RGBA) are the shell's; TEL returns plain values. | [[ADR-0007 Shell UI Layer#Module data reaches the view through shell entry points (2026-10-25)]] |
| T10 | **Versioned.** A file can say which language version it uses, so later changes do not break old files. | The `shell:` key carries a version already |
| T11 | **Python 3.14 or later**, no heavy dependencies. | [[ADR-0007 Shell UI Layer]] |
| T12 | **Testable headless.** Parse and evaluate without a display. | [[AGENTS#12. Design completeness checklist]] |
| T13 | **Standalone.** Anyone can use TEL in plain YAML by importing its parser in a Python script, with no shell and no Tesserae UI. | [[ADR-0008 Tesserae Expression Language]] |
| T14 | **Efficient.** Much more efficient than Tesserae's `expr.py`: parse once, cheap re-evaluation, nothing re-run unless an input changed. A target and a benchmark are set in the TEL project. | Maintainer, 2026-10-25 |

## What Tesserae's `expr.py` shows

From the local clone (commit `0eda3fe`, read 2026-10-25). It already provides the sandbox by `ast` whitelist (T2), limits (T2), static against reactive expressions (T4, T5), a scope lookup (T5), and positions with a caret in errors (T6). It also parses handlers (short lists of statements). Its gaps for TEL: it imports `tesserae.reactive` (against T1), and nothing in the module header covers a Python front-end that builds the same tree (T7). TEL is a redesign that starts from `expr.py` (decided 2026-10-25).

## Open questions

- [x] TEL's name: Tesserae Expression Language, `tel` in code. PyPI: `tesserae-expression-language`, else `tel` (taken on 2026-10-25), else `tess-el`.
- [x] Redesign or extraction: a redesign starting from `expr.py`.
- [x] Who owns structure: TEL owns structure and values.
- [x] TEL's repository and licence: [mindderivative/tess-el](https://github.com/mindderivative/tess-el), MIT (2026-10-25). Local project `/home/phil/Projects/pyDev/projects/tess-el`.
- [ ] TEL's versioning and release process (the maintainer's).
- [x] Syntax, statements and form are worked out in the TEL project (maintainer, 2026-10-25). The shell's needs are T1 to T14 above.
- [ ] How the shell and any other user share TEL's releases without blocking each other.

## Acceptance criteria

- [ ] A TEL expression compiles once and evaluates against a caller-supplied scope.
- [ ] After evaluation, the caller can list the names it read.
- [ ] An expression with an error reports file, line and column inside the YAML file.
- [ ] An expression that tries file, process or attribute access is refused with a clear error.
- [ ] An expression over a limit fails with an error and returns promptly.
- [ ] The same shell written in Python and in YAML builds the same tree.
- [ ] TEL installs and runs on Python 3.14 with no import of the shell, tre or Tesserae UI.

## Links

- [[TEL Project Brief]] (the hand-off for the TEL project) · [[ADR-0008 Tesserae Expression Language]] · [[ADR-0007 Shell UI Layer]] · [[Expression Languages for YAML]] · [[40 Specifications]]

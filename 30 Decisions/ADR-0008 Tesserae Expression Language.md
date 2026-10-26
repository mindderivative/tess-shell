---
title: ADR-0008 Tesserae Expression Language
aliases: [ADR-0008, TEL, Tesserae Expression Language]
type: adr
status: accepted
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [adr, architecture]
related: ["[[ADR-0007 Shell UI Layer]]", "[[ADR-0006 Shell Independent of Tesserae UI]]", "[[Expression Languages for YAML]]", "[[Expression Language Requirements]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# ADR-0008: Tesserae Expression Language (TEL)

> [!summary]
> The shell's expression language is a new one, the **Tesserae Expression Language (TEL)**, designed as a separate Python library. The shell uses it and drives its requirements; TEL does not depend on the shell. Tesserae UI could use it too.

## Context

[[ADR-0007 Shell UI Layer]] decided the view format has a full expression language and left open whether to build one or adopt one. [[Expression Languages for YAML]] surveyed Jinja2, jinjyaml, simpleeval, CEL and others, and recommended adopting a small safe evaluator.

The maintainer chose to design a language of their own (2026-10-25, in chat): it can then do what the shell needs and wants, and Tesserae UI "needs something better than what it is currently using".

What Tesserae has today (local clone `/home/phil/Projects/pyDev/projects/tesserae`, commit `0eda3fe`, read 2026-10-25): `src/tesserae/expr.py`, 1,198 lines, "a sandboxed subset of Python". It parses with Python's `ast`, checks nodes against a whitelist, runs a small evaluator and never `eval`s. It resolves names through a scope, tells static from reactive expressions, applies limits (a step budget, source size, caps on `range`, repeated sequences, `**` and strings), and reports every failure with a line and column. It imports `tesserae.reactive` (`Signal`, `Computed`), so it is tied to Tesserae. Its design is described in Tesserae's `design/yaml-language.md`, section 8.

## Options

### Option A — Design TEL as a separate library (chosen)

- **For:** shaped for what the shell needs; shareable with Tesserae UI; no coupling to either; one language for both.
- **Against:** a third project to design, test and version. Real work: grammar, evaluator, error reporting, limits, docs.

### Option B — Adopt an existing evaluator

simpleeval, CEL or a Jinja2 expression mode ([[Expression Languages for YAML]]).

- **For:** less to write.
- **Against:** their syntax and error reporting are not ours; name tracking for live re-evaluation has to be built around them.

### Option C — Reuse Tesserae's `expr.py` inside the shell

- **Against:** it imports Tesserae's reactive types, which [[ADR-0006 Shell Independent of Tesserae UI]] rules out as a dependency.

## Decision

Accepted 2026-10-25 by the maintainer in chat: **Option A**.

- TEL is designed as a **separate entity**, with its own parser, written in Python and used like any other Python library.
- The shell **uses TEL and drives it from its needs**. TEL does **not** depend on the shell.
- Tesserae UI may use TEL later; TEL does not depend on Tesserae UI either.

Details, decided by the maintainer in chat on 2026-10-25:

- **A redesign, with `expr.py` as the starting point.** Tesserae's `expr.py` is the starting point, not the design. TEL is separated from it and made much more efficient.
- **TEL owns structure and values.** It has everything it needs to run on its own, with no shell and no Tesserae UI. Anyone can adopt it in plain YAML by importing its parser in a Python script.
- **Name.** The Tesserae Expression Language, written `tel` in code, as `tre` is for the engine. For PyPI the maintainer's preference is `tesserae-expression-language`, else `tel`, else `tess-el`. On 2026-10-25 `tel` is already a package on PyPI; no package named `tesserae-expression-language` or `tess-el` was found. #needs-verification: availability when registering.
- **Kept separate from Tesserae.** The maintainer handles all contact with the Tesserae project, including `expr.py`. The shell side does not message the `tesserae` session about it.

## Consequences

- The shell now depends on tre **and TEL**. [[ADR-0006 Shell Independent of Tesserae UI]] and [[ADR-0007 Shell UI Layer]] said "tre only"; TEL is a library, not Tesserae UI, so the independence from Tesserae UI stands.
- The vault holds the shell's requirements on TEL ([[Expression Language Requirements]]). TEL's own design lives in the TEL project, not here. Do not copy its design into this vault; link it once it exists ([[AGENTS#2. Hard rules]], rule 4).
- Tesserae's `expr.py` is the starting point: it shows what worked (sandbox by `ast` whitelist, static against reactive, limits, positions in errors). TEL is a redesign, not an extraction.
- TEL needs its own repository, versioning and licence, and a language version recorded in files. The name is decided (above); the repository, versioning and licence are the maintainer's, not decided.
- Risk: three projects (tre, TEL, the shell) must move together at first. Keep the TEL interface small and stable.

> [!danger] Scope risk
> A language of one's own can grow without limit and runs from a configuration file. Keep it to values and structure with a sandbox, and test that the Python front-end and the YAML give the same tree ([[ADR-0007 Shell UI Layer#View format: a full expression language, and Python as an equal front-end (2026-10-25)]]).

## Links

- [[ADR-0007 Shell UI Layer]] · [[ADR-0006 Shell Independent of Tesserae UI]] · [[Expression Languages for YAML]] · [[Expression Language Requirements]]

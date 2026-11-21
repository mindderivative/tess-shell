---
title: ADR-0022 Default Stylesheet
aliases: [ADR-0022, Appearance Stylesheets Default]
type: adr
status: accepted
owner: phil
created: 2026-11-20
updated: 2026-11-21
tags: [adr, design/style]
---

# ADR-0022: Default Stylesheet When `Appearance.Stylesheets` Is Absent

## Context

`tess-shell` found that a shell with no `Appearance { Stylesheets: [...] }` key shows unreadable widgets: the setting defaults to an empty list, no stylesheet colours TextField or List, and tre draws its black default. The maintainer saw black text on a dark background in the Launcher on a throwaway config. Every guide example sets `Stylesheets: [Default]`, so the examples hide the problem.

This follows from a decision already in the vault: [Style Schema](../41%20TDL%20Reference/Style%20Schema.md) D36 says the shipped `Default` stylesheet applies only when named in `Appearance.Stylesheets`; with none named a block keeps its own look. D38 puts the stylesheet below style and inline values and above nothing but the theme tokens, so an unnamed stylesheet leaves widgets with no colours except what a block sets itself. No spec or ADR says what the minimum readable result is, and none says `check` reports it. The report that D36 produced this result is the code session's, relayed by the Orchestrator and not run in the vault.

## Options

### Option A: absent key falls back to `[Default]` (recommended)

An absent `Stylesheets` key means `[Default]`. An explicit empty list `Stylesheets: []` still means none.

- Pro: a new or throwaway config is readable with no extra step; the guide examples and real configs behave the same.
- Pro: it is the smallest change and keeps the author's choice: `[]` is the way to say "no stylesheet".
- Con: it amends D36 (needs the maintainer's word), and "absent" differs from "empty" in a settings file, which is a subtle rule to document.
- Con: a shell that relied on blocks keeping their own look with the key absent changes appearance. The shell is pre-1.0, and the code session can state whether any shipped file relies on it.

### Option B: keep the empty default; `check` warns; shipped modules carry a readable minimum

D36 stays. `check` emits a Warning or Note ("no stylesheet: widgets use engine defaults"), and the shipped modules (Launcher and the others) carry their own readable colours.

- Pro: D36 is untouched and the shell stays explicit.
- Con: a user's own TextField or List is still unreadable until they read the warning, and the shipped modules duplicate colours the `Default` stylesheet already defines, against rule 4 (one source of truth).

### Option C: refuse to start surfaces that need a stylesheet without one

- Pro: no silent bad result.
- Con: the hardest failure for the commonest mistake; a throwaway config would not start. It also needs a definition of "needs a stylesheet" for every block, user modules included. Not recommended.

## Decision

Option A, accepted by the maintainer on 2026-11-21 (relayed by the Orchestrator, item 16). An absent `Appearance.Stylesheets` key means `[Default]`; an explicit empty list `[]` still means none; `check` emits a Note (proposed id `appearance-no-stylesheet`) when `Stylesheets` is `[]` and a TextField or List is in use. This amends [Style Schema](../41%20TDL%20Reference/Style%20Schema.md) D36.

## Consequences

- A: D36 is rewritten ("absent means `[Default]`; an empty list means none"); [Settings File](../41%20TDL%20Reference/Settings%20File.md) documents the default; the schema export may need a note that the default is `[Default]`, not `()`; the code session adds a test for the absent and empty cases.
- B: `check` gains one diagnostic code; the Launcher and the other shipped modules gain colours.
- C: a new start-up failure and its message.

## Links

[Style Schema](../41%20TDL%20Reference/Style%20Schema.md) (D36 amended, D38) · [Style, Theme and Stylesheet Files](../41%20TDL%20Reference/Style%2C%20Theme%20and%20Stylesheet%20Files.md) · [Settings File](../41%20TDL%20Reference/Settings%20File.md) · [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) · [M7 Brief](../00%20Home/M7%20Brief.md)

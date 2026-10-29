---
title: Expression Languages for YAML
aliases: [Expression Language Survey, Jinja2 and jinjyaml]
type: research
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [research, needs-verification]
related: ["[[ADR-0007 Shell UI Layer]]", "[[Goals and Non-Goals]]"]
depends_on: []
---

# Expression Languages for YAML

> [!info] Outcome (2026-10-25)
> The maintainer chose to design their own language, the Tesserae Expression Language ([[ADR-0008 Tesserae Expression Language]]). This survey is kept as input. Its requirement table became [[Expression Language Requirements]].

> [!summary]
> The maintainer decided the shell's view format has a full expression language (`{if condition, do something, do something else}`) and asked whether to adopt an existing one instead of building one ([[ADR-0007 Shell UI Layer]]). Jinja2 is the standard, probably too heavy; there are lighter safe evaluators. The deciding factor is not syntax. A shell's values change while it runs, so an expression must be re-evaluated when a value it reads changes. Recommendation: adopt a small safe evaluator behind a shell-owned interface, and test two candidates in a short spike. Nothing here is tested.

## What the Shell Needs from it

| # | Requirement                                                        | Why                                                                                                                                                       |
|---|--------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | Safe: values and structure only, no file, process or system access | It runs from a configuration file. System work belongs to modules ([[ADR-0007 Shell UI Layer#View format: a full expression language, and Python as an equal front-end (2026-10-25)]]).                                              |
| 2 | Re-evaluated when an input changes (live)                          | A clock label reads a time the module sends every second. A load-time render is not enough.                                                               |
| 3 | The shell can see which names an expression reads                  | So it re-runs only the expressions whose inputs changed, on the loop thread, with no Python in layout or paint ([[AGENTS#3. Layering principle]]). |
| 4 | Errors point at `file:line:column` in the YAML                     | Required of every config error ([[AGENTS#3. Layering principle]]).                                                                                 |
| 5 | Conditions and repeaters                                           | Decided by the maintainer; workspaces and tray need repeaters.                                                                                            |
| 6 | Small, with few dependencies, and working on Python 3.14           | Option A of ADR-0007 is a small layer on tre; Python 3.14 is the minimum. #needs-verification for each candidate                                          |
| 7 | Same result from the Python front-end                              | A shell written in Python builds the same tree ([[Goals and Non-Goals]] G1).                                                              |

Two different jobs are mixed in "expression language":

- **Structure:** whether something exists and how many copies (`if`, repeat). Decided when the shell loads or when its input list changes.
- **Values:** the number, text or colour a property has (`low battery ? red : green`). Re-evaluated as inputs change.

## Candidates

| Candidate                             | What it is                                                                                                                                                                                                                   | Fit                                                                                                                                                                                        | Concerns                                                                                                                                                                                                                                                                                                        |
|---------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Jinja2                                | A text template engine; `SandboxedEnvironment` restricts what a template may touch ([sandbox docs](https://config-ninja.readthedocs.io/en/latest/jinja2/sandbox.html), a mirror; check the official page)                                                           | Mature and widely known; loops and conditions are built in                                                                                                                                 | Its own docs warn the sandbox is no perfect security and its safety depends on configuration and whitelisting. It renders text, not live values. Heavy for a small layer. Its expression-only mode (`Environment.compile_expression`, from general knowledge) is the closest fit to values. #needs-verification |
| jinjyaml                              | A PyYAML extension that renders Jinja2 only in tagged nodes (`!j2`), not the whole file ([PyPI](https://pypi.org/project/jinjyaml), [docs](https://jinjyaml.readthedocs.io/en/stable/README.html), [repo](https://github.com/tanbro/jinjyaml)) | Good for load-time structure: loops that expand into lists of mappings, includes                                                                                                           | Load-time only, so no live values. Its docs advise against Jinja2 `include` and `indent` in complex cases because of YAML indentation, and point to `pyyaml-include`. The API changed between versions. It would not give `file:line:column` for the rendered result.                                           |
| simpleeval                            | A safe evaluator for Python-style expressions; you supply names and functions ([PyPI](https://pypi.org/project/simpleeval/1.0.0))                                                                                                   | Small. Familiar syntax. Custom functions such as `if(cond, a, b)` are easy. Names can be supplied by the shell, so the shell can record what is read (to be tested)                        | Limits exist but expression cost is not fully bounded: the author says an expression can still take long or much memory, so be careful in public-facing use. Power operator capped by default; string length capped. Only expressions, no statements.                                                           |
| CEL (`cel-python`)                    | A pure-Python implementation of Google's Common Expression Language: compile, then evaluate with variables ([PyPI](https://pypi.org/project/cel-python))                                                                      | CEL is designed to be non-Turing complete and safe (from general knowledge; one page found says so for a different package). Compile once, evaluate many times: matches live re-evaluation | Version 0.5.0, marked beta, Python 3.10 or later. Types follow Go, not Python. A new syntax for users.                                                                                                                                                                                                          |
| Own small evaluator on Python's `ast` | A walker that allows only chosen node types                                                                                                                                                                                  | Total control over syntax, errors and name tracking                                                                                                                                        | More to write and secure. This is the "build our own" option.                                                                                                                                                                                                                                                   |
| YAML tags (`!if`, `!repeat`)          | PyYAML or ruamel tags that the shell handles itself                                                                                                                                                                          | Structure without an engine: keeps `file:line:column`                                                                                                                                      | Does not cover value expressions on its own                                                                                                                                                                                                                                                                     |

## Recommendation

1. **Split the job.** Structure (`if`, repeat, import) is handled by shell-owned keys the parser understands, so errors keep `file:line:column`. Values use an embedded expression evaluator.
2. **Adopt, do not build, for values.** Put an evaluator behind a shell-owned interface (`compile(source)`, `evaluate(names)`, `names_read()`), so the engine can be changed later without touching YAML files.
3. **Do not use Jinja2 or jinjyaml as the main engine.** They are load-time text templating, heavy for a small layer, and their sandbox warning conflicts with requirement 1. Keep them as a reference for syntax users already know, and as a possible later extra for load-time structure.
4. **Run a short spike on two candidates**, simpleeval and CEL, against requirements 1 to 4 and 6: can the shell see the names read, are errors usable, what does it cost per evaluation, does it install and run on Python 3.14.

## Questions for the Maintainer

- [ ] Is a syntax like Python's expressions (`battery < 20 and not charging`) acceptable, or should users see `{if ...}` as the only form? The `{if ...}` form can be a function in whichever engine is chosen.
- [ ] Is load-time templating (Jinja-style) wanted at all, beside live expressions?

## Links

- [[ADR-0007 Shell UI Layer]] · [[Goals and Non-Goals]] · [[90 Research]]

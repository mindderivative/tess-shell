---
title: ADR-0014 Shell File Language
aliases: [ADR-0014, Shell File Language, Custom Shell Language, TDL, Tesserae Data Language]
type: adr
status: proposed
owner: phil
created: 2026-10-29
updated: 2026-10-29
tags: [adr, architecture, needs-verification]
related: ["[[ADR-0007 Shell UI Layer]]", "[[ADR-0008 Tesserae Expression Language]]", "[[ADR-0011 JSON Schema for Shell Files]]", "[[Expression Language Requirements]]", "[[Python Builder]]", "[[JSON Schema and Editor Support]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]", "[[ADR-0008 Tesserae Expression Language]]"]
---

# ADR-0014: Shell File Language

> [!summary]
> The shell's view files are YAML today ([[ADR-0007 Shell UI Layer]]). This ADR proposes replacing YAML with the **Tesserae Data Language (TDL)**: a structure-only data language with brace blocks, lists, imports and expression slots. The expressions stay in TEL ([[ADR-0008 Tesserae Expression Language]]). The maintainer stated this direction in chat on 2026-10-29; the ADR stays `proposed` until the maintainer accepts it.

> [!important] Direction, not acceptance
> The maintainer said in chat (2026-10-29): "I think I want to build my own custom language. I agree to keep it structure-only data language." They then chose the name: "I think we should call it Tesserae Data Language (TDL)". The points under "Proposed Shape" beyond those statements are the agent's proposal and not yet confirmed.

## Context

[[ADR-0007 Shell UI Layer]] chose YAML as the view format, with Python as an equal front-end. The maintainer asked on 2026-10-29 whether QML would suit better, liked QML's brace blocks ("a cross between YAML and JSON"), looked at KDL, and then preferred a language of their own, so the syntax can be whatever the shell needs.

What was found:

| Finding                                                                                                                                                                                                                       | Source                                                                                                                                                  |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| QML is the language of Qt Quick and runs on Qt's QML engine. The shell renders with tre, so using QML itself means a second UI stack, and its bindings and handlers are JavaScript, which overlaps TEL.                      | [[Prior Art - Linux Shell Surfaces]] (Quickshell, Caelestia and DankMaterialShell are QML on Qt)                                                         |
| KDL 2.0.0 is brace-based with nodes, properties and children. A dot is allowed in an unquoted name, but `(` and `)` are not: they are type annotations. So `test.show(value)` is a syntax error unless quoted.             | [KDL spec](https://kdl.dev/spec/), read 2026-10-29                                                                                                      |
| A KDL parser for Python exists (maintainer). Whether it supports KDL 2.0 and reports line and column is not checked. #needs-verification                                                                                    | Maintainer, chat 2026-10-29                                                                                                                             |
| YAML already surprised the vault once: the maintainer's brace shorthand `{2, 2, 2, 2}` did not survive a YAML load (PyYAML read it as `{2: None}`).                                                                          | [[ADR-0007 Shell UI Layer#Open Items]] (four-sided shorthand)                                                                                           |
| TEL takes an expression or a `{{ }}` template together with an `Origin(file, line, column)`, so an error inside an expression can point at the right place in the host file. A host only has to say where the text starts.   | TEL project `docs/language.md` section 8 and `src/tel/origin.py` (local clone `/home/phil/Projects/pyDev/projects/tess-el`, read 2026-10-29)             |

## Options

### Option A — A Custom Structure-only Data Language, TDL (Recommended)

The shell defines its own file syntax, the Tesserae Data Language (TDL): brace blocks, properties, lists, `import`, and expression slots. It holds structure and literal values only. Every expression is handed to TEL. The Python builder produces the same tree.

- **For:** the syntax the maintainer wants; no significant whitespace; `file:line:column` errors from a parser we control; a lossless parse tree lets the shell write the UID into a file and keep the user's comments ([[ADR-0007 Shell UI Layer#Config Directory and Registry (2026-10-25)]]); a file no longer looks like a Tesserae or YAML file by accident.
- **Against:** a grammar, parser, formatter and docs to build and maintain; no editor support until we provide it, and [[ADR-0011 JSON Schema for Shell Files]] currently gets completion and hover from the YAML language server; one more project that moves with tre and TEL.

Recommended on one condition: it stays structure-only (see Proposed Shape). Before the grammar is frozen, write one small shell in YAML, in this syntax and (if still wanted) in KDL, and compare the files.

### Option B — Keep YAML

- **For:** nothing to build; the YAML language server and the JSON Schema work of [[ADR-0011 JSON Schema for Shell Files]] apply today; consistent with the maintainer's other projects.
- **Against:** significant indentation in deeply nested `children:`; the flow-mapping surprise above; the shell stays tied to YAML's rules for scalars and quoting (a value starting with `{{` must be quoted, [[ADR-0008 Tesserae Expression Language]]'s TEL notes).

### Option C — KDL

- **For:** brace blocks, comments and no significant whitespace now; a published specification; a Python parser exists (to check).
- **Against:** expressions such as `test.show(value)` must be quoted strings; KDL's own syntax (type annotations, node and property forms) shapes the files and cannot change; the maintainer would still depend on a third-party parser for line and column errors; no editor schema story either.

### Option D — QML, or a QML Copy

- **For:** the look the maintainer likes.
- **Against:** real QML needs the Qt runtime and JavaScript, against the tre-only stack and TEL. A QML-like syntax under another name invites authors to paste real QML and expect it to work, with no existing tooling. Rejected in chat (2026-10-29) in favour of Option A taking only the brace look.

## Decision

Blank until the maintainer accepts.

## Proposed Shape

Everything here is a proposal for the maintainer to confirm or change. The grammar itself is written in the language reference after acceptance, not here.

1. **Structure only.** Blocks, properties, lists, `import`, and literal values (numbers, strings, booleans, colours, lengths). The maintainer agreed to this on 2026-10-29.
2. **Expressions are TEL's.** The language has no expression syntax of its own. A value is either a literal or an expression slot that the parser passes to TEL with an `Origin`. A TEL template (`Battery {{ battery.percent }}%`) already exists and needs no new grammar.
3. **Not in the language:** variables (no `$name`), commands, statements, assignment, loops of its own. Reactive values and module values remain names that TEL reads from its scope. A call such as `test.show(value)` is a TEL expression; the vocabulary of handlers and actions is the shell's, as decided in [[ADR-0007 Shell UI Layer#Events and Module Reload (2026-10-26)]].
4. **Brackets.** `{ }` for a block, `[ ]` for a list. `( )` appear only inside TEL expressions unless the grammar later needs them.
5. **Carries over unchanged:** the keys and what they mean (`shell`, `type`, `kind`, `name`, `children`, `import`, `style`, `block`), the file types, unique names and UIDs, the registry, and a module as layout, style and `.py` ([[ADR-0007 Shell UI Layer]]). The file extension changes, because a YAML tool and a Tesserae file must not take a shell file for their own.
6. **Lossless tree.** The parser keeps comments and layout, so the UID write needs no separate YAML writer.
7. **One tree, two front-ends.** The parser and the Python builder produce the same tree, and the parity test of ADR-0007 stands.

An illustration of the feel, not the grammar. The comment lines are explanation, and the slot form on the last property is one of the open items:

```
shell: v1234
type: Shell

root shell_root {
    monitor: DP-1
    children {
        import TopBar_Shell
        panel_dock {
            kind: bar
            style: Dock_Style
            children {
                Label {
                    text: "Battery {{ battery.percent }}%"
                }
            }
        }
    }
}
```

## Consequences

If accepted:

- [[ADR-0007 Shell UI Layer]] is superseded only in its view-format parts (YAML as the file format and the `*.yaml` names). Its decisions on keys, modules, names, UIDs and the registry stand. The ADR would carry a note to that effect; it is not edited until acceptance.
- `41 YAML Reference/`, the `*.yaml` names in [[AGENTS#9. Naming in the designed system]] and the YAML examples across the specs would need rewriting. That is a large pass and needs its own instruction from the maintainer. `AGENTS.md` is not edited by the agent.
- [[ADR-0011 JSON Schema for Shell Files]] needs a rethink: the schemas can still validate the parsed tree at load, but the editor completion and hover from the YAML language server no longer apply.
- [[Expression Language Requirements]] gains one requirement: the parser tells TEL where each expression starts, for positions in errors.
- The Python builder spec stays, with the parity test now against the new parser.

> [!danger] Owning a language
> A language of the shell's own needs a parser, error messages, a formatter, syntax highlighting and docs, and none of the editor support YAML gives for free. If that is not built, authors write blind. This risk is [[Risk Register]] R-20. A grammar that grows beyond structure becomes a scripting language inside a configuration file, which [[ADR-0008 Tesserae Expression Language]] set out to avoid.

## Open Items

- [x] **Name.** Tesserae Data Language, TDL (maintainer, 2026-10-29). It pairs with TEL: TDL holds structure, TEL holds expressions. #needs-verification: that the names `tdl` (code) and any PyPI package name are free and do not clash with another well-known TDL; check before registering.
- [ ] **File extension.** Not `.yaml`. Recommendation: one short extension used for all shell file types, with `type:` telling them apart as now.
- [ ] **Expression slot.** How a TEL expression is marked and where it ends. Recommendation: a quoted string with `{{ }}` for text (already TEL's template form), plus one prefix form for a value that is only an expression; decide after the comparison.
- [ ] **Grammar basics.** Separators (newline, `;`, `,`), comments, string escapes, literal forms for colours and lengths, trailing commas.
- [ ] **Conditional and repeated structure.** ADR-0007 says the file has conditions and repeaters. Decide how structure is chosen or repeated without making the language a scripting language.
- [ ] **Where the parser lives.** Recommendation: a module in the shell package that imports nothing from the shell, so it can be split out like TEL if wanted. How it is built (hand-written or a generator) and its error codes are open. #needs-verification
- [ ] **Editor support.** Syntax highlighting (TextMate grammar or tree-sitter) and validation; how the benefits of [[ADR-0011 JSON Schema for Shell Files]] are kept; whether a language server is in scope for v1.
- [ ] **Comparison.** Write one small shell (a bar, two modules, a popup) in current YAML, in the new syntax and in KDL, and review the three files with the maintainer.
- [ ] **KDL parser facts,** only if Option C stays alive: KDL 2.0 support and line and column errors. #needs-verification
- [ ] **Version key.** `shell:` stays as the first line; whether the extra Tesserae-file guard in [[ADR-0007 Shell UI Layer#File Naming (2026-10-25)]] is still needed once the extension differs.

## Links

- [[ADR-0007 Shell UI Layer]] · [[ADR-0008 Tesserae Expression Language]] · [[ADR-0011 JSON Schema for Shell Files]] · [[Expression Language Requirements]] · [[Python Builder]] · [[Prior Art - Linux Shell Surfaces]] · [[30 Decisions]]

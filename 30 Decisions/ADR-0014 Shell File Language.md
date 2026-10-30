---
title: ADR-0014 Shell File Language
aliases: [ADR-0014, Shell File Language, Custom Shell Language, TDL, Tesserae Data Language]
type: adr
status: accepted
owner: phil
created: 2026-10-29
updated: 2026-10-29
tags: [adr, architecture, needs-verification]
related: ["[[ADR-0007 Shell UI Layer]]", "[[ADR-0008 Tesserae Expression Language]]", "[[ADR-0011 JSON Schema for Shell Files]]", "[[Expression Language Requirements]]", "[[Python Builder]]", "[[JSON Schema and Editor Support]]", "[[Shell File Syntax Comparison]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]", "[[ADR-0008 Tesserae Expression Language]]"]
---

# ADR-0014: Shell File Language

> [!summary]
> The shell's view files are written in the **Tesserae Data Language (TDL)**, a structure-only data language with brace blocks, lists, imports and expression slots, in place of YAML. Expressions stay in TEL ([[ADR-0008 Tesserae Expression Language]]). Accepted by the maintainer on 2026-10-29.

> [!success] Accepted 2026-10-29
> The maintainer chose Option A in chat and answered the open items below. Earlier the same day they said: "I think I want to build my own custom language. I agree to keep it structure-only data language." and "I think we should call it Tesserae Data Language (TDL)". Points marked "Recommendation" are the agent's and still wait for the maintainer.

## Context

[[ADR-0007 Shell UI Layer]] chose YAML as the view format, with Python as an equal front-end. The maintainer asked on 2026-10-29 whether QML would suit better, liked QML's brace blocks ("a cross between YAML and JSON"), looked at KDL, and then preferred a language of their own, so the syntax can be whatever the shell needs.

What was found:

| Finding                                                                                                                                                                                                                       | Source                                                                                                                                                  |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| QML is the language of Qt Quick and runs on Qt's QML engine. The shell renders with tre, so using QML itself means a second UI stack, and its bindings and handlers are JavaScript, which overlaps TEL.                      | [[Prior Art - Linux Shell Surfaces]] (Quickshell, Caelestia and DankMaterialShell are QML on Qt)                                                         |
| KDL 2.0.0 is brace-based with nodes, properties and children. A dot is allowed in an unquoted name, but `(` and `)` are not: they are type annotations. So `test.show(value)` is a syntax error unless quoted.             | [KDL spec](https://kdl.dev/spec/), read 2026-10-29                                                                                                      |
| YAML already surprised the vault once: the maintainer's brace shorthand `{2, 2, 2, 2}` did not survive a YAML load (PyYAML read it as `{2: None}`).                                                                          | [[ADR-0007 Shell UI Layer#Open Items]] (four-sided shorthand)                                                                                           |
| TEL takes an expression or a `{{ }}` template together with an `Origin(file, line, column)`, so an error inside an expression can point at the right place in the host file. A host only has to say where the text starts.   | TEL project `docs/language.md` section 8 and `src/tel/origin.py` (local clone `/home/phil/Projects/pyDev/projects/tess-el`, read 2026-10-29)             |

The same small shell in YAML, TDL and KDL is in [[Shell File Syntax Comparison]].

## Options

### Option A — A Custom Structure-only Data Language, TDL (Chosen)

The shell defines its own file syntax, the Tesserae Data Language (TDL): brace blocks, properties, lists, `import`, and expression slots. It holds structure and literal values only. Every expression is handed to TEL. The Python builder produces the same tree.

- **For:** the syntax the maintainer wants; no significant whitespace; `file:line:column` errors from a parser we control; a lossless parse tree lets the shell write the UID into a file and keep the user's comments ([[ADR-0007 Shell UI Layer#Config Directory and Registry (2026-10-25)]]); a file no longer looks like a Tesserae or YAML file by accident.
- **Against:** a grammar, parser, formatter and docs to build and maintain; no editor support until we provide it, and [[ADR-0011 JSON Schema for Shell Files]] currently gets completion and hover from the YAML language server; one more project that moves with tre and TEL.

### Option B — Keep YAML

- **For:** nothing to build; the YAML language server and the JSON Schema work of [[ADR-0011 JSON Schema for Shell Files]] apply today; consistent with the maintainer's other projects.
- **Against:** significant indentation in deeply nested `children:`; the flow-mapping surprise above; a value starting with `{{` must be quoted; conditions and repeats force the list form ([[Shell File Syntax Comparison]]).

### Option C — KDL

- **For:** brace blocks, comments and no significant whitespace now; a published specification.
- **Against:** expressions such as `test.show(value)` and colours such as `rgba(0,0,0,0)` must be quoted strings; KDL's own syntax shapes the files and cannot change; line and column errors would depend on a third-party parser.

### Option D — QML, or a QML Copy

- **For:** the look the maintainer likes.
- **Against:** real QML needs the Qt runtime and JavaScript, against the tre-only stack and TEL. A QML-like syntax under another name invites authors to paste real QML and expect it to work, with no existing tooling.

## Decision

Accepted 2026-10-29 by the maintainer in chat: **Option A**, the Tesserae Data Language (TDL). It is a structure-only data language. The shell's view files, modules, styles, themes and stylesheets are written in it instead of YAML. All expressions are TEL's.

## What TDL Is (Decided)

1. **Structure only** (maintainer, 2026-10-29). Blocks, properties, lists, `import`, and literal values. No variables (`$name`), commands, statements or assignment.
2. **Expression slot** (maintainer, 2026-10-29). `{{ }}` on a single line, with no quotes needed. A value that is exactly one slot keeps its type; text with a slot inside is a string ([[Shell File Syntax Comparison]] shows it in use). The parser passes the slot to TEL with an `Origin`, so errors point into the file.
3. **Separators** (maintainer, 2026-10-29). A newline or `,`. Trailing commas are allowed and never required.
4. **Comments** start with `#`.
5. **Strings** use `"..."` or `'...'`, with `\` character escapes.
6. **Colours** are a quoted hex (`"#ffffff10"`, `"#ffffff"`) or `rgba(0 0 0 0)`, with spaces between the values and no commas (maintainer, 2026-10-29). The hex is quoted because `#` starts a comment. Red, green and blue are whole numbers 0 to 255 and alpha is a float 0.0 to 1.0, so `rgba(0 0 0 0.5)` is half transparent (as recommended, maintainer, 2026-10-29).
7. **Lengths** have no unit suffix: a whole number is pixels, and a percentage is `<int>%` (`50%`) (maintainer, 2026-10-29). A float is for values that are not lengths, such as `opacity: 0.9`.
8. **Version keys** (maintainer, 2026-10-29). A file starts with `TDL:` and then `shell:`. `TDL:` names the language version and `shell:` the shell-format version. The UID is written below `shell:` as before ([[ADR-0007 Shell UI Layer#Config Directory and Registry (2026-10-25)]]).
9. **Where the parser lives** (maintainer, 2026-10-29, as recommended). A module in the shell package that imports nothing from the shell, so it can be split out like TEL if wanted.
10. **Editor support** (maintainer, 2026-10-29). No language server in v1.
11. **Brackets.** `{ }` for a block, `[ ]` for a list, and `( )` for the colour constructor `rgba(...)` and inside TEL expressions. Whether other constructors exist is open.
14. **Unquoted words are strings** (maintainer, 2026-10-29), unless the word is a syntax word such as `children`. An unquoted value runs to the end of the line or to the next `,` or closing brace; text that holds either is quoted (as recommended, maintainer, 2026-10-29), so `text: Battery {{ x }}%` needs no quotes. Reading, to confirm: a syntax word is special only where a key or keyword is expected, so `kind: children` is still the string `children`.
15. **Blocks** (maintainer, 2026-10-29). `name { ... }` is a block and `key: value` a property; blocks nest (`test { children { key: value } }`). The maintainer's example also wrote `children{` and `key:value`; reading, to confirm: spaces around `{` and after `:` are optional. Closing braces of nested blocks are separated by a space or a newline (`} }`), never written together: `{{` and `}}` belong to the expression slot. A slot next to a block therefore needs a space, and a block directly inside a block is written `{ {`.
16. **Repeated names** (maintainer, 2026-10-29). The same module or block name may appear many times in one `children { }`, ordered by position in the tree, and the entries are named from that position (`Square_1`, `Square_2`, the rule of [[ADR-0007 Shell UI Layer#Open Items]]). Siblings are separated by a newline or `,`, so `Square { }, Square { },` is valid.
17. **File extension** `.tdl` for every shell file type; the `_Shell`, `_Module`, `_Style`, `_Theme` and `_Stylesheet` suffixes stay (`Main_Shell.tdl`, `Audio_Module.tdl`, `Dock_Style.tdl`).
18. **Syntax highlighting.** A small TextMate grammar ships with v1 (maintainer, 2026-10-29). Its content comes from the TDL reference, once written.
12. **Carries over unchanged:** the keys and what they mean (`shell`, `type`, `kind`, `name`, `children`, `import`, `style`, `block`), the file types and suffixes (`_Shell`, `_Module`, `_Style`, `_Theme`, `_Stylesheet`), unique names and UIDs, the registry, and a module as layout, style and `.py` ([[ADR-0007 Shell UI Layer]]).
13. **Lossless tree.** The parser keeps comments and layout, so the UID write needs no separate YAML writer. The parser and the Python builder produce the same tree, and the parity test of ADR-0007 stands.

An illustration of the feel, not the grammar:

```
TDL: v1
shell: v1
type: Shell

root dp1_root {
    monitor: DP-1
    children {
        top_bar {
            kind: bar
            style { background: "#1e1e2ee6", radius: 8 }
            children {
                Label { text: Battery {{ battery.percent }}% }
            }
        }
    }
}
```

## Conditions and Repeats (Decided)

Confirmed as recommended by the maintainer on 2026-10-29. The aim is to choose or repeat structure without a scripting language. Two keyword blocks, `if` (with an optional `else`) and `for`. Everything else uses TEL.

```
children {
    # A value that depends on state: a TEL expression, no structure needed
    Label { text: {{ "Charging" if battery.charging else "On battery" }} }

    # One branch or the other
    if {{ battery.present }} {
        Label { text: Battery {{ battery.percent }}% }
    } else {
        Icon { svg: battery-missing }
    }

    # One entry per item, with a stable identity
    for item in {{ tray.items }} key {{ item.id }} {
        Icon { svg: {{ item.icon }} }
    }
}
```

Rules:

- **Which tool.** A changing value is a TEL expression. A thing that exists or not, or one of two subtrees, is `if`. A repeat is `for`. There is no `else if`: nest an `if` inside `else`. There is no `while`, `break`, `let` or assignment.
- **Where they go.** `if` and `for` may appear wherever `children` may. Their bodies are `children`. They are structure and do not run code.
- A `for` binds one name (`item`), visible inside its body and to TEL only there. `key` is required: it gives each generated entry a stable identity so a reordered list reuses entries, and it names them (`Icon_<key>`) under the path-name rule of [[ADR-0007 Shell UI Layer#Open Items]].
- **Reserved words:** `if`, `else`, `for`, `in`, `key`. A block or module cannot use them as its name.
- **Reactive.** The shell re-evaluates a condition or iterable when a name it reads changes (TEL tracks the names, TEL project `docs/language.md` section 12.3) and rebuilds only that branch or entry.
- **Bounded.** TEL's limits apply to the expression ([[Expression Language Requirements]]). The shell adds a cap on the number of entries a `for` creates; the value is not decided.
- **Python builder.** The builder would have the same two constructs, so the parity test covers them ([[Python Builder]]).

## Consequences

- [[ADR-0007 Shell UI Layer]] is superseded only in its view-format parts (YAML as the file format and the `*.yaml` names). Its decisions on keys, modules, names, UIDs and the registry stand. ADR-0007 carries a note to that effect.
- `41 YAML Reference/`, the `*.yaml` names in [[AGENTS#9. Naming in the designed system]] and the YAML examples across the specs need rewriting. That is a large pass and needs the maintainer's instruction; the agent has not started it and does not edit `AGENTS.md`.
- [[ADR-0011 JSON Schema for Shell Files]] needs a rethink. The schemas can still validate the parsed tree at load, but completion and hover from the YAML language server no longer apply, and there is no language server in v1.
- [[Expression Language Requirements]] gains two requirements: the parser tells TEL where each expression starts, and TEL accepts a child scope that adds the `for` name. Not yet added.
- The Python builder spec stays, with the parity test now against the TDL parser.
- The shell now owns a language: the grammar, parser, error codes and a formatter are shell work, and a TDL reference replaces the YAML reference.

> [!danger] Owning a language
> A language of the shell's own needs a parser, error messages, a formatter and docs, and none of the editor support YAML gives for free (no language server in v1). If that is not built, authors write blind. This risk is [[Risk Register]] R-20. A grammar that grows beyond structure becomes a scripting language inside a configuration file, which [[ADR-0008 Tesserae Expression Language]] set out to avoid.

## Open Items

- [x] **Name.** Tesserae Data Language, TDL (maintainer, 2026-10-29). #needs-verification: that the code name `tdl` and any PyPI package name are free and do not clash with another well-known TDL; check before registering.
- [x] **File extension.** `.tdl` (maintainer, 2026-10-29), not `.tess`, which does not say it is a data language and reads as a Tesserae file. Neither is registered in this machine's shared-mime-info (`/usr/share/mime/globs2`, checked 2026-10-29), which is a local check only.
- [x] **Expression slot.** `{{ }}` on a single line, no quotes (maintainer, 2026-10-29).
- [x] **Grammar basics.** Separators, comments, strings, colours, lengths and trailing commas, as in "What TDL Is" (maintainer, 2026-10-29).
- [x] **Conditions and repeats.** `if` with an optional `else`, and `for` with a required `key`, as recommended (maintainer, 2026-10-29).
- [x] **Where the parser lives.** As recommended (maintainer, 2026-10-29).
- [x] **Editor support.** No language server in v1 (maintainer, 2026-10-29).
- [x] **Comparison.** Done: [[Shell File Syntax Comparison]].
- [x] **KDL parser facts.** Not applicable (maintainer, 2026-10-29).
- [x] **Version key.** `TDL:` then `shell:` (maintainer, 2026-10-29). This also replaces the extra Tesserae-file guard in [[ADR-0007 Shell UI Layer#File Naming (2026-10-25)]]: the extension and `TDL:` tell a shell file from a YAML or Tesserae one.

Raised by the comparison ([[Shell File Syntax Comparison#What the TDL Sketch Shows to Settle]]) and answered by the maintainer on 2026-10-29:

- [x] **Lengths and floats.** `<int>%` for a percentage, a whole number for pixels, a float only for values that are not lengths.
- [x] **Parentheses and commas.** `rgba(0 0 0 0)`, space separated.
- [x] **Hex colours** are quoted because `#` starts a comment.
- [x] **Unquoted words** are strings unless a syntax word (reading to confirm: by position).
- [x] **Block form** confirmed, with nested blocks and `} }` never `}}`.
- [x] **A slot next to a block** confirmed: `{{` always opens a slot.
- [x] **Repeated name in one container** allowed, ordered by position.
- [x] **Syntax highlighting in v1:** a small TextMate grammar.

Still open, from the answers:

- [x] **Alpha range.** 0 to 255 for red, green and blue, 0.0 to 1.0 for alpha (as recommended, maintainer, 2026-10-29).
- [x] **Unquoted text with spaces.** Runs to the end of the line or the next `,` or closing brace (as recommended, maintainer, 2026-10-29).
- [x] **The rewrite pass** began 2026-10-29 (maintainer): breadth first through the vault tree, each level before the next. `settings.yaml` becomes `settings.tdl`: the agent's assumption, since the settings file is a shell file type; confirm. The folder `41 YAML Reference` keeps its name until the maintainer decides a rename (a move needs approval).
- [ ] **Two readings to confirm** from "What TDL Is" items 14 and 15: syntax words are special only in key position, and spaces around `{` and after `:` are optional.

## Links

- [[ADR-0007 Shell UI Layer]] · [[ADR-0008 Tesserae Expression Language]] · [[ADR-0011 JSON Schema for Shell Files]] · [[Expression Language Requirements]] · [[Python Builder]] · [[Shell File Syntax Comparison]] · [[Prior Art - Linux Shell Surfaces]] · [[30 Decisions]]

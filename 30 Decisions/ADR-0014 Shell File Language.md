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
8. **Version keys** (maintainer, 2026-10-29). Superseded the same day by the metadata block of "Layout Rules" below: the `TDL:` version and the file-type key sit between two `---` lines, and the UID is written there, not below `shell:` ([[ADR-0007 Shell UI Layer#Config Directory and Registry (2026-10-25)]]).
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

An illustration of the feel, not the grammar, in the layout of "Layout Rules" (the case of the keys inside blocks is still to be confirmed):

```
---
TDL: 0.1
Shell: v1
---

Monitor {
    Name: dp1
    Index: 0
    Children {
        Bar {
            Name: top_bar
            Style { Background: "#1e1e2ee6", Radius: 8 }
            Children {
                Label { Text: Battery {{ battery.percent }}% }
            }
        }
    }
}
```

## File Layout (Decided 2026-10-29)

The maintainer's picture of a file, given in chat after the rewrite pass, and their answers to the ten questions it raised. The sketch is reproduced as given, including the typos `Rectanlge` (read as `Rectangle`) and the lowercase `import:` (read as `Import:`, confirmed). `Kind: shape` and `FileName:` in it were examples, not decisions. The rules are under "Layout Rules" after the sketch.

```
---
TDL: 0.1
Shell: 0.2
FileName: example.tdl 
---

# This is a comment

Monitor {
  Name: DP-1
  Children {
    # one file, or a list
    import: TopBar_Shell.tdl
    Rectanlge {
      Kind: shape
      Style: Dock_Style.tdl
      # modules and containers go under children; the syntax of a module use is pending
      Children {
        Import: [
          Clock_Module.tdl,
          Audio_Module.tdl,
        ]
      }
    }
    Panel {
      Layer: overlay
      Keyboard: exclusive
      Children {
        Import: Applications_Module.tdl
      }
    }
  }
}
```

### Layout Rules

Decided by the maintainer in chat, 2026-10-29. They supersede the first-lines rule of "What TDL Is" item 8 and parts of [[ADR-0007 Shell UI Layer]] (listed in Consequences).

1. **Metadata block.** Every file starts with a block between two `---` lines. It is required. It holds the language version `TDL:` (as in the sketch), the file-type key, `UID:` (the shell writes it there), and, for a module, `Name:`. Other metadata keys are allowed; `FileName` in the sketch was an example, not a required key.
2. **The key names the file type.** `Shell: v1`, `Module: v1`, `Style:`, `Stylesheet:` or `Theme:` in the metadata says what kind of file it is, and it is required. There is no `Type:` and no separate `shell:` key. The file name suffix (`*_Shell.tdl`) says the same thing.
3. **Versions are strings** (`v1`, `0.1`).
4. **Case.** Built-in syntax is Capitalised, with snake case for several words: keys (`Name`, `Children`, `Layer`), block and surface types (`Panel`, `Rectangle`), and the structure words. A reference to a built-in type or a module by value uses its exact name: `Kind: Panel`, `Kind: Clock`.
5. **One registry of names.** Built-in blocks, the surface types (`Bar`, `Frame`, `Panel`, `Popup`) and modules are all in the built-in name registry and are treated the same way. If something is needed to tell a block from a module, `Kind: Block` or `Kind: Module` is available (optional).
6. **A block's head is its type,** so `Panel { Name: Unique_Panel_Name }` needs no `Kind:` or `Type:`. `Name:` is the unique name. This replaces `kind:` for surfaces.
7. **A module's name** is the `Name:` in the metadata of its file (`Name: Clock` in `Clock_Module.tdl`). A use is written with that name as the head: `Clock { }`. Every use of a module is an instance.
8. **Telling uses apart.** Python registers each use with the module name and the UID as a prefix or suffix. The maintainer's candidates: `Clock:UID`, `Clock#UID`, `Clock@UID`, `Clock[UID]` (a key in a Python collection). If the file itself needs a way to tell which `Clock` is which, the shell injects `UID: <UUIDv7>` into that use during parsing.
9. **Monitors.** `Monitor { }` is a top-level block and replaces `root`. `Index: 0` picks a monitor by its position in the compositor's output array; with one monitor it is `Index: 0`, and the next monitor is `Index: 1`. `Name:` is the unique name. Several `Monitor` blocks in one file are allowed.

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
- The layout rules also supersede these ADR-0007 decisions: the `shell:` and `type:` keys (the file-type key in the metadata block replaces both); `kind:` for surfaces (`Bar`, `Frame`, `Panel`, `Popup` are block heads); `root` with `monitor:` matched by connector name and description (`Monitor` with `Index:`); lowercase key names (Capitalised, snake case for several words); the `UID:` line below `shell:` (the UID goes in the metadata block). ADR-0007's rule that a unique name is the block's key becomes `Name:`. The notes rewritten earlier on 2026-10-29 still show the old forms and need a second pass once the open items below are answered.

> [!danger] Monitor index is not a stable name
> `Index: 0` is the position in the compositor's output array. If the order changes (a monitor is unplugged, the machine wakes from sleep with a dock, outputs are announced in another order), a bar can move to a different physical screen. The protocol does not promise a stable order across sessions or hot-plug, and KWin's behaviour is untested #needs-verification. ADR-0007 matched by connector name (`DP-1`) and then description for this reason. Recommendation: keep `Index:` as the maintainer decided and also allow `Connector:` and `Description:` selectors on `Monitor`, with `Index:` as a fallback. [[Risk Register]] R-21.
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

Raised while rewriting the notes for TDL (2026-10-29). Each is also an open item in the note that hit it; the agent took the shown default in the examples and the maintainer has not decided:

- [ ] **Literals not defined.** Booleans (`true`, `false`), null, and an empty list `[]`. The examples use `true` and `false`. Decide, and say whether the parser types bare words or the key's schema does.
- [ ] **Names.** Is a block's name only the word before the brace (`root dp1_root { }`, `Clock { }`), or can a `name:` key also give it? Affects module calls, the root header and the path-name rule. The notes keep a `name:` property where YAML had one.
- [ ] **Unnamed blocks as list items** (`[{color: "#000", x: 0}]`), as shadows and elevation need. Alternative: a repeated named block per item.
- [ ] **Numeric keys** (`elevation { 1: ... }`, the `space` scale 1 to 8). Alternative: named levels.
- [ ] **Stylesheet selectors** (`.warning`, `#clock_label`, `Button:hovered`, `Slider::track`) cannot be block names, because `#` starts a comment and `:` makes a property. Options: quoted names, or a separate selector form.
- [ ] **Percent plus pixels.** Is there a TDL form for tre's `calc(100% - 16)`?
- [ ] **Named sides** (`thickness {top: 8, left: 24}`, `border_thickness`). Assumed: a block with named keys.
- [ ] **One-line blocks** such as `params { format { type: string, default: "" } }` and an empty block `Spacer { }`. Assumed allowed.
- [ ] **A repeated property key in one block:** an error, or last wins? Repeated block names are allowed; repeated keys are not covered.
- [ ] **How the UID write edits the file:** patch the text at the tree node's position, or print the tree back out. Both keep comments.
- [x] **Several roots in one file** (now several `Monitor` blocks): allowed, decided 2026-10-29 ([[Shell File]] still describes `root`).
- [ ] **TEL's structure role.** [[ADR-0008 Tesserae Expression Language]] says TEL owns "structure and values" and its requirements T3 and T8 give it conditions and repeats; this ADR gives `if` and `for` to TDL. Decide whether TEL keeps any structure role, and which component builds and rebuilds those branches (the parser, the shell model or TEL) ([[Layers and Components]]).
- [ ] **ADR-0011.** Whether it stands for load-time validation only, is superseded, or is rewritten; which editor feedback is wanted after v1; whether `schemas/` is still written to disk now that no modeline points at it; and the shape of the parsed tree when names repeat ([[JSON Schema and Editor Support]]).
- [ ] **Folder rename.** The folder `41 YAML Reference` and the note type `yaml-ref`. A move needs your approval; every note says "rename pending".
- [ ] **Module context accessor.** `ctx.yaml()` in the module context ([[Module Context]]): rename (for example `ctx.file`) or keep.
- [ ] **Python builder** signatures for `If` and `For` and whether comments count in the parity test ([[Python Builder]]).
- [x] **Layout sketch, ten questions** answered by the maintainer on 2026-10-29: the metadata block is required and holds `UID:`; the file-type key replaces `Type:`; versions are strings; `FileName` was an example; one registry of names for blocks and modules; `Kind: shape` was an example; `Name:` is the unique name and `Index:` picks the monitor; several `Monitor` blocks are allowed; `Import` and `Rectangle` are the right spellings. See "Layout Rules".
- [ ] **Capitalised keys everywhere.** The maintainer's sketch and answers use Capitalised keys, but the question "is this a change to every key in the notes, with snake case for several words (`Exclusive_Zone`)" was not answered. Tre's names are lowercase (`exclusive_zone`) and "Names follow tre's" in [[Shell File]]. Confirm, because it sets the second rewrite pass.
- [ ] **Two meanings of the Kind key.** In the maintainer's text `Kind: Panel` and `Kind: Clock` reference a type by its exact name, and `Kind: Block` / `Kind: Module` tell a block from a module. Recommendation: `Kind:` is only a reference by exact name (used where a type is named by value, such as a style class or a popup call), and one name registry makes `Kind: Block` / `Kind: Module` unnecessary; a name used twice in the registry is a load error, except that a user module of the same name overrides a shipped module as decided in ADR-0007.
- [ ] **Structure words and values in the new case rules.** Recommendation: `If`, `Else`, `For`, `In` and `Key` are Capitalised; enum values stay lowercase (`Layer: overlay`, `Keyboard: exclusive`) as in the sketch.
- [ ] **Metadata keys.** Which are required (`TDL:`, the file-type key), which are optional (`UID:`, `Name:` for a module), and whether an unknown key is ignored, kept or an error. Recommendation: unknown keys are kept in the tree and ignored, with a warning for a near-miss of a known key.
- [ ] **Instance UIDs.** The maintainer said `UID: <UUIDv7>` is injected into a use if the file needs it, while ADR-0007 keeps an instance UID in the registry only and names uses from their position. Recommendation: keep instance UIDs in the registry, written with `@` (`Clock@<uid>`, which is safe in Python and does not clash with `#` or `:`), and inject `UID:` into a use only when the user asks for stable identity across reordering.
- [ ] **Monitor selectors.** `Index:` is decided; the danger callout under Consequences asks to add `Connector:` and `Description:`, and the old rule that `monitor: default` applies to every monitor no other block names needs a TDL form (for example `Index: default`).
- [ ] **File-type key and file name disagree.** Recommendation: the key is authoritative and a mismatch with the suffix is a load error naming both, as ADR-0007 did for `type:`.
- [ ] **Style tokens.** The `$color.surface` form (see [[Style Schema]]) against "no variables": the agent treated them as plain strings the shell resolves.

## Links

- [[ADR-0007 Shell UI Layer]] · [[ADR-0008 Tesserae Expression Language]] · [[ADR-0011 JSON Schema for Shell Files]] · [[Expression Language Requirements]] · [[Python Builder]] · [[Shell File Syntax Comparison]] · [[Prior Art - Linux Shell Surfaces]] · [[30 Decisions]]

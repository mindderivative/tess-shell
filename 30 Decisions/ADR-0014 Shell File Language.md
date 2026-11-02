---
title: ADR-0014 Shell File Language
aliases: [ADR-0014, Shell File Language, Custom Shell Language, TDL, Tesserae Data Language]
type: adr
status: accepted
owner: phil
created: 2026-10-29
updated: 2026-11-01
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

> [!warning] Partly superseded on 2026-10-30
> Items 2 (file-type key) and 13 (lowercase enum values) were superseded by D26 and D33, and the metadata contents of item 1 by D37 to D39. The four-sided order of item 7 of "What TDL Is" and of the earlier notes was replaced by D50. The table of Decisions and the later rounds are the current rules.

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

Decided by the maintainer in chat, 2026-10-29, answering the open items that followed:

10. **Capitalised keys everywhere.** Every key in a shell file is Capitalised, and a key of several words capitalises each word and joins them with `_` (`Exclusive_Zone`, `Border_Thickness`, `Anchor_To`). Tre's own names stay lowercase (`exclusive_zone`); the shell maps between them.
11. The Kind key has one meaning. It references a type by its exact name (`Kind: Panel`, `Kind: Clock`). There is no `Kind: Block` or `Kind: Module`. A name registered twice is a load error, except that a user module of the same name overrides a shipped module ([[ADR-0007 Shell UI Layer]]).
12. **Instance UIDs** stay in the registry, with Python keys of the form `Clock@<uid>`. The shell injects `UID:` into a use in the file only when the user asks for stable identity across reordering.
13. **Structure words** `If`, `Else`, `For`, `In` and `Key` are Capitalised. Enum values stay lowercase (`Layer: overlay`, `Keyboard: exclusive`).
14. **Unknown metadata keys** are kept and ignored. A user may add their own metadata and read it in `<Name>_Module.py`.
15. **Monitor selectors.** A `Monitor` block names its monitor with `Index:`, `Connector:` (the connector name, `DP-1`) or `Description:` (the display description). `Index: default` applies to every monitor no other `Monitor` block names. A `Monitor` block with no selector is ignored. Several selectors on one block: the shell tries `Connector`, then `Description`, then `Index`, the order of ADR-0007 (the agent's proposal, decided as recommended on 2026-10-30).
16. **The file-type key is authoritative.** A mismatch with the file suffix is a load error naming both.

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
- A `for` binds one name (`item`), visible inside its body and to TEL only there. `key` is required: it gives each generated entry a stable identity so a reordered list reuses entries, and TEL names them `Icon_0001`, `Icon_0002` and so on from a counter that only grows (D65; the TEL project's D7 and 5H).
- **Reserved words:** `if`, `else`, `for`, `in`, `key`. A block or module cannot use them as its name.
- **Reactive.** The shell re-evaluates a condition or iterable when a name it reads changes (TEL tracks the names, TEL project `docs/language.md` section 12.3) and rebuilds only that branch or entry.
- **Bounded.** TEL's limits apply to the expression ([[Expression Language Requirements]]). The shell adds a cap on the number of entries a `for` creates; the value is not decided.
- **Python builder.** The builder would have the same two constructs, so the parity test covers them ([[Python Builder]]).

## Consequences

- [[ADR-0007 Shell UI Layer]] is superseded only in its view-format parts (YAML as the file format and the `*.yaml` names). Its decisions on keys, modules, names, UIDs and the registry stand. ADR-0007 carries a note to that effect.
- The layout rules also supersede these ADR-0007 decisions: the `shell:` and `type:` keys (the file-type key in the metadata block replaces both); `kind:` for surfaces (`Bar`, `Frame`, `Panel`, `Popup` are block heads); `root` with `monitor:` matched by connector name and description (`Monitor` with `Index:`); lowercase key names (Capitalised, snake case for several words); the `UID:` line below `shell:` (the UID goes in the metadata block). ADR-0007's rule that a unique name is the block's key becomes `Name:`. The notes were revised to these forms on 2026-10-29 and 2026-10-30.

> [!danger] Monitor index is not a stable name
> `Index: 0` is the position in the compositor's output array. If the order changes (a monitor is unplugged, the machine wakes from sleep with a dock, outputs are announced in another order), a bar can move to a different physical screen. The protocol does not promise a stable order across sessions or hot-plug, and KWin's behaviour is untested #needs-verification. ADR-0007 matched by connector name (`DP-1`) and then description for this reason. Decided 2026-10-29: `Connector:` and `Description:` are also selectors on `Monitor` (Layout Rules item 15). [[Risk Register]] R-21.
- `41 TDL Reference/`, the `*.tdl` names in [[AGENTS#9. Naming in the designed system]] and the examples across the specs were rewritten in two passes on 2026-10-29 and 2026-10-30, and the open items were applied on 2026-10-30. [[TDL Language]] is the single reference.
- [[ADR-0011 JSON Schema for Shell Files]] needs a rethink. The schemas can still validate the parsed tree at load, but completion and hover from the YAML language server no longer apply, and there is no language server in v1.
- [[Expression Language Requirements]] gains two requirements: the parser tells TEL where each expression starts, and TEL accepts a child scope that adds the `for` name. Not yet added.
- The Python builder spec stays, with the parity test now against the TDL parser.
- The shell now owns a language: the grammar, parser, error codes and a formatter are shell work, and a TDL reference replaces the YAML reference.

> [!danger] Owning a language
> A language of the shell's own needs a parser, error messages, a formatter and docs, and none of the editor support YAML gives for free (no language server in v1). If that is not built, authors write blind. This risk is [[Risk Register]] R-20. A grammar that grows beyond structure becomes a scripting language inside a configuration file, which [[ADR-0008 Tesserae Expression Language]] set out to avoid.

## Second Layout Sketch (Maintainer, 2026-10-30)

The maintainer's second picture of a file, given in chat the day after the first. It is not a decision; it differs from the decided layout in several places (listed after it, with the questions under Open Items). Reproduced as given, including the `...` placeholders.

```
---
TDL: <version>        # Tesserae Data Language version
TEL: <version>        # Tesserae Expression Language version
TRE: <version>        # Tesserae Rendering Engine version
TUIF: <version>       # Tesserae UI Framework version (Required if building a normal app)
Shell: <version>      # Tesserae Shell version (Required if building a shell app)
Name: ShellRoot       # Unique name for the Shell, View, Module, Style, Stylesheet, Theme, etc...
---

# This is a comment

# Root for a Shell, use View {/} if a Tesserae app
Shell {
  Monitor {
    Name: DP-1
    Children {
      # one file, or a list
      import: TopBar_Shell.tdl
      # AND OR USE INLINE
      Bar {                   # Build-in Module made up of building blocks and built-in modules
        Name: TopBar          # Unique name of this Bar module, can use .get(ShellRoot.DP-1.TopBar)
        UID: <UUIDv7>         # Injected by Shell
        Style: TopBar_Style.tdl
        # OR USE INLINE
        Style {
          Border: [
            Color: "#1e1e1e"          # HEX or HEX + Alpha or RGBA
            Thickness: [2, 2, 2, 2]   # OR single number for all the same or 0 for no border
          ]
          Background: "#1f1f1f"
          Padding: [0, 0, 0, 0]       # Padding affects all children
          Margin: [0, 0, 0, 0]        # Margin adds transparent space around self
          CornerRadius: [8, 8, 8, 8]  # Rounding of self corners
        }
        # modules and containers go under children; the syntax of a module use is pending
        Children {
          Import: [
            Clock_Module.tdl,
            Audio_Module.tdl,
          ]
        }
        Width: 300
        Height: 50
        Edge: Top
        Alignment: Center    # Where the Bar sits along the Edge it is attached to
        Offset: 0            # Positive or Negative moves the Bar the amount of pixels along the Edge
        Flex: Horizontal    # How children are stacked; Horizontal, Vertical, None
        Grid {              # If Flex is `Flex:` None otherwise treated as `Grid: None`
          Columns: 2
          Rows: 2
          Gap: 4
          Style { ... }     # Inline or File
        
        }
      }
    }
  }
  
  Monitor {
    ...
  }
}
```

Where it differs from the decided layout (Layout Rules and D1 to D24):

- The metadata block pins the versions of TEL, TRE and TUIF (Tesserae UI Framework), and holds `Name:` for every file type. `Shell:` now reads as "Tesserae Shell version", and the file type is no longer a metadata key.
- A root block (`Shell { }`, or `View { }` for a Tesserae app) wraps the `Monitor` blocks. TDL would serve Tesserae UI as well as the shell.
- `Monitor` is named `Name: DP-1` (a connector) instead of `Index:`, `Connector:` or `Description:`.
- Names are addressed by a dotted path (`ShellRoot.DP-1.TopBar`).
- `Bar` is a built-in module, not a surface type; a `UID:` is injected into the block in the file (Layout Rules item 12 limits that to when asked).
- `Border: [ Color: ..., Thickness: ... ]` puts keys inside `[ ]`.
- `CornerRadius` is one CamelCase word; the decided rule joins capitalised words with `_`.
- Enum values are Capitalised (`Edge: Top`, `Flex: Horizontal`, `Alignment: Center`); the decided rule keeps them lowercase.
- The Bar uses `Width`, `Height`, `Edge`, `Alignment`, `Offset` and has its own `Flex` and `Grid` properties; the Bar spec has `Edge`, `Span`, `Length`, `Thickness`, `Anchor`, `Size`, `Margin` and `Exclusive_Zone`.
- Trailing comments follow values on the same line (`TDL: <version>        # ...`); the decided rule makes an unquoted value run to the end of the line.
- `import:` and `Import:` both appear.

## Decisions on the Open Items (2026-10-30)

The maintainer said in chat: "Do all as you would recommend". These are the agent's recommendations, taken as decisions on that instruction. They apply to every open item below except the question-mark conditional, which the TEL project must decide. The maintainer can change any of them.

| #   | Topic                       | Decision                                                                                                                                                                                                                                                                 |
|-----|-----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D1  | Two readings                | A syntax word (`Children`, `If`, `Import`) is special only where a key or keyword is expected, so `Kind: Children` is the string `Children`. Spaces around `{` and after `:` are optional.                                                                                |
| D2  | Booleans, null, empty list  | `true`, `false` and `null` are lowercase bare words, and `[]` is an empty list. The parser keeps a bare word as a string; the key's declared type in the schema turns it into a boolean, number or null. This follows "unquoted words are strings".                       |
| D3  | Names                       | A block's name is only its head (its type). `Name:` gives the unique name. There is no `root name { }` form.                                                                                                                                                              |
| D4  | Lists of blocks, numeric keys | No unnamed block as a list item: write repeated named blocks (`Shadows { Shadow { } Shadow { } }`), ordered by position. No numeric keys: a key starts with a letter; scales use names such as `Level_1` to `Level_5` and `Step_1` to `Step_8`.                          |
| D5  | Stylesheet selectors        | A stylesheet rule is a `Rule { Selector: ".warning", ... }` block, repeated as needed. The selector is a quoted string. No new head form is added to the grammar.                                                                                                          |
| D6  | Percent plus pixels         | Not in v1. A length is a whole number or `<int>%`. A form for tre's `calc(100% - 16)` waits for a surface that needs it.                                                                                                                                                 |
| D7  | Named sides                 | A four-sided value is one number, a list of four (top, right, bottom, left), or a block of named sides: `Thickness { Top: 8, Left: 24 }`.                                                                                                                                  |
| D8  | One-line and empty blocks   | Allowed: `Params { format { Type: string } }` and `Spacer { }`.                                                                                                                                                                                                          |
| D9  | Repeated property key       | An error naming both places. Repeated block names are allowed; repeated keys in one block are not.                                                                                                                                                                       |
| D10 | UID write                   | The shell patches the file text at the node's position and leaves every other byte alone, so comments and layout survive. It does not print the tree back out. `UID:` goes directly after the file-type key.                                                              |
| D11 | TEL's structure role        | TEL evaluates expressions (values) only. TDL owns `If` and `For`. The shell's model builder evaluates a condition or iterable through TEL and rebuilds that branch or entry. TEL's requirements T3 and T8 are narrowed to expression-level conditionals and comprehensions. |
| D12 | ADR-0011                    | Stands for load-time and reload validation of the parsed tree; the editor part (completion, hover, modelines) is dropped. `schemas/` is still generated on disk, for the `tesserae-shell schema` command and a future language server. The loader reads the metadata block first, because the file-type key picks the schema, then the schema validates both the metadata part and the block part. The parsed tree is an ordered list of entries (head, properties, children) that keeps repeated names. |
| D13 | Folder rename               | `41 TDL Reference` becomes `41 TDL Reference`, its index note becomes `41 TDL Reference`, and the note type `tdl-ref` becomes `tdl-ref`. The old names stay as aliases.                                                                                                |
| D14 | Module context accessor     | `ctx.yaml()` is renamed `ctx.tdl()`: a read-only view of the module's own TDL file, metadata included.                                                                                                                                                                   |
| D15 | Python builder              | The sketched `If(cond, then, otherwise)` and `For(name, iterable, key, body)` stand. The parity test compares trees, including metadata, and ignores comments and layout.                                                                                                |
| D16 | Style tokens                | `$color.on_surface` is a plain string that the style engine resolves by theme key, not a TDL variable. A reference is lowercase and matches the theme's Capitalised keys (`On_Surface`) without regard to case.                                                           |
| D17 | Module file layout          | `Style:` and `Params { }` sit in the body after the metadata block; the metadata holds identity, versions and user data. A param declaration may have a `Type:` property, which is not a file key.                                                                       |
| D18 | Param names on a use        | Written as the module declared them (`text:`, `format:`): they are the module author's names, so they keep their case.                                                                                                                                                   |
| D19 | Classes and themes          | A class in a style file is a block named by the user inside `Classes { }`, with `Kind: Text` naming the type it applies to. A theme may carry `Name:` in its metadata (optional; unknown metadata is kept).                                                              |
| D20 | Settings file               | The file-type key is `Settings: v1` and the file is `settings.tdl` (confirmed as the name). Settings keys are nested blocks (`Logging { Level: info }`); `Logging.Level` is only a prose shorthand for the path.                                                          |
| D21 | Frame structure             | `Inner_Border`, `Outer_Border` and `Edges` are nested blocks, and `Edges` holds `Top`, `Right`, `Bottom`, `Left` blocks.                                                                                                                                                 |
| D22 | Imported shell files        | An imported `_Shell.tdl` holds surface blocks only. It sits under a `Monitor`'s `Children` and takes that `Monitor`'s monitor.                                                                                                                                            |
| D23 | Naming a use                | Python always receives the `Clock@<uid>` key from `ctx.uses` and passes it back to name a use in an action. A use's `Name:` is for the file, references and expressions.                                                                                                  |
| D24 | Layer-window namespace      | The placeholder reads `tesserae-shell.<type>.<name>`, with the type in lower case (`bar`, `panel`).                                                                                                                                                                       |

### Second-Sketch Decisions (2026-10-30)

Decided by the maintainer in chat, answering the sixteen questions on the second sketch. They supersede Layout Rules items 2 (file-type key), 13 (lowercase enum values) and the metadata contents of item 1, and they change the Bar keys accepted on 2026-10-29.

| #   | Topic                    | Decision                                                                                                                                                                                                                                                                                                  |
|-----|--------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D25 | TDL is its own project   | TDL becomes a separate project, like TEL. Its grammar knows nothing about bars or monitors. Until it has a repository, this vault defines it ([[TDL Language]]). The shell and Tesserae UI each define their own blocks and schema on top of it. ADR-0006 holds: the shell still does not depend on `tesserae-ui`. |
| D26 | No file-type keys        | The file type is the root block: `Shell`, `View` (a Tesserae app), `Module`, `Style`, `Stylesheet` or `Theme`. The metadata keys `Shell:`, `Module:`, `Style:`, `Stylesheet:` and `Theme:` as file types are dropped. The suffix (`*_Shell.tdl`) must still agree with the root block, and a mismatch is a load error naming both. |
| D27 | Monitors                 | `Index:`, `Connector:` and `Description:` stay as selectors. `Name:` is an identifier (D28), not the connector.                                                                                                                                                                                            |
| D28 | Names                    | A `Name:` follows the unique-name convention: letters, digits and `_`, and it starts with a letter. No other characters (`DP-1` is not a name). A dotted path of names (`ShellRoot.Main.TopBar`) therefore reads the same in TDL and in a TEL expression.                                                    |
| D29 | Bar                      | `Bar` stays a surface type in the one name registry. A user module (for example `TopBar`) can hold a `Bar` and be used on several `Monitor` blocks. A module's root may therefore be a surface; surfaces still do not nest inside surfaces.                                                                   |
| D30 | UID                      | `UID:` is injected into a block only if the block has a `Name:` and the user asks for stable identity (Layout Rules item 12 stands).                                                                                                                                                                       |
| D31 | Key groups               | `[ ]` holds values only. A group of `Key: value` pairs is a block: `Border { Color: "#1e1e1e", Thickness: [2, 2, 2, 2] }`.                                                                                                                                                                                  |
| D32 | Key spelling             | Words are Capitalised and joined with `_` (`Corner_Radius`, `Exclusive_Zone`), the "blend of PascalCase and snake_case". One spelling per key; `CornerRadius` is not a second form. (Reading to confirm.)                                                                                                    |
| D33 | Enum values              | Full upper case: `LEFT`, `TOP`, `RIGHT`, `BOTTOM`, and every other enum value (`Layer: OVERLAY`, `Flex: HORIZONTAL`). `true`, `false` and `null` stay lowercase. Replaces D13 of Layout Rules ("enum values lowercase").                                                                                      |
| D34 | Bar placement            | Keep `Width`, `Height`, `Edge`, `Alignment`, `Offset`, `Exclusive_Zone` and `Layer`. A size is pixels, a percentage, `AUTO` (shrinks to wrap the content on that axis) or `EXPAND` (stretches edge to edge along the attached edge). `Max_Width`, `Max_Height`, `Min_Width` and `Min_Height` bound a size. A top Bar with `Height: EXPAND` cannot stretch (its attached edge does not reach the opposite edge), so it resolves to `Max_Height`, else `Min_Height`, else 0 px. |
| D35 | Layout properties        | `Box`, `FlexBox` and `Grid` stay blocks. A surface or module passes layout properties to its layout block: `Flex` (`VERTICAL`, `HORIZONTAL`, `NONE`), `Columns`, `Rows` and `Gap`. The exact set is written in [[Building Blocks]].                                                                              |
| D36 | Trailing comments        | A `#` after whitespace (or at the start of a line) starts a comment and ends an unquoted value. A `#` inside quotes does not, so `Color: "#ffffff"` is a colour and `Color: #fff` is an error that says to quote it.                                                                                         |

Readings of the answers, to confirm:

- Point 9 wrote `Vertical`, `Horizontal` and `None` for `Flex`, and point 10 wrote `auto`, `expand`, `max_height` and `min_height`; the table applies the rules instead (`HORIZONTAL`, `AUTO`, `Max_Height`).
- D32: "keeping the blend of PascalCase and snake_case" means `Corner_Radius`.
- D29: a module may have a surface as its root; the earlier rule "a surface places modules" now runs both ways.

> [!danger] A resolved size of 0 may be invalid
> D34 resolves an `EXPAND` height to 0 px when no `Max_Height` or `Min_Height` is set. As recalled from the layer-shell protocol, a size of 0 on an axis is allowed only when the surface is anchored to both opposite edges of that axis; otherwise the compositor raises a protocol error. Verified 2026-10-31 against the protocol text (`set_size`: "You must set your anchor to opposite edges in the dimensions you omit; not doing so is a protocol error") and the tre reference (`invalid_size`: a 0 dimension without anchors on both opposite edges). Recommendation: a Bar whose size resolves to 0 on the axis it is attached along is not created, and the shell logs a warning that names the Bar and says to set `Min_Height`.

### Third-Round Decisions (2026-10-30)

Decided by the maintainer in chat, answering the open questions of the rewritten [[TDL Language]] and the four left in this ADR.

| #   | Topic                     | Decision                                                                                                                                                                                                                                                                                                                                                              |
|-----|---------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D37 | Version pins              | `TEL:`, `TRE:`, `TUIF:` and `Shell:` are minimum versions. A shell requires `TEL`, `TRE` and `Shell`. A Tesserae app requires `TEL`, `TRE` and `TUIF`. A shell may add `TUIF` to use something from a Tesserae app, and an app may add `Shell` to use something from the shell. `TDL:` is always required.                                                         |
| D38 | Meaning of `Shell:`       | The version of the Tesserae Shell release.                                                                                                                                                                                                                                                                                                                              |
| D39 | `Name:` in metadata       | Required in every file. It is the root of a dotted path, so the parser and TEL reach other elements of the file by name: `RootShell.DP1.Top_Bar` (the file's `Name`, a `Monitor`'s `Name`, a Bar's `Name`).                                                                                                                                                            |
| D40 | Import spelling           | `Import:` only, to stay in line with every other built-in name.                                                                                                                                                                                                                                                                                                        |
| D41 | Bar spacing               | A Bar has no `Margin`. `Gap:` is the space between the attached Edge and the Bar. `Offset:` moves it along the Edge. The reserved zone includes the Gap (the rule of 2026-10-27 stands).                                                                                                                                                                                |
| D42 | Padding                   | Every element that has `Children` has `Padding`: transparent space between all its children and its four sides.                                                                                                                                                                                                                                                         |
| D43 | Panel keys                | A Panel's `Offset:` positions it on screen; this replaces the Panel's four-sided `Margin:` of 2026-10-29. `Margin:` is the transparent space around the Panel, and `Padding:` is inside it.                                                                                                                                                                              |
| D44 | Panel on a Frame          | When a Panel is attached to a Frame, `Margin:` on the sides facing the Frame separates the two. With a margin there the Frame and Panel do not meld: the Frame edge continues straight as if the Panel were not there, and the Panel's corners round as a floating Panel's do. With no margin they meld as before ([[Panel]], [[Frame]]).                                |
| D45 | Frame keys                | A Frame has `Margin:` (four-sided), not `Gap:`. It is transparent space between the Frame's outer sides and the edge of the display, and it adds to the Frame's total size: a Frame of thickness 10 with `Margin: [5, 5, 5, 5]` is 15 on every side, and a 2 px border makes 17. The reserved zone is the total. A Frame's `Padding:` applies only to a side used as a strip (a side whose `Children` are enabled). |
| D46 | Zero-size Bar             | A Bar whose size resolves to 0 on the axis it is attached along is not created (the shell warns). This must not stop hide, peek, expand or contract of a Bar or a Frame strip: those are states of a surface that exists, not creation.                                                                                                                                  |
| D47 | `calc`                    | Not in v1 ([[TDL Language]] drops the open item). `EXPAND` with `Gap`, `Margin` and `Padding` covers "full width minus spacing".                                                                                                                                                                                                                                       |
| D48 | Shipped modules           | The list waits until the building blocks are worked out ([[Building Blocks]]); then the shell's standard additions are decided.                                                                                                                                                                                                                                         |

Readings and conflicts in the answers (the notes follow the readings; the maintainer can change them):

- `Gap` now has three meanings: a Bar's distance from its Edge (D41), spacing between children in a layout (D35: `Flex`, `Columns`, `Rows`, `Gap`), and a Panel's or Popup's distance to its target or anchor ([[Panel]], [[Popup]]). Recommendation: `Gap` means the distance to the thing a surface is attached to (Bar to Edge, Popup to anchor, Panel to a target that is not a Frame), and the layout child spacing becomes `Spacing`.
- The Panel example `Margin: [10, 0, 0, 10]` for a bottom-left Panel gives 10 px at the top and left under the decided order (top, right, bottom, left). A bottom-left Panel with space from the left and bottom Frame edges is `Margin: [0, 0, 10, 10]`.
- `Offset` has two shapes: a Bar's is one number along its Edge (D41), a Panel's is four-sided from its anchored edges (D43). Recommendation: keep the name in both and document the shapes.
- The answer on D46 is read as: the check runs when a size is resolved at creation. A hidden, collapsed or peeking surface keeps its window (a peek strip), so it does not resolve to 0. How a collapsed Bar keeps a surface in the protocol is #needs-verification.
- `Name:` is unique across the shell (decided 2026-10-26) and also forms a path (D39). A module used twice gets a path name for each use (`RootShell.DP1.Top_Bar.Clock_1`).

### Fourth-Round Decisions (2026-10-30)

Decided by the maintainer in chat, settling the three conflicts left by the third round.

| #   | Topic                 | Decision                                                                                                                                                                                                                                                                                                                                                                   |
|-----|-----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D49 | `Gap` and `Spacing`   | `Gap` is the distance to the thing a surface is attached to: a Bar to its Edge, a Popup to its anchor, a Panel to a target that is not a Frame. The spacing between the children of a layout is `Spacing` (D35 becomes `Flex`, `Columns`, `Rows`, `Spacing`).                                                                                                              |
| D50 | Four-sided order      | Left, Top, Right, Bottom, the convention of other UI frameworks. It replaces the clockwise order from the top (top, right, bottom, left) of 2026-10-26. `Margin: [10, 0, 0, 10]` on a bottom-left Panel is 10 px on the left and bottom. Named sides (`Thickness { Left: 8, Top: 4 }`) are unchanged. The shell reorders to tre's order when it passes a value to tre. |
| D51 | `Offset` shapes       | A Bar's `Offset` is one number along its Edge. A Panel's `Offset` is four-sided (Left, Top, Right, Bottom) from its anchored edges. The name is kept for both.                                                                                                                                                                                                                |

Readings: the order of four corner radii is not stated. It stays top-left, top-right, bottom-right, bottom-left (clockwise from the top-left corner) until the maintainer says otherwise. An asymmetric four-sided value in an earlier example is reordered from (top, right, bottom, left) to (left, top, right, bottom); a symmetric one such as `[2, 2, 2, 2]` is unchanged.

### Fifth-Round Decisions (2026-10-31)

Decided by the maintainer in chat.

| #   | Topic              | Decision                                                                                                                                              |
|-----|--------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| D52 | TDL error list     | The 18 error codes in [[TDL Language#Errors]] are accepted. The maintainer asked what "T17 to T20" meant; the plain-language explanation is in [[Expression Language Requirements#Requests to the TEL Project (T17 to T20)]]. |
| D53 | Corner-radius order | Four corner radii run top-left, top-right, bottom-right, bottom-left (clockwise from the top-left corner), as kept in D50.                          |
| D54 | Where a slot ends  | A slot ends at the first `}}` that is not inside a quoted string (single or double quotes, with `\` escapes). A `}}` meant for the expression is written `} }`. The TDL parser cuts every slot out of the file and gives TEL only the inner text and its start; TEL's template scanner is not used for shell files. Accepted by the maintainer, 2026-10-31. |

### Proposed Answers for the Third-Pass Leftovers (2026-10-31)

The agent's recommendations for the seven items under "Raised by the third rewrite pass". They are proposals: nothing below is decided until the maintainer answers (for example "as recommended").

| #   | Item                                | Recommendation                                                                                                                                                                                                                                                                                                                                                                             |
|-----|-------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| P1  | Alignment, Offset and Gap to tre     | The mapping and worked examples are in [[Bar#Mapping to tre]]. `Gap` becomes the margin on the Edge's own side and is added to the exclusive zone; `START` and `END` anchor the Edge plus one perpendicular side with a margin of `Offset` or `-Offset`; `CENTER` without an Offset anchors the Edge only and the compositor centres it; `EXPAND` along the Edge anchors both perpendicular edges with size 0. A hidden Bar keeps its size and slides by a negative margin, so size 0 never arises at creation. |
| P2  | Alignment values and default         | `START`, `CENTER`, `END`. Default `CENTER` (the maintainer's sketch). `Alignment` and `Offset` have no effect on an `EXPAND` axis and the shell warns if they are set.                                                                                                                                                                                                                         |
| P3  | The `Meld` key on a Panel            | Remove it. A margin on the Frame-facing sides already decides the meld (D44), so a second switch would give two ways to say the same thing. If a seamless but non-melded join is ever wanted it can be added then.                                                                                                                                                                              |
| P4  | Registry state order                 | Changed from my earlier recommendation. The registry is the shell's own file, not tre's, so store a moved Panel's position as `offset` in the TDL order (left, top, right, bottom) and convert at the tre boundary. One order across all shell data is less error-prone than one JSON field in tre's order. Name the order in [[Config Discovery and Registry]].                                |
| P5  | Enum values of settings keys         | `Logging.Level`: `TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL` (Loguru's level names, already upper case). `Logging.Format`: `TEXT`, `JSON`. `KWin.Script`: `RUNTIME`, `PERSISTENT`, `OFF`. Add them to [[Settings File]].                                                                                                                                                 |
| P6  | Where Padding applies                | Decide it in the building-blocks step (next on the list): `Padding` belongs to a block with `Children`; whether a leaf block such as `TextField` has an inner inset is a Building Blocks question.                                                                                                                                                                                              |
| P7  | Schema version-folder id             | Two folders, because there are two languages: `tdl/<major.minor>/` for the metadata part, keyed by `TDL:`, and `shell/<major.minor>/` for the blocks, keyed by the `Shell:` minimum. The loader picks the metadata schema first, then the shell schema.                                                                                                                                         |

Verified while preparing P1 (2026-10-31): the protocol makes a 0 size without opposite anchors an error, which is why D46 is right; tre accepts negative margins and animates them (so hiding by margin is allowed); a positive exclusive zone counts only for one edge or one edge plus both perpendicular edges, and a corner anchor needs `exclusive_edge` (layer-shell version 5). Not verified: what zone KWin 6.8.1 reserves when a margin is set (the 2026-10-27 reading is zone = size plus Gap), whether the compositor ignores margins on an unanchored axis, whether `Output` sizes are already rotated, and how to measure content for `AUTO` before the window exists.

### Sixth-Round Decisions (2026-10-31)

Decided by the maintainer in chat: "P2 - P7 as recommended" (the proposed answers above). P1, the mapping of `Alignment`, `Offset` and `Gap` to tre, was not answered and stays open.

| #   | Topic                    | Decision                                                                                                                                                                                                                                                                     |
|-----|--------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D55 | `Alignment`              | Values `START`, `CENTER`, `END`; default `CENTER`. `Alignment` and `Offset` have no effect on an `EXPAND` axis, and the shell warns if they are set.                                                                                                                           |
| D56 | `Meld` on a Panel        | Removed. A `Margin` on the Frame-facing sides decides the meld (D44). A Bar attached to a Frame keeps its `Meld` key; whether a Bar `Gap` should decide its meld the same way is open.                                                                                         |
| D57 | Registry position order  | The registry stores a moved Panel's position as `offset` in the shell's left, top, right, bottom order and converts at the tre boundary ([[Config Discovery and Registry]]).                                                                                                  |
| D58 | Settings enum values     | `Logging.Level`: `TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL`. `Logging.Format`: `TEXT`, `JSON`. `KWin.Script`: `RUNTIME`, `PERSISTENT`, `OFF` ([[Settings File]]).                                                                                      |
| D59 | Where `Padding` applies  | Decided in the building-blocks step, not before: `Padding` belongs to a block with `Children`; whether a leaf block such as `TextField` has an inner inset is a [[Building Blocks]] question.                                                                                  |
| D60 | Schema version folders   | `tdl/<major.minor>/` for the metadata part, keyed by `TDL:`, and `shell/<major.minor>/` for the blocks, keyed by the `Shell:` minimum. The loader picks the metadata schema first ([[JSON Schema and Editor Support]]).                                                        |

### Seventh-Round Decisions (2026-10-31)

Decided by the maintainer in chat: "P1 is accepted" and "yes a Bar's gap will determine if it is melded to a frame. A frame must be present as well."

| #   | Topic                    | Decision                                                                                                                                                                                                                                                                                              |
|-----|--------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D61 | Bar-to-tre mapping       | P1 is accepted: the mapping and worked examples in [[Bar#Mapping to tre]] are the design. A hidden or peeking Bar keeps its size and slides by a negative margin, so a size of 0 never arises at creation.                                                                                             |
| D62 | Bar meld                 | A Bar's `Gap` on the Frame-facing side decides whether it melds with a Frame: 0 melds, above 0 does not. A Frame must be present; a Bar with no Frame never melds. This is the Bar's counterpart of the Panel `Margin` rule (D44).                                                                       |
| D56 | Correction of D56        | D56 removed the Panel `Meld` key on the agent's recommendation that the margin made it redundant. That was a misreading: in [[Frame]] the `Meld` key chooses the mechanism (hosted inside the Frame's surface, or a window of its own), while the margin or gap decides whether the surface melds at all. The key is restored on the Panel and stays on the Bar, with that meaning only, default `false`. Confirmed by the maintainer, 2026-10-31. |

Both `Meld` and the `Gap` or `Margin` rule apply only with `Attach_To` naming a Frame. `Meld: true` with a `Gap` or `Margin` above 0 on the Frame-facing side has nothing to host and the shell warns.

### Eighth-Round Notes (2026-11-01)

Facts from the TEL repository, read on 2026-11-01. They are TEL's decisions (the maintainer's, in the TEL project), recorded here because they touch D11 and the `For` rules.

| #   | Topic                      | What the TEL repository says                                                                                                                                                                                                                                              |
|-----|----------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| D63 | `?:` in TEL                | Accepted and built (TEL decisions S to W; issue #24; language version 0.1), local and not yet released. Compile cost about 2.1 to 2.9 times for an expression that uses it; evaluation and memory the same.                                                                 |
| D64 | TEL and structure          | TEL evaluates a condition and reconciles a repeater by key; the shell owns the keys, the tree and the UIDs (TEL's D15 and D16, 2026-11-01). Conditions are built; the repeater reconciliation is designed and approved, not built. This refines D11 (TEL is an expression language with a reconciliation helper). |
| D65 | Names of `For` entries     | Adopted from TEL: an entry of a `For` is named `<name>_0001`, `<name>_0002` and so on, from a counter that only grows; a key that disappears and returns gets a new number (maintainer, 2026-11-01, "adopt tel's counter names"). Identity by key stays TEL's (kept, new, moved, removed). The `<name>` is the `Name:` of the `For` block when it has one, else the head of its child, else `For` (the agent's proposal, confirmed by the maintainer 2026-11-01: "as you propose for the base-name rule"). Statically repeated blocks keep their position names (`Square_1`, `Square_2`). |

Open from this: the names of repeated entries. TEL names an entry `<name>_0001` from a counter that only grows and gives a new number to a key that disappears and returns (TEL's D7 and 5H). The TDL rules above say a `For` entry is named `Icon_<key>`. Recommendation: use TEL's counter names. A key can be any value (`DP-1`, a path, a number), but a `Name:` may hold only letters, digits and `_` (D28), so a key-based name could break the name rules. Identity by key stays TEL's (kept, new, moved, removed). The TDL `For ... In ... Key` header maps to TEL's repeater: the item name, the inner text of the iterable slot and the inner text of the `Key` slot. Decided 2026-11-01 (D65).

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
- [x] **The rewrite pass** began 2026-10-29 (maintainer): breadth first through the vault tree, each level before the next. `settings.yaml` became `settings.tdl` (confirmed in D20), and the folder was renamed on 2026-10-30 (D13).
- [x] **Two readings to confirm** from "What TDL Is" items 14 and 15: syntax words are special only in key position, and spaces around `{` and after `:` are optional. Decided 2026-10-30, see Decisions on the Open Items.

Raised while rewriting the notes for TDL (2026-10-29) and decided on 2026-10-30 as recommended (D1 to D24). Each was also an open item in the note that hit it:

- [x] **Literals not defined.** Booleans (`true`, `false`), null, and an empty list `[]`. The examples use `true` and `false`. Decide, and say whether the parser types bare words or the key's schema does. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Names.** Is a block's name only the word before the brace (`root dp1_root { }`, `Clock { }`), or can a `name:` key also give it? Affects module calls, the root header and the path-name rule. The notes keep a `name:` property where YAML had one. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Unnamed blocks as list items** (`[{color: "#000", x: 0}]`), as shadows and elevation need. Alternative: a repeated named block per item. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Numeric keys** (`elevation { 1: ... }`, the `space` scale 1 to 8). Alternative: named levels. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Stylesheet selectors** (`.warning`, `#clock_label`, `Button:hovered`, `Slider::track`) cannot be block names, because `#` starts a comment and `:` makes a property. Options: quoted names, or a separate selector form. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Percent plus pixels.** Is there a TDL form for tre's `calc(100% - 16)`? Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Named sides** (`thickness {top: 8, left: 24}`, `border_thickness`). Assumed: a block with named keys. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **One-line blocks** such as `params { format { type: string, default: "" } }` and an empty block `Spacer { }`. Assumed allowed. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **A repeated property key in one block:** an error, or last wins? Repeated block names are allowed; repeated keys are not covered. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **How the UID write edits the file:** patch the text at the tree node's position, or print the tree back out. Both keep comments. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Several roots in one file** (now several `Monitor` blocks): allowed, decided 2026-10-29 ([[Shell File]] still describes `root`).
- [x] **TEL's structure role.** [[ADR-0008 Tesserae Expression Language]] says TEL owns "structure and values" and its requirements T3 and T8 give it conditions and repeats; this ADR gives `if` and `for` to TDL. Decide whether TEL keeps any structure role, and which component builds and rebuilds those branches (the parser, the shell model or TEL) ([[Layers and Components]]). Decided 2026-10-30, see Decisions on the Open Items.
- [x] **ADR-0011.** Whether it stands for load-time validation only, is superseded, or is rewritten; which editor feedback is wanted after v1; whether `schemas/` is still written to disk now that no modeline points at it; and the shape of the parsed tree when names repeat ([[JSON Schema and Editor Support]]). Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Folder rename.** Done 2026-10-30: the folder `41 YAML Reference` is now `41 TDL Reference`, its index note is `41 TDL Reference`, and the note type `yaml-ref` is now `tdl-ref`. The old names stay as aliases (see Decisions on the Open Items, D13).
- [x] **Module context accessor.** `ctx.yaml()` in the module context ([[Module Context]]): rename (for example `ctx.file`) or keep. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Python builder** signatures for `If` and `For` and whether comments count in the parity test ([[Python Builder]]). Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Layout sketch, ten questions** answered by the maintainer on 2026-10-29: the metadata block is required and holds `UID:`; the file-type key replaces `Type:`; versions are strings; `FileName` was an example; one registry of names for blocks and modules; `Kind: shape` was an example; `Name:` is the unique name and `Index:` picks the monitor; several `Monitor` blocks are allowed; `Import` and `Rectangle` are the right spellings. See "Layout Rules".
- [x] **Capitalised keys everywhere,** with each word of a key Capitalised and joined by `_` (maintainer, 2026-10-29; Layout Rules item 10).
- [x] **One meaning of the Kind key:** a reference by exact name only (Layout Rules item 11).
- [x] **Structure words and values:** `If`, `Else`, `For`, `In`, `Key` Capitalised; enum values lowercase (item 13).
- [x] **Metadata keys:** unknown keys are kept and ignored (item 14). Which keys are required is in the TDL language reference.
- [x] **Instance UIDs:** in the registry as `Clock@<uid>`; `UID:` injected into a use only on request (item 12).
- [x] **Monitor selectors:** `Index:`, `Connector:`, `Description:`, and `Index: default` (item 15). Open: the order when a block has several selectors.
- [x] **Question-mark conditional for values** (maintainer, 2026-10-29: "supporting this would be great", `If` stays). It belongs to TEL, not to TDL, so it is written inside a slot: `Color: {{ hovered ? "#1e1e2e" : "#313244" }}`. Outside a slot the text is an unquoted string (Layout Rules, "What TDL Is" item 14). TEL has `a if c else b` today; `?:` needs a change in TEL, recorded as the proposed T19 in [[Expression Language Requirements]]. The maintainer carries it to the TEL project. Settled 2026-11-01: TEL accepted it (its decisions S to W) and built it, local and unreleased ([[Expression Language Requirements#TEL's Answers (2026-10-31)]]).
- [x] **File-type key and file name disagree:** the key is authoritative; a mismatch is a load error (item 16).
- [x] **Style tokens.** The `$color.surface` form (see [[Style Schema]]) against "no variables": the agent treated them as plain strings the shell resolves. Decided 2026-10-30, see Decisions on the Open Items.

Raised by the second rewrite pass (2026-10-29). The notes use the default shown; the maintainer has not decided:

- [x] **Module file layout.** Do `Style:` and `Params { }` sit in the body after the metadata block (as the notes show) or in the metadata block? Is `Type:` acceptable inside a param declaration now that it is gone as a file key? ([[Module File]]) Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Param names on a use.** Written as the module declared them (`format:`, the notes' default) or Capitalised (`Format:`)? Module File's own Label example declares `text` and passes `Text:`, which is inconsistent until this is decided. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Classes and themes.** How a style class is written when a block head is normally a registered type (the notes use the class name as the head with `Kind: Text` inside). Whether a theme has `Name:` in its metadata. Whether `$color.on_surface` token references match `On_Surface` case-insensitively ([[Style Schema]], [[Style, Theme and Stylesheet Files]]). Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Settings file.** The file-type key and metadata form of `settings.tdl` (the notes show `Settings: v1` as a placeholder), and whether settings keys are written nested or dotted (`Logging.Level`) ([[Settings File]]). Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Frame structure.** `Inner_Border`, `Outer_Border`, `Edges` and the edge names `Top`, `Right`, `Bottom`, `Left`: nested blocks or properties? ([[Frame]]) Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Imported shell files.** Does an imported `_Shell.tdl` hold surface blocks only, or its own `Monitor` blocks? (The notes keep "an imported file takes the importing Monitor's monitor".) Decided 2026-10-30, see Decisions on the Open Items.
- [x] **UID position** in the metadata block (`UID:`). The notes write it after the file-type key. Decided 2026-10-30, see Decisions on the Open Items.
- [x] **How an action names a use:** `Label@<uid>` or the use's `Name:` ([[Module Context]]). Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Schema and the metadata block.** Whether the JSON Schema validates the metadata part, or the loader checks `TDL:` and the file-type key first ([[JSON Schema and Editor Support]]). Decided 2026-10-30, see Decisions on the Open Items.
- [x] **Layer-window namespace.** `tesserae-shell.<kind>.<name>` should read `<type>` now that surfaces have no `Kind:` ([[Surface Types]]). Decided 2026-10-30, see Decisions on the Open Items.

Raised by the second layout sketch (2026-10-30). Each is a question for the maintainer; the agent's recommendation follows it:

- [x] **Is TDL now a language shared with Tesserae UI,** as `TUIF:` and `View { }` suggest? This changes [[ADR-0006 Shell Independent of Tesserae UI]] only at the language level (the shell still does not depend on `tesserae-ui`). Recommendation: yes, TDL is a separate project like TEL, with its own repository and version; its grammar knows nothing about bars or monitors; the shell and Tesserae UI each define their own blocks and schema on top of it. Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Where does the file type live?** The sketch has no file-type key; the root block (`Shell`, `View`, and presumably `Module`, `Style`, `Stylesheet`, `Theme`) may name it. This replaces Layout Rules item 2. Recommendation: the root block names the file type and the metadata `Shell:` / `Module:` etc. goes away; the suffix must agree, as before. Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Meaning of the Shell version.** What `Shell: <version>` means: the format version of the shell's blocks, or the version of the Tesserae Shell program? Recommendation: the shell-format version, since a file records what it was written for; `TRE:`, `TEL:` and `TUIF:` are the minimum versions of the other projects. State "minimum" or "exact" for each. Decided 2026-10-30, see Third-Round Decisions.
- [x] **Name in the metadata.** Is `Name:` required in every file? The sketch puts it there for all types. Recommendation: required for a module (the call name), optional for the rest. Decided 2026-10-30, see Third-Round Decisions.
- [x] **How is a monitor chosen?** `Name: DP-1` is a connector, which makes the unique name unstable and clashes with the decided `Index:`, `Connector:`, `Description:` selectors. Recommendation: keep the selectors and give `Monitor` its own identifier-style `Name:` (`Name: main`). Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Dotted name paths** (`ShellRoot.DP-1.TopBar`, `.get(...)`). `DP-1` is not an identifier, so inside a TEL expression `ShellRoot.DP-1.TopBar` reads as a subtraction. Recommendation: names are identifiers (letters, digits, `_`), and paths use them. Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Bar as surface or module.** Is `Bar` a surface or a module? The sketch says it is a built-in module. Recommendation: it stays a surface type (it owns a layer window); it is called like a module and sits in the same name registry. Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **UID injection.** The sketch writes `UID:` into the `Bar` block. Recommendation: only into a block that has a `Name:`, and only when the user asks for stable identity (Layout Rules item 12 stays). Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Keys inside brackets.** The `Border: [ Color: ..., Thickness: ... ]` form puts keys inside `[ ]` break the rule that `[ ]` is a list and `{ }` a block. Recommendation: write `Border { Color: "#1e1e1e", Thickness: [2, 2, 2, 2] }`. Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Key spelling.** `CornerRadius` or `Corner_Radius`? Recommendation: keep the decided `Corner_Radius`. Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Enum value case.** Capitalised (`Edge: Top`) or lowercase (`Layer: overlay`)? Recommendation: Capitalised for every enum value, because the sketch uses it throughout and it reads the same as the keys; this reverses D13's "enum values lowercase" and needs a pass over the notes. Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Bar geometry keys.** `Width`, `Height`, `Edge`, `Alignment`, `Offset` against the accepted `Edge`, `Span`, `Length`, `Thickness`, `Anchor`, `Size`, `Margin`, `Exclusive_Zone` ([[Bar]], [[Shell File]]). Recommendation: adopt the sketch's names for a Bar's placement and keep `Exclusive_Zone` and `Layer`; map them to tre's `anchor`, `margin` and `size` in the shell. Decide how a full-width Bar is written (`Width: 100%`). Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Layout properties on every block.** `Flex` and `Grid` on every block? The sketch gives the Bar its own `Flex` property and `Grid { }` block; [[Building Blocks]] has `Box`, `FlexBox` and `Grid` as blocks. Recommendation: keep the blocks and let a surface or module hold one layout child; do not add layout properties to every block. Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Trailing comments.** `Key: value   # note` needs a rule, or the comment becomes part of the value. Recommendation: a `#` after whitespace ends an unquoted value and starts a comment; a value that needs `#` is quoted. Decided 2026-10-30, see Second-Sketch Decisions.
- [x] **Import spelling.** Both `import:` and `Import:` appear. Recommendation: only `Import`. Decided 2026-10-30, see Third-Round Decisions.
- [x] **Margin and Padding meanings.** `Padding` inside, `Margin` outside the block, as in the comments. The Bar spec's `Margin` is the offset from the anchored edge. Recommendation: one meaning (outside space) and a separate key for the edge offset (`Offset`). Decided 2026-10-30, see Third-Round Decisions.

Raised by the third rewrite pass (2026-10-30). The notes keep the shown default:

- [x] **Alignment, Offset and Gap to tre.** How the shell computes tre's `anchor`, `size` and margins from `Edge`, `Width`, `Height`, `Alignment`, `Offset` and `Gap` (the same kind of computation as the Panel attachment geometry), and how a collapsed Bar keeps a layer surface so that a size of 0 never arises at creation ([[Bar]]; #needs-verification). Decided 2026-10-31 (D61): the mapping in [[Bar#Mapping to tre]] is accepted.
- [x] **Alignment values.** `START`, `CENTER`, `END` are used in the examples; the maintainer has not listed the values or the default. Decided 2026-10-31 (D55).
- [x] **The Meld key on a Panel.** The key `Meld`: a margin on the Frame-facing sides now decides whether a Panel melds with a Frame, so the `Meld` key may be redundant ([[Panel]]). Decided 2026-10-31 (D56): removed on a Panel.
- [x] **Registry state order.** The registry stores a moved Panel's `margin` in tre's order (top, right, bottom, left), because it comes from tre's `moved` event. Recommendation: leave the JSON in tre's order and name the order in the registry note ([[Config Discovery and Registry]]). Decided 2026-10-31 (D57): `offset` in the shell's order.
- [x] **Setting keys and values.** The enum values of settings keys (`Logging.Format`: `TEXT`, `JSON`; `KWin.Script`: `RUNTIME`, `PERSISTENT`, `OFF`; log levels) follow the upper-case rule but are not listed in [[Settings File]]. Decided 2026-10-31 (D58).
- [ ] **Where Padding applies.** The key `Padding`: the notes say every element with `Children` (Bar, Panel, Frame strips, Popup); the block-level list waits for the building blocks ([[Building Blocks]]). Decided 2026-10-31 (D59): decided in the Building Blocks step; stays open until then. Proposed 2026-11-01 in [[Block Reference]] (R6): `Padding` on every block with `Children` and also on `Text` and `TextField`, which own a text inset.
- [x] **Version-folder id.** The schema `$id` folder used to come from `Shell: v1`; how `TDL:` and `Shell:` map to it is open ([[JSON Schema and Editor Support]]). Decided 2026-10-31 (D60).

Raised by the maintainer's question on slot handling (2026-10-31):

- [x] **Where a slot ends.** The idea that TDL cuts every `{{ }}` out of the file, passes the texts to TEL, and takes values back is mostly the design already: TDL parses the file once and gives TEL each slot's text and start (T17); TEL compiles once and re-evaluates on a name change; results go to the model, not back into the file, and the shell converts them. What is missing is a rule that lets TDL find the end of a slot without TEL's parser. Today TEL's template rule ends a part at the first `}}` after which the text reads as one expression (TEL project `docs/language.md`, section 8). Recommendation: a slot ends at the first `}}` that is not inside a quoted string (single or double quotes, with `\` escapes), and a `}}` meant for the expression is written `} }`, the same habit as closing nested blocks. TDL then gives TEL only the inner text and TEL's template scanner is not used for shell files. Cost: an expression with nested braces needs a space. See [[Expression Language Requirements#Requests to the TEL Project (T17 to T20)]]. Decided 2026-10-31 as recommended (D54).

Raised by the answers of the `tess-el` session (2026-10-31, [[Expression Language Requirements#TEL's Answers (2026-10-31)]]):

- [x] **Dependency tracking for the name tree.** Settled 2026-10-31: TEL built full-path tracking, so the shell uses `reads` and does not record reads itself ([[Expression Language Requirements#TEL's Answers (2026-10-31)]]). The earlier text follows. TEL reports only the top-level name (`RootShell`) until it builds full-path tracking (the TEL project's D13, which waits for the maintainer's go-ahead). Recommendation: the shell records each property read in its own object layer, so a slot depends on `Top_Bar.Width` and not on the whole tree; drop that when TEL has path tracking. The alternative is to re-evaluate every slot that reads `RootShell` on any change.
- [x] **Go-ahead in the TEL project** (given for path tracking; the cost test for T19 is still the TEL project's) for path tracking (T20) and for the cost test of the question-mark conditional (T19). Both are the maintainer's decisions in the TEL project; the shell sends nothing more.

Raised by TEL's step 5 design (2026-11-01):

- [x] **Names of repeated entries.** Adopt TEL's `<name>_0001` counter names for `For` entries instead of `Icon_<key>`, as recommended under Eighth-Round Notes. Also adopt `If` as TEL's condition with the first true branch winning, and `Else` as the end of the chain. Decided 2026-11-01 (D65) for the counter names. The `If` chain is unchanged: `If` with an optional `Else`, no `Else If`; the shell calls TEL's `select` with the one condition.

## Links

- [[ADR-0007 Shell UI Layer]] · [[ADR-0008 Tesserae Expression Language]] · [[ADR-0011 JSON Schema for Shell Files]] · [[Expression Language Requirements]] · [[Python Builder]] · [[Shell File Syntax Comparison]] · [[Prior Art - Linux Shell Surfaces]] · [[30 Decisions]]

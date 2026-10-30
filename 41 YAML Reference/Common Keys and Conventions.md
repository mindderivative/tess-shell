---
title: Common Keys and Conventions
aliases: [YAML Conventions, Shell YAML Keys, TDL Conventions]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-29
tags: [yaml-ref, needs-verification]
related: ["[[41 YAML Reference]]", "[[Shell File]]", "[[Module File]]", "[[Style, Theme and Stylesheet Files]]", "[[ADR-0007 Shell UI Layer]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# Common Keys and Conventions

> [!summary]
> The keys and value forms every shell file (written in TDL, [[ADR-0014 Shell File Language]]) shares. The decisions live in [[ADR-0007 Shell UI Layer]]; this note collects them so a file author has one place to look, and says which parts are decided and which are proposed. Examples are illustrations. Expressions are TEL's ([[Expression Language Requirements]]); the `{{ }}` slot that holds one is TDL's (ADR-0014), and the expression grammar inside it is TEL's.

## Keys Every File Has

| Key     | Meaning                                                               | Rule                                                                                                                                                                                                                                                                   | Status                              |
|---------|-----------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------|
| `TDL`   | The TDL language version (`v1` in the examples)                       | Required, top level, the first line (ADR-0014). Names the language, not the shell format                                                                                                                                                                              | Decided (2026-10-29); version format not decided |
| `shell` | The shell format version (`v1`, `v1234` in the examples)              | Required, top level, directly after `TDL:`. A file without it is not a shell file and is refused with an error naming it                                                                                                                                              | Decided; version format not decided |
| `type`  | What the file is                                                      | Required, top level. `Shell`, `Module`, `Theme`, `Style`, `Stylesheet`, `Settings`. Must agree with the file suffix (`settings.tdl` is a fixed name; the `.tdl` name is an assumption to confirm, [[ADR-0014 Shell File Language#Open Items]])                                                                                                                  | Decided                             |
| `UID`   | The file's shell-wide identifier (UUIDv7)                             | Written by the shell, directly below `shell:`, when the entry is first registered. Authors do not write it. The TDL parser keeps a lossless tree, so the write keeps the file's comments (ADR-0014)                                                                                                                                                             | Decided                             |
| `name`  | A name for a root, surface, container, module, widget or special case | Required on a root, surface and module. **Unique across the shell** (maintainer, 2026-10-26, replacing "per monitor"); reachable from anywhere through the registry. Anything with a unique name gets a UID. Repeated uses of one definition get path names (proposed) | Decided; path names proposed |

File suffixes: `<Name>_Shell.tdl`, `<Name>_Module.tdl`, `<Name>_Style.tdl`, `<Name>_Theme.tdl`, `<Name>_Stylesheet.tdl`, plus a Python file `<Name>_Module.py` next to a module ([[ADR-0007 Shell UI Layer#File naming (2026-10-25)]]). A shell is one `*.tdl` file or a `Main_Shell.tdl` importing `<Name>_Shell.tdl` files. In a file, a block is `name { ... }` and a property is `key: value` ([[ADR-0014 Shell File Language#What TDL Is (Decided)]]); a block's name is the word before the brace, so a root is written `root dp1_root { ... }` (the form of the ADR-0014 sketch; whether a separate `name:` key is also allowed is open).

## Keys that Say what Something is

| Key                      | Names            | Values                                                                                                                                                                          | Status                                                  |
|--------------------------|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|
| `type:`                  | A file's type    | `Shell`, `Module`, `Theme`, `Style`, `Stylesheet`                                                                                                                               | Decided                                                 |
| `kind:`                  | A surface's kind | `bar`, `frame`, `panel`, `popup`                                                                                                                                                | Decided                                                 |
| `block:`                 | A building block | Box, FlexBox, Grid, Text, TextField, Bitmap, SVG, Square, Rectangle, Triangle, Hexagon, Circle, Ellipse, Ring, Path, Terminal, Canvas ([[Building Blocks]]) | Decided (2026-10-26; replaces `widget:`)                |
| A module's name as a key | A module call    | The key is the module's unique `name:`, resolved by the registry; params and `style:` are keys beneath it                                                                       | Decided (2026-10-26); repeats in one container allowed, ordered by position (ADR-0014, 2026-10-29) |
|                          |                  |                                                                                                                                                                                 |                                                         |

- A block is `block: Text`. An entry in `children:` has its own unique key (`title:`) and says what it is with `block:` or by calling a module. A block can be placed anywhere `children:` is allowed: on a surface, in a container, in a module or in a popup (decided 2026-10-27).
- `widget:` and `module:` no longer exist as keys; "module" survives only as `type: Module`.
- **Case.** File types are capitalised (`Module`), surface kinds are lower case (`bar`). Recommendation: match case-insensitively and write the canonical form in files. Not decided.
- The Label style example writes `kind: Text` inside a class to say which block it applies to. `kind:` is the surface kind everywhere else. Recommendation: `block: Text` inside a class. See [[Style, Theme and Stylesheet Files#Classes]].

## Structure Keys

| Key        | Where                                                 | Meaning                                                                                                                                                                                                                                                      | Status                                                                                                                                                                                  |
|------------|-------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `root`     | Shell file                                            | The tree of one monitor's surfaces: `name`, `monitor`, `children`                                                                                                                                                                                            | Decided; multiple roots open ([[Shell File]])                                                                                                                  |
| `monitor`  | A root                                                | Connector name, then description; `default` for monitors no root names; no `monitor` means the root is ignored                                                                                                                                               | Decided                                                                                                                                                                                 |
| `children` | A root, a surface, a container, a popup               | A block of entries: named blocks (a block call or a module call) and `import:` properties; the same name may repeat, ordered by position, and `if` and `for` blocks may appear among them ([[ADR-0014 Shell File Language#Conditions and Repeats (Decided)]]). The only holder of contents; `modules:` is gone | Decided                                                                                                                                                                                 |
| `import`   | Inside `children`                                     | One file name or a list of `<Name>_Shell.tdl` files; paths are relative to the importing file; imports nest                                                                                                                                                 | Decided                                                                                                                                                                                 |
| `import`   | A shell file, a module file, an inline `style:`       | Brings in another `_Shell.tdl`; embeds a module file at that position (`import: <Name>_Module.tdl`), which is how modules nest; inside `style` it imports a style file                                                                                    | Decided                                                                                                                                                                                 |
| `params`   | A module file declares them; a use passes them        | Typed values                                                                                                                                                                                                                                                 | Decided that they exist; type names proposed                                                                                                                                  |
| `tooltip`  | A module use; a block or surface when written by hand | A Popup file name or an inline Popup, opened as that thing's tooltip. Available on every module, built-in and custom, with no module code ([[Popup#Tooltips (decided 2026-10-28)]]). On a Popup entry, `tooltip: true` makes it a tooltip                    | Decided (2026-10-28); the unique-name form is proposed                                                                                                                                  |
| `style`    | A surface, a module                                   | A style file name, or an inline `style { }` block of style values                                                                                                                                                                                                      | Decided                                                                                                                                                                                 |
| `layer`    | A surface                                             | `background`, `bottom`, `top`, `overlay`, numbered 0 to 3 as in the protocol; `overlay` is the highest. A Bar or Panel may use `bottom`, `top` or `overlay`; a Frame only `top`; a Popup stacks above its parent                                             | Decided (the key and the four values, flow diagram 2026-10-26). Only `top` surfaces may reserve space (`exclusive_zone`). `background` is for wallpapers only, for now: no kind uses it |

## Names and References

- A `name` is unique across the shell (maintainer, 2026-10-26) and reachable from anywhere through the registry, nested or not. Anything with a unique name gets a UID. A definition that is used many times (a module, an imported surface set) has local names inside it; each use gets a path name such as `top_label.Label_Text` (proposed, [[ADR-0007 Shell UI Layer#Open items]]).
- A reference to a name in another file is resolved through the registry: a Panel attached to a Bar names the Bar. An unresolved reference is an error at load; a target that disappears while running is a warning and the Panel stays hidden until it returns ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]]).
- Surfaces do not nest. They are siblings and refer to each other by name.
- A UID can also address a file; Python reaches a module's TDL by file name, unique name or UID.

## Value Forms

| Kind                                                        | Forms                                                                                                                                            | Notes                                                                                                       |
|-------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| Colour                                                      | `"#RRGGBB"`, `"#RRGGBBAA"` (quoted, because `#` starts a comment), `rgba(0 0 0 0.5)` (space separated; red, green and blue 0 to 255, alpha 0.0 to 1.0), a theme token name                                                   | The shell converts to tre's `(r, g, b, a)` with 0 to 255 integers ([[Value Types and Conversion]]) |
| Four-sided values (borders, corner radii, margins, padding) | One number for all sides; a list of four clockwise from the top (top, right, bottom, left), `[2, 2, 2, 2]`; named sides as a block, `margin { left: 2, top: 2, right: 2, bottom: 2 }` | The brace-only form `{2, 2, 2, 2}` is not used (PyYAML read it as `{2: None}` on 2026-10-26; in TDL a brace opens a named block) |
| Size                                                        | A whole number of pixels, `auto`, a percentage `50%`; a percentage plus pixels (tre's `calc(100% - 16)`) has no TDL form yet, see Open | Lengths have no unit suffix; a float is only for non-lengths such as `opacity: 0.9` (ADR-0014). The forms tre accepts                                                                                     |
| Text, numbers, booleans                                     | Unquoted words are strings; quote text that holds a `,` or a closing brace; `"..."` or `'...'` with `\` escapes                                   | Boolean spelling is not stated in ADR-0014, see Open                                                        |
| Lists, blocks                                               | `[a, b]` lists; `name { ... }` blocks                                                                                                              | A list feeds a `for` repeat                                                                                 |
| Expression                                                  | A `{{ ... }}` slot on one line, no quotes; TEL evaluates it                                                                                                   | Reads `params.<name>` and values the module sends                                                           |

## Errors

Every error carries `file:line:column`, from the shell's own TDL parser (ADR-0014) and says what is wrong and what to write ([[AGENTS#3. Layering principle]]). Errors that apply to every file: no `shell:` key; a `type:` that does not match the suffix; an unknown key; an unknown `kind:` or `widget:`; a name defined twice (both places named); an import cycle (the chain of files printed); a missing file; a param of the wrong type.

## Open

- [ ] The `shell:` version format and what a version change means.
- [ ] Case rules for `type:` and `kind:` values.
- [x] Unknown keys are errors (decided 2026-10-28, [[Validation and Errors]]).
- [x] The expression delimiter: `{{ }}` on one line (ADR-0014, 2026-10-29). The expression syntax inside it is TEL's.
- [ ] Units beyond pixels (a scale-aware unit).
- [ ] A TDL form for a percentage plus pixels (`calc(100% - 16)`), which ADR-0014 does not define.
- [ ] Boolean and null spellings in TDL (`true`/`false`), which ADR-0014 does not state.
- [ ] Whether a block is named by the word before the brace only (`root dp1_root { }`) or also by a `name:` key.

## Links

- [[41 YAML Reference]] · [[Shell File]] · [[Module File]] · [[Style, Theme and Stylesheet Files]] · [[ADR-0007 Shell UI Layer]]

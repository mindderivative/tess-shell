---
title: Common Keys and Conventions
aliases: [YAML Conventions, Shell YAML Keys, TDL Conventions]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-29
tags: [yaml-ref, needs-verification]
related: ["[[41 YAML Reference]]", "[[TDL Language]]", "[[Shell File]]", "[[Module File]]", "[[Style, Theme and Stylesheet Files]]", "[[ADR-0007 Shell UI Layer]]", "[[ADR-0014 Shell File Language]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]", "[[ADR-0014 Shell File Language]]"]
---

# Common Keys and Conventions

> [!summary]
> The keys and value forms every shell file (written in TDL) shares. The language rules, the metadata block, the name registry and the monitor selectors are stated once in [[TDL Language]]; this note links to them and lists only what a file author needs beside them. The decisions live in [[ADR-0007 Shell UI Layer]] and, for the file layout and the key names, [[ADR-0014 Shell File Language#File Layout (Decided 2026-10-29)]]. Examples are illustrations. Expressions are TEL's ([[Expression Language Requirements]]); the `{{ }}` slot that holds one is TDL's.

## Keys Every File Has

Every file starts with a metadata block between two `---` lines. The keys, the version format and who writes `UID:` are in [[TDL Language#The Metadata Block]]; this table only names them.

| Key                                              | Meaning                                                                 | Status                                  |
|--------------------------------------------------|-------------------------------------------------------------------------|-----------------------------------------|
| `TDL`                                            | The language version, a string                                          | Decided (2026-10-29)                    |
| `Shell`, `Module`, `Style`, `Stylesheet`, `Theme` | The file-type key: exactly one, its value a version string (`Shell: v1`). Authoritative; the suffix must agree | Decided (2026-10-29)                    |
| `UID`                                            | The file's shell-wide identifier (UUIDv7), written by the shell         | Decided                                 |
| `Name`                                           | A module file only: its unique name and the word that calls it          | Decided (2026-10-29)                    |

File suffixes: `<Name>_Shell.tdl`, `<Name>_Module.tdl`, `<Name>_Style.tdl`, `<Name>_Theme.tdl`, `<Name>_Stylesheet.tdl`, plus a Python file `<Name>_Module.py` next to a module ([[ADR-0007 Shell UI Layer#File naming (2026-10-25)]]). The settings file is `settings.tdl` (assumed name, to confirm, [[Settings File]]). A shell is one `*.tdl` file or a `Main_Shell.tdl` importing `<Name>_Shell.tdl` files. The syntax of blocks and properties is in [[TDL Language#Punctuation]].

## Keys that Say what Something is

There is no `Type:`, no lowercase `shell:`, no `Kind:` on a surface and no `Block:` key. What a thing is comes from the file-type key (a file) or from the word before the brace (a block).

| Where                           | What says it                                                                                                | Values                                                                                                                                              | Status                                                  |
|---------------------------------|-------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|
| A file                          | The file-type key in the metadata block                                                                     | `Shell`, `Module`, `Style`, `Stylesheet`, `Theme`                                                                                                   | Decided (2026-10-29)                                    |
| A surface                       | The block head                                                                                              | `Bar`, `Frame`, `Panel`, `Popup` ([[Surface Types]])                                                                                                | Decided (2026-10-29; replaces `kind:`)                  |
| A building block                | The block head                                                                                              | Box, FlexBox, Grid, Text, TextField, Bitmap, SVG, Square, Rectangle, Triangle, Hexagon, Circle, Ellipse, Ring, Path, Terminal, Canvas ([[Building Blocks]]) | Decided (2026-10-29; replaces `block:`)                 |
| A module call                   | The block head, which is the `Name:` in the module file's metadata                                           | `Clock { }`; params and `Style` are keys inside                                                                                                     | Decided (2026-10-29); repeats allowed, ordered by position |
| A monitor                       | The block head `Monitor`                                                                                    | Selectors are in [[TDL Language#Monitors]]                                                                                                          | Decided (2026-10-29; replaces `root`)                   |

- All of these names are in one registry. A name registered twice is a load error, except that a user module of the same name overrides a shipped module ([[TDL Language#Names and the Registry]]).
- `Name:` is the unique name of a block, surface or module. A block can be placed anywhere `Children` is allowed: on a surface, in a container, in a module or in a popup (decided 2026-10-27).
- `Kind:` has one meaning: it references a type by its exact name where a type is named by value (`Kind: Panel`, `Kind: Clock`). A style class that applies to text writes `Kind: Text` ([[Style, Theme and Stylesheet Files#Classes]]). There is no `Kind: Block` and no `Kind: Module`.
- `widget:` and `module:` no longer exist as keys. The word "module" is a file type (`Module: v1`) and a registry name.
- Case: keys, block heads and structure words are Capitalised; enum values are lowercase (`Layer: overlay`) ([[TDL Language#Names and the Registry]]).

## Structure Keys

| Key                          | Where                                                  | Meaning                                                                                                                                                                                                                                                        | Status                                                                                                                                                                                  |
|------------------------------|--------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `Monitor`                    | Top level of a shell file                              | The tree of one monitor's surfaces; several per file. Keys: `Name`, a selector (`Index`, `Connector`, `Description`), `Children` ([[Shell File]])                                                                                                              | Decided (2026-10-29)                                                                                                                                                                    |
| `Children`                   | A Monitor, a surface, a container, a popup             | A block of entries: blocks and module calls (the same head may repeat, ordered by position), `Import` properties, and `If` and `For` blocks ([[ADR-0014 Shell File Language#Conditions and Repeats (Decided)]]). The only holder of contents; `modules:` is gone | Decided                                                                                                                                                                                 |
| `Import`                     | Inside `Children`; a shell file; a module file; an inline `Style` | One file name or a list. Inside `Children` it brings in `<Name>_Shell.tdl` surfaces or embeds a `<Name>_Module.tdl` at that position, which is how modules nest; inside `Style` it imports a style file. Paths are relative to the importing file; imports nest | Decided                                                                                                                                                                                 |
| `If`, `Else`, `For`, `In`, `Key` | Inside `Children`                                  | Conditions and repeats; the forms are in [[TDL Language#Structure Words]]                                                                                                                                                                                       | Decided (2026-10-29)                                                                                                                                                                    |
| `Params`                     | A module file declares them; a use passes them         | Typed values                                                                                                                                                                                                                                                   | Decided that they exist; type names proposed                                                                                                                                            |
| `Tooltip`                    | A module use; a block or surface when written by hand  | A Popup file name or an inline Popup, opened as that thing's tooltip. Available on every module, built-in and custom, with no module code ([[Popup#Tooltips (decided 2026-10-28)]]). On a Popup entry, `Tooltip: true` makes it a tooltip                      | Decided (2026-10-28); the unique-name form is proposed                                                                                                                                  |
| `Style`                      | A surface, a module                                    | A style file name, or an inline `Style { }` block of style values                                                                                                                                                                                              | Decided                                                                                                                                                                                 |
| `Layer`                      | A surface                                              | `background`, `bottom`, `top`, `overlay`, numbered 0 to 3 as in the protocol; `overlay` is the highest. A Bar or Panel may use `bottom`, `top` or `overlay`; a Frame only `top`; a Popup stacks above its parent                                               | Decided (the key and the four values, flow diagram 2026-10-26). Only `top` surfaces may reserve space (`Exclusive_Zone`). `background` is for wallpapers only, for now: no surface type uses it |

## Names and References

- A `Name` is unique across the shell (maintainer, 2026-10-26) and reachable from anywhere through the registry, nested or not. Anything with a unique name gets a UID. A definition that is used many times (a module, an imported surface set) has local names inside it; each use gets a path name such as `top_label.Label_Text` (proposed, [[ADR-0007 Shell UI Layer#Open items]]).
- Each use of a module is an instance. Python keys it as `Clock@<uid>`; the shell writes `UID:` into the use in the file only when the user asks for stable identity across reordering ([[TDL Language#Names and the Registry]]).
- A reference to a name in another file is resolved through the registry: a Panel attached to a Bar names the Bar. An unresolved reference is an error at load; a target that disappears while running is a warning and the Panel stays hidden until it returns ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]]).
- Surfaces do not nest. They are siblings and refer to each other by name.
- A UID can also address a file; Python reaches a module's TDL by file name, unique name or UID.

## Value Forms

The value forms are stated once in [[TDL Language#Values]]; this table adds how the shell uses them.

| Kind                                                        | Forms                                                                                                                                            | Notes                                                                                                       |
|-------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| Colour                                                      | `"#RRGGBB"`, `"#RRGGBBAA"` (quoted, because `#` starts a comment), `rgba(0 0 0 0.5)` (space separated; red, green and blue 0 to 255, alpha 0.0 to 1.0), a theme token name | The shell converts to tre's `(r, g, b, a)` with 0 to 255 integers ([[Value Types and Conversion]]) |
| Four-sided values (borders, corner radii, margins, padding) | One number for all sides; a list of four clockwise from the top (top, right, bottom, left), `[2, 2, 2, 2]`; named sides as a block, `Margin { Left: 2, Top: 2, Right: 2, Bottom: 2 }` | The brace-only form `{2, 2, 2, 2}` is not used (PyYAML read it as `{2: None}` on 2026-10-26; in TDL a brace opens a named block) |
| Size                                                        | A whole number of pixels, `auto`, a percentage `50%`; a percentage plus pixels (tre's `calc(100% - 16)`) has no TDL form yet, see Open | Lengths have no unit suffix; a float is only for non-lengths such as `Opacity: 0.9` (ADR-0014). The forms tre accepts |
| Text, numbers, booleans                                     | Unquoted words are strings; quote text that holds a `,` or a closing brace; `"..."` or `'...'` with `\` escapes                                   | Boolean spelling is not stated in ADR-0014, see Open                                                        |
| Lists, blocks                                               | `[a, b]` lists; `Head { ... }` blocks                                                                                                            | A list feeds a `For` repeat                                                                                 |
| Expression                                                  | A `{{ ... }}` slot on one line, no quotes; TEL evaluates it                                                                                      | Reads `params.<name>` and values the module sends                                                           |

## Errors

Every error carries `file:line:column`, from the shell's own TDL parser (ADR-0014) and says what is wrong and what to write ([[AGENTS#3. Layering principle]]). Errors that apply to every file: a missing metadata block, `TDL:` or file-type key; a file-type key that does not match the suffix (both named); an unknown key; a head word that is not in the registry; a name defined twice (both places named); an import cycle (the chain of files printed); a missing file; a param of the wrong type. The full list is in [[Validation and Errors]].

## Open

- [ ] What a version change of `TDL:` or of a file-type key means (the format is a string, `v1`, `0.1`).
- [x] Case rules for the file-type and surface values: keys and block heads are Capitalised, enum values lowercase, `Kind:` takes an exact name ([[ADR-0014 Shell File Language#Layout Rules]], items 4, 10, 11 and 13).
- [x] Unknown keys are errors (decided 2026-10-28, [[Validation and Errors]]); unknown metadata keys are kept and ignored (ADR-0014, item 14).
- [x] The expression delimiter: `{{ }}` on one line (ADR-0014, 2026-10-29). The expression syntax inside it is TEL's.
- [x] Whether a block is named by the word before the brace or by a key: the head is the type and `Name:` is the unique name (ADR-0014, item 6).
- [ ] Units beyond pixels (a scale-aware unit).
- [ ] A TDL form for a percentage plus pixels (`calc(100% - 16)`), which ADR-0014 does not define.
- [ ] Boolean and null spellings in TDL (`true`/`false`), which ADR-0014 does not state.
- [ ] How a repeated use names itself in the file; see [[TDL Language#Open]].

## Links

- [[41 YAML Reference]] · [[TDL Language]] · [[Shell File]] · [[Module File]] · [[Style, Theme and Stylesheet Files]] · [[ADR-0007 Shell UI Layer]]

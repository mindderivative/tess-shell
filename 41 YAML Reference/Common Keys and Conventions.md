---
title: Common Keys and Conventions
aliases: [YAML Conventions, Shell YAML Keys]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [yaml-ref, needs-verification]
related: ["[[41 YAML Reference]]", "[[Shell File]]", "[[Module File]]", "[[Style, Theme and Stylesheet Files]]", "[[ADR-0007 Shell UI Layer]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# Common keys and conventions

> [!summary]
> The keys and value forms every shell YAML file shares. The decisions live in [[ADR-0007 Shell UI Layer]]; this note collects them so a file author has one place to look, and says which parts are decided and which are proposed. Examples are illustrations. Expressions are TEL's ([[Expression Language Requirements]]); the `{{ }}` delimiter in examples is a placeholder until TEL's syntax is set.

## Keys every file has

| Key | Meaning | Rule | Status |
|---|---|---|---|
| `shell` | The shell format version (`v1`, `v1234` in the examples) | Required, top level, first. A file without it is not a shell file and is refused with an error naming it | Decided; version format not decided |
| `type` | What the file is | Required, top level. `Shell`, `Module`, `Theme`, `Style`, `Stylesheet`. Must agree with the file suffix | Decided |
| `UID` | The file's shell-wide identifier (UUIDv7) | Written by the shell, directly below `shell:`, when the entry is first registered. Authors do not write it | Decided |
| `name` | A name for a root, surface, container, module, widget or special case | Required on a root, surface and module. **Unique across the shell** (maintainer, 2026-10-26, replacing "per monitor"); reachable from anywhere through the registry. Anything with a unique name gets a UID. Repeated uses of one definition get path names (proposed) | Decided; path names proposed |

File suffixes: `<Name>_Shell.yaml`, `<Name>_Module.yaml`, `<Name>_Style.yaml`, `<Name>_Theme.yaml`, `<Name>_Stylesheet.yaml`, plus a Python file `<Name>_Module.py` next to a module ([[ADR-0007 Shell UI Layer#File naming (2026-10-25)]]). A shell is one `*.yaml` file or a `Main_Shell.yaml` importing `<Name>_Shell.yaml` files.

## Keys that say what something is

| Key | Names | Values | Status |
|---|---|---|---|
| `type:` | A file's type | `Shell`, `Module`, `Theme`, `Style`, `Stylesheet` | Decided |
| `kind:` | A surface's kind | `bar`, `frame`, `panel`, `popup` | Decided |
| `block:` | A building block | Box, FlexBox, Grid, Text, TextField, Bitmap, SVG, Square, Rectangle, Triangle, Hexagon, Circle, Ellipse, Ring, Path, Terminal, Canvas ([[Building Blocks]]) | Decided (2026-10-26; replaces `widget:`) |
| A module's name as a key | A module call | The key is the module's unique `name:`, resolved by the registry; params and `style:` are keys beneath it | Decided (2026-10-26); repeats in one container are open |

- A block is `block: Text`. An entry in `children:` has its own unique key (`title:`) and says what it is with `block:` or by calling a module.
- `widget:` and `module:` no longer exist as keys; "module" survives only as `type: Module`.
- **Case.** File types are capitalised (`Module`), surface kinds are lower case (`bar`). Recommendation: match case-insensitively and write the canonical form in files. Not decided.
- The Label style example writes `kind: Text` inside a class to say which block it applies to. `kind:` is the surface kind everywhere else. Recommendation: `block: Text` inside a class. See [[Style, Theme and Stylesheet Files#Classes]].

## Structure keys

| Key | Where | Meaning | Status |
|---|---|---|---|
| `root` | Shell file | The tree of one monitor's surfaces: `name`, `monitor`, `children` | Decided; multiple roots open ([[Shell File]]) |
| `monitor` | A root | Connector name, then description; `default` for monitors no root names; no `monitor` means the root is ignored | Decided |
| `children` | A root, a surface, a container, a popup | A mapping of unique names to entries; `import:` pulls in another file. The only holder of contents; `modules:` is gone | Decided |
| `import` | Inside `children` | One file name or a list of `<Name>_Shell.yaml` files; paths are relative to the importing file; imports nest | Decided |
| `import` | A shell file, a module file, an inline `style:` | Brings in another `_Shell.yaml`; embeds a module file at that position (`import: <Name>_Module.yaml`), which is how modules nest; inside `style:` it imports a style file | Decided |
| `params` | A module file declares them; a use passes them | Typed values | Decided that they exist; type names proposed |
| `style` | A surface, a module | A style file name, or an inline mapping of style values | Decided |
| `layer` | A surface | `background`, `bottom`, `top`, `overlay`, numbered 0 to 3 as in the protocol; `overlay` is the highest. A Bar or Panel may use `bottom`, `top` or `overlay`; a Frame only `top`; a Popup stacks above its parent | Decided (the key and the four values, flow diagram 2026-10-26). Only `top` surfaces may reserve space (`exclusive_zone`). `background` is for wallpapers only, for now: no kind uses it |

## Names and references

- A `name` is unique across the shell (maintainer, 2026-10-26) and reachable from anywhere through the registry, nested or not. Anything with a unique name gets a UID. A definition that is used many times (a module, an imported surface set) has local names inside it; each use gets a path name such as `top_label.Label_Text` (proposed, [[ADR-0007 Shell UI Layer#Open items]]).
- A reference to a name in another file is resolved through the registry: a Panel attached to a Bar names the Bar. An unresolved reference is an error at load; a target that disappears while running is a warning and the Panel stays hidden until it returns ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]]).
- Surfaces do not nest. They are siblings and refer to each other by name.
- A UID can also address a file; Python reaches a module's YAML by file name, unique name or UID.

## Value forms

| Kind | Forms | Notes |
|---|---|---|
| Colour | `"#RRGGBB"`, `"#RRGGBBAA"`, `RGBA(r, g, b, a)` with `a` from 0.0 to 1.0, a theme token name | The shell converts to tre's `(r, g, b, a)` with 0 to 255 integers ([[Value Types and Conversion]]) |
| Four-sided values (borders, corner radii, margins, padding) | One number for all sides; a list of four clockwise from the top (top, right, bottom, left); named sides `{left: 2, top: 2, right: 2, bottom: 2}` | The brace-only forms `{2, 2, 2, 2}` are not used: a standard YAML load reads them as `{2: None}` |
| Size | A number of pixels, `"auto"`, a percentage `"50%"`, a percentage plus pixels `"calc(100% - 16)"` | The forms tre accepts |
| Text, numbers, booleans | Plain YAML | |
| Lists, mappings | Plain YAML | A list feeds a repeater |
| Expression | A string TEL evaluates; the delimiter is TEL's | Reads `params.<name>` and values the module sends |

## Errors

Every error carries `file:line:column` and says what is wrong and what to write ([[AGENTS#3. Layering principle]]). Errors that apply to every file: no `shell:` key; a `type:` that does not match the suffix; an unknown key; an unknown `kind:` or `widget:`; a name defined twice (both places named); an import cycle (the chain of files printed); a missing file; a param of the wrong type.

## Open

- [ ] The `shell:` version format and what a version change means.
- [ ] Case rules for `type:` and `kind:` values.
- [ ] Whether unknown keys are errors or warnings (recommendation: errors, for typos).
- [ ] The expression delimiter and syntax (TEL).
- [ ] Units beyond pixels (a scale-aware unit).

## Links

- [[41 YAML Reference]] · [[Shell File]] · [[Module File]] · [[Style, Theme and Stylesheet Files]] · [[ADR-0007 Shell UI Layer]]

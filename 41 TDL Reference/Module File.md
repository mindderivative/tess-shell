---
title: Module File
aliases: [_Module.yaml, Module YAML, _Module.tdl, Module TDL]
type: tdl-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-30
tags: [tdl-ref, needs-verification]
related: ["[[41 TDL Reference]]", "[[TDL Language]]", "[[Common Keys and Conventions]]", "[[Shell File]]", "[[Module Contract]]", "[[Module Context]]", "[[ADR-0014 Shell File Language]]"]
depends_on: ["[[Common Keys and Conventions]]", "[[ADR-0007 Shell UI Layer]]"]
---

# Module File

> [!summary]
> A module file (file-type key `Module: v1`, suffix `_Module.tdl`, written in TDL, [[ADR-0014 Shell File Language]]) is the layout part of a module: its widgets, the expressions that place data in them, and the params it accepts. It sits beside a style file and a matching Python file in a `Modules/<module_name>/` folder ([[ADR-0007 Shell UI Layer#What a module is (2026-10-26)]]). The Python is described in [[Module Contract]]. The metadata block and the registry are in [[TDL Language]]. Examples are illustrations; the Label example is the maintainer's ([[Module Context#Example: the Label module]]).

## Structure

```
---
TDL: 0.1
Module: v1
Name: Label
---

Style: Label_Style.tdl
Params {
    text { Type: string }
}

FlexBox {
    Name: Label_Module_FlexBox
    Alignment: horizontal
    Width: 120
    Height: 34
    Children {
        Icon {
            Name: Monitor_Icon
            Icon: monitor.svg
        }
        Text {
            Name: Label_Text
            Class: text_style
        }
    }
}
```

## Keys

| Key                                                      | Meaning                                                                          | Status                       |
|----------------------------------------------------------|----------------------------------------------------------------------------------|------------------------------|
| `TDL`, `Module`, `Name`, `UID` (metadata block)          | As every file ([[TDL Language#The Metadata Block]]). `Name` is the module's unique name and the word that calls it. Required | Decided (2026-10-29)         |
| `Style`                                                  | In the body after the metadata block: a style file name, or an inline `Style { }` block of style values | Decided (D17, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]) |
| `Params`                                                 | In the body after the metadata block: the values a use may pass, each a block that may have a `Type:` property | Decided (D17); the type names are proposed |
| A top-level block (`FlexBox { }`, `Box { }`)             | The root of the module's layout; the head is a building block or a module        | Decided (the form)           |
| `Children`                                               | The root block's children, blocks and module uses                                | Decided                      |

A module file has one layout root. There is no `Monitor` and no surface head in it: a module is not a surface.

## Blocks and Modules in the Layout

A module's layout is made of building blocks and other modules ([[ADR-0007 Shell UI Layer#Blocks, modules and styling (2026-10-26)]], decided 2026-10-26). Both are called the same way, by the registry name as the block head ([[TDL Language#Names and the Registry]]).

- A block is called by its name as the head (`FlexBox { }`, `Text { }`). A block needs no `Name:` and no UID unless the Python or an expression refers to it.
- A module is called by the `Name:` in its metadata, with its params as keys inside (`Label { text: Hello }`; the names are the module author's and keep their case, D18). A module nests another with `Import: <Name>_Module.tdl`.
- `Name:` on a block or use is its unique name, optional unless something refers to it.
- A block or module may take `Class:` to pick up a class from a style file, or `Style:` for its own style ([[Style, Theme and Stylesheet Files]]).
- The v1 blocks and standard modules are in [[V1 Widgets]] and [[Building Blocks]].

## Params

```
Params {
    text { Type: string }
    size { Type: number, Default: 16 }
    color { Type: color, Default: "#ffffff" }
}
```

- The module declares typed params. A use passes values; the shell checks them against the declaration and reports a mismatch with `file:line:column` ([[Module Contract#Failure modes and recovery]]).
- Param names (`text`, `size`) are the author's. Type names are proposed, matching [[Value Types and Conversion]]: `string`, `number`, `boolean`, `color`, `size`, `list`, `mapping`. A `Default` is optional (proposed). `Type:` is a property of a param declaration and not a file key (D17).
- In the Python a use's params are `use.params` ([[Module Context]]).
- In an expression a param is `params.<name>`.

## Data in the Layout

Expressions in the module's TDL place data in widgets. They read two kinds of name (decided 2026-10-26):

| Name            | Source                                                       |
|-----------------|--------------------------------------------------------------|
| `params.<name>` | The value the use passed                                     |
| `<key>`         | A value the module's Python sent with `ctx.send(key, value)` |

```
Text {
    Name: Label_Text
    # the slot is TDL's; the expression inside it is TEL's (illustration only)
    Text: {{ params.text if params.text else text }}
}
```

- A value sent with `use=` reaches only that use; one sent without reaches every use ([[Module Context#Sending values]]).
- A clash between a param and a sent value of the same name is avoided by the `params.` prefix.
- Direct addressing of a widget by its `Name:` from Python is optional.

## Using a Module

A module is placed under `Children` (there is no `modules:` key since 2026-10-26). Decided (maintainer, 2026-10-26 and 2026-10-29): a module is called by the `Name:` in its metadata as the block head, `widget:` and `module:` are gone, params are keys inside the block, and `Import:` embeds a module file at that position ([[ADR-0007 Shell UI Layer#Module call, shipped modules and Path (2026-10-26)]]). A building block is called the same way, by its head, with no `Block:` key.

```
Children {
    # embeds that module file at this position
    Import: Custom_Module.tdl
    # a module, called by its name
    Label {
        # a param, as a key inside the call
        text: "This is a title"
        # an inline style can import a style file
        Style { Import: Custom_Style.tdl }
    }
    Icon {
        # or a file path; wrap in quotes if needed
        Svg: home.svg
        Style {
            Foreground: "#ffffff"
            Size: 18
        }
    }
    # a building block
    Text {
        Name: title
        Text: Hello
    }
}
```

A module file may be used many times; there is one Python instance for all uses, with a `use` record per call. Two uses of one module in one container are written as the same head repeated in one `Children { }`, ordered by position (ADR-0014, 2026-10-29; it replaces the list form decided on 2026-10-26):

```
Children {
    Label { text: "label 1" }
    Label { text: "label 2" }
    Import: Custom_Module.tdl
}
```

`Import:` is a property of the same `Children` block. An optional `Name:` per use keeps its path name unique; without one the shell names it from its position (`Label_1`, `Label_2`), decided 2026-10-26 ([[ADR-0007 Shell UI Layer#Open items]]). Python keys each use as `Label@<uid>`; the shell writes `UID:` into a use in the file only if the user asks for stable identity across reordering ([[TDL Language#Names and the Registry]]).

## Params down the Tree

The maintainer suggested a "bubble up" policy for params (2026-10-26). My reading and thoughts:

- **Reading:** a nested module or widget that needs a param it was not given looks *up* the tree to its ancestors until it finds one (so a deep `Text` can read the outer module's `text` without every level passing it). The other possible reading, values moving from a child to its parent, is better done with events and actions, and is not proposed.
- **For:** less repetition when a value is needed several levels down (a colour, a monitor name).
- **Against:** it makes dependencies invisible and a rename can silently change which ancestor supplies a value; a module used in two places may find different values.
- **Recommendation:** explicit and opt-in. A param declares `Inherit: true` to be looked up the ancestry when not passed; the nearest ancestor that has it wins; a required param found nowhere is an error naming the chain it searched. Everything else must be passed. Because names and UIDs are reachable shell-wide through the registry, a value can also be read by an explicit reference, so inheriting is a convenience and not a necessity.
- Decided (maintainer, 2026-10-26): opt-in only, as recommended. A param declares `Inherit: true`; the nearest ancestor wins; a required param found nowhere is an error naming the chain.

## Errors Specific to Module Files

- A `Module:` file without a matching `_Module.py`: error naming both files.
- A file-type key and suffix that disagree: error naming both.
- A module file without `Name:` in its metadata: error.
- A `Name` registered twice: error naming both places; a user module of a shipped module's name overrides it ([[TDL Language#Names and the Registry]]).
- A param passed that is not declared, or of the wrong type: error naming the use and the param.
- A param declared without a default and not passed: error at the use.
- A `Style:` file that is not found: error with the search paths.
- A `Name:` defined twice in one file: error, both places named.

## Open

- [ ] The `Params` type names and whether defaults are v1.
- [ ] How the module's root is written when it is not a container (a single `Text`).
- [ ] The widget property names (`Foreground`, `Fill`, `Alignment`, `Justify_Content`, `Align_Content`, `Width`, `Height`) and which go in style or on the widget.
- [x] Where a module file's own `Style:` and `Params { }` sit: in the body after the metadata block (D17, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).
- [x] Whether `Type:` stays inside a param declaration: yes, as a property, not a file key (D17). Open: `Default:` and the type names ([[#Params]]).
- [ ] Whether a module can declare the keys its Python sends, so the shell checks a layout against them at load ([[Value Types and Conversion#Open questions]]).
- [x] Whether a module can contain other modules: the flow diagram says yes ("Can Nest"); the meaning for params, names and UIDs is open ([[Shell Structure]]).
- [ ] How events are declared on a widget (`On_Click:` and the like) and how they name `@action` methods ([[ADR-0007 Shell UI Layer#Events and module reload (2026-10-26)]]).
- [x] Whether a module call may take the name word before the brace: yes, the head is the module's metadata `Name:` (ADR-0014, item 7). Open: how a repeated use names itself in the file ([[TDL Language#Open]]).

## Links

- [[41 TDL Reference]] · [[TDL Language]] · [[Common Keys and Conventions]] · [[Shell File]] · [[Module Contract]] · [[Module Context]]

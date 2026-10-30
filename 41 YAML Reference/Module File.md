---
title: Module File
aliases: [_Module.yaml, Module YAML, _Module.tdl, Module TDL]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-29
tags: [yaml-ref, needs-verification]
related: ["[[41 YAML Reference]]", "[[Common Keys and Conventions]]", "[[Shell File]]", "[[Module Contract]]", "[[Module Context]]"]
depends_on: ["[[Common Keys and Conventions]]", "[[ADR-0007 Shell UI Layer]]"]
---

# Module File

> [!summary]
> A module file (`type: Module`, suffix `_Module.tdl`, written in TDL, [[ADR-0014 Shell File Language]]) is the layout part of a module: its widgets, the expressions that place data in them, and the params it accepts. It sits beside a style file and a matching Python file in a `Modules/<module_name>/` folder ([[ADR-0007 Shell UI Layer#What a module is (2026-10-26)]]). The Python is described in [[Module Contract]]. Examples are illustrations; the Label example is the maintainer's ([[Module Context#Example: the Label module]]).

## Structure

```
TDL: v1
shell: v1
type: Module
name: label
style: Label_Style.tdl
params {
    text { type: string }
}

FlexBox {
    name: Label_Module_FlexBox
    alignment: horizontal
    width: 120
    height: 34
    children {
        Icon {
            name: Monitor_Icon
            icon: monitor.svg
        }
        Text {
            name: Label_Text
            class: text_style
        }
    }
}
```

## Keys

| Key                                                      | Meaning                                                          | Status                       |
|----------------------------------------------------------|------------------------------------------------------------------|------------------------------|
| `shell`, `type: Module`, `UID`                           | As every file ([[Common Keys and Conventions]])          | Decided                      |
| `name`                                                   | The module's name. Required                                      | Decided                      |
| `style`                                                  | A style file name, or an inline `style { }` block of style values | Decided                      |
| `params`                                                 | The values a use may pass, with their types                      | Decided; type names proposed |
| A top-level widget (`FlexBox { }`, `Box { }` or `block: FlexBox`) | The root of the module's layout                                  | Decided (the form)           |
| `children`                                               | The root widget's children, a block of uniquely named widgets    | Decided                      |

A module file has one layout root. There is no `root:` key and no `kind:`: a module is not a surface.

## Blocks and Modules in the Layout

A module's layout is made of building blocks and other modules ([[ADR-0007 Shell UI Layer#Blocks, modules and styling (2026-10-26)]], decided 2026-10-26).

- A block is called with `block:` (`block: FlexBox`, `block: Text`). Blocks need no name and no UID.
- A module is called by its unique `name:`, which the registry resolves. A module nests another with `import: <Name>_Module.tdl`. Its params are keys on the call.
- Entries in `children` have their own unique names.
- A `name:` on a block is optional unless the Python or an expression refers to it.
- A block or module may take `class:` to pick up a class from a style file, or `style:` for its own style ([[Style, Theme and Stylesheet Files]]).
- The v1 blocks and standard modules are in [[V1 Widgets]] and [[Building Blocks]].

### The Label Example under the New Keys

An illustration only; the maintainer's original is in [[Module Context#Example: the Label module]].

```
TDL: v1
shell: v1
type: Module
name: label
style: Label_Style.tdl
params {
    text { type: string }
}

block: FlexBox
alignment: horizontal
width: 120
height: 34
children {
    # a module, called by its name
    Icon {
        svg: monitor.svg
    }
    label_text {
        block: Text
        class: text_style
    }
}
```

## Params

```
params {
    text { type: string }
    size { type: number, default: 16 }
    color { type: color, default: "#ffffff" }
}
```

- The module declares typed params. A use passes values; the shell checks them against the declaration and reports a mismatch with `file:line:column` ([[Module Contract#Failure modes and recovery]]).
- Type names are proposed, matching [[Value Types and Conversion]]: `string`, `number`, `boolean`, `color`, `size`, `list`, `mapping`. A `default` is optional (proposed).
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
    name: Label_Text
    # the slot is TDL's; the expression inside it is TEL's (illustration only)
    text: {{ params.text if params.text else text }}
}
```

- A value sent with `use=` reaches only that use; one sent without reaches every use ([[Module Context#Sending values]]).
- A clash between a param and a sent value of the same name is avoided by the `params.` prefix.
- Direct addressing of a widget by its `name:` from Python is optional.

## Using a Module

A module is placed under `children` (there is no `modules:` key since 2026-10-26), each use with its own unique key. Decided (maintainer, 2026-10-26): a module is called by its unique name as the key, `widget:` and `module:` are gone, params are keys beneath it, and `import:` embeds a module file at that position ([[ADR-0007 Shell UI Layer#Module call, shipped modules and Path (2026-10-26)]]). A block is called with `block:`, under a key of its own.

```
children {
    # embeds that module file at this position
    import: Custom_Module.tdl
    # a module, called by its unique name
    Label {
        # a param, as a key on the call
        text: "This is a title"
        # an inline style can import a style file
        style { import: Custom_Style.tdl }
    }
    Icon {
        # or a file path; wrap in quotes if needed
        svg: home.svg
        style {
            foreground: "#ffffff"
            size: 18
        }
    }
    # a building block
    title {
        block: Text
        text: Hello
    }
}
```

A module file may be used many times; there is one Python instance for all uses, with a `use` record per call. Two uses of one module in one container were decided as a list form on 2026-10-26; ADR-0014 (2026-10-29) replaces it with the same name repeated in one `children { }`, ordered by position:

```
children {
    Label { text: "label 1" }
    Label { text: "label 2" }
    import: Custom_Module.tdl
}
```

`import:` is a property of the same `children` block. An optional `name:` per entry keeps each use's path name unique; without one the shell names it from its position (`Label_1`, `Label_2`), decided 2026-10-26 ([[ADR-0007 Shell UI Layer#Open items]]).

## Params down the Tree

The maintainer suggested a "bubble up" policy for params (2026-10-26). My reading and thoughts:

- **Reading:** a nested module or widget that needs a param it was not given looks *up* the tree to its ancestors until it finds one (so a deep `Text` can read the outer module's `text` without every level passing it). The other possible reading, values moving from a child to its parent, is better done with events and actions, and is not proposed.
- **For:** less repetition when a value is needed several levels down (a colour, a monitor name).
- **Against:** it makes dependencies invisible and a rename can silently change which ancestor supplies a value; a module used in two places may find different values.
- **Recommendation:** explicit and opt-in. A param declares `inherit: true` to be looked up the ancestry when not passed; the nearest ancestor that has it wins; a required param found nowhere is an error naming the chain it searched. Everything else must be passed. Because names and UIDs are reachable shell-wide through the registry, a value can also be read by an explicit reference, so inheriting is a convenience and not a necessity.
- Decided (maintainer, 2026-10-26): opt-in only, as recommended. A param declares `inherit: true`; the nearest ancestor wins; a required param found nowhere is an error naming the chain.

## Errors Specific to Module Files

- `type: Module` without a matching `_Module.py`: error naming both files.
- A `type:` and suffix that disagree: error.
- A param passed that is not declared, or of the wrong type: error naming the use and the param.
- A param declared without a default and not passed: error at the use.
- A `style:` file that is not found: error with the search paths.
- A `name` defined twice in one file: error, both places named.

## Open

- [ ] The `params` type names and whether defaults are v1.
- [ ] How the module's root is written when it is not a container (a single `Text`).
- [ ] The widget property names (`foreground`, `fill`, `alignment`, `justify_content`, `align_content`, `width`, `height`) and which go in style or on the widget.
- [ ] Whether a module can declare the keys its Python sends, so the shell checks a layout against them at load ([[Value Types and Conversion#Open questions]]).
- [x] Whether a module can contain other modules: the flow diagram says yes ("Can Nest"); the meaning for params, names and UIDs is open ([[Shell Structure]]).
- [ ] How events are declared on a widget (`on_click:` and the like) and how they name `@action` methods ([[ADR-0007 Shell UI Layer#Events and module reload (2026-10-26)]]).
- [ ] Whether a module call may take the name word before the brace as its unique name, or `name:` stays a key on the call (ADR-0014 does not say).

## Links

- [[41 YAML Reference]] · [[Common Keys and Conventions]] · [[Shell File]] · [[Module Contract]] · [[Module Context]]

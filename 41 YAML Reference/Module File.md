---
title: Module File
aliases: [_Module.yaml, Module YAML]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [yaml-ref, needs-verification]
related: ["[[41 YAML Reference]]", "[[Common Keys and Conventions]]", "[[Shell File]]", "[[Module Contract]]", "[[Module Context]]"]
depends_on: ["[[Common Keys and Conventions]]", "[[ADR-0007 Shell UI Layer]]"]
---

# Module file

> [!summary]
> A module file (`type: Module`, suffix `_Module.yaml`) is the layout part of a module: its widgets, the expressions that place data in them, and the params it accepts. It sits beside a style file and a matching Python file in a `Modules/<module_name>/` folder ([[ADR-0007 Shell UI Layer#What a module is (2026-10-26)]]). The Python is described in [[Module Contract]]. Examples are illustrations; the Label example is the maintainer's ([[Module Context#Example: the Label module]]).

## Structure

```yaml
shell: v1
type: Module
name: label
style: Label_Style.yaml
params:
    text: {type: string}

FlexBox:
    name: Label_Module_FlexBox
    alignment: horizontal
    width: 120
    height: 34
    children:
        Icon:
            name: Monitor_Icon
            icon: monitor.svg
        Text:
            name: Label_Text
            class: text_style
```

## Keys

| Key | Meaning | Status |
|---|---|---|
| `shell`, `type: Module`, `UID` | As every file ([[Common Keys and Conventions]]) | Decided |
| `name` | The module's name. Required | Decided |
| `style` | A style file name, or an inline mapping of style values | Decided |
| `params` | The values a use may pass, with their types | Decided; type names proposed |
| A top-level widget (`FlexBox:`, `Box:` or `widget: ...`) | The root of the module's layout | Decided (the form) |
| `children` | The root widget's children, a mapping of unique names to widgets | Decided |

A module file has one layout root. There is no `root:` key and no `kind:`: a module is not a surface.

## Widgets in the layout

- A widget is written `Text:` or `widget: Text`; they mean the same. Where a type repeats, use a unique key with `widget: Text` inside ([[Common Keys and Conventions#Keys that say what something is]]).
- Every widget may have a `name:`, optional unless the Python or an expression refers to it; names are unique per monitor and scoped to the file.
- A widget may have a `class:` that picks up a class from the style file ([[Style, Theme and Stylesheet Files#Classes]]).
- Containers: `Box` (no auto-stacking; invisible if unstyled) and `FlexBox` (auto-stacking, `alignment: vertical` or `horizontal`). The v1 list is [[V1 Widgets]].
- Widget properties not in the style (an icon file, a label's text, a size) are written on the widget, and may be expressions.

## Params

```yaml
params:
    text: {type: string}
    size: {type: number, default: 16}
    color: {type: color, default: "#ffffff"}
```

- The module declares typed params. A use passes values; the shell checks them against the declaration and reports a mismatch with `file:line:column` ([[Module Contract#Failure modes and recovery]]).
- Type names are proposed, matching [[Value Types and Conversion]]: `string`, `number`, `boolean`, `color`, `size`, `list`, `mapping`. A `default` is optional (proposed).
- In the Python a use's params are `use.params` ([[Module Context]]).
- In an expression a param is `params.<name>`.

## Data in the layout

Expressions in the module's YAML place data in widgets. They read two kinds of name (decided 2026-10-26):

| Name | Source |
|---|---|
| `params.<name>` | The value the use passed |
| `<key>` | A value the module's Python sent with `ctx.send(key, value)` |

```yaml
Text:
    name: Label_Text
    text: "{{ params.text if params.text else text }}"     # TEL decides the syntax; illustration only
```

- A value sent with `use=` reaches only that use; one sent without reaches every use ([[Module Context#Sending values]]).
- A clash between a param and a sent value of the same name is avoided by the `params.` prefix.
- Direct addressing of a widget by its `name:` from Python is optional.

## Using a module

A surface lists modules under `modules:`, each with a unique name:

```yaml
modules:
    audio: Audio_Module.yaml                   # just the file
    top_label:                                 # the file plus params
        module: Label_Module.yaml
        text: "Work"
```

The scalar form is the module file alone; the mapping form adds `module:` and the values for its `params`. The mapping form is a proposal. A module file may be used many times; there is one Python instance for all uses.

## Errors specific to module files

- `type: Module` without a matching `_Module.py`: error naming both files.
- A `type:` and suffix that disagree: error.
- A param passed that is not declared, or of the wrong type: error naming the use and the param.
- A param declared without a default and not passed: error at the use.
- A `style:` file that is not found: error with the search paths.
- A widget `name` defined twice in one file: error, both places named.

## Open

- [ ] The `params` type names and whether defaults are v1.
- [ ] How the module's root is written when it is not a container (a single `Text`).
- [ ] The widget property names (`foreground`, `fill`, `alignment`, `justify_content`, `align_content`, `width`, `height`) and which go in style or on the widget.
- [ ] Whether a module can declare the keys its Python sends, so the shell checks a layout against them at load ([[Value Types and Conversion#Open questions]]).
- [ ] Whether a module can contain other modules.
- [ ] How events are declared on a widget (`on_click:` and the like) and how they name `@action` methods ([[ADR-0007 Shell UI Layer#Events and module reload (2026-10-26)]]).

## Links

- [[41 YAML Reference]] · [[Common Keys and Conventions]] · [[Shell File]] · [[Module Contract]] · [[Module Context]]

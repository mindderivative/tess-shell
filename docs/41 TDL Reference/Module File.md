---
title: Module File
aliases: [_Module.yaml, Module YAML, _Module.tdl, Module TDL]
type: tdl-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-30
tags: [tdl-ref, needs-verification]
---

# Module File

> [!NOTE]
> A module file (root block `Module { }`, suffix `_Module.tdl`, written in TDL, [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)) is the layout part of a module: its widgets, the expressions that place data in them, and the params it accepts. It sits beside a style file and a matching Python file in a `Modules/<module_name>/` folder ([ADR-0007 Shell UI Layer > What a module is (2026-10-26)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#what-a-module-is-2026-10-26)). The Python is described in [Module Contract](../42%20Python%20API/Module%20Contract.md). The metadata block and the registry are in [TDL Language](TDL%20Language.md). Examples are illustrations; the Label example is the maintainer's ([Module Context > Example: the Label module](../42%20Python%20API/Module%20Context.md#example-the-label-module)).

## Structure

```
---
TDL: 0.1
TEL: 0.1
TRE: 0.5.9
Shell: 0.1
Name: Label
---

Module {
    Style: Label_Style.tdl
    Params {
        text { Type: string }
    }

    FlexBox {
        Name: Label_Module_FlexBox
        Flex: HORIZONTAL
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
}
```

The metadata `Name: Label` is the module's call name. The root block `Module { }` holds `Params { }`, `Style` and the layout. A module whose root layout is a surface holds it the same way, for example a module `Top_Bar` with `Module { Bar { Name: Top_Bar_Surface Edge: TOP Width: EXPAND Height: 32 } }`, usable under several `Monitor` blocks (D29).

## Keys

| Key                                                      | Meaning                                                                          | Status                       |
|----------------------------------------------------------|----------------------------------------------------------------------------------|------------------------------|
| `TDL`, version pins, `Name`, `UID` (metadata block)      | As every file ([TDL Language > The Metadata Block](TDL%20Language.md#the-metadata-block)). `Name` is the module's call name and unique name. Required (D39) | Decided (2026-10-30)         |
| `Module { }`                                             | The root block; it names the file type and holds everything below                | Decided (2026-10-30)         |
| `Style`                                                  | Inside `Module { }`: a style file name, or an inline `Style { }` block of style values | Decided (D17, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)) |
| `Params`                                                 | Inside `Module { }`: the values a use may pass, each a block that may have a `Type:` property | Decided (D17); the type names are proposed |
| A block inside `Module { }` (`FlexBox { }`, `Box { }`)   | The root of the module's layout; the head is a building block, a module or a surface | Decided (the form)           |
| `Children`                                               | The root block's children, blocks and module uses                                | Decided                      |

A module file has one layout root. There is no `Monitor` in it. The layout root may be a surface (`Bar`, `Panel`, ...), but surfaces never nest inside surfaces.

## Blocks and Modules in the Layout

A module's layout is made of building blocks and other modules ([ADR-0007 Shell UI Layer > Blocks, modules and styling (2026-10-26)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#blocks-modules-and-styling-2026-10-26), decided 2026-10-26). Both are called the same way, by the registry name as the block head ([TDL Language > Names and the Registry](TDL%20Language.md#names-and-the-registry)).

- A block is called by its name as the head (`FlexBox { }`, `Text { }`). A block needs no `Name:` and no UID unless the Python or an expression refers to it.
- A module is called by the `Name:` in its metadata, with its params as keys inside (`Label { text: Hello }`; the names are the module author's and keep their case, D18). A module nests another with `Import: <Name>_Module.tdl`.
- `Name:` on a block or use is its unique name, optional unless something refers to it.
- A block or module may take `Class:` to pick up a class from a style file, or `Style:` for its own style ([Style, Theme and Stylesheet Files](Style%2C%20Theme%20and%20Stylesheet%20Files.md)).
- The v1 blocks and standard modules are in [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) and [Building Blocks](../50%20Design%20System/Building%20Blocks.md).

## Params

```
Params {
    text { Type: string }
    size { Type: number, Default: 16 }
    color { Type: color, Default: "#ffffff" }
}
```

- The module declares typed params. A use passes values; the shell checks them against the declaration and reports a mismatch with `file:line:column` ([Module Contract > Failure modes and recovery](../42%20Python%20API/Module%20Contract.md#failure-modes-and-recovery)).
- Param names (`text`, `size`) are the author's. Type names are proposed, matching [Value Types and Conversion](../42%20Python%20API/Value%20Types%20and%20Conversion.md): `string`, `number`, `boolean`, `color`, `size`, `list`, `mapping`. A `Default` is optional (proposed). `Type:` is a property of a param declaration and not a file key (D17).
- In the Python a use's params are `use.params` ([Module Context](../42%20Python%20API/Module%20Context.md)).
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

- A value sent with `use=` reaches only that use; one sent without reaches every use ([Module Context > Sending values](../42%20Python%20API/Module%20Context.md#sending-values)).
- A clash between a param and a sent value of the same name is avoided by the `params.` prefix.
- Direct addressing of a widget by its `Name:` from Python is optional.

## Using a Module

A module is placed under `Children` (there is no `modules:` key since 2026-10-26). Decided (maintainer, 2026-10-26 and 2026-10-29): a module is called by the `Name:` in its metadata as the block head, `widget:` and `module:` are gone, params are keys inside the block, and `Import:` embeds a module file at that position ([ADR-0007 Shell UI Layer > Module call, shipped modules and Path (2026-10-26)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#module-call-shipped-modules-and-path-2026-10-26)). A building block is called the same way, by its head, with no `Block:` key.

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
        Width: 18
        Height: 18
        Style {
            Foreground: "#ffffff"
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

`Import:` is a property of the same `Children` block. An optional `Name:` per use keeps its path name unique; without one the shell names it from its position (`Label_1`, `Label_2`), decided 2026-10-26 ([ADR-0007 Shell UI Layer > Open items](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#open-items)). Python keys each use as `Label@<uid>`; the shell writes `UID:` into a use in the file only if the user asks for stable identity across reordering ([TDL Language > Names and the Registry](TDL%20Language.md#names-and-the-registry)).

## Params down the Tree

The maintainer suggested a "bubble up" policy for params (2026-10-26). My reading and thoughts:

- **Reading:** a nested module or widget that needs a param it was not given looks *up* the tree to its ancestors until it finds one (so a deep `Text` can read the outer module's `text` without every level passing it). The other possible reading, values moving from a child to its parent, is better done with events and actions, and is not proposed.
- **For:** less repetition when a value is needed several levels down (a colour, a monitor name).
- **Against:** it makes dependencies invisible and a rename can silently change which ancestor supplies a value; a module used in two places may find different values.
- **Recommendation:** explicit and opt-in. A param declares `Inherit: true` to be looked up the ancestry when not passed; the nearest ancestor that has it wins; a required param found nowhere is an error naming the chain it searched. Everything else must be passed. Because names and UIDs are reachable shell-wide through the registry, a value can also be read by an explicit reference, so inheriting is a convenience and not a necessity.
- Decided (maintainer, 2026-10-26): opt-in only, as recommended. A param declares `Inherit: true`; the nearest ancestor wins; a required param found nowhere is an error naming the chain.

## Errors Specific to Module Files

- A `Module { }` file without a matching `_Module.py`: error naming both files.
- A root block and suffix that disagree: error naming both.
- A module file without `Name:` in its metadata: error.
- A `Name` registered twice: error naming both places; a user module of a shipped module's name overrides it ([TDL Language > Names and the Registry](TDL%20Language.md#names-and-the-registry)).
- A param passed that is not declared, or of the wrong type: error naming the use and the param.
- A param declared without a default and not passed: error at the use.
- A `Style:` file that is not found: error with the search paths.
- A `Name:` defined twice in one file: error, both places named.

## Open

- [ ] The `Params` type names and whether defaults are v1.
- [ ] How the module's root is written when it is not a container (a single `Text`).
- [ ] The widget property names (`Foreground`, `Fill`, `Alignment`, `Justify_Content`, `Align_Content`, `Width`, `Height`) and which go in style or on the widget.
- [x] Where a module file's own `Style:` and `Params { }` sit: inside the `Module { }` root block (D17, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [x] Whether `Type:` stays inside a param declaration: yes, as a property, not a file key (D17). Open: `Default:` and the type names ([Params](#params)).
- [ ] Whether a module can declare the keys its Python sends, so the shell checks a layout against them at load ([Value Types and Conversion > Open questions](../42%20Python%20API/Value%20Types%20and%20Conversion.md#open-questions)).
- [x] Whether a module can contain other modules: the flow diagram says yes ("Can Nest"); the meaning for params, names and UIDs is open ([Shell Structure](../20%20Architecture/Shell%20Structure.md)).
- [ ] How events are declared on a widget (`On_Click:` and the like) and how they name `@action` methods ([ADR-0007 Shell UI Layer > Events and module reload (2026-10-26)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#events-and-module-reload-2026-10-26)).
- [x] Whether a module call may take the name word before the brace: yes, the head is the module's metadata `Name:` (ADR-0014, item 7). Open: how a repeated use names itself in the file ([TDL Language > Open](TDL%20Language.md#open)).

## Links

- [41 TDL Reference](41%20TDL%20Reference.md) · [TDL Language](TDL%20Language.md) · [Common Keys and Conventions](Common%20Keys%20and%20Conventions.md) · [Shell File](Shell%20File.md) · [Module Contract](../42%20Python%20API/Module%20Contract.md) · [Module Context](../42%20Python%20API/Module%20Context.md)

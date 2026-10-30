---
title: Shell File Syntax Comparison
aliases: [YAML TDL KDL Comparison, TDL Comparison]
type: research
status: draft
owner: phil
created: 2026-10-29
updated: 2026-10-29
tags: [research, tdl]
related: ["[[ADR-0014 Shell File Language]]", "[[ADR-0007 Shell UI Layer]]", "[[Shell File]]", "[[Common Keys and Conventions]]"]
depends_on: []
---

# Shell File Syntax Comparison

> [!summary]
> One small shell written three ways: YAML (today, [[ADR-0007 Shell UI Layer]]), TDL (the language chosen in [[ADR-0014 Shell File Language]]) and KDL 2. The shell has one bar with a clock and a battery, a tray that repeats, and a popup. The TDL form follows the maintainer's answers of 2026-10-29. Keys come from [[Shell File]]; the module calls (`Label`, `Icon`) follow [[ADR-0007 Shell UI Layer#Module Call, Shipped Modules and Path (2026-10-26)]]. All three are illustrations, not grammar.

## What Each File Must Say

- A version, a file type, one monitor's root.
- A top bar: anchored top, left and right; 32 px high; reserves 32 px; four-sided margin; a style with a colour, a border colour with alpha, a radius and an opacity.
- A battery label that shows only when a battery exists, with a Battery icon as the other branch.
- A tray: one icon per item of a list, each with a stable identity.
- A popup that a click opens.
- A comment on at least one line.

## YAML

```yaml
shell: v1
type: Shell

# One monitor's tree
root:
    name: dp1_root
    monitor: DP-1
    children:
        top_bar:
            kind: bar
            layer: top
            anchor: [top, left, right]
            size: [0, 32]
            exclusive_zone: 32
            margin: [4, 4, 0, 4]            # top, right, bottom, left
            style:
                background: "#1e1e2ee6"
                border_color: "rgba(255, 255, 255, 0.1)"
                radius: 8
                opacity: 0.9
            children:
                - Label:
                    text: "{{ clock.time }}"
                - if: "{{ battery.present }}"
                  then:
                      - Label:
                          text: "Battery {{ battery.percent }}%"
                  else:
                      - Icon:
                          svg: battery-missing
                - for: item
                  in: "{{ tray.items }}"
                  key: "{{ item.id }}"
                  do:
                      - Icon:
                          svg: "{{ item.icon }}"
        tray_menu:
            kind: popup
            anchor_to: top_bar
            children:
                - Label:
                    text: "{{ caller.data.title }}"
```

- A value that starts with `{{` must be quoted, or YAML reads it as a flow mapping ([[ADR-0008 Tesserae Expression Language]], TEL notes on templates).
- A `children` that holds an `if` and a `for` has to be a list, so every entry gets a dash and an extra indent level. Mapping keys cannot repeat, which is why repeated modules need the list form too ([[ADR-0007 Shell UI Layer#Open Items]]).
- The sides of the margin are positional (`[4, 4, 0, 4]`); the brace form `{4, 4, 0, 4}` fails (PyYAML read it as `{4: None}` on 2026-10-26).

## TDL

```
TDL: v1
shell: v1
type: Shell

# One monitor's tree
root dp1_root {
    monitor: DP-1
    children {
        top_bar {
            kind: bar
            layer: top
            anchor: [top, left, right]
            size: [0, 32]
            exclusive_zone: 32
            margin: [4, 4, 0, 4]            # top, right, bottom, left
            style {
                background: "#1e1e2ee6"
                border_color: rgba(255 255 255 0.1)
                radius: 8
                opacity: 0.9
            }
            children {
                Label { text: {{ clock.time }} }

                if {{ battery.present }} {
                    Label { text: Battery {{ battery.percent }}% }
                } else {
                    Icon { svg: battery-missing }
                }

                for item in {{ tray.items }} key {{ item.id }} {
                    Icon { svg: {{ item.icon }} }
                }
            }
        }
        tray_menu {
            kind: popup
            anchor_to: top_bar
            children {
                Label { text: {{ caller.data.title }} }
            }
        }
    }
}
```

- `{{ }}` needs no quotes. A value that is exactly one slot keeps its type; text with a slot in it is a string ([[ADR-0008 Tesserae Expression Language]] and the TEL project's `docs/language.md`, section 8).
- A block is a name and braces. A property is `key: value`. Entries sit on their own lines or are separated by `,`.
- `children` holds an `if` and a `for` among module calls without turning into a list.

## KDL 2

```
shell v1
type Shell

// One monitor's tree
root dp1_root monitor=DP-1 {
    children {
        top_bar kind=bar layer=top {
            anchor top left right
            size 0 32
            exclusive_zone 32
            margin 4 4 0 4                  // top, right, bottom, left
            style {
                background "#1e1e2ee6"
                border_color "rgba(255, 255, 255, 0.1)"
                radius 8
                opacity 0.9
            }
            children {
                Label text="{{ clock.time }}"

                if "{{ battery.present }}" {
                    Label text="Battery {{ battery.percent }}%"
                }
                else {
                    Icon svg=battery-missing
                }

                for item "{{ tray.items }}" key="{{ item.id }}" {
                    Icon svg="{{ item.icon }}"
                }
            }
        }
        tray_menu kind=popup anchor_to=top_bar {
            children {
                Label text="{{ caller.data.title }}"
            }
        }
    }
}
```

- Checked against the [KDL 2.0.0 spec](https://kdl.dev/spec/) (read 2026-10-29): bare words are valid strings, `//` starts a comment, repeated node names are allowed, and a node takes arguments, `key=value` properties and a `{ }` block. `(` and `)` are type annotations, so a bare `rgba(255, 255, 255, 0.1)` is not valid and the colour is a quoted string.
- Repeated nodes mean `children` needs no list form. `else` is a sibling node, so nothing ties it to its `if` except order. `#` is not a comment character, and `#true` is a boolean.
- KDL cannot carry a bare `rgba(...)`, a bare slot, or the maintainer's chosen separators; its syntax is fixed by the specification.

## Side by Side

| Point                                                    | YAML                                                         | TDL                                                                   | KDL 2                                                  |
|----------------------------------------------------------|--------------------------------------------------------------|-----------------------------------------------------------------------|--------------------------------------------------------|
| Nesting is explicit                                      | No: indentation                                              | Yes: braces                                                           | Yes: braces                                            |
| Expression slot costs quotes                             | Yes, when it starts with `{{`                                | No                                                                    | Yes, always a quoted string                            |
| Conditions and repeats among module calls                | List form, extra indent, keys `then`, `else`, `do`           | Keyword blocks, no list form                                          | Keyword nodes, no list form                            |
| Repeated module of one name in one container             | List form                                                    | Allowed, ordered by position ([[ADR-0014 Shell File Language#What TDL Is (Decided)]]) | Natural (nodes repeat)                                 |
| Colour with alpha                                        | Quoted string                                                | `rgba(...)` bare, or a quoted hex                                     | Quoted string                                          |
| Comment                                                  | `#`                                                          | `#` (so a hex colour must be quoted)                                  | `//` and `/-`                                          |
| Four-sided values                                        | List; brace form fails                                       | List now; a brace form can be defined                                 | Several arguments (`margin 4 4 0 4`)                   |
| File looks like a Tesserae or YAML file                  | Yes, unless the version key is checked                       | No: its own extension and a `TDL:` first line                         | No, with its own extension                             |
| Parser and error positions                               | Third-party, in use by the vault                             | Ours to build and test                                                | Third-party; Python package not checked                |
| Editor help (completion, hover) today                    | YAML language server and JSON Schema ([[ADR-0011 JSON Schema for Shell Files]]) | None in v1 (maintainer, 2026-10-29)                    | None for our keys                                      |
| Round trip for the UID write                             | Needs a comment-keeping YAML writer                          | Our parser keeps a lossless tree                                      | Parser dependent; not checked                          |
| New work                                                 | None                                                         | Grammar, parser, formatter, docs                                      | Parser dependency, schema                              |

## What the TDL Sketch Shows to Settle

These are problems the first sketch surfaced, not criticism of the choice. The maintainer answered them on 2026-10-29 ([[ADR-0014 Shell File Language#Open Items]]); the answer is after each point.

1. `rgba(255, 255, 255, 0.1)` has commas inside parentheses, but `,` is also a separator. Answer: write `rgba(255 255 255 0.1)`, space separated.
2. `#` starts a comment, so `#1e1e2ee6` has to be quoted but `rgba(...)` does not. Two forms for colours. Answer: keep the quotes on hex.
3. `text: Battery {{ battery.percent }}%` is an unquoted string with spaces. A comma in such text would split it. Open: where an unquoted value ends.
4. `}} {` in `if {{ x }} {` reads as two closers and an opener. It parses, but is easy to misread. Answer: `}}` is only ever a slot end, and nested blocks close as `} }`.
5. `{{` always opens a slot. A block directly inside a block needs a space (`{ {`). Answer: confirmed.
6. `opacity: 0.9` is a plain number while `size: [0.5, 32]` would be a fraction of the parent. Answer: a percentage is `50%`, and a float is only for values that are not lengths.

## Result

The comparison supports the maintainer's choice on two points: the slot needs no quotes in TDL, and conditions and repeats read as structure instead of a list of one-key mappings. It does not remove the cost listed in [[Risk Register]] R-20. KDL is the closest ready-made option; its fixed syntax would leave `rgba(...)`, bare slots and the chosen separators out of reach.

## Links

- [[ADR-0014 Shell File Language]] · [[ADR-0007 Shell UI Layer]] · [[Shell File]] · [[Expression Language Requirements]] · [[90 Research]]

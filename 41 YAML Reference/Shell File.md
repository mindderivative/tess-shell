---
title: Shell File
aliases: [_Shell.yaml, Main_Shell.yaml, Shell YAML, _Shell.tdl, Main_Shell.tdl, Shell TDL]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-29
tags: [yaml-ref, spec/surface, needs-verification]
related: ["[[41 YAML Reference]]", "[[Common Keys and Conventions]]", "[[Surface Types]]", "[[Module File]]"]
depends_on: ["[[Common Keys and Conventions]]", "[[Surface Types]]"]
---

# Shell File

> [!summary]
> A shell file (`type: Shell`, suffix `_Shell.tdl`, written in TDL, [[ADR-0014 Shell File Language]]) defines the surfaces on one monitor and places modules in them. The whole shell is one such file, or a `Main_Shell.tdl` that imports others. This note lists the keys. **Decided** keys come from [[ADR-0007 Shell UI Layer]]; the surface property names mirror tre's `LayerWindow` settings ([[TRE-REQ-001 Layer Surface Window]]) and were accepted by the maintainer on 2026-10-29. Examples are illustrations.

## Structure

```
TDL: v1
shell: v1
type: Shell

root dp1_root {
    monitor: DP-1
    children {
        # one file, or a list
        import: TopBar_Shell.tdl
        top_bar {
            kind: bar
            style: Dock_Style.tdl
            # modules and containers go under children; the syntax of a module use is pending
            children {
                import: [Clock_Module.tdl, Audio_Module.tdl]
            }
        }
        launcher {
            kind: panel
            layer: overlay
            keyboard: exclusive
            children {
                import: Applications_Module.tdl
            }
        }
    }
}
```

- `root` holds one monitor's tree. Its name is required and is the word before the brace (`root dp1_root { }`, the form of the ADR-0014 sketch); `monitor` binds it to a monitor; `children` is a block.
- A child is a surface, a block named by its own unique name. `import:` inside `children` pulls in surfaces from another `_Shell.tdl`; an imported file takes the importing root's monitor.
- Surfaces are siblings and never nest ([[Common Keys and Conventions#Names and references]]).

## Root Keys

| Key        | Meaning                                                                                                                                                    | Status                                 |
|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------|
| `name`     | Required; unique across the shell (full path for repeated uses, see [[ADR-0007 Shell UI Layer#Open items]])                                               | Decided (the rule); path form proposed |
| `monitor`  | A connector name (`DP-1`); falls back to the display description; `default` applies to every monitor no other root names; absent means the root is ignored | Decided                                |
| `children` | Surfaces and imports                                                                                                                                       | Decided                                |

## Surface Keys

| Key              | Meaning                                                                                                                                                                                                                                                      | Applies to        | Status                                                  |
|------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|---------------------------------------------------------|
| `kind`           | `bar`, `frame`, `panel`, `popup`                                                                                                                                                                                                                             | All               | Decided                                                 |
| `layer`          | `background`, `bottom`, `top`, `overlay`                                                                                                                                                                                                                     | All               | Decided (the key)                                       |
| `style`          | A style file or an inline `style { }` block                                                                                                                                                                                                                            | All               | Decided                                                 |
| `children`       | The surface's contents: blocks (containers included) and module uses. `children` is the only holder; `modules:` is gone (maintainer, 2026-10-26). The syntax of a module use waits for the widget/module decision ([[Shell Structure#Blocks and modules (decided 2026-10-26)]]) | All               | Decided (the key)                                       |
| `anchor`         | Edges to attach to: `top`, `bottom`, `left`, `right` (one or a list)                                                                                                                                                                                         | bar, panel        | Decided (key name accepted 2026-10-29)                 |
| `size`           | `[width, height]`; `0` stretches between two anchored edges                                                                                                                                                                                                  | bar, panel, popup | Decided (key name accepted 2026-10-29)                 |
| `exclusive_zone` | Space reserved along the anchored edge, in pixels. Only allowed on `layer: top`; on any other layer it is a load error (maintainer, 2026-10-26)                                                                                                              | bar, panel, frame | Rule decided; key accepted 2026-10-29                  |
| `margin`         | Four-sided offset from the anchored edges                                                                                                                                                                                                                    | bar, panel        | Decided (key name accepted 2026-10-29)                 |
| `keyboard`       | `none`, `on_demand`, `exclusive`                                                                                                                                                                                                                             | All               | Decided (key name accepted 2026-10-29) (`exclusive` used for the launcher) |
| `input_region`   | Where input lands: the whole surface, nothing, rectangles, or `auto`                                                                                                                                                                                         | All               | Decided (key name accepted 2026-10-29)                 |
| `movable`        | A Panel the mouse can move; its position is saved                                                                                                                                                                                                            | panel             | Decided (key name accepted 2026-10-29)                 |
| `hidden`         | Start hidden                                                                                                                                                                                                                                                 | All               | Decided (key name accepted 2026-10-29)                 |
| `attach_to`      | The name of the surface a Panel attaches to                                                                                                                                                                                                                  | panel             | Decided (key name accepted 2026-10-29) (decided: attachment is by naming the surface) |
| `anchor_to`      | The name of the surface a Popup hangs off; optional, because the caller's surface is the parent ([[Popup#Parent and anchor]])                                                                                                                    | popup             | Decided (key name accepted 2026-10-29)                 |

Names follow tre's so the shell maps them directly. Per-kind keys (a Frame's side thicknesses and corner shapes, a Bar's span, a Popup's gravity) are listed in the per-kind specs once written ([[Surface Types]]).

## Monitors

- One root per monitor. A monitor no root names gets the `monitor: default` root if there is one, and nothing otherwise.
- A surface set for one monitor can be shared by several roots by importing the same `_Shell.tdl`.
- A Popup opens only on the monitor of the surface that called it ([[Surface Types#Open questions]]).

## Errors Specific to Shell Files

- A root with no `name`, or two with the same name on one monitor: error, both places named.
- A `kind:` that is not one of the four: error with the list.
- A module use whose file is not found: error with the search paths tried.
- An `attach_to` or `anchor_to` that never resolves: error at load; a target that disappears while running: warning, the surface stays hidden.
- A module with no matching `.py`: error naming both files.

## Open

- [ ] Several `root` blocks in one file, or one file per monitor (the Label example used two files).
- [x] Where shell files live: `$HOME/.config/tesserae-shell/Shells/`, or the directory `settings.tdl` names (decided 2026-10-27, [[Settings File]]).
- [ ] Which shell file is the top-level one when `Shells/` holds several: proposed `main_shell` in `settings.tdl`, default `Main_Shell.tdl`.
- [x] The names of the surface keys: accepted by the maintainer on 2026-10-29. Their types follow the per-kind specs.
- [ ] How a surface lays out its modules (order, spacing, alignment): a surface layout key, or the surface being a container widget.
- [ ] The keys each kind adds ([[Surface Types]]).
- [ ] Whether a root's name is only the word before the brace (`root dp1_root { }`) or also a `name:` key; the Root Keys table keeps `name` as the meaning.

## Links

- [[41 YAML Reference]] · [[Common Keys and Conventions]] · [[Module File]] · [[Surface Types]]

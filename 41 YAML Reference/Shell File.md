---
title: Shell File
aliases: [_Shell.yaml, Main_Shell.yaml, Shell YAML]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [yaml-ref, spec/surface, needs-verification]
related: ["[[41 YAML Reference]]", "[[Common Keys and Conventions]]", "[[Surface Types]]", "[[Module File]]"]
depends_on: ["[[Common Keys and Conventions]]", "[[Surface Types]]"]
---

# Shell file

> [!summary]
> A shell file (`type: Shell`, suffix `_Shell.yaml`) defines the surfaces on one monitor and places modules in them. The whole shell is one such file, or a `Main_Shell.yaml` that imports others. This note lists the keys. **Decided** keys come from [[ADR-0007 Shell UI Layer]]; the surface property names marked **proposed** mirror tre's `LayerWindow` settings ([[TRE-REQ-001 Layer Surface Window]]) and are not yet agreed. Examples are illustrations.

## Structure

```yaml
shell: v1
type: Shell

root:
    name: dp1_root
    monitor: DP-1
    children:
        import: TopBar_Shell.yaml            # one file, or a list
        top_bar:
            kind: bar
            style: Dock_Style.yaml
            children:                            # modules and containers go under children; the syntax of a module use is pending
                clock: Clock_Module.yaml
                audio: Audio_Module.yaml
        launcher:
            kind: panel
            layer: overlay
            keyboard: exclusive
            children:
                apps: Applications_Module.yaml
```

- `root` holds one monitor's tree. Its `name` is required; `monitor` binds it to a monitor; `children` is a mapping.
- A child is a surface, keyed by its own unique name. `import:` inside `children:` pulls in surfaces from another `_Shell.yaml`; an imported file takes the importing root's monitor.
- Surfaces are siblings and never nest ([[Common Keys and Conventions#Names and references]]).

## Root keys

| Key | Meaning | Status |
|---|---|---|
| `name` | Required; unique across the shell (full path for repeated uses, see [[ADR-0007 Shell UI Layer#Open items]]) | Decided (the rule); path form proposed |
| `monitor` | A connector name (`DP-1`); falls back to the display description; `default` applies to every monitor no other root names; absent means the root is ignored | Decided |
| `children` | Surfaces and imports | Decided |

## Surface keys

| Key | Meaning | Applies to | Status |
|---|---|---|---|
| `kind` | `bar`, `frame`, `panel`, `popup` | All | Decided |
| `layer` | `background`, `bottom`, `top`, `overlay` | All | Decided (the key) |
| `style` | A style file or an inline mapping | All | Decided |
| `children` | The surface's contents: containers and module uses. `children:` is the only holder; `modules:` is gone (maintainer, 2026-10-26). The syntax of a module use waits for the widget/module decision ([[Shell Structure#Widgets, modules and building blocks]]) | All | Decided (the key) |
| `anchor` | Edges to attach to: `top`, `bottom`, `left`, `right` (one or a list) | bar, panel | Proposed |
| `size` | `[width, height]`; `0` stretches between two anchored edges | bar, panel, popup | Proposed |
| `exclusive_zone` | Space reserved along the anchored edge, in pixels. Only allowed on `layer: top`; on any other layer it is a load error (maintainer, 2026-10-26; error handling proposed) | bar, panel, frame | Rule decided; key name proposed |
| `margin` | Four-sided offset from the anchored edges | bar, panel | Proposed |
| `keyboard` | `none`, `on_demand`, `exclusive` | All | Proposed (`exclusive` used for the launcher) |
| `input_region` | Where input lands: the whole surface, nothing, rectangles, or `auto` | All | Proposed |
| `movable` | A Panel the mouse can move; its position is saved | panel | Proposed |
| `hidden` | Start hidden | All | Proposed |
| `attach_to` | The name of the surface a Panel attaches to | panel | Proposed (decided: attachment is by naming the surface) |
| `anchor_to` | The name of the surface a Popup hangs off | popup | Proposed |

Names follow tre's so the shell maps them directly. Per-kind keys (a Frame's side thicknesses and corner shapes, a Bar's span, a Popup's gravity) are listed in the per-kind specs once written ([[Surface Types]]).

## Monitors

- One root per monitor. A monitor no root names gets the `monitor: default` root if there is one, and nothing otherwise.
- A surface set for one monitor can be shared by several roots by importing the same `_Shell.yaml`.
- A Popup opens only on the monitor of the surface that called it ([[Surface Types#Open questions]]).

## Errors specific to shell files

- A root with no `name`, or two with the same name on one monitor: error, both places named.
- A `kind:` that is not one of the four: error with the list.
- A module use whose file is not found: error with the search paths tried.
- An `attach_to` or `anchor_to` that never resolves: error at load; a target that disappears while running: warning, the surface stays hidden.
- A module with no matching `.py`: error naming both files.

## Open

- [ ] Several `root:` blocks in one file, or one file per monitor (the Label example used two files).
- [ ] How the shell finds top-level shell files in the config directory and the `look-at` paths.
- [ ] The final names and types of the surface keys marked proposed.
- [ ] How a surface lays out its modules (order, spacing, alignment): a surface layout key, or the surface being a container widget.
- [ ] The keys each kind adds ([[Surface Types]]).

## Links

- [[41 YAML Reference]] · [[Common Keys and Conventions]] · [[Module File]] · [[Surface Types]]

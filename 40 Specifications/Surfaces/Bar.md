---
title: Bar
aliases: [Bar Surface, kind bar, Dock, Top Bar, Side Bar]
type: spec
status: review
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [spec/surface, needs-verification]
related: ["[[Surfaces]]", "[[Surface Types]]", "[[Panel]]", "[[Frame]]", "[[Shell File]]", "[[TRE-REQ-001 Layer Surface Window]]"]
depends_on: ["[[Surface Types]]", "[[TRE-REQ-001 Layer Surface Window]]"]
---

# Bar

> [!summary]
> The Bar (`kind: bar`) is a surface attached to one screen edge that reserves space, so maximised windows stop short of it. It can span the whole edge, touching three edges (its own and the two across it), or be shorter and sit at a position along the edge. A dock, a top bar and a side bar are all Bars. A Bar can have margins and then looks as if it floats, but it is still attached to its edge: the margin space is reserved, so it behaves as if the Bar were flush (maintainer, 2026-10-27). A surface that is not attached to an edge and reserves nothing is a Panel. It is highly customisable: size, position, margins, animation, hidden state, background, borders, rounded corners, shadows with elevation and colour, and transparency. A Bar is a tre `LayerWindow` anchored to an edge. The decisions are the maintainer's ([[Surface Types]]); the key names were accepted by the maintainer on 2026-10-29 (many mirror tre's settings). YAML is illustration.

## Purpose and Scope

- The v1 uses: the top bar with the clock, workspaces, tray and system modules; a dock; a side bar ([[V1 Scope#Surfaces]]).
- Not in this note: what a Bar contains (blocks, containers and modules, [[Building Blocks]]), the Panel that slides out of a Bar ([[Panel]]), and the Frame ([[Frame]]).

## Behaviour

### Geometry

| Shape                              | tre settings                                                                                                                        | Example                                                                                                                   |
|------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| Full-span bar on one edge          | `anchor` the edge and both perpendicular edges; `size` 0 along the edge and the thickness across it; `exclusive_zone` the thickness | A top bar across the screen: anchor top, left, right; size (0, 32); zone 32                                               |
| A shorter bar, centred on its edge | `anchor` the edge only; `size` the length and the thickness                                                                         | A dock: anchor bottom; size (560, 64); zone 64. With one edge anchored the compositor centres it along that edge          |
| A shorter bar at a corner end      | `anchor` the edge and one perpendicular edge; `margin` along the edge                                                               | A top bar starting 200 px in: anchor top, left; margin left 200                                                           |
| A bar that looks floating          | The same, with a `margin` on its own edge                                                                                           | A top bar 8 px below the top: margin top 8; **the zone must include the margin**. It is still a Bar: the 8 px is reserved |

- A positive `exclusive_zone` counts only for a surface anchored to one edge, or one edge plus both perpendicular edges; with any other anchor set the compositor treats it as 0, and a `warning` event says so ([[TRE-REQ-001 Layer Surface Window#Shell need]]).
- **A margin is part of the Bar (decided 2026-10-27).** A Bar with a margin looks as if it floats but stays attached to its edge, and the margin space is reserved, so windows stop where they would for a flush Bar. The protocol says the exclusive zone includes the margin: "The exclusive zone includes the margin" ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1), read 2026-10-27). So a Bar with a margin of 8 and a thickness of 32 sets a zone of 40, or windows would overlap its gap. The shell computes the zone from `thickness` and `margin`. A Panel differs: it is not attached to an edge and does not have to reserve anything. #needs-verification on KWin 6.8.1.
- **Layers and reserving space.** A Bar may use `bottom`, `top` or `overlay`. It may reserve space only on `top`; an `exclusive_zone` on another layer is a load error ([[Surface Types#Layers per kind]]). A Bar on `bottom` or `overlay` is therefore not reserving and is for effects (a decorative strip, a launcher dock that floats over windows).
- **Corner anchors.** A bar anchored to an edge and one perpendicular edge reserves nothing unless `exclusive_edge` names the edge; tre binds layer-shell version 5 for this ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]). KWin 6.8.1 and sway were tested for corner reservation.

### States

A Bar is `Hidden`, `Showing`, `Visible`, `Hiding` or `Closed`, as a Panel is ([[Panel#States]]). Moving is not offered: a Bar is anchored, and a movable surface is a Panel.

### Auto-hide (Decided 2026-10-27)

- **On by default; the user opts out** with `auto_hide: false`.
- **A reasonable default delay,** which the user can change (`auto_hide_delay`, milliseconds). Proposed default: 1000 ms after the pointer leaves the Bar, tuned in testing.
- **Keyboard reveal: none by default.** The user can set a key (`reveal_key`, a global shortcut through the KDE global-accel service, [[ADR-0005 Global Shortcuts]]). A Bar that hides itself and has no reveal key is still reachable by pointer through the hover strip.
- The slide follows the pattern in the tre request ([[TRE-REQ-001 Layer Surface Window#Shell patterns]]):
  - Hide: slide the bar out by animating a margin (a negative margin slides it past the edge; tre accepts negative margins on KWin), then set `exclusive_zone` to 0 when the slide ends.
  - Show: set the zone first, then slide in. Windows reflow once, not on every frame.
  - A hover-to-reveal strip keeps a thin input area at the edge while the bar is hidden.

### Vertical Bars (Decided 2026-10-27)

A Bar on a left or right edge lays its contents out as a `FlexBox` with a vertical direction. Text is not rotated by default; the user opts in (`text_rotation`, proposed key and values). The standard modules follow the Bar's direction.

### Contents

A Bar holds modules, containers and blocks under `children:` ([[Common Keys and Conventions]]). The usual layout is a `FlexBox` with left, centre and right groups pushed apart by Spacer modules.

### Multi-monitor

A Bar belongs to a root, and so to one monitor ([[Shell File]]). A Bar defined once and imported by several roots appears on each. Each Bar reserves space on its own output only.

## Configuration

| Key                 | Meaning                                                                                                                                           | Status                                                                       |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| `kind: bar`         | The kind                                                                                                                                          | Decided                                                                      |
| `layer`             | `bottom`, `top` or `overlay`                                                                                                                      | Decided                                                                      |
| `children`          | Blocks, containers and modules                                                                                                                    | Decided                                                                      |
| `style`             | A style file or inline values                                                                                                                     | Decided                                                                      |
| `edge`              | `left`, `right`, `top` or `bottom`: the edge it attaches to                                                                                       | Decided (maintainer, 2026-10-27)                                             |
| `span`              | `absolute` (a fixed length), `expanded` (stretches along the whole edge, touching three edges) or `auto` (sized to its content)                   | Decided (the three values); how an absolute length is given is open          |
| `length`            | The fixed length for `span: absolute`                                                                                                             | Decided (key name accepted 2026-10-29)                                      |
| `align`             | Where a shorter bar sits along the edge: `start`, `center`, `end`, or an offset                                                                   | Decided (key name accepted 2026-10-29)                                      |
| `thickness`         | The size across the edge                                                                                                                          | Decided (maintainer, 2026-10-27)                                             |
| `margin`            | Four-sided gap, clockwise from the top; the reserved zone includes it                                                                             | Decided (key name accepted 2026-10-29); order decided; margins kept (maintainer, 2026-10-27) |
| `reserve`           | Reserve space: on or off. The shell computes `exclusive_zone` (thickness plus the margin on that edge)                                            | Decided (key name accepted 2026-10-29); rule decided (only on `top`)        |
| `exclusive_zone`    | The raw tre value, for an exact figure                                                                                                            | Rule decided; key accepted 2026-10-29                                       |
| `anchor`, `size`    | The raw tre forms; `edge`, `span`, `length` and `thickness` map to them                                                                           | Decided (key name accepted 2026-10-29)                                      |
| `keyboard`          | `none`, `on_demand` or `exclusive`                                                                                                                | Decided (key name accepted 2026-10-29)                                      |
| `input_region`      | Whole, nothing, rectangles or `auto`                                                                                                              | Decided (key name accepted 2026-10-29)                                      |
| `attach_to`, `meld` | With `attach_to` a Frame: draw the Bar inside the Frame's surface, so it grows out of the frame; a thicker Frame edge (a strip) does the same job | Decided (key name accepted 2026-10-29); the mechanism is decided ([[Frame#Hosted melding (decided 2026-10-27)]]) |
| `hidden`            | Start hidden                                                                                                                                      | Decided (key name accepted 2026-10-29)                                      |
| `auto_hide`         | Slide out after the delay when the pointer leaves; default true                                                                                   | Decided (on by default, opt-out, 2026-10-27)                                 |
| `auto_hide_delay`   | The delay in milliseconds                                                                                                                         | Decided that it exists; default 1000 ms proposed                             |
| `reveal_key`        | A keyboard shortcut that reveals the Bar; default none                                                                                            | Decided (default none, 2026-10-27); key accepted 2026-10-29                 |
| `text_rotation`     | Rotate text on a vertical Bar; default off                                                                                                        | Decided (opt-in, 2026-10-27); key accepted 2026-10-29                       |
| `animation`         | Slide or fade, with a duration                                                                                                                    | Decided (key name accepted 2026-10-29)                                      |

```yaml
children:
    top_bar:
        kind: bar
        layer: top
        edge: top
        span: expanded
        thickness: 32
        reserve: true
        style: TopBar_Style.yaml
        children:
            - FlexBox:
                alignment: horizontal
                children:
                    - Workspaces:
                    - Spacer:
                    - Clock:
                    - Spacer:
                    - Tray:
    dock:
        kind: bar
        layer: top
        edge: bottom
        span: absolute
        length: 560
        thickness: 64
        margin: [0, 0, 8, 0]
        reserve: true
        children:
            - Tasks:
```

An illustration only. The module names (Workspaces, Tray, Tasks) are v1 modules whose specs are not written; `length` and `reserve` are proposals.

## Python Contract

A Bar has no Python of its own. Modules in it receive `use` records with the Bar's monitor ([[Module Context#Uses]]). A module can show or hide the Bar through shell actions, as for a Panel ([[Panel#Python contract]]).

## Integration

- tre: a `LayerWindow` with `layer`, `anchor`, `size`, `exclusive_zone`, `exclusive_edge`, `margin`, `keyboard`, `input_region` (live through `set()` in one commit), margin animation, and `output` bound to the monitor ([[TRE-REQ-001 Layer Surface Window]]). A change to `output` or `namespace` means reopening the window.
- Threads: window operations on the loop thread ([[Process Model and Threading]]).
- **Coexistence with the Plasma panel.** plasmashell's panel reserves space too. Decided 2026-10-27: the Bar wins over a Plasma panel unless that panel is set to always on top, or a window is fullscreen ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]); this is about fullscreen, not maximised. On the same edge the compositor stacks the zones in an order the shell does not control, so how the Bar wins is #needs-verification; different edges or monitors avoid it. The maintainer's Edge Shell design used a per-monitor mode (shell, Plasma, both, none).
- Memory: about 18 MiB for a 1280 x 32 bar on tre 0.5.8; one surface per bar per monitor ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]).

## Design

- The look is a style file, stylesheet or inline `style:` over the root container: background, border, corner radius, shadow, opacity ([[Style, Theme and Stylesheet Files#Rules]]).
- A Bar matches the rest of the shell's surface elements (decided 2026-10-27): the same tokens, the same style keys and the same corner, border and shadow rules as a Panel and the Frame ([[Style Schema]]); a Bar has no look of its own.
- Shadows: a surface cannot draw outside its own bounds. A Bar with a shadow is a larger transparent surface; the zone covers the body only and `input_region` follows the body ([[ADR-0010 Surface Shadows]], decided 2026-10-27).
- Rounded corners on a full-span bar are drawn with the container's corner radius; a bar that melds into the Frame uses Path blocks ([[Frame#Melding]]).

## Accessibility

- tre publishes the Bar as one window of the application; the bar's window node has no accessible name yet, so the shell sets the surface name ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]).
- Every module in it is keyboard-reachable. A hidden or auto-hidden Bar needs a keyboard way to reveal it (a global shortcut or a shell action).
- Reduced motion: show and hide are instant ([[Goals and Non-Goals]] G7).
- Auto-hide is on and the keyboard reveal is off by default (maintainer, 2026-10-27), so a keyboard-only user has no way to reveal the Bar until they set `reveal_key`. Open: whether the shell warns at first start, or reveals the Bar when it takes keyboard focus ([[#Auto-hide (decided 2026-10-27)]]).

## Performance Budget

- A Bar draws no frames at idle and wakes the loop only for its modules' timers.
- Sliding is margin animation: one small commit per step, no buffer change; the zone changes once, at the start or the end, not per frame.
- Budgets are set in `60 Quality/`.

## Failure Modes and Recovery

| Failure                                                   | Result                                                                                     |
|-----------------------------------------------------------|--------------------------------------------------------------------------------------------|
| `exclusive_zone` on a layer other than `top`              | Error at load naming the file, the Bar and the key                                         |
| A size of 0 on an axis without both opposite anchors      | Error before any request to the compositor                                                 |
| The zone does not include the margin                      | Windows overlap the gap; the shell computes the zone from thickness and margin to avoid it |
| A corner-anchored Bar with a zone and no `exclusive_edge` | Reserves nothing; a `warning` event says so                                                |
| The monitor is removed                                    | The Bar closes (`output_removed`); recreated when the monitor returns                      |
| Two reserving surfaces on one edge                        | The compositor decides the order                                                           |

## Open Questions

- [x] The keys `edge`, `span` (`absolute`, `expanded`, `auto`) and `thickness` (maintainer, 2026-10-27). Open: the key for an absolute length (`length` proposed), `align`, `reserve`, and whether the raw `anchor` and `size` are also allowed.
- [x] Movable: no, a Bar is anchored and a movable surface is a Panel. Floating: a Bar with margins looks floating but stays attached and its margin space is reserved (maintainer, 2026-10-27).
- [x] Auto-hide: on by default with opt-out, a default delay the user can change, keyboard reveal none by default (maintainer, 2026-10-27). Open: the default delay value, the hover strip's thickness, and the reveal key's key name.
- [x] The Plasma panel on the same edge: the Bar wins, unless the Plasma panel is always on top or a window is fullscreen (maintainer, 2026-10-27). Open: how, and how KWin orders two zones on one edge. #needs-verification
- [x] A vertical Bar: a FlexBox with a vertical direction; text rotation is opt-in (maintainer, 2026-10-27). Open: the `text_rotation` values.
- [x] Shadow keys: `elevation`, `shadow` and `shadow_bleed` ([[Style Schema#Shadow keys]], accepted 2026-10-27).

## Acceptance Criteria

- [ ] A full-span top Bar with a zone of 32 makes a maximised window stop 32 px below the top edge on KWin.
- [ ] A dock with an 8 px gap and a thickness of 64 sets a zone of 72 and keeps maximised windows 72 px above the edge, the same as a flush Bar of that total size.
- [ ] A Bar on `bottom` or `overlay` with an `exclusive_zone` is a load error.
- [ ] A Bar on each of two monitors appears on both, and unplugging one removes only its Bar.
- [ ] Auto-hide is on with no key written; `auto_hide: false` keeps the Bar visible. The Bar slides out after the delay, then sets the zone to 0, and windows reflow once; the pointer at the edge brings it back.
- [ ] With `reveal_key` unset, no key reveals the Bar; with it set, the key does.
- [ ] A left or right Bar lays out vertically with unrotated text; `text_rotation` turns rotation on.
- [ ] A fullscreen window covers the Bar; a maximised window stops at it.
- [ ] An idle Bar draws no frames between module updates.

## Links

- [[Surfaces]] · [[Surface Types]] · [[Panel]] · [[Frame]] · [[Shell File]] · [[Building Blocks]]

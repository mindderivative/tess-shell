---
title: Bar
aliases: [Bar Surface, kind bar, Dock, Top Bar, Side Bar]
type: spec
status: review
owner: phil
created: 2026-10-27
updated: 2026-11-02
tags: [spec/surface, needs-verification]
---

# Bar

> [!NOTE]
> The Bar (the `Bar` block) is a surface attached to one screen edge that reserves space, so maximised windows stop short of it. It can span the whole edge, touching three edges (its own and the two across it), or be shorter and sit at a position along the edge. A dock, a top bar and a side bar are all Bars. A Bar can have a `Gap` to its edge and then looks as if it floats, but it is still attached to its edge: the gap space is reserved, so it behaves as if the Bar were flush (maintainer, 2026-10-27). A Bar has no `Margin`; its placement keys are `Edge`, `Width`, `Height`, `Alignment`, `Offset` and `Gap` (maintainer, 2026-10-30). A surface that is not attached to an edge and reserves nothing is a Panel. It is highly customisable: size, position, gap, animation, hidden state, background, borders, rounded corners, shadows with elevation and colour, and transparency. A Bar is a tre `LayerWindow` anchored to an edge. The decisions are the maintainer's ([Surface Types](Surface%20Types.md)); the key names were accepted by the maintainer on 2026-10-29 (many mirror tre's settings). The examples are TDL illustrations ([ADR-0014 Shell File Language](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)).

## Purpose and Scope

- The v1 uses: the top bar with the clock, workspaces, tray and system modules; a dock; a side bar ([V1 Scope > Surfaces](../../10%20Vision/V1%20Scope.md#surfaces)).
- Not in this note: what a Bar contains (blocks, containers and modules, [Building Blocks](../../50%20Design%20System/Building%20Blocks.md)), the Panel that slides out of a Bar ([Panel](Panel.md)), and the Frame ([Frame](Frame.md)).

## Behaviour

### Geometry

The Bar is placed with `Edge`, `Width`, `Height`, `Alignment`, `Offset` and `Gap` ([Shell File > Surface Keys](../../41%20TDL%20Reference/Shell%20File.md#surface-keys)). For a top or bottom Bar `Width` is the length along the edge and `Height` the size across it; for a left or right Bar `Width` is the size across the edge and `Height` the length along it.

| Shape                              | TDL keys (top Bar shown)                                       | tre settings it implies                                                                                                        |
|------------------------------------|----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| Full-span bar on one edge          | `Edge: TOP`, `Width: EXPAND`, `Height: 32`                     | `anchor` the edge and both perpendicular edges; `size` 0 along the edge and 32 across it; `exclusive_zone` 32                   |
| A shorter bar, centred on its edge | `Edge: BOTTOM`, `Width: 560`, `Height: 64`, `Alignment: CENTER` | `anchor` the edge only; `size` (560, 64); the compositor centres it along that edge                                            |
| A shorter bar at one end           | `Edge: TOP`, `Width: 400`, `Height: 32`, `Alignment: START`, `Offset: 200` | `anchor` the edge and one perpendicular edge; a `margin` along the edge for the offset                                         |
| A bar that looks floating          | `Edge: TOP`, `Width: EXPAND`, `Height: 32`, `Gap: 8`           | The same, with a `margin` on its own edge; the zone is 40. It is still a Bar: the 8 px is reserved                              |

The shell computes tre's `anchor`, `size`, `margin` and `exclusive_zone` from `Edge`, `Width`, `Height`, `Alignment`, `Offset` and `Gap`, the same way it computes a Panel's attachment geometry. The maintainer accepted the computation below on 2026-10-31 (D61).

#### Mapping to tre

Sources: the [layer-shell protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1) (`set_size`, `set_anchor`, `set_exclusive_zone`, `set_margin`, read 2026-10-31) and the [tre LayerWindow reference](https://mindderivative.github.io/tre/reference/layer-window/) (read 2026-10-31). tre takes `margin` as (top, right, bottom, left), whole pixels, negative allowed; `size` 0 on an axis stretches between two anchors on that axis and is otherwise a protocol error (`invalid_size`); `anchor`, `size`, `margin` and `exclusive_zone` are live through `set()`; a margin can be animated.

Terms. The along axis runs along the Edge (x for a top or bottom Bar, y for a left or right Bar), the across axis is the thickness. `L` is the resolved length along the Edge (`Width` for top and bottom, `Height` for left and right), `T` the resolved thickness across it, and `O` the output's logical size along the Edge (`Output.width` or `Output.height` from `App.outputs()`, in logical pixels). The start side is the left side of a top or bottom Bar and the top side of a left or right Bar. A positive `Offset` moves the Bar toward the end of the Edge.

| Step                | Rule                                                                                                                                                                                                                                       |
|---------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Resolve a size      | Pixels stay; `p%` is p/100 of the output's size on that axis; `AUTO` is the content's size on that axis; `EXPAND` along the Edge stretches (below); `EXPAND` across the Edge is `Max_`, else `Min_`, else 0. Then clamp to `Min_` and `Max_`. |
| Across size and zone | `size` across is `T`. The Gap goes on the Edge's own side: `margin` on that side is `Gap`. `exclusive_zone` is `T + Gap` (2026-10-27 rule above), only when `Layer` is `TOP` and `Reserve` is true.                                                |
| `EXPAND` along      | `anchor` is the Edge plus both perpendicular edges; `size` along is 0; no margin along. `Alignment` and `Offset` have no effect; the shell warns if either is set.                                                                      |
| `START`             | `anchor` is the Edge plus the start side; `margin` on the start side is `Offset`; `size` along is `L`; `exclusive_edge` is the Edge.                                                                                                   |
| `END`               | `anchor` is the Edge plus the end side; `margin` on the end side is `-Offset`; `size` along is `L`; `exclusive_edge` is the Edge.                                                                                                      |
| `CENTER`, no Offset | `anchor` is the Edge only; the compositor centres the Bar along it; `size` along is `L`. No `exclusive_edge` is needed.                                                                                                                  |
| `CENTER` with Offset | `anchor` is the Edge plus the start side; `margin` on the start side is `(O - L) / 2 + Offset`; `exclusive_edge` is the Edge. The shell recomputes it on `output_updated`.                                                                  |
| Zero size           | A resolved `T`, or an `L` that is not `EXPAND`, of 0 is not created (D46). This matches the protocol: a 0 on an axis without anchors on both opposite edges is `invalid_size`.                                                          |
| Hidden or peeking   | The window keeps its size. The shell animates the Edge-side margin to `-(T - peek)` (negative margins are accepted and were honoured on KWin, [TRE-REQ-001 Layer Surface Window](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md)) and sets `exclusive_zone` to 0 when the slide ends. A size of 0 never arises. |
| Recompute           | On any live key change, on `output_updated` (size, scale or rotation), and when an `AUTO` size's content changes. The shell sends one `set()` with the new `anchor`, `size`, `margin` and `exclusive_zone`.                              |

Worked examples on a 1920 px wide output (margin as top, right, bottom, left):

| TDL                                                                                   | `anchor`           | `size`      | `margin`        | `exclusive_zone`        |
|---------------------------------------------------------------------------------------|--------------------|-------------|-----------------|-------------------------|
| `Edge: TOP`, `Width: EXPAND`, `Height: 32`                                            | top, left, right   | (0, 32)     | (0, 0, 0, 0)    | 32                      |
| `Edge: TOP`, `Width: EXPAND`, `Height: 32`, `Gap: 8`                                  | top, left, right   | (0, 32)     | (8, 0, 0, 0)    | 40                      |
| `Edge: BOTTOM`, `Width: 560`, `Height: 64`, `Alignment: CENTER`                       | bottom             | (560, 64)   | (0, 0, 0, 0)    | 64 (only if `Layer` is `TOP`)   |
| `Edge: TOP`, `Width: 400`, `Height: 32`, `Alignment: START`, `Offset: 200`            | top, left          | (400, 32)   | (0, 0, 0, 200)  | 32, `exclusive_edge` top |
| `Edge: TOP`, `Width: 400`, `Height: 32`, `Alignment: END`, `Offset: 40`               | top, right         | (400, 32)   | (0, -40, 0, 0)  | 32, `exclusive_edge` top |

Still unverified (#needs-verification): the exact zone a compositor reserves for a margin (the protocol says the zone "includes the margin"; the 40 above is the 2026-10-27 reading) on KWin 6.8.1; whether margins on an axis with no anchor are ignored by the compositor (the reason `CENTER` with an Offset anchors to the start side instead); whether `Output.width` and `height` are already rotated for a rotated output; and whether tre offers a way to measure content for `AUTO` before the window exists.

- A positive `exclusive_zone` counts only for a surface anchored to one edge, or one edge plus both perpendicular edges; with any other anchor set the compositor treats it as 0, and a `warning` event says so ([TRE-REQ-001 Layer Surface Window > Shell need](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#shell-need)).
- A size is pixels, a percent, `AUTO` or `EXPAND` ([TDL Language > Sizes (Shell Schema)](../../41%20TDL%20Reference/TDL%20Language.md#sizes-shell-schema)). `AUTO` shrinks the Bar to its content on that axis. `Max_Width`, `Max_Height`, `Min_Width` and `Min_Height` bound the result.
- **The EXPAND rule.** `EXPAND` stretches the Bar edge to edge along its attached Edge. Across the Edge it cannot stretch, because the attached edge does not reach the opposite edge: a top Bar with `Height: EXPAND` resolves to `Max_Height`, else `Min_Height`, else 0 px (D34, D46).
- **The zero-size rule.** A Bar whose size resolves to 0 on the axis it is attached along (a top Bar with `Height: EXPAND` and no bound, or `Height: 0`) is not created. The shell warns, names the Bar and says to set `Min_Height` (`Min_Width` for a left or right Bar). The check runs at creation only; it never stops hide, peek, expand or contract of a Bar or of a Frame strip, which may reach a size of 0 while hidden or contracted ([Frame > Strip: Expand, Contract, Peek](Frame.md#strip-expand-contract-peek)).
- **The gap is part of the Bar (decided 2026-10-27).** A Bar with a `Gap` looks as if it floats but stays attached to its edge, and the gap space is reserved, so windows stop where they would for a flush Bar. The protocol says the exclusive zone includes the margin: "The exclusive zone includes the margin" ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1), read 2026-10-27). So a Bar with a `Gap` of 8 and a `Height` of 32 sets a zone of 40, or windows would overlap its gap. The shell computes the zone from the size across the Edge and the `Gap`. A Panel differs: it is not attached to an edge and does not have to reserve anything. #needs-verification on KWin 6.8.1.
- **Layers and reserving space.** A Bar may use `BOTTOM`, `TOP` or `OVERLAY`. It may reserve space only on `TOP`; an `Exclusive_Zone` on another layer is a load error ([Surface Types > Layers per kind](Surface%20Types.md#layers-per-kind)). A Bar on `BOTTOM` or `OVERLAY` is therefore not reserving and is for effects (a decorative strip, a launcher dock that floats over windows).
- **Corner anchors.** A bar anchored to an edge and one perpendicular edge reserves nothing unless `exclusive_edge` (tre's argument) names the edge; tre binds layer-shell version 5 for this ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)). KWin 6.8.1 and sway were tested for corner reservation.

### States

A Bar is `Hidden`, `Showing`, `Visible`, `Hiding` or `Closed`, as a Panel is ([Panel > States](Panel.md#states)); `Hidden` and `Visible` here are states, not keys; the `Visible` key chooses the state it starts in. Moving is not offered: a Bar is anchored, and a movable surface is a Panel.

### Auto-hide (Decided 2026-10-27)

- **On by default; the user opts out** with `Auto_Hide: false`.
- **A reasonable default delay,** which the user can change (`Auto_Hide_Delay`, milliseconds). Proposed default: 1000 ms after the pointer leaves the Bar, tuned in testing.
- **Keyboard reveal: none by default.** The user can set a key (`Reveal_Key`, a global shortcut through the KDE global-accel service, [ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md)). A Bar that hides itself and has no reveal key is still reachable by pointer through the hover strip.
- The slide follows the pattern in the tre request ([TRE-REQ-001 Layer Surface Window > Shell patterns](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#shell-patterns)):
  - Hide: slide the bar out by animating a margin (a negative margin slides it past the edge; tre accepts negative margins on KWin), then set `exclusive_zone` to 0 when the slide ends.
  - Show: set the zone first, then slide in. Windows reflow once, not on every frame.
  - A hover-to-reveal strip keeps a thin input area at the edge while the bar is hidden.

### Vertical Bars (Decided 2026-10-27)

A Bar on a left or right edge lays its contents out as a `FlexBox` with `Flex: VERTICAL`. Text is not rotated by default; the user opts in (`Text_Rotation`, proposed key and values). The standard modules follow the Bar's direction.

### Contents

A Bar holds modules, containers and blocks under `Children` ([Common Keys and Conventions](../../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md)). The usual layout is a `FlexBox` with left, centre and right groups pushed apart by Spacer modules.

### Multi-monitor

A Bar belongs to a `Monitor` block, and so to one monitor ([Shell File](../../41%20TDL%20Reference/Shell%20File.md)). A Bar defined once and imported by several `Monitor` blocks appears on each. Each Bar reserves space on its own output only.

## Configuration

| Key                                                  | Meaning                                                                                                                                                                                                                                                                                                          | Status                                                                                                           |
|------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| `Bar` (the head)                                     | The type; there is no `Kind:` key                                                                                                                                                                                                                                                                                | Decided                                                                                                          |
| `Layer`                                              | `BOTTOM`, `TOP` or `OVERLAY`                                                                                                                                                                                                                                                                                     | Decided                                                                                                          |
| `Children`                                           | Blocks, containers and modules                                                                                                                                                                                                                                                                                   | Decided                                                                                                          |
| `Style`                                              | A style file or inline values                                                                                                                                                                                                                                                                                    | Decided                                                                                                          |
| `Edge`                                               | `LEFT`, `RIGHT`, `TOP` or `BOTTOM`: the edge it attaches to                                                                                                                                                                                                                                                      | Decided (maintainer, 2026-10-27)                                                                                 |
| `Width`, `Height`                                    | Pixels, `50%`, `AUTO` (shrink to content on that axis) or `EXPAND` (stretch edge to edge along the Edge); the EXPAND rule and the zero-size rule are in Geometry                                                                                                                                                 | Decided (D34, D46; replaces `Span`, `Length` and `Thickness`)                                                    |
| `Max_Width`, `Max_Height`, `Min_Width`, `Min_Height` | Bounds on the size, in pixels                                                                                                                                                                                                                                                                                    | Decided (D34)                                                                                                    |
| `Alignment`                                          | Where a shorter Bar sits along the Edge: `START`, `CENTER`, `END`; default `CENTER`; no effect on an `EXPAND` axis (D55). The Panel and the Popup use the same name for the same idea, along the edge they share with their target ([Panel > Attachment Geometry (Decided 2026-10-27)](Panel.md#attachment-geometry-decided-2026-10-27))                          | Decided (2026-10-30; replaces `Align`)                                                                           |
| `Offset`                                             | One number that moves the Bar along the Edge; positive or negative                                                                                                                                                                                                                                               | Decided (D51)                                                                                                    |
| `Gap`                                                | One number: the space between the Edge and the Bar; the reserved zone includes it                                                                                                                                                                                                                                | Decided (D49); replaces the Bar `Margin`                                                                         |
| `Reserve`                                            | Reserve space: on or off. The shell computes `Exclusive_Zone` (the size across the Edge plus the `Gap`)                                                                                                                                                                                                          | Decided (key name accepted 2026-10-29); rule decided (only on `TOP`)                                             |
| `Exclusive_Zone`                                     | The raw tre value, for an exact figure                                                                                                                                                                                                                                                                           | Rule decided; key accepted 2026-10-29                                                                            |
| `Keyboard`                                           | `NONE`, `ON_DEMAND` or `EXCLUSIVE`                                                                                                                                                                                                                                                                               | Decided (key name accepted 2026-10-29)                                                                           |
| `Input_Region`                                       | Whole, nothing, rectangles or `auto`                                                                                                                                                                                                                                                                             | Decided (key name accepted 2026-10-29)                                                                           |
| `Attach_To`, `Meld`                                  | With `Attach_To` a Frame, a Bar melds when its `Gap` on the Frame-facing side is 0, and does not when the `Gap` is above 0; with no Frame there is no meld (D62). `Meld: true` draws a melded Bar inside the Frame's surface instead of in a window of its own; a thicker Frame edge (a strip) does the same job | Decided (key name accepted 2026-10-29); the mechanism is decided ([Frame > Hosted melding (decided 2026-10-27)](Frame.md#hosted-melding-decided-2026-10-27)) |
| `Visible`                                            | `true` (the default) starts the Bar shown; `false` starts it hidden. The opposite of the earlier `Hidden`                                                                                                                                                                                                        | Decided (key name accepted 2026-10-29; renamed from `Hidden`, 2026-11-02)                                        |
| `Auto_Hide`                                          | Slide out after the delay when the pointer leaves; default true                                                                                                                                                                                                                                                  | Decided (on by default, opt-out, 2026-10-27)                                                                     |
| `Auto_Hide_Delay`                                    | The delay in milliseconds                                                                                                                                                                                                                                                                                        | Decided that it exists; default 1000 ms proposed                                                                 |
| `Reveal_Key`                                         | A keyboard shortcut that reveals the Bar; default none                                                                                                                                                                                                                                                           | Decided (default none, 2026-10-27); key accepted 2026-10-29                                                      |
| `Text_Rotation`                                      | Rotate text on a vertical Bar; default off                                                                                                                                                                                                                                                                       | Decided (opt-in, 2026-10-27); key accepted 2026-10-29                                                            |
| `Animation`                                          | Slide or fade, with a duration                                                                                                                                                                                                                                                                                   | Decided (key name accepted 2026-10-29)                                                                           |

The Bar has no `Margin` and no raw `Anchor` or `Size`: the shell computes tre's `anchor`, `size` and `margin` from the placement keys (Geometry). `Padding` is allowed, as on every element that has `Children` ([Common Keys and Conventions](../../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md)).

```
Bar {
    Name: Top_Bar
    Layer: TOP
    Edge: TOP
    Width: EXPAND
    Height: 32
    Reserve: true
    Style: TopBar_Style.tdl
    Children {
        FlexBox {
            Name: Top_Bar_Row
            Flex: HORIZONTAL
            Children {
                Workspaces { }
                Spacer { }
                Clock { }
                Spacer { }
                Tray { }
            }
        }
    }
}

Bar {
    Name: Dock
    Layer: TOP
    Edge: BOTTOM
    Width: 560
    Height: 64
    Alignment: CENTER
    Gap: 8
    Reserve: true
    Children {
        Tasks { }
    }
}
```

An illustration only. The module names (Workspaces, Tray, Tasks) are v1 modules whose specs are not written; `Reserve` is a proposal. `Reserve: true` is a bare word that the parser keeps as a string and the key's declared type turns into a boolean ([ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30), D2), and a module use is written with the module's name as the head ([Module File > Using a Module](../../41%20TDL%20Reference/Module%20File.md#using-a-module)). The dock reserves 72 px: its height of 64 plus its `Gap` of 8.

## Python Contract

A Bar has no Python of its own. Modules in it receive `use` records with the Bar's monitor ([Module Context > Uses](../../42%20Python%20API/Module%20Context.md#uses)). A module can show or hide the Bar through shell actions, as for a Panel ([Panel > Python contract](Panel.md#python-contract)).

## Integration

- tre: a `LayerWindow` with `layer`, `anchor`, `size`, `exclusive_zone`, `exclusive_edge`, `margin`, `keyboard`, `input_region` (live through `set()` in one commit), margin animation, and `output` bound to the monitor ([TRE-REQ-001 Layer Surface Window](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md)). A change to `output` or `namespace` means reopening the window.
- Threads: window operations on the loop thread ([Process Model and Threading](../../20%20Architecture/Process%20Model%20and%20Threading.md)).
- **Coexistence with the Plasma panel.** plasmashell's panel reserves space too. Decided 2026-10-27: the Bar wins over a Plasma panel unless that panel is set to always on top, or a window is fullscreen ([Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27)); this is about fullscreen, not maximised. On the same edge the compositor stacks the zones in an order the shell does not control, so how the Bar wins is #needs-verification; different edges or monitors avoid it. The maintainer's Edge Shell design used a per-monitor mode (shell, Plasma, both, none).
- Memory: about 18 MiB for a 1280 x 32 bar on tre 0.5.8; one surface per bar per monitor ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)).

## Design

- The look is a style file, stylesheet or an inline `Style` block over the root container: background, border, corner radius, shadow, opacity ([Style, Theme and Stylesheet Files > Rules](../../41%20TDL%20Reference/Style%2C%20Theme%20and%20Stylesheet%20Files.md#rules)).
- A Bar matches the rest of the shell's surface elements (decided 2026-10-27): the same tokens, the same style keys and the same corner, border and shadow rules as a Panel and the Frame ([Style Schema](../../41%20TDL%20Reference/Style%20Schema.md)); a Bar has no look of its own.
- Shadows: a surface cannot draw outside its own bounds. A Bar with a shadow is a larger transparent surface; the zone covers the body only and `input_region` follows the body ([ADR-0010 Surface Shadows](../../30%20Decisions/ADR-0010%20Surface%20Shadows.md), decided 2026-10-27).
- Rounded corners on a full-span bar are drawn with the container's corner radius; a bar that melds into the Frame uses Path blocks ([Frame > Melding](Frame.md#melding)).

## Accessibility

- tre publishes the Bar as one window of the application; the bar's window node has no accessible name yet, so the shell sets the surface name ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)).
- Every module in it is keyboard-reachable. A hidden or auto-hidden Bar needs a keyboard way to reveal it (a global shortcut or a shell action).
- Reduced motion: show and hide are instant ([Goals and Non-Goals](../../10%20Vision/Goals%20and%20Non-Goals.md) G7).
- Auto-hide is on and the keyboard reveal is off by default (maintainer, 2026-10-27), so a keyboard-only user has no way to reveal the Bar until they set `Reveal_Key`. Open: whether the shell warns at first start, or reveals the Bar when it takes keyboard focus ([Auto-hide (decided 2026-10-27)](#auto-hide-decided-2026-10-27)).

## Performance Budget

- A Bar draws no frames at idle and wakes the loop only for its modules' timers.
- Sliding is margin animation: one small commit per step, no buffer change; the zone changes once, at the start or the end, not per frame.
- Budgets are set in `60 Quality/`.

## Failure Modes and Recovery

| Failure                                                   | Result                                                                                     |
|-----------------------------------------------------------|--------------------------------------------------------------------------------------------|
| `Exclusive_Zone` on a layer other than `TOP`              | Error at load naming the file, the Bar and the key                                         |
| A size of 0 on the axis it is attached along              | The Bar is not created; a warning names the Bar and says to set `Min_Height` or `Min_Width`. Checked at creation only |
| The zone does not include the `Gap`                       | Windows overlap the gap; the shell computes the zone from the size across the Edge and the `Gap` to avoid it |
| A corner-anchored Bar with a zone and no `exclusive_edge` | Reserves nothing; a `warning` event says so                                                |
| The monitor is removed                                    | The Bar closes (`output_removed`); recreated when the monitor returns                      |
| Two reserving surfaces on one edge                        | The compositor decides the order                                                           |

## Open Questions

- [x] The placement keys: `Edge`, `Width`, `Height`, the `Max_` and `Min_` bounds, `Alignment`, `Offset` and `Gap`; they replace `Span`, `Length`, `Thickness`, `Margin` and the raw `Anchor` and `Size` (maintainer, 2026-10-30).
- [x] The mapping of `Edge`, `Width`, `Height`, `Alignment`, `Offset` and `Gap` to tre is accepted (maintainer, 2026-10-31, D61), under Geometry. A hidden or peeking Bar keeps its size and slides by a negative margin, so a size of 0 never arises. Open, #needs-verification: the points listed under the mapping table.
- [x] Movable: no, a Bar is anchored and a movable surface is a Panel. Floating: a Bar with a `Gap` looks floating but stays attached and its gap space is reserved (maintainer, 2026-10-27).
- [x] Auto-hide: on by default with opt-out, a default delay the user can change, keyboard reveal none by default (maintainer, 2026-10-27). Open: the default delay value, the hover strip's thickness, and the reveal key's key name (`Reveal_Key`).
- [x] The Plasma panel on the same edge: the Bar wins, unless the Plasma panel is always on top or a window is fullscreen (maintainer, 2026-10-27). Open: how, and how KWin orders two zones on one edge. #needs-verification
- [x] A vertical Bar: a FlexBox with a vertical direction; text rotation is opt-in (maintainer, 2026-10-27). Open: the `Text_Rotation` values.
- [x] Shadow keys: `Elevation`, `Shadow` and `Shadow_Bleed` ([Style Schema > Shadow keys](../../41%20TDL%20Reference/Style%20Schema.md#shadow-keys), accepted 2026-10-27).

## Acceptance Criteria

- [ ] A full-span top Bar with a zone of 32 makes a maximised window stop 32 px below the top edge on KWin.
- [ ] A dock with a `Gap` of 8 and a `Height` of 64 sets a zone of 72 and keeps maximised windows 72 px above the edge, the same as a flush Bar of that total size.
- [ ] A Bar on `BOTTOM` or `OVERLAY` with an `Exclusive_Zone` is a load error.
- [ ] A top Bar with `Height: EXPAND` resolves to `Max_Height`, else `Min_Height`, else 0; at 0 it is not created and the warning names `Min_Height`.
- [ ] A Bar or Frame strip that is hidden or contracted can still be shown or expanded; the zero-size check does not stop it.
- [ ] A Bar on each of two monitors appears on both, and unplugging one removes only its Bar.
- [ ] Auto-hide is on with no key written; `Auto_Hide: false` keeps the Bar visible. The Bar slides out after the delay, then sets the zone to 0, and windows reflow once; the pointer at the edge brings it back.
- [ ] With `Reveal_Key` unset, no key reveals the Bar; with it set, the key does.
- [ ] A left or right Bar lays out vertically with unrotated text; `Text_Rotation` turns rotation on.
- [ ] A fullscreen window covers the Bar; a maximised window stops at it.
- [ ] An idle Bar draws no frames between module updates.

## Links

- [Surfaces](Surfaces.md) · [Surface Types](Surface%20Types.md) · [Panel](Panel.md) · [Frame](Frame.md) · [Shell File](../../41%20TDL%20Reference/Shell%20File.md) · [Building Blocks](../../50%20Design%20System/Building%20Blocks.md)

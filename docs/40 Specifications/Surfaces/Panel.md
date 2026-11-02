---
title: Panel
aliases: [Panel Surface, kind panel]
type: spec
status: review
owner: phil
created: 2026-10-27
updated: 2026-10-31
tags: [spec/surface, needs-verification]
---

# Panel

> [!NOTE]
> The Panel (the `Panel` block) is the multi-purpose surface. It can attach to the Frame, a Bar or another surface by naming it, or float free. It can be moved with the mouse, anchored, hidden and animated, and it can sit on the Bottom, Top or Overlay layer. The OSD, the desktop widget, the launcher and the slide-in panel are all Panels. A Panel is a tre `LayerWindow`; it may become the baseline other kinds build on. The decisions are the maintainer's ([Surface Types](Surface%20Types.md), [ADR-0007 Shell UI Layer](../../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md)); the key names were accepted by the maintainer on 2026-10-29 (many mirror tre's settings). The examples are TDL illustrations ([ADR-0014 Shell File Language](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)).

## Purpose and Scope

- One surface type that covers four v1 uses ([V1 Scope > Surfaces](../../10%20Vision/V1%20Scope.md#surfaces)): the OSD, the desktop widget, the launcher and the slide-in panel, plus an overlay popup panel (a Panel on the overlay layer, [Surface Types > Overlay](Surface%20Types.md#overlay)).
- Not in this note: the Bar and Frame (their own specs), the Popup (menus and flyouts anchored to a surface, [Surface Types > Special cases](Surface%20Types.md#special-cases)), and what a Panel contains (blocks, containers and modules, [Building Blocks](../../50%20Design%20System/Building%20Blocks.md)).

## Behaviour

### States

```mermaid
stateDiagram-v2
    [*] --> Hidden: loaded, hidden
    [*] --> Visible: loaded, shown
    Hidden --> Showing: show
    Showing --> Visible: animation ends
    Visible --> Hiding: hide
    Hiding --> Hidden: animation ends
    Visible --> Moving: press on a drag handle
    Moving --> Visible: release, position saved
    Visible --> Closed: monitor removed
    Hidden --> Closed: monitor removed
    Closed --> Hidden: monitor added again
```

- Show, hide and toggle are shell actions a module or an event can call; a Panel can also hide itself after a time (an OSD).
- Moving is done by the engine: the surface follows the pointer by changing its tre `margin`, with no Python in the loop. On release the Panel's `moved` event gives the final margins, which the shell turns into an `Offset` and saves ([TRE-REQ-001 Layer Surface Window > Margin drag](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#margin-drag)).
- A closed Panel is dead; the shell creates a new window when the monitor returns ([Data Flow > Monitor hot-plug](../../20%20Architecture/Data%20Flow.md#monitor-hot-plug)).

### Position and Attachment

| Mode                          | How it is written (proposed)                                    | How it is built on tre                                                    |
|-------------------------------|-----------------------------------------------------------------|---------------------------------------------------------------------------|
| Anchored to an edge or corner | `Anchor: [TOP, RIGHT]` with `Offset`                            | `anchor` and `margin` settings (the shell reorders `Offset` to tre's order) |
| Floating                      | no `Anchor`                                                     | The compositor centres it; an `Offset` places it                    |
| Movable                       | `Movable: true`                                                 | A node with `window_region="drag_margin"`; the engine changes the margins |
| Attached to a target          | `Attach_To: Top_Bar`, `Attach: LEFT`, `Gap: 10`, `Align: START` | The shell computes margins from the target's geometry (below)             |

- **Attaching is by naming the surface** (decided, [ADR-0007 Shell UI Layer > Open items](../../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#open-items)). It is a reference, not nesting. The registry resolves the name; an unresolved name is an error at load, and a target that disappears while running is a warning and the Panel stays hidden until it returns.
- layer-shell has no way to place one surface relative to another, so the shell computes the margins itself and recomputes them when the target moves or animates. Two separate surfaces animating together can differ by up to a frame on screen ([TRE-REQ-001 Layer Surface Window > Animation](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#animation)).
- Dragging clamps the Panel to its output. It does not cross to another monitor (no cross-monitor dragging for now; a later item), and other surfaces' reserved zones do not limit it.
- **Only a floating Panel has a persistent position** (decided 2026-10-27). An attached or anchored Panel is placed by its target or its anchor, so nothing is saved for it. The floating Panel's position is saved in the registry, which already holds a unique identity for it (proposed key: the final margins from the `moved` event, kept as an `Offset`).

### Attachment Geometry (Decided 2026-10-27)

`Attach_To` names the target. Three keys say where the Panel sits against it:

| Key      | Values                           | Meaning                                      |
|----------|----------------------------------|----------------------------------------------|
| `Attach` | `LEFT`, `RIGHT`, `TOP`, `BOTTOM` | Which edge of the target the Panel meets     |
| `Gap`    | An integer, in pixels            | The space between the Panel and the target   |
| `Align`  | `START`, `CENTER`, `END`         | How the Panel lines up along the shared edge |

- `Attach: LEFT` puts the Panel's right edge against the target's left edge. `Attach: RIGHT` puts the Panel's left edge against the target's right edge. `Attach: TOP` puts the Panel's bottom edge against the target's top edge. `Attach: BOTTOM` puts the Panel's top edge against the target's bottom edge.
- `Gap` is the true visible gap, borders included: the distance between the Panel's outer border edge and the target's outer edge. A Panel with a 2 px border and a target with none, with `Gap: 10`, has exactly 10 px between them. The shell subtracts the border from the offset it computes, and ignores a shadow margin, which is transparent ([ADR-0010 Surface Shadows](../../30%20Decisions/ADR-0010%20Surface%20Shadows.md)).
- `Align` runs along the edge: for `Attach: LEFT` or `RIGHT`, `START` lines up the top edges, `CENTER` the middles and `END` the bottom edges; for `Attach: TOP` or `BOTTOM`, `START` lines up the left edges and `END` the right edges (the second half is by analogy).

```
Attach_To: Top_Bar
Attach: LEFT
Align: START
Gap: 10
```

This form is for a target that is not a Frame. A Panel attached to a Frame uses `Margin` instead of `Gap`; see Attached to a Frame below.

This attaches the Panel's right edge to the target's left edge, lines up their top edges, and leaves 10 px between the Panel's right edge and the target's left edge.

**Attached to a Frame (decided 2026-10-30, D49 to D51).** A Frame has no `Gap`. The Panel's `Margin` on the sides that face the Frame is the separation:

- With no margin on those sides, the Panel and the Frame meld as before ([Frame > Hosted melding (decided 2026-10-27)](Frame.md#hosted-melding-decided-2026-10-27)).
- With a margin there, they do not meld: the Frame edge continues straight and the Panel's corners round as a floating Panel's do.
- Whether a Panel melds is decided by its `Margin` on the Frame-facing sides (D44). The `Meld` key does not switch melding on or off: it only chooses how a melded Panel is drawn, hosted inside the Frame's surface or as a window of its own (D56, amended 2026-10-31). With a margin there, `Meld` has no effect.
- `Offset` positions the Panel from its anchored edges; `Margin` is transparent space around the Panel and `Padding` is inside it ([Shell File > Surface Keys](../../41%20TDL%20Reference/Shell%20File.md#surface-keys)).

**Following the target (decided 2026-10-27).**

- The Panel follows a target that animates (slides, expands, contracts).
- If the target is hidden while the Panel is open, the Panel hides ("hides or closes"; hidden, not closed, see Hide and show).
- If the target has peeking on and peeks while the Panel is open, the Panel follows the peek animation and stays open.
- Opened by a keyboard shortcut while the target is hidden: if the target has peeking enabled, the Panel opens; if not, it does not open until the target is visible.

**One Panel, one target (decided 2026-10-27).** A target has one attached Panel. A second Panel attaches to the first Panel (a chain). Opening the second from the first is opt-in: either the origin target opens both (proposed key `Open_With_Target`, default off), or the first Panel has its own way to open the second.

**A module as the target (decided 2026-10-27).** The target can be a module inside a Bar. Then `Attach` and `Align` are computed against the module's geometry, not the Bar's, while the gap respects the parent Bar, so the Panel does not overlap it. A Bar can therefore carry several Panels, one per module. A Panel can be attached to a Bar itself and open when the Bar becomes visible, for a stylised application menu. How the shell reads a module's geometry, and what "the gap respects the parent Bar" means exactly (the gap measured from the Bar's edge), are open. #needs-verification

### Hide and Show (Decided 2026-10-27)

Hide and show mean hidden, not closed. A hidden Panel keeps its identity and its place in the tree; it does not reload, and a Panel that is shown again returns where it was. The window mechanics (tre's `show_layer` is about node layers inside a window, per its layer-window reference, not surface visibility, so surface hiding may need another route) are open. #needs-verification

### Collapsed Handle (Decided 2026-10-27: Use the Edge Shell as the Example)

A Panel can collapse to a handle on its edge, as the maintainer's Edge Shell does ([design spec](file://~/Projects/pyDev/projects/myShell/docs/superpowers/specs/2026-10-11-edge-shell-design.md), [Shell_Specs](file://~/Projects/pyDev/projects/myShell/docs/Shell_Specs.md)). What it does, as written there:

| State     | Visible                                                           | Enters when                                                                       |
|-----------|-------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| Collapsed | The handle only; the Panel is hidden                              | Start-up default, a click on the handle while extended, a drag released below 50% |
| Peek      | A short slide out (14 px in the Edge Shell); the handle brightens | The pointer enters the hover zone                                                 |
| Extended  | Full depth                                                        | A click on the handle, or a drag released at 50% or more                          |

- The handle is three 3 px dots with 3 px gaps; its colour changes on hover. The Edge Shell lists per-panel properties for its shape, size, weight, offset, colour and hover colour, and for whether click, hover and drag act.
- The hover zone is an invisible strip beyond the edge (16 px in the Edge Shell) that wakes a collapsed Panel.
- A press that moves under 4 px is a click; a longer press moves the depth along the panel's axis and snaps at 50% on release.
- The handle is a focusable button with an accessible name such as "Expand dock".
- Proposed keys, from the Edge Shell names: `State` (`collapsed`, `extended`), `Peek` (pixels), `Hover_Zone` (pixels), `Handle` (a block for shape, size, weight, offset, colour and hover colour), `Click`, `Hover` and `Drag` (booleans). These are proposals; the maintainer chose the Edge Shell as the model, not the key names.

### Layers

A Panel may use `BOTTOM`, `TOP` or `OVERLAY`. It may reserve space only on `TOP` (an `Exclusive_Zone` elsewhere is a load error, [Surface Types > Layers per kind](Surface%20Types.md#layers-per-kind)).

- The protocol leaves the order of surfaces on one layer undefined ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)). So a Panel that must draw over a Bar needs a higher layer than the Bar (a Bar on `TOP`, the Panel on `OVERLAY`), or it must not overlap it.
- `BACKGROUND` is not offered to any surface type.

### Keyboard and Focus

- `Keyboard: NONE` is the default; a Panel with a text field needs `ON_DEMAND`; the launcher uses `EXCLUSIVE` on the overlay layer.
- A popup a Panel calls inherits the Panel's keyboard setting ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)).

### Input Region

By default a Panel takes input over its whole surface. A Panel with a non-rectangular shape, a transparent margin for a shadow, or a click-through OSD sets the input region: the whole surface, nothing, rectangles, or `auto` (the union of the drawn shapes). The OSD uses nothing so clicks pass through. Shape-aware `auto` for curved and concave shapes uses `hit_shape="painted"` on path nodes, released in tre 0.5.9 ([Hit Testing for Concave Corners](../../90%20Research/Hit%20Testing%20for%20Concave%20Corners.md)).

## Configuration

Keys of a Panel entry. Decided keys are from [Common Keys and Conventions](../../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md); proposed ones mirror tre ([Shell File > Surface keys](../../41%20TDL%20Reference/Shell%20File.md#surface-keys)).

| Key                | Meaning                                                                                                                                              | Status                                                                       |
|--------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| `Panel` (the head) | The type; there is no `Kind:` key                                                                                                                                           | Decided                                                                      |
| `Layer`            | `BOTTOM`, `TOP` or `OVERLAY`                                                                                                                         | Decided                                                                      |
| `Children`         | Blocks, containers and modules                                                                                                                       | Decided                                                                      |
| `Style`            | A style file or inline values                                                                                                                        | Decided                                                                      |
| `Attach_To`        | The name of the target: a surface, a module in a Bar, or another Panel                                                                               | Decided that attachment is by name; key accepted 2026-10-29                 |
| `Attach`           | `LEFT`, `RIGHT`, `TOP`, `BOTTOM`: the target's edge the Panel meets                                                                                  | Decided (2026-10-27)                                                         |
| `Gap`              | Pixels between the Panel and a target that is not a Frame, borders included                                                                                            | Decided (2026-10-27)                                                         |
| `Align`            | `START`, `CENTER`, `END` along the shared edge                                                                                                       | Decided (2026-10-27)                                                         |
| `Open_With_Target` | Opening the target also opens this Panel; default off                                                                                                | Opt-in decided (2026-10-27); key accepted 2026-10-29                        |
| `Anchor`           | `TOP`, `BOTTOM`, `LEFT`, `RIGHT` (one or a list)                                                                                                     | Decided (key name accepted 2026-10-29)                                      |
| `Size`             | `[width, height]`                                                                                                                                    | Decided (key name accepted 2026-10-29)                                      |
| `Offset`           | Four-sided position from the anchored edges (left, top, right, bottom); replaces the Panel's old `Margin`. The shell reorders it to tre's `margin` | Decided (D51)                                                               |
| `Meld`             | Only with `Attach_To` a Frame and no `Margin` on the Frame-facing sides: `true` draws the Panel inside the Frame's surface (hosted melding); `false`, the default, keeps a window of its own that draws its own joins. It does not decide whether the Panel melds; the `Margin` does | Amended 2026-10-31 (D56); the mechanism is decided ([Frame > Hosted Melding (Decided 2026-10-27)](Frame.md#hosted-melding-decided-2026-10-27)) |
| `Margin`           | Transparent space around the Panel (left, top, right, bottom). Attached to a Frame, on the Frame-facing sides it separates the two and stops the meld | Decided (D41 to D45)                                                        |
| `Padding`          | Transparent space between the children and the Panel's four sides (left, top, right, bottom)                                                        | Decided (D41 to D45)                                                        |
| `Keyboard`         | `NONE`, `ON_DEMAND`, `EXCLUSIVE`                                                                                                                     | Decided (key name accepted 2026-10-29)                                      |
| `Input_Region`     | Whole, nothing, rectangles or `auto`                                                                                                                 | Decided (key name accepted 2026-10-29)                                      |
| `Exclusive_Zone`   | Space to reserve; only on `TOP`                                                                                                                      | Rule decided; key accepted 2026-10-29                                       |
| `Movable`          | The mouse can move it; the position is saved. Floating Panels only                                                                                   | Decided (key name accepted 2026-10-29); saved in the registry (decided 2026-10-27) |
| `Hidden`           | Start hidden                                                                                                                                         | Decided (key name accepted 2026-10-29)                                      |
| `Hide_After`       | Hide itself after a time, for an OSD; the default is a reasonable value the user can set, and the caller resets the timer when it re-shows the Panel | Decided (2026-10-27); the default value is open                              |
| `Animation`        | Slide, fade or none, with a duration                                                                                                                 | Decided (key name accepted 2026-10-29)                                      |

### The Four Uses

```
# OSD: brief, click-through, on the overlay layer
Panel {
    Name: Volume_OSD
    Layer: OVERLAY
    Anchor: [BOTTOM]
    Offset: [0, 0, 0, 80]
    Size: [260, 60]
    Input_Region: []
    Hide_After: 1500
    Children {
        ProgressBar { Value: {{ volume }} }
    }
}

# desktop widget: movable, position saved
Panel {
    Name: Clock_Widget
    Layer: BOTTOM
    Anchor: [TOP, LEFT]
    Offset: [40, 40, 0, 0]
    Movable: true
    Children {
        Clock { }
    }
}

# launcher: overlay layer, exclusive keyboard
Panel {
    Name: Launcher
    Layer: OVERLAY
    Keyboard: EXCLUSIVE
    Size: [600, 400]
    Hidden: true
    Children {
        TextInput { }
        List { }
    }
}

# slide-in panel attached to a bar
Panel {
    Name: Side_Panel
    Layer: TOP
    Attach_To: Top_Bar
    Attach: BOTTOM
    Align: END
    Gap: 8
    Hidden: true
    Animation { Type: SLIDE, Duration: 200 }
    Children {
        Slider { }
    }
}
```

An illustration only: the module params (`Value`, a Slider's params) are not designed here; a module use is written with the module's name as the head ([Module File > Using a Module](../../41%20TDL%20Reference/Module%20File.md#using-a-module)). `true` in `Movable: true` and `Hidden: true` is a bare word that the parser keeps as a string and the key's declared type turns into a boolean, and `[]` in `Input_Region: []` is the empty list (D2, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).

## Python Contract

A Panel has no Python of its own. A module reaches it through shell actions: show, hide, toggle, move. A module is told when a use appears or goes away ([Module Context > Uses](../../42%20Python%20API/Module%20Context.md#uses)). The position the user dragged to is shell state, not module state.

## Integration

- tre: a `LayerWindow` with `layer`, `anchor`, `size`, `margin`, `keyboard`, `input_region`, `exclusive_zone` (live through `set()`), margin animation with `animate`, `window_region="drag_margin"` and the `moved` event ([TRE-REQ-001 Layer Surface Window](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md)). `namespace` and `output` are constructor-only, so a change means reopening the window.
- Threads: window operations on the loop thread; no worker thread ([Process Model and Threading](../../20%20Architecture/Process%20Model%20and%20Threading.md)).
- Saved position: only a floating Panel has one. The registry holds each entry's state ([ADR-0007 Shell UI Layer > Config directory and registry (2026-10-25)](../../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#config-directory-and-registry-2026-10-25)); the final margins from `moved` are written there (decided 2026-10-27, key proposed). On a monitor change the saved position is clamped to the output.
- Memory: a surface costs about 18 MiB for a 1280 x 32 bar and 31 MiB for a 200 x 100 window on tre 0.5.8, and a full-screen 4K overlay about 177 MiB ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)). A launcher should be a sized panel, not full-screen, unless a dimmed backdrop is wanted.

## Design

- A Panel's look is a style file, a stylesheet or an inline `Style` block over a Box or FlexBox; shape, border, radius, shadow and background are style properties ([Style, Theme and Stylesheet Files > Rules](../../41%20TDL%20Reference/Style%2C%20Theme%20and%20Stylesheet%20Files.md#rules)).
- Shadows: as [ADR-0010 Surface Shadows](../../30%20Decisions/ADR-0010%20Surface%20Shadows.md) defines them: a larger transparent surface, the input region on the body, and the shadow keys `Elevation`, `Shadow` and `Shadow_Bleed` ([Style Schema > Shadow keys](../../41%20TDL%20Reference/Style%20Schema.md#shadow-keys)). Shadows are excluded from the hit shape.
- A visual meld with a Bar or the Frame is drawn with Path blocks and a shared colour, on separate surfaces ([Surface Types > Risks](Surface%20Types.md#risks)).

## Accessibility

- The Panel's window is published as one window of the application, with the nodes' roles, labels and states set in the shell file. A hidden Panel is not in the tab order.
- The launcher takes the keyboard exclusively on open; Escape closes it.
- The screen reader gets the tree but no screen position for a layer surface ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)).
- Reduced motion: show and hide are instant, no slide or fade ([Goals and Non-Goals](../../10%20Vision/Goals%20and%20Non-Goals.md) G7).
- A collapsed or auto-hidden Panel needs a keyboard-reachable way to open it.

## Performance Budget

- A hidden Panel with `Hidden: true` should not hold a surface if the compositor allows; whether the window is created hidden or destroyed and recreated is open.
- Moving is done in the engine, with one commit per input frame and no Python in the loop.
- A slide uses margin animation, one small commit per step with no buffer change. Size and `Exclusive_Zone` changes are not animated (a configure round trip each).
- Budgets are set in `60 Quality/`.

## Failure Modes and Recovery

| Failure                                                  | Result                                                                            |
|----------------------------------------------------------|-----------------------------------------------------------------------------------|
| `Attach_To` never resolves                               | Error at load naming the file, the Panel and the name                             |
| The target disappears while running                      | Warning; the Panel stays hidden until the target returns                          |
| A size of 0 on an axis without both opposite anchors     | Error before any request to the compositor (tre rejects it)                       |
| `Exclusive_Zone` on a layer other than `TOP`             | Error at load                                                                     |
| The saved position is off the output (a monitor changed) | Clamped to the output; if impossible, the configured default                      |
| The monitor is removed                                   | The Panel closes (`output_removed`); it is created again when the monitor returns |
| The compositor closes the surface                        | The Panel is dead; the shell recreates it                                         |
| Two Panels overlap on the same layer                     | Draw order undefined; use different layers                                        |

## Open Questions

- [x] Attachment geometry: `Attach`, `Gap` and `Align`, and how `Attach_To` treats a hidden or animating target (maintainer, 2026-10-27).
- [x] One Panel per target; further Panels chain to the previous Panel; opening both is opt-in. A module in a Bar can be the target (maintainer, 2026-10-27).
- [x] Hide and show: hidden, not closed (maintainer, 2026-10-27). Open: the window mechanics and the first-show flash.
- [x] Where the position is saved: the registry, for floating Panels only (maintainer, 2026-10-27). Open: the key that turns saving on.
- [x] A collapsed handle: as the Edge Shell does it (maintainer, 2026-10-27). Open: the key names and the hover zone's size.
- [x] Dragging across monitors: not now, something to look into later (maintainer, 2026-10-27).
- [x] Auto-hide timing for an OSD: a reasonable default the user can set; the caller controls the reset (maintainer, 2026-10-27). Open: the default value.
- [x] Shadow keys: as ADR-0010 defines them (maintainer, 2026-10-27).
- [x] Keys the type adds, and the baseline for other types: no additions at this time (maintainer, 2026-10-27).
- [ ] How the shell reads a module's geometry for a module target, and what the gap against the parent Bar means exactly.

## Acceptance Criteria

- [ ] A Panel with `Layer: BOTTOM`, an anchor and an `Offset` appears at that place on its monitor and above the wallpaper.
- [ ] A movable Panel follows the mouse, stays on its output, and its final position is saved and used on the next start.
- [ ] A Panel with `Attach_To` appears next to its named target; with the target removed from the file, loading reports the missing name; with the target hidden while running, a warning is logged and the Panel hides.
- [ ] A Panel on the overlay layer with `Keyboard: EXCLUSIVE` takes the keyboard and Escape closes it.
- [ ] An OSD with `Input_Region: []` lets clicks pass through and hides itself after `Hide_After`.
- [ ] A slide-in Panel moves by margin animation and, with reduced motion on, appears instantly.
- [ ] An `Exclusive_Zone` on a Panel that is not on `TOP` is a load error.
- [ ] After the monitor is unplugged and plugged back, the Panel is created again where it was saved.
- [ ] `Attach: LEFT`, `Align: START`, `Gap: 10` puts the Panel's right edge 10 px from the target's left edge with their top edges level; a 2 px Panel border is inside the 10.
- [ ] A Panel follows an animating target; it hides when the target hides, and stays open and follows when the target peeks.
- [ ] A keyboard shortcut opens the Panel while its target is hidden only if the target has peeking.
- [ ] A second Panel attached to the first follows it; `Open_With_Target` opens both from the target.
- [ ] A hidden Panel is not closed: showing it returns it to the same state and place.
- [ ] A collapsed Panel shows its handle; hover peeks, a click or a drag past 50% extends it.
- [ ] Only a floating Panel's position is written to the registry.
- [ ] A Panel attached to a Frame with no `Margin` on the Frame-facing sides melds; with a `Margin` there it does not meld, the Frame edge continues straight and the Panel's corners round.

## Links

- [Surfaces](Surfaces.md) · [Surface Types](Surface%20Types.md) · [Shell File](../../41%20TDL%20Reference/Shell%20File.md) · [Building Blocks](../../50%20Design%20System/Building%20Blocks.md) · [Shell Structure](../../20%20Architecture/Shell%20Structure.md)

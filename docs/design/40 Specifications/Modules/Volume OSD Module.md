---
title: Volume OSD Module
aliases: [Volume_OSD, OSD, Volume OSD, M7h]
type: spec
status: review
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [spec/module, quality]
---

# Volume OSD Module

> [!NOTE]
> A shipped module, `Volume_OSD`, that shows a small card (an icon, the output's name, a bar and the percentage or "Muted") when the default output's volume or mute changes, and hides it after a moment. It is the volume on-screen display of use case UC3 in [V1 Scope](../../10%20Vision/V1%20Scope.md). The maintainer decided on 2026-11-17 that the OSD ships as a module ([M7 Brief](../../00%20Home/M7%20Brief.md), M7h). This note was written after the build, from the code session's report of `tess-shell` PR #60 (merged 2026-11-17, CI green, not run in the vault), so that the design record has what was built; status `review` until the maintainer answers the decisions below.

## Purpose and scope

- In: the module, its params, when it shows and when it stays silent, the Panel the user puts it in, the module-contract call it added, accessibility, the tests.
- Out: brightness (no brightness service exists), kind-specific icons, a shipped Panel for it.

## Behaviour

- The module follows the sound server itself through `ctx.audio` ([Audio Module](Audio%20Module.md), [ADR-0021 Audio Access](../../30%20Decisions/ADR-0021%20Audio%20Access.md)) and shows its Panel when the default output's volume or mute changes, then hides it after the duration.
- It shows nothing at start, for the first reading, for a server restart, for a switch of the default output (a silent new baseline), and for a microphone or output-list change.
- The card shows an icon chosen by level (a crossed speaker and a dimmed bar when muted), the output's name, a progress bar and the percentage, or "Muted".

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `duration` | integer, milliseconds | 1500 | How long the Panel stays; 0 to 60000. It replaces the Panel's own `Hide_After` for each show |
| `show_name` | boolean | true | Whether the output's name is on the card |

The user puts the module in a Panel they write, in the README's pattern:

```
Panel { Name: Volume_OSD_Panel, Layer: OVERLAY, Visible: false, Input_Region: [], Keyboard: NONE, ... Children { Volume_OSD { } } }
```

The Panel must start `Visible: false`, because the module cannot hide it at start without a flash. The card's look lives in the Panel's `Style`. The guide example `guide/examples/05-modules/volume-osd` passes `check`; the Panel example in `04-surfaces` is unchanged.

## Python contract

A new additive call in the module contract: `ctx.surface.show(use=None, *, hide_after=None)` (`SurfacePort.show_use`, `SurfaceManager.show_use`, an optional per-show time on `show` and `_arm_hide_after`). It shows the surface of a use for an optional time, so a module can show its own Panel without a user action ([Module Context](../../42%20Python%20API/Module%20Context.md)).

## Integration

- Thread and source: the module reads the sound server through `ctx.audio`, which crosses to the loop as the other Audio code does.
- It announces nothing itself: the Audio module's `announce` param speaks the change ([TRE-REQ-021 Announce Without a Node](../../80%20Requests/TRE-REQ-021%20Announce%20Without%20a%20Node.md)), so a screen reader hears it once.

## Accessibility

The card is not a live region. It is a labelled group with a named progress bar ([Accessibility](../../60%20Quality/Accessibility.md)).

## Decisions for the maintainer (code session's list)

1. [ ] Attachment: the Panel is one the user writes (the README's pattern), not a shipped Panel on the Launcher's model. Context: a shipped Panel would need a trigger rule so that a module in it is enabled with one line (for example a settings key). Recommendation: keep it as built; add the one-line enabler only if users ask.
2. [ ] The module's `duration` replaces the Panel's `Hide_After` for each show. Recommendation: yes, as built.
3. [ ] A switch of the default output shows nothing; the alternative is to show the new output's level. Recommendation: as built: a silent new baseline, since the user did not change a volume.
4. [ ] No brightness (no service exists) and no kind-specific icons: the icon follows the level and mute, and the output's name is shown. Recommendation: as built; brightness follows a brightness service.
5. [ ] The Panel must start `Visible: false`. Recommendation: as built; the alternative flashes the card at start.
6. [ ] The card's look is in the Panel's `Style`, not the module. Recommendation: as built, so a user restyles it like any Panel.

## Questions After Testing

1. [ ] Is the real-compositor look right: placement, and the layer above the Plasma panels? Context: the code session tested headless only (input region `[]`, keyboard none) and built no private-sway wire check of the layer surface; the placement and the layer on the real KWin are a hand check with no kit line yet. Recommendation: add a kit line under [Hand Checks](../../00%20Home/Hand%20Checks.md) that the session runs on the private KWin, and the maintainer's look on his session. Answered by: that line.

## Acceptance criteria

- [x] Start, volume change, mute change, hide timing and restart, the cases that show nothing, announce-once, the accessibility tree, a Bar use and `ctx.surface.show` are covered by 25 tests (reported); four deliberate breaks of the module were each caught.
- [x] The guide example checks clean.
- [ ] The look and the layer on a real compositor are seen.

## Links

[Audio Module](Audio%20Module.md) · [Panel](../Surfaces/Panel.md) · [Accessibility](../../60%20Quality/Accessibility.md) · [V1 Scope](../../10%20Vision/V1%20Scope.md) · [M7 Brief](../../00%20Home/M7%20Brief.md) · [Modules](Modules.md)

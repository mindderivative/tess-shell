---
title: M3 Brief
aliases: [M3, More Surfaces Brief, Shell M3]
type: moc
status: draft
owner: phil
created: 2026-11-04
updated: 2026-11-06
tags: [moc, roadmap, brief]
---

# M3 Brief

> [!NOTE]
> The scope of milestone M3, "more surfaces": the shell stops being one Bar. It gains a look (themes and tokens, shadows), the surfaces that open and close (`Panel`, `Popup`), the events that open them, the `Frame` ring, and multi-monitor with hot-plug. It follows [M2 Brief](M2%20Brief.md) (live values and hot reload, scoped and waiting on the maintainer's answers). This is a plan for the maintainer, written to keep the design ahead of the build ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). It starts when M2 is done and the maintainer says so.

> [!WARNING]
> **M3c is built but not accepted on its look (2026-11-06)**
> M3a, M3b and M3c are built and every KWin checklist line passes, including the Frame, hot-plug and the melded Panel animation. The maintainer's look test of the Frame did not pass: the melded join animation and edge smoothness are poor, and some content is not centred ([Frame > Found on KWin: the look is not good enough (maintainer, 2026-11-06)](../40%20Specifications/Surfaces/Frame.md#found-on-kwin-the-look-is-not-good-enough-maintainer-2026-11-06), R-31). The acceptance boxes below stay unticked until that is settled.

## Goal and Definition of Done

M3 is done when:

- A theme file sets the colours, type, shape, space and motion tokens; a style or stylesheet refers to them; the default theme follows the desktop's light or dark setting.
- A surface with an `Elevation` shows its shadow inside a transparent margin, and the reserved space does not change ([ADR-0010 Surface Shadows](../30%20Decisions/ADR-0010%20Surface%20Shadows.md)).
- A `Panel` opens as an overlay, as an anchored surface and attached to a Bar module, takes the keyboard when told to, and closes on Escape or after `Hide_After`; a movable Panel keeps its position across restarts.
- A `Popup` opens beside the module that called it, flips at the screen edge, and closes on an outside click or Escape; a module's `Tooltip` opens after `Enter_Delay`.
- A click on a module runs an action in its Python (`On_Click`), and a shell action (`Show`, `Hide`, `Toggle`) opens a Panel.
- A `Frame` reserves its sides, shows convex and concave corners, passes clicks through its opening, and melds with a Panel.
- Unplugging and plugging a monitor removes and recreates only that monitor's windows.

Not in M3: services and the tray menu (M4), shortcuts, the KWin script and fullscreen hiding (M5), packaging.

## Proposed Split

| Half | Content | Done when |
|---|---|---|
| M3a: the look | Theme and style files, tokens, stylesheets and selectors, the desktop's light/dark and accent from the portal, a default theme, `Elevation` and shadows with the real numbers | A themed Bar with a shadow follows a light/dark switch |
| M3b: Panel and Popup | Events and actions, `Panel`, `Popup`, tooltips, `ctx.popup`, saved Panel positions, the Clock's `locale` and tooltip | A click on the Clock opens a Popup beside it; an OSD Panel hides itself |
| M3c: Frame and monitors | `Frame` with strips, radii, input region and melding; hot-plug; saved positions per monitor | Unplugging a monitor removes only its windows |

Recommendation: build in that order. A Panel and a Popup need the look, and the `Frame` is the heaviest and riskiest piece, so it goes last.

## Design Needed First

| # | Gap | State | Recommendation |
|---|---|---|---|
| G1 (answered, [Events and Actions](../42%20Python%20API/Events%20and%20Actions.md)) | Events and actions: the value of an `On_*` key, the `@action` decorator's name, how an event reaches a module on the loop thread, and the built-in shell actions (`Show`, `Hide`, `Toggle`, `Close`) | Decided in part (2026-11-01: a bare action name, or a block with `Action:` and named arguments); the list of built-in actions has been open since 2026-10 | Write one note, "Events and Actions", before M3b; it needs the list of built-in actions from the maintainer |
| G2 | The default theme: colour roles, type scale, shape, space and motion values; light and dark; high contrast | Token names are proposed in [Style Schema](../41%20TDL%20Reference/Style%20Schema.md); the values belong to the design system, which is not written | Write the design-system principles and the default tokens; hand-written palettes, not generated from the accent (recommended for M3: no extra dependency); generation can come later |
| G3 | Following the desktop: light/dark, accent, contrast and reduced motion from the portal | Written in [Portals](../40%20Specifications/Integration/Portals.md) | Use it in M3a |
| G4 | Shadows in tre: the `Elevation` curve and the 64 px figure are provisional | [Style Schema](../41%20TDL%20Reference/Style%20Schema.md), D88 and D90 | Test how tre renders `shadows` on a box and inside a margin, set the numbers from the test, record them |
| G5 | Popup geometry: tre's popup placement and the shadow margin; [TRE-REQ-007 Popup Body Geometry](../80%20Requests/TRE-REQ-007%20Popup%20Body%20Geometry.md) is a draft, not filed | The shell's workaround (shift `offset` by the margin) does not need it | Keep the workaround; carry the request only if the workaround fails |
| G6 | Saved positions: a moved Panel's margin in the registry; the stored order (tre's top, right, bottom, left) | An open item in [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) | Store in tre's order, convert on read and write, and document it in [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md) |
| G7 | Hot-plug: what `output_updated` does to surfaces whose size depends on the output; how windows are recreated | An open item in [Data Flow](../20%20Architecture/Data%20Flow.md) | Recompute geometry on `output_updated`; recreate windows on `output_removed` then `output_added`; write it down in [Data Flow](../20%20Architecture/Data%20Flow.md) |
| G8 | The Frame's cost: four reservers plus a full-output painter, 177 MiB measured for a 4K overlay, the 256-rectangle input-region cap, many joins untested | R-15, R-16, [Frame](../40%20Specifications/Surfaces/Frame.md) | Measure on KWin at the start of M3c and record the figures before the rest of the Frame is built |
| G9 | `locale` for the Clock | Written in [Clock Module](../40%20Specifications/Modules/Clock%20Module.md) | M3b, with the tooltip |

Notes that must be at `review` before M3b starts: Events and Actions (to write), [Popup](../40%20Specifications/Surfaces/Popup.md) (draft now), [Panel](../40%20Specifications/Surfaces/Panel.md) and [Frame](../40%20Specifications/Surfaces/Frame.md) (review), [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md) (review).

## Tasks

### M3a: the Look

| # | Task | Done when |
|---|---|---|
| A1 | `config/` and `files/`: `Theme`, `Style` and `Stylesheet` root blocks, token tables, `$group.name` references resolved by the shell before binding | A theme with every token group loads; an unknown token names the nearest ones |
| A2 | Selectors and states (`Hovered`, `Pressed`, `Focused`, `Disabled`) in stylesheets | Each selector form applies in the stated priority ([Style Schema](../41%20TDL%20Reference/Style%20Schema.md)) |
| A3 | The portal reader: light/dark, accent, contrast, reduced motion; re-resolve on `SettingChanged` | Switching the desktop scheme changes the theme within 100 ms |
| A4 | `Elevation` and `Shadow_Bleed` in the surface margin | A shadow is fully visible and the reserved space is unchanged |
| A5 | Tests, a KWin check, a measurement of shadow memory per surface | Reported against [Performance Budgets](../60%20Quality/Performance%20Budgets.md) |

### M3b: Panel and Popup

| # | Task | Done when |
|---|---|---|
| B1 | Events and actions: `On_Click` and the other events reach a module's action; the built-in actions open and close surfaces | A click on a block calls its action on the loop thread |
| B2 | `Panel`: layers, keyboard modes, `Inset`, `Attach_To` with `Attach`, `Alignment`, `Gap`, `Input_Region`, `Hide_After`, the slide animation | The acceptance cases in [Panel](../40%20Specifications/Surfaces/Panel.md) that do not need a Frame pass |
| B3 | A movable Panel and its saved position | The position survives a restart |
| B4 | `Popup`: placement, flip and slide, focus and dismissal, `ctx.popup` with the caller's record | A click opens a Popup beside the caller and an outside click closes it |
| B5 | Tooltips (`Tooltip`, `Enter_Delay`, `Exit_Delay`) and the Clock's `locale` | The Clock shows a tooltip in German month names with `locale: de_DE` |
| B6 | Tests, a KWin check, a measurement | Reported |

### M3c: Frame and Monitors

| # | Task | Done when |
|---|---|---|
| C1 | The Frame measurement on KWin (G8) | The figures are recorded before more is built |
| C2 | `Frame`: strips with thickness, corner radii, border, the painter, the input region | The ring reserves its sides and passes clicks in the opening |
| C3 | Melding: hosted melding of a Panel in the Frame's surface | No seam at idle |
| C4 | Hot-plug: `output_added`, `output_removed`, `output_updated`; per-monitor windows | Only the affected monitor's windows change |
| C5 | Tests (a headless sway can add and remove outputs), a KWin check, a measurement | Reported |

## Dependencies

`tess_re` (`PopupWindow`, `LayerWindow` input regions and `hit_shape`, `Painter`, shadows), `tess_utils` (colour, sides), the portal reader through the D-Bus helper (so `dbus-fast` comes in at M3a, earlier than M4), and the packages already in use.

## Questions for the Maintainer

All six were answered on 2026-11-04, together with G1 to G9 ("As recommended" for each).

1. [x] M3 is split into M3a, M3b and M3c, in that order.
2. [x] G1: "Events and Actions" is written ([Events and Actions](../42%20Python%20API/Events%20and%20Actions.md)) from the maintainer's list of twelve events and the possible later additions.
3. [x] G2: hand-written default palettes, generation from the accent later.
4. [x] G3: the portal reader belongs in M3a, so `dbus-fast` comes in before M4.
5. [x] G8: measure the Frame on KWin first (C1) and decide from the figures.
6. [x] The Clock's `locale` and tooltip move to M3b.

### Added on 2026-11-04

7. [x] Decided yes by the maintainer (2026-11-05). Does `mdi` ship in the package from M3? The earlier decision is that v1 ships only `mdi` (2026-11-01), and D26 left the icon set out of M2. Recommendation: yes, as package data with its Apache 2.0 licence text and the per-icon exceptions list (R-23), read as the lowest-priority set after the user's `Icons` folders.

## Acceptance Criteria

- [x] Every line of "Goal and Definition of Done" is true, with a KWin check of the themed Bar, a Panel, a Popup and the Frame (maintainer, 2026-11-08).
- [x] Each task has a test or a recorded measurement.
- [ ] The notes listed under "Design Needed First" are at `review` before the half that needs them starts.
- [x] Design gaps found are handed back to the vault session.

## Links

- [Development Readiness](Development%20Readiness.md) · [M2 Brief](M2%20Brief.md) · [Panel](../40%20Specifications/Surfaces/Panel.md) · [Popup](../40%20Specifications/Surfaces/Popup.md) · [Frame](../40%20Specifications/Surfaces/Frame.md) · [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md) · [Style Schema](../41%20TDL%20Reference/Style%20Schema.md)

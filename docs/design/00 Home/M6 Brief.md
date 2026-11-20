---
title: M6 Brief
aliases: [M6, Focus and Keyboard Brief, Shell M6]
type: moc
status: draft
owner: phil
created: 2026-11-08
updated: 2026-11-13
tags: [moc, roadmap, brief]
---

# M6 Brief

> [!NOTE]
> The scope of milestone M6, "focus and keyboard": every widget of [M4 Brief](M4%20Brief.md) can be reached and operated from the keyboard, the user's own shortcut keys work, and the shell can be used without the mouse. The maintainer made this its own milestone on 2026-11-08 ("Focus and keyboard will be its own milestone M6") and moved release to M7. M4 builds the widgets and operates them by the pointer; M6 adds the focus model and the keyboard on top. The shortcut keys register through the D-Bus layer of [M5 Brief](M5%20Brief.md), so M6 follows M5. This is a plan for the maintainer, written to keep the design ahead of the build ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). It starts when the maintainer says go.

## What Moved Here

- The focus model and keyboard operation, which were gap W2 of the first [M4 Brief](M4%20Brief.md) plan: no block can take focus today (D53), and the keyboard-only way into a surface is open (M3 Build Log D102).
- Global shortcuts and the `Shortcuts` block of `settings.tdl`, decided on 2026-11-08 ([Global Shortcuts > Keyboard Access: Shortcuts in settings.tdl (Decided 2026-11-08, Names to Be Determined)](../40%20Specifications/Integration/Global%20Shortcuts.md#keyboard-access-shortcuts-in-settingstdl-decided-2026-11-08-names-to-be-determined)); they were part of the old M5 desktop integration.
- The launcher (it needs a shortcut key, a TextInput and a List), from the old M5.

## State of the Shell Before M6

Written on 2026-11-08, before M4 and M5 are built; the code session's inventory in M4 (task W0) corrects it.

| What M6 builds on | State |
|---|---|
| Surface keyboard modes (`NONE`, `ON_DEMAND`, `EXCLUSIVE`) | Built for the Panel and the Frame in M3: an `on_demand` surface is focused by the compositor on a click |
| Widgets | Built in M4 and operated by the pointer; a clicked text field takes typed text |
| A focus model: Tab order, focus ring, `:focused` | None (D53) |
| The D-Bus layer for shortcut registration | Built in M5a |
| `Shortcuts` block, registration, conflicts | Designed (desktop shortcuts win; two shell actions on one key at the same level both stay unbound, with one warning; any-case key strings; form `Shortcuts { Name: "keys" }`; shortcuts stay changeable at reload); four action names given on 2026-11-10 ([Global Shortcuts](../40%20Specifications/Integration/Global%20Shortcuts.md)) |
| Shortcut modes (`Shortcut_Mode`, `Enter_Shortcut_Mode`, `Exit_Shortcut_Mode`, `Set_Shortcut_Mode`, `Next_Focus`, `Previous_Focus`, `Tab_Index`) | Designed by the maintainer on 2026-11-10 and written as a draft in [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md); not built |

## Goal and Definition of Done

M6 is done when:

- A focus model exists: the widgets that take input can take focus, Tab and Shift+Tab move through a surface in a defined order, the focus ring shows, and `:focused` works as a style selector ([Block Reference > Accessibility Defaults](../41%20TDL%20Reference/Block%20Reference.md#accessibility-defaults)).
- Every widget of M4 is operable from the keyboard as its section of `Standard Modules` says: Enter and Space activate a Button, Toggle and Checkbox; the arrow keys move a Slider, List and Menu and open and close submenus; Escape closes a Popup and returns focus.
- The user's `Shortcuts` in `settings.tdl` are registered and work with no shell surface focused (KDE's global shortcuts; another desktop's mechanism where it has one); conflicts warn as decided; keys are accepted in any case.
- The shell can be used from the keyboard alone: `Enter_Shortcut_Mode` puts the Frame in shortcut mode with focus, `Next_Focus` and `Previous_Focus` move through surfaces by `Tab_Index`, a key puts a focused Panel in its own mode, and Tab and the keys then work ([Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md)).
- The launcher works by key and by pointer.
- A KWin check by the maintainer of each line above, with the keyboard only where the line says so.

Not in M6: character wrapping in text fields (later) and packaging and release (M7). Shortcut modes are in M6 by the maintainer's design of 2026-11-10 ([Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md)); my earlier reading, that modes stay a direction, was replaced by it.

## Proposed Split

| Part | Content | Done when |
|---|---|---|
| M6a: focus | The focus model: focusable widgets, the Tab order, the focus ring, `:focused`, focus on a Popup and back, `Keyboard` mode handling on surfaces | A test layout is traversed by Tab and Shift+Tab headless; the ring shows on KWin |
| M6b: keyboard operation | Each widget's keys (K2): Button, Toggle, Checkbox, Slider, List, Menu and submenus, TextInput and TextEditor with Tab, Expander, peek triggers | The gallery of M4 is operated by the keyboard, one look each |
| M6c: shortcuts | The `Shortcuts` block in `settings.tdl`, registration with the desktop, any-case keys, the conflict warnings, the `Shortcuts` section of the validation | A key press with no surface focused runs its action; a taken key and a shared key warn as decided |
| M6d: keyboard-only access and the launcher | The action that focuses a shell surface, the one that moves focus between surfaces (names to be decided), the launcher (Applications) | The shell is used from the keyboard alone, from a shortcut to a launched application |

Recommendation: build in that order.

## Design Needed First

| # | Gap | State | Recommendation |
|---|---|---|---|
| K1 | The focus model. | Written as [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md), `draft` (maintainer: "As recommended", 2026-11-10; it also carries his shortcut-mode design) | Review before M6a |
| K2 | Keyboard operation of each widget | Written as the Keyboard Operation section of [Standard Modules](../50%20Design%20System/Standard%20Modules.md) ("As recommended, in `Standard Modules`", 2026-11-10); `review` | Checked in M6b |
| K3 | The `Shortcuts` action names and what each does | Partly decided: `Enter_Shortcut_Mode`, `Exit_Shortcut_Mode`, `Set_Shortcut_Mode`, `Next_Focus`, `Previous_Focus` given; the rest to be found by testing, shortcuts kept changeable ([Global Shortcuts > Open Questions](../40%20Specifications/Integration/Global%20Shortcuts.md#open-questions), items 4 and 7) | The list grows from the live test |
| K4 | Shortcuts on a desktop other than KDE | The live test is allowed, with a copy of `kglobalshortcutsrc` first (maintainer, 2026-11-10, as recommended); the portal path is not built in v1 | The live test at the start of M6c; decide the second desktop's mechanism then |
| K5 | The launcher | "As recommended" (2026-11-10): write the Applications module spec before M6d: the desktop-file source, the search through TextInput and List, launching, the key that opens it | Written 2026-11-13: [Applications Module](../40%20Specifications/Modules/Applications%20Module.md), accepted by the orchestrator |
| K6 | Modes | Resolved by the maintainer's design: shortcut mode on a surface, [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md). His answer "As recommended" to K6 (do not build modes) and his design of the same day (build `Shortcut_Mode`) differ; the vault follows the specific design | Per-surface mode, as in the design; nothing broader |

Notes that must be at `review` before a part starts: M6a and M6b need [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md) (`review`, 2026-11-10) and [Standard Modules](../50%20Design%20System/Standard%20Modules.md) (`review`); M6c needs [Global Shortcuts](../40%20Specifications/Integration/Global%20Shortcuts.md) (accepted 2026-11-13), [Settings File](../41%20TDL%20Reference/Settings%20File.md) and [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md); M6d needs [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) (accepted 2026-11-13) and [Portals](../40%20Specifications/Integration/Portals.md) (accepted).

## Tasks

Written by the orchestrator on 2026-11-13. Each task has automated tests; a KWin check by the maintainer is welcome and is not a gate ([Tesserae Shell Directive](Tesserae%20Shell%20Directive.md)).

| # | Task | Done when |
|---|---|---|
| A1 | M6a: `Focusable`, `Tab_Index`, Tab and Shift+Tab order, the focus ring, `:focused`, focus into a Popup and back, the `Keyboard` mode of a surface ([Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md)) | A test layout is traversed headless by simulated keys; the acceptance criteria of [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md) that do not need shortcut mode pass |
| B1 | M6b: the keys of each widget, as the Keyboard Operation table of [Standard Modules](../50%20Design%20System/Standard%20Modules.md) says, including Menu and submenus, the Slider (`On_Changed` then `On_Released` per step), and key events from a text field reaching its module | The M4 galleries are operated headless by key events only, one test per widget |
| C1 | M6c: the `Shortcuts` block: parsing of key strings ([Global Shortcuts > Key Names (Decided 2026-11-13)](../40%20Specifications/Integration/Global%20Shortcuts.md#key-names-decided-2026-11-13)), the action forms ([Global Shortcuts > Action Names and Forms (Decided 2026-11-13)](../40%20Specifications/Integration/Global%20Shortcuts.md#action-names-and-forms-decided-2026-11-13)), registration with KDE's shortcut service through the D-Bus layer, the conflict warnings, changes applied at reload, the key-name list in the schema export | Every criterion of [Global Shortcuts](../40%20Specifications/Integration/Global%20Shortcuts.md) passes against a fake shortcut service on a private bus. No session registers a shortcut with the maintainer's real service; that is a hand check |
| D1 | M6d: shortcut mode (`Shortcut_Mode`, the five actions, all peeks shown in the Frame's mode) ([Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md)) | The remaining criteria of [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md) pass headless |
| D2 | M6d: the application index, `ctx.apps`, the Applications module and the shipped `Launcher` Panel ([Applications Module](../40%20Specifications/Modules/Applications%20Module.md)) | The criteria of [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) pass; the whole flow runs headless by key events only |
| E1 | The accessibility pass: the announcements left to M6 by the Network, Media and Audio specs, names and roles of every shipped module ([Accessibility](../60%20Quality/Accessibility.md)) | Each announcement is asserted in a test through the accessibility tree |

## Dependencies

The widgets of [M4 Brief](M4%20Brief.md); the D-Bus layer of [M5 Brief](M5%20Brief.md) (M5a) for shortcut registration; `tess_re` (focus and key events); `dbus-fast`. A gap found goes to a `TRE-REQ` through the maintainer (AGENTS > 6. Requests Between Projects).

## Risks

- Focus on layer surfaces depends on the compositor: an `on_demand` surface is focused on a click, and the keyboard-only way in needs a global shortcut to focus it. The M6a checks start with a click.
- Registering a shortcut from a non-KDE client is untested ([Global Shortcuts](../40%20Specifications/Integration/Global%20Shortcuts.md)); M6c starts with the live test.
- A shortcut written by the user can collide with the desktop's; the decided rule is that the desktop wins, with a warning.
- Modes, if added later, change what a key means at a level; the per-level conflict rule is written for that.

## Questions for the Maintainer

1. [x] The parts: M6a focus, M6b keyboard operation, M6c shortcuts, M6d keyboard-only access and the launcher (maintainer, 2026-11-10, as recommended).
2. [x] The launcher belongs to M6 (it needs a shortcut), not M5 (maintainer, 2026-11-10, as recommended).
3. [x] K3: the `Shortcuts` action names: see [Global Shortcuts > Open Questions](../40%20Specifications/Integration/Global%20Shortcuts.md#open-questions) (maintainer, 2026-11-10); four given, the rest by testing.
4. [x] K4: the live shortcut test on this machine at the start of M6c, after a copy of `kglobalshortcutsrc` (maintainer, 2026-11-10, as recommended).

## Acceptance Criteria

- [ ] Every line of "Goal and Definition of Done" is true, with a KWin check of each.
- [ ] Each task has a test or a recorded measurement.
- [ ] The notes listed under "Design Needed First" are at `review` before the part that needs them starts, or the maintainer has waived one.
- [ ] Design gaps found are handed back to the vault session.

## Notes

A question asking the maintainer to say go is not written in a brief: he tells `tess-shell` when to start, as he always does (maintainer, 2026-11-10).

## Links

- [M6 Build Log](M6%20Build%20Log.md) · [Development Readiness](Development%20Readiness.md) · [M4 Brief](M4%20Brief.md) · [M5 Brief](M5%20Brief.md) · [Global Shortcuts](../40%20Specifications/Integration/Global%20Shortcuts.md) · [Settings File](../41%20TDL%20Reference/Settings%20File.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [Frame](../40%20Specifications/Surfaces/Frame.md) · [Popup](../40%20Specifications/Surfaces/Popup.md) · [Panel](../40%20Specifications/Surfaces/Panel.md) · [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) · [Portals](../40%20Specifications/Integration/Portals.md) · [V1 Scope](../10%20Vision/V1%20Scope.md)

---
title: Focus and Keyboard
aliases: [Focus Model, Keyboard Model, Shortcut Mode, Tab_Index]
type: spec
status: review
owner: phil
created: 2026-11-10
updated: 2026-11-21
tags: [spec/integration, needs-verification]
---

# Focus and Keyboard

> [!NOTE]
> How keyboard focus moves in the shell and how a user reaches and operates it from the keyboard. It is gap K1 of [M6 Brief](../../00%20Home/M6%20Brief.md) ("As recommended", maintainer, 2026-11-10) and carries the maintainer's design for shortcut modes of the same day: a `Shortcut_Mode` key on a surface, the actions `Enter_Shortcut_Mode`, `Exit_Shortcut_Mode`, `Next_Focus` and `Previous_Focus`, and a `Tab_Index` key. Everything is built in M6; M4 widgets are operated by the pointer. The key and action names below are the maintainer's, from his answer to [Global Shortcuts > Open Questions](Global%20Shortcuts.md#open-questions) item 11; the rest is the vault session's design, a draft for review. Nothing here was tested on a compositor. #needs-verification

## Purpose and Scope

- Give the shell one focus model: what can take focus, in what order, how focus is shown and how a user starts and leaves keyboard use.
- Out of scope: the registration of global shortcuts ([Global Shortcuts](Global%20Shortcuts.md)); per-widget keys (the Keyboard operation section of [Standard Modules](../../50%20Design%20System/Standard%20Modules.md)); the user's key bindings (`Shortcuts` in `settings.tdl`, [Settings File](../../41%20TDL%20Reference/Settings%20File.md)).

## Behaviour

### Focusable Things and the Focus Ring

- A block that takes input (the interactive widgets of [Standard Modules](../../50%20Design%20System/Standard%20Modules.md) and a TextField) can take focus. A `Focusable` key already exists ([Block Reference > State](../../41%20TDL%20Reference/Block%20Reference.md#state)): true on interactive blocks, false otherwise.
- Keyboard focus shows as a ring on the block (the style state `Focused`, `focus_visible` from tre, [Block Reference > Accessibility Defaults](../../41%20TDL%20Reference/Block%20Reference.md#accessibility-defaults)): a non-blurred shadow with spread, so it does not shift layout. A pointer click focuses a block without a ring.
- A surface takes keyboard focus only when its `Keyboard` mode allows it (`NONE`, `ON_DEMAND`, `EXCLUSIVE`, [Surface Types](../Surfaces/Surface%20Types.md)). On Wayland a compositor decides which layer surface has keyboard focus; the shell cannot take it without asking for it (see Entering and Leaving).

### Tab Order: `Tab_Index`

`Tab_Index: <integer>` sets the position of a focusable block or surface in the order Tab and the focus actions follow. Decided by the maintainer (2026-11-10): an integer from 0 to the largest signed 32-bit integer (2 147 483 647).

| Rule | Behaviour |
|---|---|
| Order | Ascending `Tab_Index`; items with the same index keep document order; items with no `Tab_Index` come after all indexed ones, in document order |
| Scope | One order for the shell's surfaces (the level of the Frame, a Panel, a Bar, a strip) and one order inside each surface for its blocks; Next and Previous move within the level that has focus |
| Out of range, or not an integer | A load error with `file:line:column` |
| Where it is held | In memory, rebuilt from the loaded tree at load and at each hot reload (recommended): it is derived data and a file on disk would be a second source of truth that can go stale. A JSON file is not recommended; if one is wanted for tools to read, it is a write-only export |

### Shortcut Mode (the maintainer's design, 2026-11-10)

A surface can be in shortcut mode. It is declared on the surface as a boolean:

```tdl
Panel { Name: Dock, Shortcut_Mode: false }
```

`Shortcut_Mode` is a key of every surface: Frame, Panel, Bar, Popup's parent surfaces and a strip. Rules, as the maintainer gave them:

1. At most one `Shortcut_Mode: true` exists at a time. Setting one to true sets every other to false.
2. Setting a surface to false when no other is true turns shortcut mode off for the whole shell.
3. `Enter_Shortcut_Mode` (an action a global shortcut runs) sets the shell's lowest level to true, the Frame. `Exit_Shortcut_Mode` sets every `Shortcut_Mode` to false and leaves shortcut mode.
4. The Frame has the initial focus when shortcut mode is entered. A developer sets which surface starts with focus by a method in Python (a default focus; the name is for the code session).
5. In shortcut mode, `Next_Focus` and `Previous_Focus` move focus through the Frame's panels, peeks, bars and strips in `Tab_Index` order.
6. With a Panel focused, another shortcut sets `Shortcut_Mode: true` on that Panel, which turns the Frame's off (rule 1): the Panel's own keys apply and the Frame's do not. The action is `Set_Shortcut_Mode` (maintainer, 2026-11-10): one action that toggles `Shortcut_Mode` of the focused surface, from false to true and from true to false. The exact key combinations for entering a mode are the user's and irrelevant to the design.
7. In a Frame with `Shortcut_Mode: true`, every peek shows at the same time, if the surfaces can render together.
8. A hidden Bar is revealed by shortcut mode (maintainer, 2026-11-21, amends the 2026-10-27 "no key reveals a Bar" of [Bar > Auto-hide (Decided 2026-10-27)](../Surfaces/Bar.md#auto-hide-decided-2026-10-27)): entering the mode shows a Bar hidden by `Auto_Hide` and moves focus into it; leaving the mode or Escape hides it again per `Auto_Hide`. Proposed as built, not run in the vault: the reveal uses the Bar's normal show slide, and the focus move is announced like any other ([Accessibility](../../60%20Quality/Accessibility.md)). Open for the code session: the order of the Bar among `Tab_Index` stops when it was hidden.

Consequence of rules 1 and 2 (stated by the maintainer, noted here so it is not a surprise): leaving a Panel's mode by setting it to false turns shortcut mode off for the whole shell, it does not return to the Frame. To go back to the Frame the user presses the Enter action again.

#### How mode keys are delivered (decided 2026-11-10: option A)

The keys that act inside a mode (arrows, `Next_Focus` and `Previous_Focus` while in the mode) must not be registered as global shortcuts for the whole session: a global registration would take those keys from every application. Two ways were considered:

| Way | How | Cost |
|---|---|---|
| A. The mode takes keyboard focus | `Enter_Shortcut_Mode` is the one global key (registered through the desktop). When it fires, the Frame's surface asks for keyboard focus (`Keyboard: ON_DEMAND` or `EXCLUSIVE` for the duration); the mode's keys then arrive as ordinary key events on that surface, and `Exit_Shortcut_Mode` or Escape gives focus back | Needs the compositor to give a layer surface focus after a global key; untested on KWin. While the mode is on, the user's other windows get no typing |
| B. Register mode keys only while the mode is on | On enter, register the mode keys with the desktop; on exit, unregister them | Each registration writes to the user's shortcut settings; a crash leaves them registered; more D-Bus traffic |

Decided: A (maintainer, 2026-11-10, "as recommended"). The live test of [Global Shortcuts > Questions After Testing](Global%20Shortcuts.md#questions-after-testing) item 1 proves the focus handover. The maintainer asked that these be easy to change after testing ("as dynamic as possible and if not then easily changed or tweaked"), so the shell keeps the key bindings of a mode in `settings.tdl` and reads them at reload, with no key hard-coded.

### Entering and Leaving

| Step | What happens |
|---|---|
| Enter | A user key runs `Enter_Shortcut_Mode`: the Frame gets `Shortcut_Mode: true` and focus; all peeks show |
| Move | `Next_Focus` or `Previous_Focus` moves the focus ring to the next surface or block by `Tab_Index` |
| Go in | `Set_Shortcut_Mode` on the focused Panel sets its `Shortcut_Mode: true` (rule 6); its widgets take Tab, Enter, Space and the arrows as the Keyboard operation section of [Standard Modules](../../50%20Design%20System/Standard%20Modules.md) says. Run again, it sets it to false and, by rule 2, ends shortcut mode |
| Leave | `Exit_Shortcut_Mode`, or Escape at the lowest level, sets all to false; focus returns to the window that had it |

### Popups and Focus

A Popup that opens from a focused block takes focus; when it closes, focus returns to the opener ([Accessibility](../../60%20Quality/Accessibility.md) rule 12). A Popup opened by a key never grabs ([Global Shortcuts > A Key Press](Global%20Shortcuts.md#a-key-press): a key opens a Panel and never a Popup), with one exception: a Menu opened from the keyboard takes focus, closes on Escape and returns focus to its opener (maintainer, 2026-11-10). The pointer-only case needs nothing.

Keyboard mode of the mode (maintainer, 2026-11-15): while shortcut mode is on, the Frame's surface uses `EXCLUSIVE`. `Debug { Mode_Keyboard: ON_DEMAND }` switches it for a test. This stands until a KWin check says `ON_DEMAND` is enough ([Questions After Testing](#questions-after-testing) 2).

Selectable text (maintainer, 2026-11-16, relayed by the code session): a `Text` with `Selectable` is not a Tab stop. Nothing is built, it shows no focus ring, and the Tab-stop question left open by M6a and the accessibility pass is closed.

Tab in a `TextEditor`: tre 0.6.8 has the property `tab_navigates` on a multi-line text input, and the shell sets it on every `TextEditor`, so Tab and Shift+Tab leave the field instead of typing a tab character ([TRE-REQ-018 Tab Leaves a Multi-Line Text Input](../../80%20Requests/TRE-REQ-018%20Tab%20Leaves%20a%20Multi-Line%20Text%20Input.md), by the code session's report of 2026-11-15).

## Configuration

| Key | On | Values | Meaning |
|---|---|---|---|
| `Shortcut_Mode` | A surface | true, false (default false) | Whether the surface is in shortcut mode |
| `Tab_Index` | A surface or a focusable block | An integer 0 to 2 147 483 647 | Its place in the order |
| `Focusable` | A block | true, false | As in [Block Reference > State](../../41%20TDL%20Reference/Block%20Reference.md#state) |

Actions (the maintainer's names): `Enter_Shortcut_Mode`, `Exit_Shortcut_Mode`, `Set_Shortcut_Mode`, `Next_Focus`, `Previous_Focus`. They are named in `Shortcuts` in `settings.tdl` with the keys the user chooses, for example `Shortcuts { Enter_Shortcut_Mode: "ctrl+shift+F1" }`; the keys are the user's ([Global Shortcuts > Keyboard Access: Shortcuts in settings.tdl (Decided 2026-11-08, Names to Be Determined)](Global%20Shortcuts.md#keyboard-access-shortcuts-in-settingstdl-decided-2026-11-08-names-to-be-determined)).

## Python Contract

A developer sets the surface that starts with focus, and may set `Shortcut_Mode` at run time through the module context ([Module Context](../../42%20Python%20API/Module%20Context.md)); the names are for the code session. Recommended: `ctx.focus.default = "Dock"` and `ctx.focus.set_mode("Dock", True)`.

## Accessibility

Focus is visible whenever the keyboard moves it ([Accessibility](../../60%20Quality/Accessibility.md)); an announced name and role accompany each move; entering and leaving shortcut mode is announced as a status ([Accessibility](../../60%20Quality/Accessibility.md) rule 6, `POLITE`).

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| Two surfaces start with `Shortcut_Mode: true` in the files | A load warning naming both with `file:line:column`; the first in document order keeps it (rule 1) |
| `Tab_Index` is out of range | A load error naming the position |
| The compositor does not give a layer surface focus | The mode keys do not arrive; one warning; the user can still reach the shell by the pointer |
| Focus is on a surface that closes | Focus goes to the next surface in the order, or the shell leaves shortcut mode if none is left |

## Open Questions

1. [x] Do `Next_Focus` and `Previous_Focus` also work outside shortcut mode as a global pair? No; they act inside the mode only (maintainer, 2026-11-10, as recommended).
2. [x] What is the name of the action that sets `Shortcut_Mode` on the focused Panel? `Set_Shortcut_Mode`, one action that toggles the flag of the focused surface between true and false (maintainer, 2026-11-10).
3. [x] Does a Menu opened from the keyboard take focus and grab input? Yes (maintainer, 2026-11-10): it closes on Escape and returns focus to its opener; settled in M6b.

## Questions After Testing

1. [x] How are mode keys delivered? Option A, the mode takes keyboard focus (maintainer, 2026-11-10, as recommended). Yes, the shell may use `EXCLUSIVE` keyboard mode for the length of the mode if KWin does not hand focus over after a global key (maintainer, 2026-11-10, as recommended); the live KWin test shows whether it is needed.
2. [ ] What are KWin's focus rules for layer surfaces, and which `Keyboard` mode (`ON_DEMAND` or `EXCLUSIVE`) does the mode need? Context: on Wayland the compositor decides which layer surface has keyboard focus. Recommendation: try `ON_DEMAND` first and use `EXCLUSIVE` for the duration of the mode only if KWin does not hand focus over. Answered by: the live KWin test (key press, then check which surface receives key events). Until that test: the maintainer decided on 2026-11-15 that shortcut mode keeps `EXCLUSIVE` as the default and the recommendation to try `ON_DEMAND` first is not taken; `Debug { Mode_Keyboard: ON_DEMAND }` in `settings.tdl` stays as the switch to try the other mode. Built this way in `45f7a9f` (the code session's report).

## Acceptance Criteria

- [ ] `Tab_Index` orders focus as the table says, with a load error for a value outside 0 to 2 147 483 647.
- [ ] Setting one `Shortcut_Mode: true` sets every other to false; setting the last one false turns shortcut mode off.
- [ ] `Enter_Shortcut_Mode` puts the Frame in the mode with focus and shows all peeks; `Exit_Shortcut_Mode` clears every mode.
- [ ] `Next_Focus` and `Previous_Focus` move the focus ring in `Tab_Index` order.
- [ ] A Panel in shortcut mode takes the keys of its widgets and the Frame's mode is off.
- [ ] The focus ring shows for keyboard focus and not for a click.
- [ ] A Popup returns focus to its opener when it closes.

## Links

- [M6 Brief](../../00%20Home/M6%20Brief.md) · [Global Shortcuts](Global%20Shortcuts.md) · [Standard Modules](../../50%20Design%20System/Standard%20Modules.md) · [Accessibility](../../60%20Quality/Accessibility.md) · [Block Reference](../../41%20TDL%20Reference/Block%20Reference.md) · [Frame](../Surfaces/Frame.md) · [Panel](../Surfaces/Panel.md) · [Popup](../Surfaces/Popup.md) · [Settings File](../../41%20TDL%20Reference/Settings%20File.md)

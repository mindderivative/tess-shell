---
title: Events and Actions
aliases: [Events, On_ Events, Built-in Events, Handlers]
type: api
status: review
owner: phil
created: 2026-11-04
updated: 2026-11-14
tags: [api, events, needs-verification]
---

# Events and Actions

> [!NOTE]
> The events a surface or a block can raise, written as `On_<Event>` keys in a TDL file, and the actions a handler can run: a built-in shell action or a module's `@action` method. The v1 set of twelve events and the list of possible later ones are the maintainer's, given on 2026-11-04 (the M3 answers). Events come in two kinds by timing: some run when the request is made, before the thing happens; others run after it has happened. This note is the design for M3b ([M3 Brief](../00%20Home/M3%20Brief.md), G1).

## Purpose and Scope

- Fix the event vocabulary, when each event runs, which blocks and surfaces raise it, the form of a handler, and how a handler reaches Python.
- Not in scope: the lower-level pointer, key and wheel events that [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) already lists (see [Relation to the Older Event Names](#relation-to-the-older-event-names)), and the module context API ([Module Context](Module%20Context.md)).

## The Events

Timing is the maintainer's own wording: a "before" event runs when the event to do the thing is called, not after the thing happens; an "after" event runs when it has happened.

| Event | Key (see [Naming](#naming)) | Timing | Meaning | Raised by |
|---|---|---|---|---|
| Open | `On_Open` | Before | The request to open is made, not after it has opened | Panel, Popup, Frame strip, Expander |
| Close | `On_Close` | Before | The request to close is made, not after it has closed | the same |
| Visible | `On_Visible` | After | The element is actually visible | Surfaces, blocks with `Visible` |
| Hidden | `On_Hidden` | After | The element is actually hidden | the same |
| Focus | `On_Focus` | After | The element has focus | Focusable blocks |
| Unfocus | `On_Unfocus` | After | The element no longer has focus | the same |
| Toggle | `On_Toggle` | Before | The request to toggle is made, not after the toggle happens | Switch-like blocks, Expander, surfaces |
| Click | `On_Click` | Before | The click event is called, not after the click happens | Any block that takes pointer input |
| AnimStart | `On_Anim_Start` | After | The element's animation starts | Animated surfaces and blocks |
| AnimEnd | `On_Anim_End` | After | The element's animation ends | the same |
| Changed | `On_Changed` | After | The change has happened | TextField, Slider, Checkbox and other value blocks |
| Change | `On_Change` | Before | The change event is called, not after the change happens | the same |

Possible later additions, recorded and not built: `Closed` (after a close succeeds), `DoubleClick`, `MouseDown` (button pressed and held), `MouseUp`, `KeyDown`, `KeyUp`, `Input` (all keyboard, mouse and other input codes as `On_Input(Event, Args)`), and `MouseInput` (the mouse codes alone, to separate them from keyboard input).

The events pair up: `Open` then `Visible`, `Close` then `Hidden` (and later `Closed`), `Change` then `Changed`, `Toggle` then `Visible` or `Hidden`.

## Naming

[Common Keys and Conventions](../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md) writes a key of several words with each word Capitalised and joined by `_`, so the keys are `On_Anim_Start`, `On_Anim_End`, and for the later set `On_Double_Click`, `On_Mouse_Down`, `On_Key_Down`, `On_Mouse_Input`. The maintainer wrote the events without the underscores (`AnimStart`, `KeyDown`) and decided on 2026-11-04 to use the underscore rule.

## A Handler

The value of an `On_<Event>` key is one of two forms, decided on 2026-11-01 ([Module Contract](Module%20Contract.md)):

```
Button { On_Click: Open_Launcher }                       # a bare action name
Button { On_Click { Action: Show, Target: Launcher } }   # a block with Action and named arguments (illustrative)
```

- **A bare name** is an `@action` method of the module the block belongs to, or a built-in action.
- **The block form** names the action and gives arguments by name. The argument values are plain values or `<| |>` slots.
- **Built-in actions** are the shell's own: `Show`, `Hide` and `Toggle` (a surface by its unique `Name:`), `Close` (the Popup that holds the block) and `Call` (a module action by name), the same operations as the methods of the control interface ([IPC and CLI > The Interface](../40%20Specifications/Runtime/IPC%20and%20CLI.md#the-interface)). A module's own action shadows no built-in; a clash is a load error.
- A handler receives the event record: the event name, the source block's unique name or module use, a monotonic timestamp, and for `Changed`/`Change` the old and new value.

## How a Handler Runs

1. tre reports a raw event (pointer down and up, focus, an animation completing, a window shown or hidden). The shell turns it into one of the events above on the loop thread.
2. A "before" event runs its handler first; then the shell does the thing (opens the surface, applies the change). An "after" event runs once the shell sees the result.
3. A built-in action is applied between frames. A module action is a Python method called on the loop thread; it returns quickly or hands slow work to a thread ([Module Contract](Module%20Contract.md)).
4. A handler that raises is caught and logged with the module name, the event and the block's `file:line:column`; the event is not repeated and the shell keeps running.

## Where an Event Comes From

| Event | Source in tre or the shell |
|---|---|
| Click | The shell pairs `pointer_down` and `pointer_up` on the same node |
| Focus, Unfocus | tre's `focus` and `unfocus` events (`focus_visible` for keyboard focus, [Block Reference](../41%20TDL%20Reference/Block%20Reference.md)) |
| Visible, Hidden | The window shown or hidden by the shell; a block's `Visible` key changing |
| Open, Close, Toggle | The shell's own surface requests (a built-in action, a shortcut, the control interface) |
| AnimStart, AnimEnd | The shell starts a tre animation; tre's completion listener ends it #needs-verification |
| Change, Changed | A value block's input; `Changed` after the module or the key has taken the value |

## Call, caller.data and Submenus (Decided 2026-11-10)

The maintainer answered "As recommended" to W4 of [M4 Brief](../00%20Home/M4%20Brief.md) on 2026-11-10, so the recommendation there is the decision: `Call` runs a module's `@action` with arguments, a Menu is a Popup whose content is MenuItems, a submenu is a Popup parented to its MenuItem, and `caller.data` is the data the opening block passes. The forms below are the vault session's writing of that decision; the key names are proposals and are marked draft until reviewed.

**Call.** The built-in action that runs a module's `@action` by name, the same operation as the control interface's `Call` ([IPC and CLI > The Interface](../40%20Specifications/Runtime/IPC%20and%20CLI.md#the-interface)). Its target is `<Module>.<action>`, the same spelling as a shortcut action ([Global Shortcuts > Component and Action Names](../40%20Specifications/Integration/Global%20Shortcuts.md#component-and-action-names)):

```tdl
Button { On_Click { Action: Call, Target: "Clock.cycle_format", Format: "24h" } }
```

- `Target` is the module use's name and the action; the other keys are the action's arguments, written as the Python parameters are ([Block Reference > Events](../41%20TDL%20Reference/Block%20Reference.md#events)).
- An argument value is a literal or a `<| |>` slot, evaluated when the event fires. The scope of the slot holds `event`, the module's values, and the variable of an enclosing `For` (decided here: the loop variable may be read in an argument slot, which closes [Workspaces Module](../40%20Specifications/Modules/Workspaces%20Module.md) open question 1; the same rule reads `On_Click { Action: switch, Id: <| desktop.id |> }`).
- An unknown `Target` or an unknown argument is a load error naming the nearest module and action. An argument of the wrong type is a runtime error logged with the position, as for any handler ([How a Handler Runs](#how-a-handler-runs)).
- A module action called through `Call` runs on the loop thread like any action.

**caller.data.** The data the opening block gives a Popup:

```tdl
Button { On_Click { Action: Show, Target: Item_Menu, Data { Title: <| item.name |>, Id: <| item.id |> } } }
```

and in the Popup's content `<| caller.data.Title |>`. From Python, `ctx.popup(name, data={...})` gives the same ([Module Context](Module%20Context.md); D58, D59 in [M3 Build Log](../00%20Home/M3%20Build%20Log.md) built the parameter and refused a slot that reads it).

- `data` is a plain mapping of plain values (text, numbers, booleans, lists, mappings), the same rule as every TEL scope ([TEL Integration](../20%20Architecture/TEL%20Integration.md)). It is copied when the Popup opens and does not follow later changes; it is read-only inside the Popup; it is gone when the Popup closes.
- `caller` is in scope only inside the content of a Popup (and so of a Menu). `caller.data` with no data is an empty mapping. `caller.source` is the opening block's unique name, for logging.
- A slot that reads a key `data` does not have is a runtime warning and renders as empty, not a load error, since the keys are only known when the Popup opens.

**Menu and submenus.** A Menu is a Popup whose content is MenuItems ([Standard Modules > Menu and MenuItem](../50%20Design%20System/Standard%20Modules.md#menu-and-menuitem)). A MenuItem that holds a child `Menu` is a submenu opener: the child opens as a Popup parented to the MenuItem's own Popup, beside the item.

| Rule | Value |
|---|---|
| Opens | On a click on the item, or after the pointer rests on it for 250 ms |
| One at a time | Opening a sibling's submenu closes the open one |
| Closes | When the pointer rests on another item of the parent for 300 ms, when the parent closes, or after a click on an item inside |
| Depth | Up to three levels in v1 (a Menu, a submenu, a submenu of that) |
| A click that reaches an action | Runs it, then closes every open level |
| Data | A submenu's `caller.data` is the data of the item that opened it; the root Menu's data is not inherited |

> [!CAUTION]
> **Whether tre can parent a popup to a popup is not known**
> tre's `PopupWindow` is documented as an `xdg_popup` parented to a layer surface ([Popup](../40%20Specifications/Surfaces/Popup.md)). A submenu is a popup of a popup. The code session probes this at the start of M4c. If tre cannot, the choices are a request to tre (a `TRE-REQ`, carried by the maintainer) or, meanwhile, a submenu that expands inline inside the same Popup. The maintainer decides after the probe. #needs-verification

The keyboard half of submenus (arrow keys open and close a level, Escape closes the innermost) is [M6 Brief](../00%20Home/M6%20Brief.md) and [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md).

### As Built in M4 and Decided 2026-11-13

- `Call` checks its arguments at load against the target action's Python signature, by this rule (proposed by the code session, approved by the maintainer on 2026-11-13, because every shipped action is `def x(self, event)` and reads `event.args`, so reading all names would break Workspaces' `Id`): the parameters after `event` are the action's arguments; an unknown argument is a load finding `unknown-argument` at the handler with the nearest parameter name, and a missing required one is `missing-argument`; a `{ }` argument is checked by name only; the declared arguments reach the action as keywords and `event.args` stays fully filled; an action with only `event` is unchecked and free-form; an action with `**kwargs` takes any names but its required parameters are enforced; one finding per handler however many uses. It applies to `Call` in shell files, Popup content, module layouts and `For` entries, and to a bare action name in a module's layout. `Target` is the module's `Name` (`Clock.cycle_format`); arguments arrive unordered in `event.args`.
- A submenu is declared only as a named Popup (`Submenu: Share_Menu`). The inline form `MenuItem { Children { Menu } }` is left out of v1 (maintainer, 2026-11-13, as recommended).
- A submenu receives the `caller.data` of the Menu that opened it, read-only and inherited (maintainer, 2026-11-13, as recommended). The code session built an empty `caller.data` for a submenu, so this is a change for it.
- `On_Text_Commit` stays silent when `Max_Length` rejects an edit: the shell ignores a commit whose text equals the previous text (maintainer, 2026-11-13, as recommended).

## Relation to the Older Event Names

[Block Reference](../41%20TDL%20Reference/Block%20Reference.md) already lists `On_Click`, `On_Secondary_Click`, `On_Pointer_Down`, `On_Pointer_Up`, `On_Pointer_Enter`, `On_Pointer_Leave`, `On_Wheel`, `On_Scroll`, `On_Key_Down`, `On_Key_Up`, `On_Focus`, `On_Unfocus`, `On_Submit`, `On_Link`, `On_Changed` and `On_Text_Commit` (D80). This note defines the twelve v1 events and their timing. Until the two lists are reconciled, the older names that are not among the twelve stay as they are; the later additions the maintainer listed (`MouseDown`, `MouseUp`, `KeyDown`, `KeyUp`) overlap `On_Pointer_Down`, `On_Pointer_Up`, `On_Key_Down` and `On_Key_Up` and decide which names win.

## Configuration

None. Which event a block can raise is part of its entry in [Block Reference](../41%20TDL%20Reference/Block%20Reference.md).

## Python Contract

```python
from tess_shell import Module, action

class Launcher(Module):
    @action
    def open_launcher(self, event):
        ...        # event.name, event.source, event.time; event.old / event.new for changes
```

The decorator is `action` ([Module Contract](Module%20Contract.md) left its final name open; this note uses it). An action may return nothing; a returned value is ignored in v1.

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| An unknown `On_` key | Load error naming the nearest event keys |
| An unknown action name | Load error naming the module and its actions |
| An event a block cannot raise | Load error: the block does not raise it |
| A handler raises | Logged with the module, event and position; the event is not repeated |
| A handler is slow | The loop is blocked; a handler over 50 ms is logged as slow ([Performance Budgets](../60%20Quality/Performance%20Budgets.md)) |

## Open Questions

1. [x] The spelling of two-word events is the underscore rule: `On_Anim_Start` (maintainer, 2026-11-04).
2. [ ] Can a "before" handler cancel the thing it precedes (a veto)? Context: events run either before or after the thing happens, so a "before" handler could in principle stop it. Recommendation: no veto in v1; a handler only observes and may run an action.
3. [ ] How are the older event names and the later additions reconciled? Context: the twelve v1 events and the list of possible later ones come from the maintainer's M3 answers (see [The Events](#the-events)), and the older names in this note differ in places. Recommendation: keep the maintainer's twelve as the canonical v1 set and list the older names as later additions until each is needed.
4. [ ] What is the final shape of the event record and of `On_Input(Event, Args)`? Context: the handler example reads `event.name`, `event.source`, `event.time`, and `event.old` and `event.new` for changes. Recommendation: fix exactly that record for v1 and add fields only with a new event that needs them.
5. [x] `Call`, `caller.data` and submenus: as recommended (maintainer, 2026-11-10), written above.

## Questions After Testing

1. [ ] Does tre report animation start and end to the shell? #needs-verification Context: `On_Anim_Start` and `On_Anim_End` depend on it. Recommendation: raise them from the shell's own animation timers if tre does not report them. Answered by: a probe of tre's animation reporting.
2. [ ] Can tre parent a popup to a popup? Context: submenus in `Call` need it (question 5 above). Recommendation: if tre cannot, open the submenu as a sibling popup positioned beside its parent. Answered by: the M4c tre probe.

## Acceptance Criteria

- [ ] Each of the twelve events has a test that raises it and sees its handler run.
- [ ] A "before" handler runs before the surface opens; a `Visible` handler runs after the surface is shown.
- [ ] A click calls the module's action on the loop thread with the event record.
- [ ] An unknown event key and an unknown action name each fail at load with the nearest names.
- [ ] A handler that raises does not stop the shell and is logged once.

## Links

- [Module Contract](Module%20Contract.md) · [Module Context](Module%20Context.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [Panel](../40%20Specifications/Surfaces/Panel.md) · [Popup](../40%20Specifications/Surfaces/Popup.md) · [IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md) · [M3 Brief](../00%20Home/M3%20Brief.md)

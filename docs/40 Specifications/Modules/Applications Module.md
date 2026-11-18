---
title: Applications Module
aliases: [Applications, Applications_Module, Launcher, App Launcher]
type: spec
status: accepted
owner: phil
created: 2026-11-13
updated: 2026-11-17
tags: [spec/module, needs-verification]
---

# Applications Module

> [!NOTE]
> The launcher: a Panel that opens from a key, with a text field and a list of installed applications that narrows as the user types; Enter starts the selected one. It is gap K5 of [M6 Brief](../../00%20Home/M6%20Brief.md) and is built in M6d. The applications come from desktop entry files, not from a D-Bus service (decided 2026-11-12, [D-Bus Service Layer > Open Questions](../Integration/D-Bus%20Service%20Layer.md#open-questions)). The index of desktop entries is a shell service shared with [Tasks Module](Tasks%20Module.md). Written and decided by the orchestrator under the [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md). The rules for desktop entries follow the [Desktop Entry Specification](https://specifications.freedesktop.org/desktop-entry-spec/latest/); on the maintainer's machine `~/.local/share/applications` and `/usr/share/applications` hold 212 entries, and `XDG_DATA_DIRS` also names two Flatpak export folders (read 2026-11-13).

## Purpose and Scope

- Find an installed application by typing and start it, from the keyboard alone or with the pointer.
- v1: applications only. Not in v1: files, calculator, web search, commands, KRunner as a backend, desktop actions (an entry's extra `Actions`), categories and a browsable grid, pinned favourites.

## Files

```
Modules/Applications/
    Applications_Module.tdl    the field and the list
    Applications_Style.tdl     the look
    Applications_Module.py     the logic
```

The shipped default shell also carries a Panel named `Launcher` that holds the module, so a user gets a launcher by binding one key.

## Behaviour

### The Application Index (a Shell Service)

`ctx.apps`, shared by this module and by the icon lookup of [Tasks Module > Icons](Tasks%20Module.md#icons):

| Rule | Detail |
|---|---|
| Where | The `applications` folder of `XDG_DATA_HOME` (default `~/.local/share`) and of each entry of `XDG_DATA_DIRS` (default `/usr/local/share:/usr/share`), sub-folders included. An entry's id is its path below that folder with `/` replaced by `-`. The first folder that has an id wins |
| Which entries | `Type=Application`, not `Hidden=true`, not `NoDisplay=true`, passing `OnlyShowIn` and `NotShowIn` against `XDG_CURRENT_DESKTOP`, and, when `TryExec` is set, its program found on the path |
| What is kept | `Name`, `GenericName`, `Comment`, `Keywords`, `Icon`, `Exec`, `Terminal`, `Path`, `StartupWMClass`, each localised value (`Name[de]`) chosen by the locale in `LC_MESSAGES`, then `LANG` |
| When it is built | On the first use, on a worker thread, never on the loop thread. The folders are watched with inotify (a dependency the shell already has), and a change rebuilds the index after 500 ms of quiet |
| A broken entry | Skipped, with one debug line naming the file; a broken file never stops the index |

### Search

The query is what the field holds, compared without case and without accents. An entry matches when every word of the query matches it. The rank of one word, best first:

1. The start of `Name`.
2. The start of a word in `Name`.
3. Anywhere in `Name`.
4. The start of a word in `GenericName` or a `Keywords` entry.
5. Anywhere in `GenericName`, `Keywords` or `Comment`.

Entries of equal rank are ordered by how often the user started them (a count per id kept in the shell's state folder), then by name. An empty query lists the most often started applications, then the rest by name. The list holds at most `max_results` entries.

### Values Sent

| Key | Type | Meaning |
|---|---|---|
| `ready` | boolean | The index is built |
| `query` | string | The field's text |
| `results` | list | `id`, `name`, `comment` (the `GenericName`, else the `Comment`), `icon` |
| `selected` | number | The index of the selected result, 0 when the list changes |
| `has_results` | boolean | The list is not empty |

### Keys and Clicks

The text field keeps the keyboard focus while the list is shown; the list's selection is moved from the field ([Standard Modules > Keyboard Operation (M6)](../../50%20Design%20System/Standard%20Modules.md#keyboard-operation-m6)).

| Input | Effect |
|---|---|
| Typing | `search`: the list narrows; the first result is selected |
| Down, Up | The selection moves and wraps; Page Down and Page Up move by the rows shown |
| Enter | Starts the selected result |
| Escape | With text: clears the field. Without text: hides the Panel |
| A click on a result | Starts it |
| Hover | Does not change the selection (the pointer resting over the list must not fight the keys) |

After an application is started the field is cleared and the Panel hides.

### Opening

- The Panel opens from a shortcut action, `Toggle_Launcher` ([Global Shortcuts > Action Names and Forms (Decided 2026-11-13)](../Integration/Global%20Shortcuts.md#action-names-and-forms-decided-2026-11-13)), or from a click on any block with `On_Click { Action: Toggle, Target: Launcher }`.
- When the Panel shows, the text field takes the keyboard focus and its text is selected, so typing starts a new search. This is the default-focus call of [Focus and Keyboard > Python Contract](../Integration/Focus%20and%20Keyboard.md#python-contract). The Panel's `Keyboard` is `EXCLUSIVE` (decided by the maintainer on 2026-11-16, "proceed as recommended"): it is verified on his real KWin, where the keyboard is gained at once, while `ON_DEMAND` got no keys without a click on sway and was never tried on KWin.
- Closing: Escape, starting an application and the shortcut toggle close the Panel. A click outside the Panel does not hide it, and nothing is built for that (maintainer, 2026-11-16). If it is wanted later it is shell-side and needs no tre request: a transparent full-output click-catcher Panel under the Launcher, with stacking untested.
- The Panel's size is fixed at 480 by 400 (maintainer, 2026-11-16). On 2026-11-17 the maintainer asked for a content-sized layer surface so that a short result list leaves no empty space, with the Panel's padding kept: when [TRE-REQ-022 Content-Sized Layer Surface](../../80%20Requests/TRE-REQ-022%20Content-Sized%20Layer%20Surface.md) is built the Launcher becomes `Width: 480`, `Height: AUTO`, `Max_Height: 400` ([Panel > Content-Sized Panels That Follow Their Content (Decided 2026-11-17; Needs TRE-REQ-022)](../Surfaces/Panel.md#content-sized-panels-that-follow-their-content-decided-2026-11-17-needs-tre-req-022)). Until then it stays fixed.
- Click-away closing waits for tre: either an outside-press or a keyboard-leave signal, whichever tre can build ([TRE-REQ-024 Outside Press and Keyboard Leave on Layer Surfaces](../../80%20Requests/TRE-REQ-024%20Outside%20Press%20and%20Keyboard%20Leave%20on%20Layer%20Surfaces.md)).

### Starting an Application

1. The `Exec` value is split by the specification's quoting rules. The field codes `%f`, `%F`, `%u`, `%U` are removed (nothing is passed), `%i` becomes `--icon <Icon>` when `Icon` is set, `%c` the localised name, `%k` the file's path, `%%` a percent sign; a deprecated code is removed.
2. The program is started detached from the shell: its own session, the working folder from `Path` or the user's home, the shell's environment without the shell's own variables. When `systemd-run` is on the path it runs as a transient user scope named `app-<id>-<random>.scope`, so the application has its own control group and outlives the shell; otherwise as a plain detached process.
3. `Terminal=true`: the command is run through `xdg-terminal-exec` when that is on the path; otherwise nothing starts and one warning names the entry.
4. `DBusActivatable=true` is not used in v1; `Exec` is.
5. The start count of the id is raised and written to the state folder.

Focus for the new window (tre 0.6.8 has `Window.request_activation_token(callback, app_id=None)`, released 2026-11-15 and the shell's floor is now 0.6.8, so the call no longer needs a `hasattr` guard): on Wayland an application gets focus at start only with an activation token from the launching surface (`xdg_activation_v1`), passed as `XDG_ACTIVATION_TOKEN`. `tess_re` 0.6.7 has no call for it (`tess-re`'s report of 2026-11-13); it was added on `tess-re`'s main on 2026-11-13 (#300, after 0.6.7, not released) as `window.request_activation_token(callback, app_id=None)` on `Window` and `LayerWindow`; the callback gets the token or `None` on the loop thread ([Upgrading to 0.6.x](https://mindderivative.github.io/tess-re/migrating-0.6/); the vault has not read the page since the merge #needs-verification). The token must be requested inside the key or click handler that starts the application, because a compositor honours a token only with a recent input serial. The launcher uses the call when the engine has it. Without a token the application still starts; KWin may open its window without focus.

### Layout (`Applications_Module.tdl`)

```
Module {
    Style: Applications_Style.tdl
    Params {
        max_results { Type: number, Default: 8 }
        show_comment { Type: boolean, Default: true }
        icon_size { Type: number, Default: 24 }
        placeholder { Type: string, Default: "Search applications" }
    }

    FlexBox {
        Flex: VERTICAL
        Children {
            TextInput {
                Name: query
                Text: <| query |>
                Placeholder: <| placeholder |>
                On_Changed { Action: search, text: <| event.value |> }
                On_Submit: launch_selected
            }
            If <| has_results |> {
                List {
                    Selected_Index: <| selected |>
                    For app In <| results |> Key <| app.id |> {
                        MenuItem {
                            icon: <| app.icon |>
                            label: <| app.name |>
                            On_Click { Action: launch, id: <| app.id |> }
                        }
                    }
                }
            }
        }
    }
}
```

A sketch; the code session aligns the spellings with what is built. The shipped Panel:

```
Panel {
    Name: Launcher
    Visible: false
    Keyboard: EXCLUSIVE
    Width: 480
    Children { Applications { } }
}
```

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `max_results` | number | 8 | Rows shown |
| `show_comment` | boolean | true | The generic name or comment under each name |
| `icon_size` | number | 24 | The icon's size |
| `placeholder` | string | "Search applications" | The field's hint |

## Needs from the Shell

| Need | Shape |
|---|---|
| The index | `ctx.apps`: `ready`, `search(query, limit)`, `get(id)`, `launch(id)`, `on_changed(callback)`; `ctx.icons.app_icon(id, size)` over the same index |
| Focus on show | The default-focus call of [Focus and Keyboard](../Integration/Focus%20and%20Keyboard.md) (M6a) and a way for a module to hide its own surface (`ctx.surface.hide()`, the name is the code session's) |
| Arrow keys from a text field | No engine change is needed (`tess-re`'s report, 2026-11-13, headless): a `key_down` listener on a single-line `text_input` hears every key before the field acts and cannot veto it; the field does nothing with Up and Down, fires `submit` on Enter, and does not use Escape. The shell routes those keys from the TextInput to the module's actions, and makes sure the Panel's own Escape-hides rule does not also fire while the field has text (M6b) |
| The opening key | The `Toggle_<Name>` shortcut action (M6c) |

## Python Contract

One instance. `start` asks for the index; `search` runs on the loop thread against the built index (a list in memory) and sends `results`; `launch` hands the start to a worker. No timer. The start count file is written by the worker, with a temporary file and a rename.

## Integration

- Files: desktop entries, the icon theme (through the icon service), one count file in the shell's state folder.
- Processes: the started application, detached. The shell never waits for it.
- Tests: no test starts a real application or reads the user's real `applications` folders ([Orchestration Log](../../00%20Home/Orchestration%20Log.md) D-019). Tests point `XDG_DATA_HOME` and `XDG_DATA_DIRS` at temporary folders with made-up entries and replace the starter with a recorder; one test starts a made-up entry whose `Exec` is a script in the temporary folder that writes a marker file, to prove the detached start and the field codes.

## Design

A text field over a list of rows, each an icon, a name and a faint comment; the selected row uses the `:selected` look. The Panel uses the surface and elevation tokens of the theme.

## Accessibility

- The field's name is the placeholder; the list is a list box whose selected row is announced as the selection moves, while focus stays in the field (the active-descendant pattern). tre built the relation on a local branch on 2026-11-17 ([TRE-REQ-023 Active Descendant](../../80%20Requests/TRE-REQ-023%20Active%20Descendant.md)); until it is released each move is a polite announcement through `ctx.announce`, which is `Window.announce` since the shell's engine floor became 0.6.9 (no live region and no zero-width mark any more).
- "No results" is announced when a query matches nothing.
- Everything works from the keyboard alone, which is the acceptance test of M6d.

## Performance Budget

- Building the index of 500 entries: under 150 ms, off the loop thread; the Panel is usable before it finishes (`ready` false shows an empty list).
- One search over 500 entries: under 2 ms.
- A keystroke to the list updated: within one frame (16 ms).
- Idle: no timer; the folder watch wakes the shell only when an entry file changes.

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| No `applications` folder exists | An empty index; the list shows "No applications found" |
| An entry file is malformed | Skipped, one debug line |
| The `Exec` program is missing at start | One warning naming the entry; the Panel stays open with the text "Could not start <name>" |
| `Terminal=true` and no `xdg-terminal-exec` | One warning; nothing starts |
| `systemd-run` fails | The plain detached start is used; one debug line |
| The count file cannot be written | One warning; ranking uses the counts in memory |
| A folder watch cannot be set (inotify limit) | One warning; the index is rebuilt each time the Panel opens |
| The callback raises | Caught and logged with the module name ([Module Contract](../../42%20Python%20API/Module%20Contract.md)) |

## Open Questions

Decided by the orchestrator on 2026-11-13 ([Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md) rule 7, Tier 1; [Orchestration Log](../../00%20Home/Orchestration%20Log.md) D-048).

1. [x] Where do applications come from? Desktop entry files; KRunner is not used.
2. [x] How is an application started? Detached, in a transient user scope when `systemd-run` exists; D-Bus activation is not used in v1.
3. [x] Is the launcher a Popup or a Panel? A Panel: a key opens a Panel and never a Popup ([Global Shortcuts > A Key Press](../Integration/Global%20Shortcuts.md#a-key-press)).
4. [x] Does the ranking learn? Yes, by a start count per application, kept locally.
5. [x] Does it list `Terminal=true` applications? Yes; they start through `xdg-terminal-exec`.

## Questions After Testing

1. [ ] Does KWin give a started application's window focus when the launcher passes an activation token? Context: `tess_re` could not request a token (report of 2026-11-13); the call is being added (T-051) and its round trip is testable on sway, but KWin's behaviour is not. Recommendation: use the token when present and start without one otherwise. Answered by: a hand check on KWin once T-051 is merged.
2. [x] Does KWin hand keyboard focus to the Panel when it opens from a global key? Answered 2026-11-16 for `EXCLUSIVE`: yes, the Launcher opened from a global key gets the keyboard at once on the maintainer's real KWin (the code session's real-session run, with his yes); `ON_DEMAND` was not tried there, and the maintainer chose `EXCLUSIVE`. Original text: Context: the same question as shortcut mode ([Focus and Keyboard > Questions After Testing](../Integration/Focus%20and%20Keyboard.md#questions-after-testing)). Recommendation: `ON_DEMAND` first, `EXCLUSIVE` while open if needed. Answered by: a hand check on KWin.

## Acceptance Criteria

All with temporary data folders and a recorded starter unless a line says otherwise.

- [ ] Entries that are hidden, `NoDisplay`, of another type, excluded by `OnlyShowIn` or `NotShowIn`, or whose `TryExec` program is missing are not listed; an id in the user's folder hides the same id in a system folder.
- [ ] A localised name is used for the matching locale and the plain name otherwise.
- [ ] The five rank levels order the results as the table says; the start count breaks ties; an empty query lists the most started first.
- [ ] Typing narrows the list within one frame; Down and Up move the selection and wrap; Enter starts the selected entry; Escape clears, then hides.
- [ ] The field has the keyboard focus when the Panel shows, with its text selected; after a start the field is empty and the Panel hidden.
- [ ] `Exec` parsing: quoting, `%f %F %u %U` removed, `%i`, `%c`, `%k`, `%%`, each against the specification's examples.
- [ ] One real detached start of a made-up entry inside the temporary folder writes its marker file, and the process is not a child of the shell afterwards.
- [ ] Adding and removing an entry file changes the list without a restart.
- [ ] With the index built and nothing changing, no wake-ups over 60 seconds.
- [ ] No test reads the user's real `applications` folders or starts a real application.
- [ ] The whole flow passes headless with key events only: the toggle action, typing, Down, Enter.

## Links

- [Modules](Modules.md) · [M6 Brief](../../00%20Home/M6%20Brief.md) · [Focus and Keyboard](../Integration/Focus%20and%20Keyboard.md) · [Global Shortcuts](../Integration/Global%20Shortcuts.md) · [Tasks Module](Tasks%20Module.md) · [Tray Module](Tray%20Module.md) · [Standard Modules](../../50%20Design%20System/Standard%20Modules.md) · [Panel](../Surfaces/Panel.md) · [Module Context](../../42%20Python%20API/Module%20Context.md) · [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md)

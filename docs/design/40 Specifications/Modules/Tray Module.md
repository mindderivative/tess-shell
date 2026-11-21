---
title: Tray Module
aliases: [Tray, Tray_Module, System Tray, StatusNotifier Host]
type: spec
status: accepted
owner: phil
created: 2026-11-13
updated: 2026-11-14
tags: [spec/module, integration/dbus, needs-verification]
---

# Tray Module

> [!NOTE]
> The Tray module shows the system tray: one icon per application that registers a StatusNotifierItem, with its tooltip, a click that activates it, and its context menu drawn by the shell from the application's `com.canonical.dbusmenu` menu. The shell is a second tray host next to Plasma's ([Plasma Coexistence > Tray](../Integration/Plasma%20Coexistence.md#tray), coexist). It settles two gaps of [M5 Brief](../../00%20Home/M5%20Brief.md): G8, how an icon name from an application becomes pixels, and G9, the menu. The members were read on the maintainer's machine on 2026-11-13 (read-only `busctl`; one item present) and follow the [StatusNotifierItem specification](https://www.freedesktop.org/wiki/Specifications/StatusNotifierItem/) #needs-verification for members this machine did not show. Written and decided by the orchestrator under the [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md); M5f builds it.

## Purpose and Scope

- Show every tray item, activate it on click, open its menu, show its tooltip.
- v1: items that speak StatusNotifierItem. Not in v1: the old XEmbed tray (X11 windows), animated attention icons (`AttentionMovieName`), a hidden-items overflow, re-ordering by the user.

## Files

```
Modules/Tray/
    Tray_Module.tdl      the row of items
    Tray_Menu.tdl        the Popup that draws an item's menu
    Tray_Style.tdl       the look
    Tray_Module.py       the logic
```

## Behaviour

### What It Reads

Session bus.

| Object | Member | Use | Read on 2026-11-13 |
|---|---|---|---|
| `org.kde.StatusNotifierWatcher` at `/StatusNotifierWatcher` (owned by `kded6`) | `RegisteredStatusNotifierItems` (as) | The items, each as `<bus name><object path>` | One: `org.kde.StatusNotifierItem-927553-1/StatusNotifierItem` |
| | signals `StatusNotifierItemRegistered` (s), `StatusNotifierItemUnregistered` (s) | Items coming and going | Present |
| | `RegisterStatusNotifierHost` (s), `IsStatusNotifierHostRegistered` (b) | The shell registers as a host | Present; a host is registered (Plasma's); `ProtocolVersion` 0 |
| An item, interface `org.kde.StatusNotifierItem` | `Id`, `Title`, `Category`, `Status` (s) | Identity; `Status` is `Passive`, `Active` or `NeedsAttention` | "Cachy-Update", "Cachy-Update", "SystemServices", "Active" |
| | `IconName` (s), `IconPixmap` (a(iiay)), `IconThemePath` (s) | The icon | `IconName` "cachy-update_updates-available-blue"; no pixmap; empty theme path |
| | `AttentionIconName`, `AttentionIconPixmap`, `OverlayIconName`, `OverlayIconPixmap` | The attention icon and an overlay | All empty |
| | `ToolTip` ((sa(iiay)ss)): icon name, icon pixmap, title, text | The tooltip | Title "Cachy-Update", text "95 updates available" |
| | `Menu` (o), `ItemIsMenu` (b) | The menu object; whether a click opens the menu | `/MenuBar`; false |
| | signals `NewIcon`, `NewAttentionIcon`, `NewOverlayIcon`, `NewTitle`, `NewToolTip`, `NewStatus` (s) | Re-read the matching property | Present. The properties carry `emits-change` here, but the specification's way is these signals, so the module listens to the signals |
| | methods `Activate` (ii), `SecondaryActivate` (ii), `ContextMenu` (ii), `Scroll` (is) | The clicks; the two integers are screen coordinates | Present; not called |
| The menu, interface `com.canonical.dbusmenu` at the `Menu` path | `GetLayout` (iias), `AboutToShow` (i), `Event` (isvu), signals `LayoutUpdated` (ui), `ItemsPropertiesUpdated` | The menu's tree and clicks | `Version` 3; `GetLayout(0, -1, [])` returned a root with `children-display: submenu`, an entry labelled "95 updates available" and a submenu "All (95)" with 95 entries |

### The Host

The shell registers as a tray host, as [Plasma Coexistence > Tray](../Integration/Plasma%20Coexistence.md#tray) decided: it owns the bus name `org.kde.StatusNotifierHost-<pid>` and calls `RegisterStatusNotifierHost` with that name. Owning a name is new for the layer ([Needs from the Shell](#needs-from-the-shell)). If the watcher is absent the module is hidden and waits for it (`on_service_found`); the shell does not start a watcher of its own in v1.

### Values Sent

| Key | Type | Meaning |
|---|---|---|
| `has_items` | boolean | The root is `Visible: <\| available and has_items \|>` |
| `items` | list | One entry per shown item, in the order of registration: `id` (the bus name and path), `title`, `status`, `icon` (an icon reference, Icons), `tooltip_title`, `tooltip_text`, `attention` (boolean) |

A `Passive` item is not shown unless `show_passive` is true. An item whose `Status` is `NeedsAttention` shows its attention icon when it has one, and `attention` is true so the style can mark it.

### Clicks

| Input | Call |
|---|---|
| Primary click | `Activate(x, y)`; when `ItemIsMenu` is true, the menu opens instead |
| Middle click | `SecondaryActivate(x, y)` |
| Secondary click | The shell's own menu from the item's `Menu` object; when the item has no `Menu`, `ContextMenu(x, y)` so the application shows its own |
| Scroll | `Scroll(delta, "vertical")` |

`x` and `y` are the centre of the item on the screen in the compositor's coordinates, as far as the shell knows them (the anchor rectangle of the click; [Popup > What the Popup Knows](../Surfaces/Popup.md#what-the-popup-knows)). An application that places its own window from them may be off on Wayland; that is the application's limit.

### The Menu (G9)

The shell draws the menu itself, in a Popup, from `com.canonical.dbusmenu`:

1. On a secondary click: `AboutToShow(0)`, then `GetLayout(0, -1, [])` for the whole tree, then the Popup opens with the tree as `caller.data`.
2. Each node becomes a `MenuItem` through a `For` (a module call in a `For` inside a Popup, built in M5): `label` (an underscore marks a mnemonic and is removed), `enabled`, `visible`, `icon-name` or `icon-data` (PNG bytes), `type` (`separator` draws a line), `toggle-type` (`checkmark` or `radio`) with `toggle-state`, and `children-display: submenu` for a submenu, opened as a named submenu Popup ([Events and Actions > As Built in M4 and Decided 2026-11-13](../../42%20Python%20API/Events%20and%20Actions.md#as-built-in-m4-and-decided-2026-11-13)).
3. A click on an entry sends `Event(id, "clicked", <empty variant>, timestamp)` and closes the menu.
4. `LayoutUpdated` and `ItemsPropertiesUpdated` while the menu is open re-read the tree and rebuild the open Popup's entries.
5. A submenu is fetched with the tree in step 1; a menu deeper than three levels shows its first three ([Events and Actions](../../42%20Python%20API/Events%20and%20Actions.md), three levels).

A long menu (the one read has 95 entries in a submenu) scrolls: the Popup's content is a `ScrollBox` capped at 60 % of the screen's height.

### Icons (G8)

An item gives a name, pixmaps, or both. The shell turns them into pixels in this order and hands tre decoded pixels or an SVG document, never a path ([Vault Reference > Layering principle](../../00%20Home/Vault%20Reference.md#layering-principle)):

1. `IconName` looked up in the item's `IconThemePath` (when set), then in the user's icon theme, then in the themes it inherits, then in `hicolor`, by the [Icon Theme Specification](https://specifications.freedesktop.org/icon-theme-spec/latest/): the folders `$XDG_DATA_HOME/icons`, each of `$XDG_DATA_DIRS/icons`, and `/usr/share/pixmaps`; each theme's `index.theme` gives its folders, sizes and `Inherits`. A scalable SVG is preferred; otherwise the PNG whose size is nearest above the wanted size times the scale.
2. `IconPixmap` when the name gives nothing: the entry nearest above the wanted size; the bytes are ARGB32 in network byte order and are converted to the engine's RGBA.
3. The shipped `mdi` icon `application-outline` when both give nothing.

The user's theme name is read from the portal's settings where it offers it, else from `kdeglobals` (`[Icons] Theme`; read on this machine as `breeze-dark`), else `hicolor`. The item read on 2026-11-13 resolves to `/usr/share/icons/hicolor/scalable/apps/cachy-update_updates-available-blue.svg`.

The lookup is a service of the shell, not of this module, because Tasks (M5g) and the launcher (M6) need it too: `ctx.icons.theme_icon(name, size, theme_path=None)` returns an icon reference a block's `Icon:` accepts ([Block Reference > Icons (R7)](../../41%20TDL%20Reference/Block%20Reference.md#icons-r7) already lists the freedesktop theme second in the lookup order). Theme folders are indexed once on first use and again when the theme changes; a lookup reads no folder after that.

### Layout (`Tray_Module.tdl`)

```
Module {
    Style: Tray_Style.tdl
    Visible: <| available and has_items |>
    Params {
        icon_size { Type: number, Default: 18 }
        show_passive { Type: boolean, Default: false }
        spacing { Type: number, Default: 6 }
    }

    FlexBox {
        Flex: HORIZONTAL
        Spacing: <| spacing |>
        Children {
            For item In <| items |> Key <| item.id |> {
                Tray_Item {
                    icon: <| item.icon |>
                    size: <| icon_size |>
                    tooltip_title: <| item.tooltip_title |>
                    tooltip_text: <| item.tooltip_text |>
                    Selected: <| item.attention |>
                    On_Click { Action: activate, id: <| item.id |> }
                    On_Middle_Click { Action: secondary, id: <| item.id |> }
                    On_Secondary_Click { Action: menu, id: <| item.id |> }
                    On_Scroll { Action: scroll, id: <| item.id |>, delta: <| event.delta |> }
                }
            }
        }
    }
}
```

A sketch; the code session aligns the spellings with what is built. `Tray_Item` is a small module in the same folder (an `Icon` with a `Tooltip`).

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `icon_size` | number | 18 | The icon's size in pixels |
| `show_passive` | boolean | false | Show items whose status is `Passive` |
| `spacing` | number | 6 | Space between items |

## Needs from the Shell

All inside `tess-shell` (Tier 1):

| Need | Shape |
|---|---|
| Owning a bus name | `bus.own_name(name)` for a shell service only, not offered to user modules through `ctx.dbus` (which stays unable to own a name, [D-Bus Service Layer > Own Names and Objects](../Integration/D-Bus%20Service%20Layer.md#own-names-and-objects)); re-requested through `Bus.on_reconnect` |
| The theme icon lookup | `ctx.icons.theme_icon(name, size, theme_path=None)`, with the index and the pixmap conversion; shared with Tasks and the launcher |
| Signals without `PropertiesChanged` | `proxy.on_signal` (built in M5a) for `NewIcon` and the others, followed by a `get(..., fresh=True)` |
| A middle click and a scroll on a block | `On_Middle_Click` and `On_Scroll` among the event keys ([Events and Actions](../../42%20Python%20API/Events%20and%20Actions.md)); built here if not yet |
| The screen position of a click | The anchor rectangle the Popup already gets |

## Python Contract

One instance. It keeps a table of items by bus name and path, with a proxy each (`optional=True`, so `available` follows the watcher only). The watcher's two signals add and remove entries; `bus.forget` drops a gone item's name. Icon lookups run on the `dbus` thread or a worker, never on the loop. The menu's tree is fetched on demand and not kept after the Popup closes.

## Integration

- Services: the watcher (`kded6`), every item, each item's menu. The shell owns one name for the host.
- Plasma: its tray shows the same items; both hosts may activate them ([Plasma Coexistence](../Integration/Plasma%20Coexistence.md)).
- Files: icon theme folders and `index.theme` files are read by the shell. No network, no subprocess.
- Tests: a fake watcher, fake items and a fake dbusmenu on a private bus; a temporary icon theme folder. No test touches the real session bus or calls a real item's method ([Orchestration Log](../../00%20Home/Orchestration%20Log.md) D-019, D-025).

## Design

Icons in a row at one size; an item that needs attention uses the `:selected` look with the warning token. The menu uses `Menu` and `MenuItem` from [Standard Modules](../../50%20Design%20System/Standard%20Modules.md).

## Accessibility

- The module's name is "Tesserae Shell tray", so a screen reader user can tell it from Plasma's ([Plasma Coexistence](../Integration/Plasma%20Coexistence.md)).
- Each item's name is its `Title`, with the tooltip text as the description; a status of `NeedsAttention` is said in the name.
- Menu entries carry their label, checked state and disabled state.
- Keyboard operation is M6.

## Performance Budget

- Idle: no timer; wake-ups only on the watcher's and items' signals.
- Per signal: under 1 ms of the module's own work; an icon lookup after the index is built: under 1 ms; building the index for one theme chain: under 100 ms, once, off the loop thread.
- Opening a menu of 100 entries: the Popup shows within 100 ms of the click on this machine. Measured after the cheap measure of 2026-11-13 (code session's report): 60 to 86 ms on a quiet machine, 95 to 118 ms with 24 busy loops running. A budget is read on an otherwise idle machine, so it is met; building only the rows that fit is the next step if longer menus need it.

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| No watcher on the bus | Hidden; shows when the watcher appears |
| The watcher restarts | The shell registers its host again and re-reads the items |
| The host name is taken | `-<pid>-<n>` with the next `n`; after three tries one error and nothing shown ([Plasma Coexistence](../Integration/Plasma%20Coexistence.md)) |
| An item leaves without unregistering | Its name loses its owner; the item is removed |
| An item's property read fails or times out | The item is shown with what was read; a missing icon uses the fallback |
| An icon name resolves nowhere and there is no pixmap | `application-outline` |
| A pixmap has a wrong length for its size | Ignored, with one warning naming the item |
| An item has no `Menu` | Secondary click calls `ContextMenu` |
| `GetLayout` fails | One warning; no menu opens |
| A menu entry's `Event` call fails | Logged once a minute per item; the menu closes |
| A callback raises | Caught and logged with the module name ([Module Contract](../../42%20Python%20API/Module%20Contract.md)) |

## Open Questions

Decided by the orchestrator on 2026-11-13 ([Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md) rule 7, Tier 1).

1. [x] Does the shell draw the menu or ask the application to? The shell draws it from `com.canonical.dbusmenu`; `ContextMenu` is the fallback when an item has no menu.
2. [x] Is the old XEmbed tray supported? No.
3. [x] Where does the icon lookup live? In the shell, as `ctx.icons.theme_icon`, shared by Tray, Tasks and the launcher.
4. [x] Are passive items shown? Not by default; `show_passive` shows them.
5. [x] Does the shell start a watcher when none exists? No in v1; the module waits.
6. [x] Where does the icon theme's name come from? The portal's settings where offered, else `kdeglobals`, else `hicolor`.

## Questions After Testing

1. [ ] Do common tray applications (a chat client, a cloud sync client, Steam) behave as the specification says, in particular the `New*` signals, pixmap-only icons and `ItemIsMenu`? Context: one item was read. Recommendation: keep the design; fix per finding. Answered by: fake items in the tests for the rules, and a hand run on the maintainer's desktop for real applications.
2. [ ] Do `Activate` coordinates matter to real applications on Wayland? Context: some place a window from them. Recommendation: send the item's centre. Answered by: a hand run.
3. [ ] Does the portal offer the icon theme's name? Context: not read. #needs-verification. Recommendation: use it if a read-only probe finds it, else `kdeglobals`. Answered by: a read-only `ReadAll` on the portal's settings.

## Acceptance Criteria

All on a private bus with fakes.

- [ ] With no watcher the module is hidden; a fake watcher appearing shows the items with no shell restart.
- [ ] The shell owns `org.kde.StatusNotifierHost-<pid>` and has called `RegisterStatusNotifierHost` once; after the fake watcher restarts it registers again.
- [ ] A registered item appears; an unregistered one, and one whose bus name loses its owner, disappears.
- [ ] `NewIcon`, `NewToolTip`, `NewTitle` and `NewStatus` each change the matching value after one fresh read; a `Passive` item is hidden unless `show_passive`.
- [ ] A primary click calls `Activate` once with the item's centre; a middle click `SecondaryActivate`; a scroll `Scroll`; with `ItemIsMenu` true a primary click opens the menu.
- [ ] A secondary click calls `AboutToShow` and `GetLayout` and opens a Popup whose entries match the fake tree: labels, a separator, a disabled entry, a checked entry, a submenu; a click on an entry sends `Event(id, "clicked", ...)` once and closes the menu.
- [ ] `LayoutUpdated` while the menu is open rebuilds its entries.
- [ ] An icon name is found in a temporary theme folder through `Inherits` and `hicolor`, preferring the SVG; a pixmap-only item shows its pixmap with the right colours (a known ARGB pattern); neither gives the fallback icon.
- [ ] With no signal traffic the module causes no wake-ups over 60 seconds.
- [ ] No test reaches the real session bus; a user module cannot own a bus name through `ctx.dbus`.

## Links

- [Modules](Modules.md) · [Plasma Coexistence](../Integration/Plasma%20Coexistence.md) · [D-Bus Service Layer](../Integration/D-Bus%20Service%20Layer.md) · [Module Context](../../42%20Python%20API/Module%20Context.md) · [Block Reference](../../41%20TDL%20Reference/Block%20Reference.md) · [Standard Modules](../../50%20Design%20System/Standard%20Modules.md) · [Events and Actions](../../42%20Python%20API/Events%20and%20Actions.md) · [M5 Brief](../../00%20Home/M5%20Brief.md) · [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md)

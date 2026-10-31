---
title: KWin Integration
aliases: [KWin, KWin Script, KWin Rules]
type: spec
status: review
owner: phil
created: 2026-10-29
updated: 2026-10-30
tags: [spec/integration, integration/kwin, needs-verification]
related: ["[[Integration]]", "[[Wayland Protocols]]", "[[ADR-0012 Keeping the Shell Above Plasma Panels]]", "[[ADR-0013 Control Interface]]", "[[IPC and CLI]]", "[[Surface Types]]", "[[System Context]]", "[[Bar]]", "[[Frame]]"]
depends_on: ["[[ADR-0012 Keeping the Shell Above Plasma Panels]]", "[[ADR-0013 Control Interface]]"]
---

# KWin integration

> [!summary]
> What the shell does with KWin beyond the Wayland protocols: a small KWin script that reports which outputs have an active fullscreen window, the optional window rule that keeps the shell above Plasma panels, the KWin D-Bus interfaces the shell reads, and how the shell checks the KWin version. The choices come from [[ADR-0012 Keeping the Shell Above Plasma Panels]] (accepted) and [[ADR-0013 Control Interface]] (accepted). Facts about KWin come from this machine's KWin and Plasma 6.8.1 (D-Bus introspection, small read-only tests, and a read-only script run inside KWin with the maintainer's permission, all on 2026-10-29), from KWin's source, and from KDE's scripting page; each is marked with how it was obtained. Everything not decided is a proposal with a recommendation.

## Purpose and scope

- Specify the KWin script (what it reports, how it is loaded, what happens when it is missing), the window rule and the `kwin` commands, the D-Bus interfaces of KWin the shell uses, and the version check.
- Not in this note: the protocols ([[Wayland Protocols]]), the KWin global-shortcut service ([[ADR-0005 Global Shortcuts]], the shortcuts note to write), and the stacking rules themselves ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]).

## Behaviour

### What KWin offers over D-Bus (introspected on 2026-10-29)

| Object | What it has | Used for |
|---|---|---|
| `/KWin` | `supportInformation` (text that includes `KWin version: 6.8.1`), `getWindowInfo(uuid)`, `queryWindowInfo` (the user picks a window), `showDesktop`, `currentDesktop`, `setCurrentDesktop`, `activeOutputName`, `reconfigure`, `reloadConfig` | The version check; window facts for a known window |
| `/Scripting` | `loadScript(path[, name])`, `loadDeclarativeScript(path[, name])`, `isScriptLoaded(name)`, `unloadScript(name)`, `start()` | Loading the shell's script at run time |
| `/VirtualDesktopManager` | `current`, `desktops`, `currentChanged` ([[System Context#Observed D-Bus names]]) | The Workspaces module |
| `/WindowsRunner` | A KRunner interface that matches windows | Not used; a possible way to list windows, unverified #needs-verification |

- `getWindowInfo(uuid)` returns 30 properties, among them `fullscreen`, `layer`, `resourceClass`, `resourceName`, `type`, `keepAbove`, `keepBelow`, `skipTaskbar`, `caption`, `desktopFile`, and the geometry. Checked on 2026-10-29 against a Chrome window: `fullscreen` false, `layer` 2, `resourceClass` `google-chrome`. The layer values follow KWin's enum, where 2 is the normal layer ([KWin `globals.h`](https://invent.kde.org/plasma/kwin/-/raw/master/src/effect/globals.h), read 2026-10-28).
- **No call lists the windows.** `/KWin` has no list method. A window's uuid comes from the `org_kde_plasma_window_management` protocol or from a KWin script ([[Wayland Protocols#Protocols the shell needs and tre does not expose]]). So fullscreen detection by D-Bus alone needs one of those two to learn the uuids; that is why the script is the route.
- **Layer-shell surfaces and Plasma panels are not in that window list.** A test on 2026-10-29 started a layer-shell surface (the scratch client from the shadow test) and listed `org_kde_plasma_window_management` windows: only the five ordinary windows appeared. So `getWindowInfo` cannot show how KWin matches a shell surface or a panel; only a script inside KWin can, which is what the rule test in [[#Window rules]] needs.

### The KWin script

**Purpose (v1).** Report the outputs that have an active fullscreen window, so the shell can hide its surfaces there ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]). Why "active": KWin puts a fullscreen window in its Active layer only while it is active; a fullscreen window that is not active stays in the normal layer ([KWin `globals.h`](https://invent.kde.org/plasma/kwin/-/raw/master/src/effect/globals.h): "active fullscreen, or active dialog"). Surfaces on the `top` layer are covered by an active fullscreen window by KWin itself; surfaces on `overlay` are not, so the shell must hide them, and it releases the reserved space of the hidden Bar and Frame ([[Frame#Hidden and shown at runtime (decided 2026-10-27)]]).

**What it sends.** One call, `FullscreenState(s outputs)`, on the shell's interface: the full list of output names that have an active fullscreen window, empty when none, written as a JSON array in one string, for example `["DP-1"]` ([[IPC and CLI#The interface]]; the list is decided 2026-10-28, the string form follows from the test below). It sends the full state each time, so a lost message is corrected by the next. It sends nothing else in v1: no titles, no classes, no window ids.

**When it sends.** At load, and whenever the active window changes, a window closes, a window enters or leaves fullscreen, or a window moves to another output. The signals it listens to are `windowActivated` and `windowRemoved` on `workspace`, and per window `fullScreenChanged` and `outputChanged`; the test below found all four present on KWin 6.8.1.

```js
// main.js, an illustration of the shape; not tested code
function report() {
    const out = [];
    const w = workspace.activeWindow;
    if (w && w.fullScreen && w.output) out.push(w.output.name);
    callDBus("io.github.mindderivative.TesseraeShell",
             "/io/github/mindderivative/TesseraeShell",
             "io.github.mindderivative.TesseraeShell1",
             "FullscreenState", JSON.stringify(out));
}
```

`callDBus` is asynchronous and takes the service, path, interface, method and arguments ([KWin scripting API](https://develop.kde.org/docs/plasma/kwin/api/)). Properties used: `fullScreen` (read-write), `output` ("the output where the window center is on", read-only) with its `name`, and `workspace.activeWindow`; the test below found all present.

**Package.** A KPackage of type `KWin/Script`: a `metadata.json` and `contents/code/main.js`, like the script already installed on this machine (`kzones`: `KPackageStructure` `KWin/Script`, `X-Plasma-API` `declarativescript`, `X-Plasma-MainScript` `ui/main.qml`, `X-Plasma-MainScriptX` `code/main.js`, `X-Plasma-API-Minimum-Version` `6.0`; read 2026-10-29). The shell's package carries its own script at `kwin/TesseraeShell/` (proposed), with the id `tesserae-shell-kwin` (proposed).

### What a script inside KWin showed (test of 2026-10-29)

The maintainer allowed a read-only script run (question 3, answered as recommended). A short script was loaded with `loadScript` from a folder outside KWin's own, printed to KWin's journal, called a scratch D-Bus service on the session bus, and was then unloaded. It touched no setting and wrote no file in KWin's configuration. A layer-shell test surface (the scratch client from the shadow test) was running at the time.

| Finding | Result |
|---|---|
| `loadScript(path, name)` accepts a path outside KWin's script folders | Yes: it returned an id, `isScriptLoaded(name)` became true, and `unloadScript(name)` returned true and made it false again. Mode R works. The script ran after `start()`; whether `loadScript` alone runs it was not separated, so the shell calls both |
| Scripting API items | `workspace.activeWindow` (an object), `workspace.windowActivated` and `windowRemoved` (signals), `workspace.stackingOrder` (a list, 9 windows), `workspace.windowList` (a function), and per window `fullScreenChanged` and `outputChanged` (signals) are all present; `window.output.name` is a string (`DP-1`, `HDMI-A-1`) |
| How a shell surface looks to KWin | `resourceClass` and `resourceName` are the surface's layer-shell namespace (`shadowtest` for the test client), `windowType` 0 (normal), `layer` 3 (the Above layer), `skipTaskbar` true |
| How a Plasma panel looks | `resourceClass` and `resourceName` `plasmashell`, `windowType` 2 (dock), `dock` true, `layer` 3 (Above) |
| The wallpaper | Two `plasmashell` windows, `windowType` 1 (desktop), `layer` 0, one per output |
| Ordinary windows | `windowType` 0, `layer` 2 (normal); `fullScreen` false for all nine windows at the time |
| What `callDBus` can send | A string argument works and the callback receives the method's return value. A JavaScript array arrives as `av` (an array of variants): a method declared `av` received it; a method declared `as` was never called, even with an empty array, and no error reached the script. So an array of strings cannot be sent as `as` |

Consequences:

- The `FullscreenState` argument is one string holding a JSON array, not `as`. [[IPC and CLI#The interface]] is updated to match. The shell parses the string and checks that every item is a string.
- **A rule can match a shell surface by its class,** because KWin's resource class is the layer-shell namespace. tre's `LayerWindow` takes `namespace` in its constructor (a change means reopening the window, [[Hot Reload]]). Decided 2026-10-29: every shell surface uses the namespace `tesserae-shell.<type>.<name>` with the type in lower case (D24, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]), for example `tesserae-shell.bar.top_bar` ([[Surface Types]]). A rule can then match the class by a substring or regular expression, and a Plasma panel by class `plasmashell` and type dock.
- **The shell can read a surface's layer** through the script (`window.layer`), which settles what KWin does with each surface; the shell does not need to, and the script sends nothing but the fullscreen list.

### Loading the script

Two ways, and the first is the recommendation:

| Mode | How | For | Against |
|---|---|---|---|
| R. Run-time load (recommended) | At start, after the shell's D-Bus name is owned, the shell calls `isScriptLoaded(id)`, then `unloadScript(id)` if it is, then `loadScript(path, id)` and `start()`; at stop it calls `unloadScript(id)` | No change to `kwinrc`; the script exists only while the shell runs, so a stopped shell leaves nothing behind; a fresh load sends the current state, which solves the shell-restart case | Verified on 2026-10-29: `loadScript` takes a path outside KWin's folders; the script does not exist before the shell starts, which does not matter because the state is only used by the shell |
| P. Persistent install | `tesserae-shell kwin script install` copies the package to `~/.local/share/kwin/scripts/tesserae-shell-kwin/`, sets `tesserae-shell-kwinEnabled=true` under `[Plugins]` in `kwinrc` and asks KWin to reconfigure | The script runs from login; it shows in System Settings; it works with the shell stopped | It writes the user's `kwinrc`; after a shell restart the state is stale until the next change (the shell would need to ask for it); needs the opt-in step |

Decided 2026-10-28 (question 1, as recommended): mode R is the default. The accepted ADR said "a persistent KWin script" and left the install step to delivery; mode R keeps the idea (a script reports fullscreen windows) and drops the install step. Mode P stays available through the `kwin script install` command.

- **Order at start.** The shell loads the script after step 12 of the start sequence, when the interface is exported ([[Shell Start and Stop#Start sequence]]); a call that arrives before the shell can answer finds no name and the script's callback ignores the failure.
- **If it fails to load** (the method returns an error, or the script file is missing): the fullscreen rule is off, the shell logs one warning naming the reason, and `tesserae-shell kwin script status` says so. The shell keeps running.
- **If KWin never reports** (a script error inside KWin, an API change): the shell cannot see script errors, which go to KWin's journal. After loading, if no `FullscreenState` call arrives within 5 seconds, the shell logs a warning that the script is silent (proposed).
- The `kwin` commands are in [[IPC and CLI#The command line]]: `kwin script install`, `remove` and `status` (mode P and the status of mode R).

### Window rules

Opt-in, never automatic ([[ADR-0012 Keeping the Shell Above Plasma Panels]]).

- **Matching.** A rule matches on the window type, the resource class and name, the window role, the client machine, the title, a tag and the transient parent; `desktopFile` is a thing a rule sets, not a thing it matches ([KWin `rules.cpp`](https://invent.kde.org/plasma/kwin/-/raw/master/src/rules.cpp), read 2026-10-29). The type is a bit mask with a default of all types.
- **The layer rule.** A force rule (`DontAffect`, `Force` or `ForceTemporarily`) sets the window's layer when it is active. The config key names and the stored values of the layer are defined outside the files read. #needs-verification
- **Two uses** ([[ADR-0012 Keeping the Shell Above Plasma Panels]]):

| Rule | Effect | Cost |
|---|---|---|
| Raise the shell's `top` surfaces to KWin's Notification layer | They sit above Plasma panels (Above) and below an active fullscreen window (Active); the Plasma panel is untouched | They share the Notification layer with Plasma's notification toasts; the order between them is not defined; needs a stable way to match shell surfaces |
| Lower the Plasma panel to the Normal layer | The shell's surfaces sit above it | A panel at the Normal layer can be covered by a normal window raised over it |

Decided 2026-10-28 (question 2, as recommended): if a rule is offered, it raises the shell's surfaces, because that changes only the shell's own windows; it stays opt-in.

- **Matching a shell surface is verified** (test above): the class is the namespace, the type is normal, the layer is Above; a Plasma panel is class `plasmashell`, type dock. What remains unverified is the rule file itself: the key names and stored values of the layer rule, and that the rule applies to a layer-shell surface and survives a reload. #needs-verification A test would write to `kwinrulesrc`, so it needs a backup and the maintainer's permission first.
- **Writing the rule.** `tesserae-shell kwin rule show` prints the group that would be written; `install` writes one group to `kwinrulesrc`, adds its id to the list in `[General]`, and asks KWin to reload; `remove` deletes only that group and its entry. The shell never edits another group. The file exists on this machine and was not read. A KDE patch for a default-rules helper writes the file and then sends `reloadConfig` on `/KWin`, which is a method on this machine's `/KWin` too; forum reports on reloading are mixed ([discussion](https://discuss.kde.org/t/applying-window-rule-via-command-line/37452)). #needs-verification

### The KWin version

At start, the shell reads `supportInformation` on `/KWin` and takes the line `KWin version: …` (6.8.1 here, checked 2026-10-29). It logs the version. A minimum version is not set: the first KWin with the layer shell is deferred to the testing phase ([[ADR-0001 Shell Surface Strategy#Open items]]). If KWin is not the compositor (the call fails, or another compositor), the KWin script and rule features are off and the shell logs it.

### If KWin goes away

KWin is the Wayland compositor. If it exits, tre's connection drops, its windows close, the loop ends and the shell exits; the script goes with KWin ([[Shell Start and Stop#Failure modes and recovery]]). The shell does nothing KWin-specific to recover.

## Configuration

`settings.tdl` (the file type is named by the root block `Settings { }` and the keys are nested blocks, D20, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]; `KWin.Script` is only a prose shorthand for the path; the settings list is deferred, [[Settings File]]). The mode values are enums, so they are upper case ([[TDL Language#Values]]):

| Key | Meaning | Default |
|---|---|---|
| `KWin.Script` | `RUNTIME` (mode R), `PERSISTENT` (mode P, installed by the command) or `OFF` | `RUNTIME` |
| `KWin.Hide_On_Fullscreen` | Hide the shell's surfaces on an output with an active fullscreen window | `true` |

```
Settings {
    KWin {
        Script: RUNTIME
        Hide_On_Fullscreen: true
    }
}
```

A surface can opt out of hiding (an OSD that should show over a game): open, [[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]].

## Python contract

None. A module does not talk to KWin; the Workspaces module reads `/VirtualDesktopManager` through the shell's D-Bus helper ([[Module Context]]).

## Integration

- D-Bus: the KWin objects above, through `dbus-fast` on the shared service thread ([[ADR-0009 D-Bus Client Library]]); the script calls the shell's interface ([[ADR-0013 Control Interface]]).
- Threads: the calls to `/Scripting` and `/KWin` run on the service thread; the incoming `FullscreenState` is handed to the loop with `call_soon` ([[IPC and CLI#Threading]]).
- Plasma: the rule and the script do not touch plasmashell; coexistence is in the Plasma note to write ([[ADR-0004 Plasma Coexistence]]).

## Design

None.

## Accessibility

Hiding surfaces on fullscreen removes shell controls from view while a video or a game runs; the keyboard way to bring them back is the shortcut or command that shows them ([[IPC and CLI]]).

## Performance budget

- The script runs inside KWin, so its cost is KWin's. It does work only on the events above, builds a short list and makes one asynchronous call; target: no timer, no polling. Measured in testing.
- At idle it sends nothing.

## Failure modes and recovery

| Failure | Result |
|---|---|
| KWin is not the compositor | Script and rule features off; a warning at start |
| `loadScript` fails | Fullscreen hiding off; one warning; `kwin script status` says why |
| The script is silent | A warning after 5 seconds |
| The script throws inside KWin | The shell cannot see it; its output is in KWin's journal; the silence warning applies |
| KWin changes a scripting property | As above; this note and the script are checked against each KWin release |
| The shell stops | The script is unloaded (mode R) |
| The rule cannot be written or reloaded | The command reports the cause and leaves `kwinrulesrc` as it was |
| Two shells | Prevented by the lock ([[Shell Start and Stop#Process rules]]) |

## Open Questions

All seven were answered on 2026-10-28 or 2026-10-29 (as recommended).

1. [x] How the script is loaded: at run time by the shell; a persistent install through the command.
2. [x] Which rule, if any: raise the shell's surfaces; opt-in.
3. [x] A test script inside KWin: permission given and the test done (above).
4. [x] The script id and folder `tesserae-shell-kwin` in `kwin/TesseraeShell/`.
5. [x] The silent-script warning after 5 seconds.
6. [x] The settings keys `KWin.Script` and `KWin.Hide_On_Fullscreen`.
7. [x] An OSD on top of a fullscreen window: none in v1, consistent with the earlier decision that a fullscreen window always covers every shell element; revisit if a need appears. (This one had no recommendation written; I took the earlier decision as the answer.)
- [x] The namespace convention: every shell surface uses the layer-shell namespace `tesserae-shell.<type>.<name>`, the type in lower case (maintainer, 2026-10-29, as proposed; the placeholder reads `<type>` since D24).
- [ ] The rule file's key names and a test of the rule (needs a backup of `kwinrulesrc` and permission).

## Acceptance Criteria

- [ ] `supportInformation` is read at start and the KWin version is in the log.
- [ ] With an active fullscreen window on one output, the script sends that output's name in `FullscreenState`; with none, it sends an empty list.
- [ ] The shell hides its surfaces on that output within one frame of the call and shows them again when the list no longer names it.
- [ ] A fullscreen window that is not active does not hide the shell.
- [ ] After a shell restart the next `FullscreenState` carries the current state (mode R: a fresh load).
- [ ] With the script unloadable, the shell starts, logs one warning, and `tesserae-shell kwin script status` reports it.
- [ ] After a normal stop in mode R, `isScriptLoaded` is false.
- [ ] `tesserae-shell kwin rule install` writes one group and removes nothing else; `remove` restores the file's earlier content for every other group.
- [ ] The script sends no window title, class or id.
- [ ] A call with the string `["DP-1"]` reaches the shell; a call with `as` from a script does not (a regression check on the interface's signature).

## Links

- [[Integration]] · [[Wayland Protocols]] · [[ADR-0012 Keeping the Shell Above Plasma Panels]] · [[ADR-0013 Control Interface]] · [[IPC and CLI]] · [[Surface Types]] · [[System Context]]

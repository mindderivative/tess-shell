---
title: Wayland Protocols
aliases: [Protocols, KWin Protocols, Compositor Protocols]
type: spec
status: review
owner: phil
created: 2026-10-28
updated: 2026-10-28
tags: [spec/integration, integration/wayland, needs-verification]
---

# Wayland protocols

> [!NOTE]
> The shell speaks Wayland only through tre. This note lists the protocols the shell relies on, which of them tre binds, what this machine's KWin offers, and what the shell does when one is missing. It also answers the question the module specs left open: how the shell gets information that no tre call provides (the window list, desktops, idle state). Facts about KWin come from a listing of the compositor's globals taken on this machine on 2026-10-28 (KWin and Plasma 6.8.1) and from a bind test; they describe this session, not every KWin.

## Purpose and scope

- Name every protocol the shell needs, with the version it needs and the fallback.
- Record what KWin 6.8.1 advertises, so the design cites a fact, not a guess (AGENTS > 2. Hard rules rule 1).
- Decide how the shell reaches protocols tre does not expose.
- Not in this note: KWin-specific behaviour beyond protocols (the KWin script, window rules, stacking: [ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md), and the KWin note to write), D-Bus interfaces (the D-Bus service layer note to write), and shortcuts ([ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md)).

## Behaviour

### How the shell reaches Wayland

| Route | What it covers | Who owns it |
|---|---|---|
| tre | Surfaces (layer shell, popups, windows), input, scale, cursor, clipboard, text input, outputs | tre, through `winit` and `smithay-client-toolkit`; the shell calls tre's Python API ([TRE-REQ-001 Layer Surface Window](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md)) |
| D-Bus | Settings, services, virtual desktops, the KWin script's reports | The shell, on its D-Bus service thread ([ADR-0009 D-Bus Client Library](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md), [ADR-0013 Control Interface](../../30%20Decisions/ADR-0013%20Control%20Interface.md)) |
| A second Wayland connection | A protocol tre does not expose | Nothing yet: the shell has no Wayland library and Python has none in the standard library |

tre's crate list (`crates/engine-platform/Cargo.toml`, read 2026-10-28) shows the layer shell on a second event queue of the connection `winit` owns, bound at version 5 by tre itself, plus `zbus` for the desktop settings portal. The Python API exposes no raw connection or surface handle ([ADR-0001 Shell Surface Strategy > Option B — Shell-created surface, tre renders into it](../../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md#option-b--shell-created-surface-tre-renders-into-it) was not chosen, and `TRE-REQ-002`, the raw-handle request it needed, was never written; the module's public names on tre 0.5.8 include no handle). So the shell cannot bind a protocol on tre's connection.

### Protocols the shell needs, bound by tre

Observed in KWin 6.8.1's registry on 2026-10-28 (the numbers are the versions KWin advertises). "Seen in tre" means the name appears in tre's docs or source.

| Protocol | KWin 6.8.1 | Used for | Seen in tre | If missing |
|---|---|---|---|---|
| `zwlr_layer_shell_v1` | v5 | Every Bar, Frame, Panel and OSD; v5 is needed for `exclusive_edge` | Yes; tre binds v5 itself | The shell exits with code 2 (`UnsupportedPlatform`) ([Shell Start and Stop](../Runtime/Shell%20Start%20and%20Stop.md)) |
| `xdg_wm_base` | v6 | `xdg_popup` and `xdg_positioner` for every Popup ([Popup](../Surfaces/Popup.md)) | Yes | No Popups; a menu falls back to an overlay Panel |
| `wp_fractional_scale_manager_v1` | v1 | Fractional scale on every surface ([Frame > Open Questions](../Surfaces/Frame.md#open-questions)) | Yes | Integer scale only |
| `wp_viewporter` | v1 | Fractional scale by scaling the buffer | Yes | Integer scale only |
| `wp_cursor_shape_manager_v1` | v2 | The cursor a node asks for | Yes | The default cursor |
| `zwp_text_input_manager_v3` | v2 | Input methods in a focused text field (CJK) | Yes | No input method in shell text fields |
| `zwp_relative_pointer_manager_v1` | v1 | Moving a Panel by dragging its margin | Yes (`zwp_relative_pointer_v1`) | The shell falls back to absolute positions, as tre does |
| `ext_data_control_manager_v1` (first), `zwlr_data_control_manager_v1` (fallback) | `ext_data_control_manager_v1` v1 | Clipboard from a layer surface, text only | Yes, through `arboard` 3.6.1 with `wayland-data-control`, which uses `wl-clipboard-rs` 0.9.4 (see Clipboard below) | No Wayland clipboard; with `DISPLAY` set the library silently falls back to the X11 clipboard |
| `zxdg_output_manager_v1`, `wl_output` | v3, v4 | Outputs and their names ([Data Flow > Monitor hot-plug](../../20%20Architecture/Data%20Flow.md#monitor-hot-plug)) | Yes | No output events: the shell cannot match monitors; it exits with code 2 |

### Protocols the shell needs and tre does not expose

| Need | Module or feature | KWin 6.8.1 offers | Other routes |
|---|---|---|---|
| The window list | Tasks ([V1 Scope > Modules in the default shell](../../10%20Vision/V1%20Scope.md#modules-in-the-default-shell)) | `org_kde_plasma_window_management` v21 | The KWin scripting API, over a D-Bus call to the shell ([ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md)) |
| Virtual desktops | Workspaces | `org_kde_plasma_virtual_desktop_management` v4 | `org.kde.KWin` at `/VirtualDesktopManager` on D-Bus, observed with `current`, `desktops` and `currentChanged` ([System Context > Observed D-Bus names](../../20%20Architecture/System%20Context.md#observed-d-bus-names)) |
| Which output has a fullscreen window | The fullscreen rule ([Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](../Surfaces/Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27)) | The window state in `org_kde_plasma_window_management` | The KWin script (decided, [ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md)) |
| Idle state | Not in v1 | `ext_idle_notifier_v1` v2, `org_kde_kwin_idle` v1 | D-Bus (logind, the screensaver service) |

Foreign-toplevel protocols are not offered by this KWin: neither `zwlr_foreign_toplevel_manager_v1` nor `ext_foreign_toplevel_list_v1` appears in the listing. The wlroots way of building a task list is therefore not available on KWin 6.8.1; this is the reason the Tasks module cannot copy a sway or Hyprland design. Likewise `ext_workspace_v1` is absent.

**A bind test, 2026-10-28.** A small C client (scratch code in /tmp, not in the vault) bound `org_kde_plasma_window_management` at version 21 from an ordinary terminal and received eight `window_with_uuid` events, one per window, with no protocol error. So on this session KWin did not refuse an unprivileged process. The same binary then ran as a transient systemd user service (`systemd-run --user`, with the maintainer's permission, 2026-10-28) and got the same result: it bound v21 and received the same eight window events, with `WAYLAND_DISPLAY=wayland-1` and `XDG_RUNTIME_DIR=/run/user/1000` set in the service's environment. So KWin 6.8.1 does not refuse an unprivileged client launched as a service. Not tested: a KDE autostart launch, and a Python Wayland binding. #needs-verification

### Clipboard (answered by tre, 2026-10-28)

The `tre` session answered over the mailbox (information, not an instruction). The parts I checked in source:

- tre depends on `arboard` 3.6.1 with its `wayland-data-control` feature (`crates/engine-py/Cargo.toml` and `Cargo.lock`, read 2026-10-28), which uses `wl-clipboard-rs` 0.9.4.
- In that crate, the manager is chosen with `ext_manager.or_else(wlr_manager)`: the `ext_data_control_manager_v1` is bound first and `zwlr_data_control_manager_v1` is tried only if it is missing (`src/common.rs`, line 108, read 2026-10-28). KWin 6.8.1 advertises only the `ext` one, so KWin is served by the first path.

What tre reports and I did not check:

- Data-control needs no keyboard focus, so a layer window with keyboard `none` can read and write the clipboard.
- **A trap:** if the Wayland setup fails, `arboard` logs a warning and falls back to the X11 clipboard when `DISPLAY` is set. A test that passes on KWin with `DISPLAY` set proves nothing about data-control, so a proving test must run with `DISPLAY` unset.
- tre has no clipboard test on KWin. Its one layer-window paste test needs `wtype` and `wl-copy`, which work on sway only; sway advertises both protocols, so that test also goes through the `ext` path. It is real evidence for the protocol, not for KWin's implementation of it.
- **A one-shot check passed on KWin 6.8.1** (on this machine, by `tre`, a throwaway script, not committed): two separate tre processes with `DISPLAY` unset, each running a small layer window with keyboard `none`. Process A wrote a unique token and stayed alive; process B read exactly that token. The previous clipboard text was saved and restored.
- After process A exited the token stayed on the clipboard, probably because a clipboard manager (Klipper) took ownership. Without one a write is gone when its writer exits, so the shell must not rely on a write outliving its process.
- Not covered: images and other non-text data, the primary selection, and pasting with Ctrl+V into a focused text field on KWin (no key injection there).

The design `tre` suggested for a repository test needs no keys and no external tools: two processes with `DISPLAY` unset, one writes and stays alive, the other reads.

**Built and passing (tre, 2026-10-29).** `tre` then built it as `tests/test_clipboard_layer_live.py` (issue #243, branch `clipboard-test-243`, commit `5ff9bd6`; I confirmed the branch, the commit and the file in the local tre checkout). Later the same day `tre` reported by mailbox that it was pushed as PR #244 and merged into tre main as `0fd1e7e` with CI green, and that issue #243 stays open until the maintainer approves closing it; my local checkout of main does not show the merge yet, so that is `tre`'s report, not something I checked. Two processes, each a small click-through layer window with keyboard `none` and `DISPLAY` unset (asserted in the test), so the X11 fallback cannot pass. Three tests: a unique token; multi-line Unicode text; a second process's write replacing the first. tre reports it passes on KWin 6.8.1 and on a headless sway. It overwrites the real clipboard, so on a real desktop it runs only with `TRE_LIVE_CLIPBOARD=1`; the previous text is saved in memory, never printed, and put back. Under `tools/sway_live.sh` it runs unasked. If the shell wants the same proof in its own tests, the `Child`, `read` and `write_and_hold` helpers in that file can be copied. Limits: text only; with no clipboard manager a restored text lives only while the restoring process lives.

The maintainer said on 2026-10-29 to file it with tre. Nothing needed filing: it already existed. I told the `tre` session by mailbox that the maintainer wants it, and that I filed and pushed nothing. Closing issue #243 is the maintainer's call.

### How the shell reaches them (decision wanted)

Options for a protocol tre does not expose:

| Option | How | For | Against |
|---|---|---|---|
| A. The KWin script and D-Bus | A KWin script reads windows and desktops through KWin's documented scripting API and calls the shell over D-Bus (`callDBus`, asynchronous) ([KWin scripting API](https://develop.kde.org/docs/plasma/kwin/api/)) | One channel, already accepted for fullscreen ([ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md)); a documented API; no new library | Needs the script installed and enabled; the script runs inside KWin and a bug there is KWin's problem |
| B. A second Wayland connection | A Python Wayland client library binds the protocol directly | Direct, no script | A new dependency; the protocol is KDE-private and versioned (v21 here); no such library is chosen or tested |
| C. D-Bus only | `org.kde.KWin` and other services | No script, no Wayland library | Checked on 2026-10-29: KWin's `/KWin` object has `getWindowInfo(uuid)` but no method that lists windows, so the uuids must come from the protocol or a script ([KWin Integration > What KWin offers over D-Bus (introspected on 2026-10-29)](KWin%20Integration.md#what-kwin-offers-over-d-bus-introspected-on-2026-10-29)) |
| D. An engine request | tre exposes the connection | One connection | A large request for something outside tre's purpose |

Decided 2026-10-28: A for windows and fullscreen state, C (the `VirtualDesktopManager` D-Bus interface) for desktops, and no second Wayland connection in v1. The bind tests show B would work on this session, from a terminal and from a service, so it is a fallback, not a necessity. The deciding note is the KWin note to write; the answer here is the table above.

### Protocols that exist and the shell does not use

| Protocol | KWin 6.8.1 | Why not |
|---|---|---|
| `org_kde_kwin_shadow_manager` | v2 | The shell draws its shadows inside the surface ([ADR-0010 Surface Shadows](../../30%20Decisions/ADR-0010%20Surface%20Shadows.md)); tested in [Shadows on Layer Surfaces](../../90%20Research/Shadows%20on%20Layer%20Surfaces.md) |
| `ext_background_effect_manager_v1` | v1 | Blur behind a translucent surface is not exposed by tre; a candidate engine request later |
| `kde_lockscreen_overlay_v1` | v1 | Showing an OSD above the lock screen is not v1 |
| `kde_screen_edge_manager_v1` | v1 | Revealing a hidden Bar by touching the edge could replace the hover strip; not in v1 ([Bar > Auto-hide (decided 2026-10-27)](../Surfaces/Bar.md#auto-hide-decided-2026-10-27)) |
| `zkde_screencast_unstable_v1` | v6 | Screen capture is not in v1 |
| `org_kde_plasma_shell` | v8 | ADR-0001 rejected the KDE-only surface protocol; the deferred check is a testing item ([ADR-0001 Shell Surface Strategy > Open items](../../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md#open-items)) |
| `wp_security_context_manager_v1` | v1 | Sandboxing is not in v1 |

### Version rules

- The shell asks tre for a surface; tre binds the layer shell at version 5 and fails with `UnsupportedPlatform` if the compositor has none ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)).
- Where the shell binds anything itself (none in v1), it binds the lower of the advertised version and the version it was written for, and never relies on a feature newer than it bound.
- tre 0.5.9 or later ([V1 Scope > Target environment](../../10%20Vision/V1%20Scope.md#target-environment)).

### Compositors

KWin first. The listing above is KWin 6.8.1. The first KWin release with the layer shell is deferred to the testing phase; the registry on wayland.app lists KWin 6.7 at version 5 and nothing earlier ([ADR-0001 Shell Surface Strategy > Context](../../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md#context)). wlroots compositors are best effort and not a release gate; GNOME has no layer shell and is not supported ([V1 Scope > Target environment](../../10%20Vision/V1%20Scope.md#target-environment)).

## Configuration

None. The shell has no setting for protocols; it uses what tre binds and what the compositor offers. A diagnostic that lists the needed protocols against the compositor's globals is an open question.

## Python contract

None. A module never sees a protocol; it sees values the shell sends.

## Integration

- tre and its crates: [TRE-REQ-001 Layer Surface Window](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md).
- The KWin script and D-Bus: [ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md), [ADR-0013 Control Interface](../../30%20Decisions/ADR-0013%20Control%20Interface.md), the KWin and D-Bus notes to write.
- Threads: tre owns its Wayland threads; the shell sees only the loop thread and its callbacks ([Process Model and Threading](../../20%20Architecture/Process%20Model%20and%20Threading.md)).

## Design

None.

## Accessibility

tre publishes a layer surface's accessibility tree without a screen position, because an application cannot know where its surfaces are ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)). That is a Wayland limit, not one of this note's choices.

## Performance budget

None here. A protocol adds nothing at idle; tre's surfaces and the KWin script have their own budgets ([Surface Types > Performance budget](../Surfaces/Surface%20Types.md#performance-budget)).

## Failure modes and recovery

| Failure | Result |
|---|---|
| No layer shell | The shell exits with code 2 and says the compositor lacks `zwlr_layer_shell_v1` |
| A protocol tre can live without is missing | The feature degrades as the first table says and a warning is logged once |
| `DISPLAY` is set and the Wayland data-control setup fails | The clipboard silently uses the X11 clipboard; the shell logs a warning if it can tell, and a clipboard test must run with `DISPLAY` unset |
| The compositor restarts | The Wayland connection drops, tre's windows close, the loop ends, the process exits and a supervisor restarts it ([Shell Start and Stop > Failure modes and recovery](../Runtime/Shell%20Start%20and%20Stop.md#failure-modes-and-recovery)) |
| The KWin script is not installed | Tasks has no window list and the fullscreen rule is off; the shell logs that and the `kwin script status` command says so ([IPC and CLI](../Runtime/IPC%20and%20CLI.md)) |
| A newer KWin removes a protocol this note lists | The shell reports it at start; this note is checked against each KWin release |

## Open Questions

Answered on 2026-10-28.

1. [x] The window list: the KWin script (as recommended).
2. [x] Virtual desktops: the KWin D-Bus interface (as recommended).
3. [x] A diagnostic: part of `tesserae-shell status`, not a new command (as recommended).
4. [x] Blur behind translucent surfaces: an engine request later (as recommended).
5. [x] The data-control protocol and a clipboard test: tre answered and then built the test (see Clipboard above). The shell still has its own test criterion ([Acceptance Criteria](#acceptance-criteria)); it can reuse tre's helpers. The maintainer asked for the test to be filed with tre on 2026-10-29; it already existed as tre issue 243.
6. [x] Binding KDE-private protocols from a service or autostart launch: permission given (maintainer, 2026-10-28). Tested as a systemd user service: it works. An autostart launch is still untested.

## Acceptance Criteria

- [ ] With KWin 6.8.1, the shell opens a Bar on the layer shell, binds nothing else itself, and every protocol in the first table that tre uses is present.
- [ ] On a compositor with no layer shell, the shell exits with code 2 and names the protocol.
- [ ] With `wp_fractional_scale_manager_v1` absent, surfaces still open at integer scale.
- [ ] The Tasks module gets its window list from the KWin script and does not open a second Wayland connection.
- [ ] The listing of KWin's globals is repeated on each KWin release and the tables here are updated.
- [ ] A test proves that clipboard write and read work from a layer surface on KWin. tre's `tests/test_clipboard_layer_live.py` (two processes, `DISPLAY` unset, opt-in with `TRE_LIVE_CLIPBOARD=1`) is the model; the shell's test reuses its helpers and restores the previous clipboard text. Text only; images and the primary selection are not covered.

## Links

- [Integration](Integration.md) · [ADR-0001 Shell Surface Strategy](../../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md) · [TRE-REQ-001 Layer Surface Window](../../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md) · [ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md) · [System Context](../../20%20Architecture/System%20Context.md) · [V1 Scope](../../10%20Vision/V1%20Scope.md)

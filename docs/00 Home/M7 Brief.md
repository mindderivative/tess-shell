---
title: M7 Brief
aliases: [M7, Release Hardening Brief, Shell M7, M8]
type: moc
status: draft
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [moc, roadmap, brief]
---

# M7 Brief

> [!NOTE]
> The next milestones of `tess-shell`: M7, "hardening for 1.0", turns a shell that has every planned feature (M0 to M6 are built and `tesserae-shell` 0.1.2 is on PyPI) into one that can be called 1.0, and M8 is the use-case sweep that proves the v1 scope of [V1 Scope](../10%20Vision/V1%20Scope.md) item by item. What comes after v1 is listed at the end for the maintainer to choose from. Written on 2026-11-17 at the maintainer's request after the code session reported an empty queue; draft until he answers the questions below. Recommendations come first, as in AGENTS.

## State this plan starts from

Read from `tess-shell` `origin/main`, PyPI and the vault on 2026-11-17; the code session's reports, not run in the vault.

| Area | State |
|---|---|
| Milestones | M0 to M6 built; the work plan of [Next Work Plan](Next%20Work%20Plan.md) done (install-session, Tasks and KWin, the launcher, the accessibility pass, the user guide, portal follow-ups, the self-running hand-check kits) |
| Surfaces and modules | Bar, Frame, Panel, Popup; every v1 module of [V1 Scope](../10%20Vision/V1%20Scope.md) (Clock, Workspaces, Tasks, Tray, Audio, Network, Battery, Media) plus the Launcher; the volume OSD exists as a Panel pattern in the README, not as a shipped module |
| Release | 0.1.2 on PyPI (pure Python wheel and sdist, Trusted Publishing); schema export 1.9 |
| Quality | Accessibility note written and built; the security model and crash recovery are not written ([Development Readiness](Development%20Readiness.md), Quality row); performance budgets exist but have not all been read on an idle machine (D-045) |
| Known gaps (code session) | Importing another `_Shell.tdl` is not built; a Bar's `Reveal_Key` does nothing useful; Clock `hour_cycle: desktop` means 24 h; the README's "Not built yet" paragraph and the Tray module header are stale; no click-outside hiding for the Launcher (decided, nothing to build) |
| Waiting on tre | [TRE-REQ-020 Layer Window Update Before the Surface Exists](../80%20Requests/TRE-REQ-020%20Layer%20Window%20Update%20Before%20the%20Surface%20Exists.md) and [TRE-REQ-021 Announce Without a Node](../80%20Requests/TRE-REQ-021%20Announce%20Without%20a%20Node.md) (drafts); the shell has workarounds for both |

## M7: Hardening for 1.0

Design first, then build. The vault session writes the two missing specs; the code session builds from them.

| Part | What | Owner | Closed when |
|---|---|---|---|
| M7a | The security model for user Python: what a user module may do, how it is loaded, what `check` warns about, how a hung module is contained. Closes R-19 or defers it by ADR | Vault writes the spec; code session builds | The spec is `accepted`; the behaviours it names are tested headless; R-19 is closed or points at the ADR |
| M7b | Crash recovery and the watchdog: the shell's watchdog pings systemd (`WatchdogSec=`, `WATCHDOG=1`), so a hung loop is restarted and not only logged; what is kept across a restart (the registry, saved widget positions); a crash loop stops after the limit already in the unit; the log says why | Vault writes the spec; code session builds | A deliberately hung fake module is detected and the shell restarts under a private systemd user manager (the self-running kits already provide one); state survives the restart |
| M7c | The performance budgets read on an idle machine ([Performance Budgets](../60%20Quality/Performance%20Budgets.md), D-045): idle CPU and wake-ups, memory per surface, frame time, start time; a regression test for each number that can be measured headless | Code session | Every budget has a recorded measurement or a stated reason; failures are fixed or the budget is changed by the maintainer |
| M7d | Upgrades: a version policy (what 0.x and 1.x promise for the command line, the schema export, the TDL files and the module contract), a `Shell:` version check with a clear error, and `tesserae-shell migrate` that wraps `tess-dl`'s slot migration for a user's files (the 0.1 to 0.2 slot change was done by hand) | Vault writes the policy; code session builds | A 0.1-era config folder is migrated by the command and passes `check`; the policy is in [Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md) |
| M7e | Licensing and third-party notices: the wheel carries a notice for every bundled or required asset (the icon set, tre's bundled Roboto font, the dependencies' licences) and CI checks the list | Code session | A `NOTICE` file in the wheel, checked in CI |
| M7f | The known gaps above: import of another `_Shell.tdl`, `Reveal_Key`, Clock `hour_cycle`, the stale README and Tray text | Code session | Each is built or removed from the schema and the docs, with a test |
| M7g | Real-hardware checks with a kit that runs what it can ([Hand Checks](Hand%20Checks.md)): two real outputs and hot-plug (UC10, UC11), a real screen reader (Orca) on the announcements, real Wi-Fi with a captive portal, real audio hardware and Bluetooth | Code session builds the kit; the maintainer runs the lines only he can | Every line has a result in the build log |

Suggested order: M7a and M7b specs (vault) while M7c, M7e and M7f are built; then M7a, M7b and M7d builds; M7g last.

## M8: The Use-Case Sweep

[V1 Scope](../10%20Vision/V1%20Scope.md) promises UC1 to UC11 ([Personas and Use Cases](../10%20Vision/Personas%20and%20Use%20Cases.md)). M8 proves each one with a runnable example in `guide/examples/` and a test, and builds what turns out to be missing.

| Part | What | Closed when |
|---|---|---|
| M8a | A table of UC1 to UC11 against the guide, the examples and the tests; each row is Done, Partly or Missing | The table is in the build log; no row is silently skipped |
| M8b | The OSD (UC3): decide whether a volume and brightness OSD is a shipped module or stays a documented Panel pattern; build it if shipped | The decision is recorded; the example runs headless |
| M8c | Movable desktop widgets with a saved position (UC5) and the slide-in Panel (UC6), if M8a finds them missing | The example runs; the position survives a restart |
| M8d | The 1.0 criteria checked: every M7 part closed, every M8 row Done or moved to "after v1" by the maintainer, CI green, docs current, `tesserae-shell` 1.0.0 candidate built | The maintainer names the release |

## Other projects in step with this

| Project | Work |
|---|---|
| `tess-ui` (configuration application) | Re-record the schema fixture at 1.9 and run its real-checker tests against the new shell; the shell's `Shell:` version check and `migrate` command (M7d) should reach its Files area |
| `tess-dl` | The formatter and a TextMate grammar for editor support (offered by its session); the migration tool the shell's `migrate` wraps |
| `tess-el` | Nothing open; 0.2.0 is released. The shell's `tesserae-el` range waits for the maintainer |
| `tre` | Review and carry [TRE-REQ-020 Layer Window Update Before the Surface Exists](../80%20Requests/TRE-REQ-020%20Layer%20Window%20Update%20Before%20the%20Surface%20Exists.md) and [TRE-REQ-021 Announce Without a Node](../80%20Requests/TRE-REQ-021%20Announce%20Without%20a%20Node.md); confirm 018 and 019 after the kit lines that need his eyes |
| `tess-utils` | Nothing for M7; its pull request #1 is waiting on the maintainer |

## After v1 (for the maintainer to choose from)

| Item | Why it waits ([V1 Scope](../10%20Vision/V1%20Scope.md)) | Recommendation |
|---|---|---|
| Notification centre | Owns `org.freedesktop.Notifications`; coexistence with plasmashell needs an ADR first | First after 1.0; a per-service ADR ([ADR-0004 Plasma Coexistence](../30%20Decisions/ADR-0004%20Plasma%20Coexistence.md)) before any code |
| More modules | The v1 list is fixed at eight | A system monitor, brightness and a power menu, by demand |
| Wallpaper | No use case written | Only with a use case |
| Other compositors | Out of scope until tested ([Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) N3) | wlroots best effort after 1.0 |
| Sharing shells | A delivery question | After the format and `migrate` settle |

## Open Questions

1. [ ] Is "1.0" the end of M7 and M8, or earlier? Context: the shell works and has users today at 0.1.2. Recommendation: call it 1.0 when M7 is closed and M8 shows every use case Done, and release 0.2.0 now for what is already built; 0.x until then, so the file formats may still change.
2. [ ] What is the security stance for user Python (M7a)? Context: R-19, a module runs in the shell's process with the user's rights. Options: A, trusted code (a module is as trusted as a script in the user's shell; `check` warns about a world-writable config folder and the shell contains hangs only); B, a separate process per user module (isolation, a large change to the process model, [ADR-0003 Process Model](../30%20Decisions/ADR-0003%20Process%20Model.md)); C, a permissions list a module declares and the shell enforces for its own API only (it cannot stop `import os`). Recommendation: A for 1.0, written down plainly in the spec and the guide, with B kept as an option for later.
3. [ ] Does a restart after a hang count as recovery (M7b), or must the shell restart without losing the user's open Popups and Panel state? Context: surfaces are rebuilt from the files at start. Recommendation: the files and the registry survive; open Popups and Panels do not.
4. [ ] Is the volume and brightness OSD shipped (M8b)? Context: UC3 is in v1, and the Audio module already sends the values. Recommendation: ship one OSD module for volume, with brightness added when a brightness service is.
5. [ ] Do the real-hardware lines in M7g gate 1.0? Context: they need his machines and a screen reader. Recommendation: Orca and two outputs gate it; Bluetooth and the captive portal do not.

## Questions After Testing

1. [ ] Which idle budgets does the shell meet on the maintainer's machine? Context: measured on an idle machine (D-045), not a loaded one. Recommendation: read the numbers in M7c and keep a budget only where it is met or consciously changed. Answered by: the M7c measurements.

## Acceptance Criteria

- [ ] Every M7 part has its closing evidence in the [M5 Build Log](M5%20Build%20Log.md) or an M7 build log.
- [ ] The security model and the crash recovery notes are `accepted`.
- [ ] A 0.1-era configuration folder is migrated and passes `check`.
- [ ] Every use case of [V1 Scope](../10%20Vision/V1%20Scope.md) is Done, or moved to "after v1" by the maintainer.

## Links

[Development Readiness](Development%20Readiness.md) · [M6 Brief](M6%20Brief.md) · [Next Work Plan](Next%20Work%20Plan.md) · [V1 Scope](../10%20Vision/V1%20Scope.md) · [Risk Register](Risk%20Register.md) · [Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md) · [Hand Checks](Hand%20Checks.md)

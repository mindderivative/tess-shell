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
> The next milestones of `tess-shell`: M7, "hardening for 1.0", turns a shell that has every planned feature (M0 to M6 are built and `tesserae-shell` 0.1.2 is on PyPI) into the release 0.2.0, and M8 is the use-case sweep that proves the v1 scope of [V1 Scope](../10%20Vision/V1%20Scope.md) item by item. The maintainer answered on 2026-11-17: 0.2.0 is the release at the end of M7, and M8 is decided after M7 has been seen ([Open Questions](#open-questions)). What comes after v1 is listed at the end for the maintainer to choose from. Written on 2026-11-17 at the maintainer's request after the code session reported an empty queue; draft until he answers the questions below. Recommendations come first, as in AGENTS.

> [!NOTE]
> **The specs are written and sent (2026-11-17)**
> [Security Model](../60%20Quality/Security%20Model.md) (M7a), [Module Process Test](../60%20Quality/Module%20Process%20Test.md) (M7a2), [Crash Recovery and Watchdog](../60%20Quality/Crash%20Recovery%20and%20Watchdog.md) (M7b) and [Version Policy and Migration](../70%20Delivery/Version%20Policy%20and%20Migration.md) (M7d) are accepted by the maintainer (2026-11-17) and were sent to the code session, which began work on receipt. [TDL-REQ-001 Slot Migration in the Library](../80%20Requests/TDL-REQ-001%20Slot%20Migration%20in%20the%20Library.md) is not sent to `tess-dl` yet (the shell uses its own scanner behind one function until then). [TRE-REQ-022 Content-Sized Layer Surface](../80%20Requests/TRE-REQ-022%20Content-Sized%20Layer%20Surface.md), [TRE-REQ-023 Active Descendant](../80%20Requests/TRE-REQ-023%20Active%20Descendant.md) and [TRE-REQ-024 Outside Press and Keyboard Leave on Layer Surfaces](../80%20Requests/TRE-REQ-024%20Outside%20Press%20and%20Keyboard%20Leave%20on%20Layer%20Surfaces.md) were sent to tre. tre did not start (2026-11-17, its reply): a peer message carries no authority under its `AGENTS.md`, and the maintainer had not told it in its own session to build them; it asked him there and starts in the order 023, 022, 024 when he says so.

> [!NOTE]
> **Sent to the code session on 2026-11-17**
> The parts that need no new spec (M7c, M7e, M7f, M7h and the M7g kit with its three exact-step lines) were sent to `tess-shell` at the maintainer's request. M7a, M7a2, M7b and M7d wait for the vault's specs.

## Progress (code session's reports, 2026-11-17, not run in the vault)

| Part | State |
|---|---|
| M7e licences | Merged (`tess-shell` PR #58, CI result green): a `NOTICE` file in the wheel and sdist covering the in-package assets (the mdi icon set under Apache-2.0, three handle SVGs, `error.png`), what `tesserae-engine` 0.6.9 bundles (four fonts, 495 Rust crates, five `auditwheel` libraries) and the dependency closure; `tests/test_notice.py` (9 tests) fails when a dependency, an asset, a licence or a range is missing, each proved by mutation |
| M7g real-hardware kit | Merged (`tess-shell` PR #57, 2026-11-17): `/tmp/tess-kwin-m7g`, three lines, all scripted ([Hand Checks > The M7g Kit (code session's report, 2026-11-17, not run in the vault)](Hand%20Checks.md#the-m7g-kit-code-sessions-report-2026-11-17-not-run-in-the-vault)). Orca is not installed on the maintainer's machine; the captive-portal part cannot be shown without taking his wired connection down, so the fake covers it |
| M7f gaps | First half merged (`tess-shell` PR #59, CI green): `Reveal_Key` removed (schema 1.9 to 1.10, a removal), Clock `hour_cycle: desktop` follows the locale, the README and the Tray header corrected. Not built: import of another `_Shell.tdl`, which waits for M7a's path rules |
| M7h volume OSD | Merged (`tess-shell` PR #60, CI green): the shipped module `Volume_OSD`, spec [Volume OSD Module](../40%20Specifications/Modules/Volume%20OSD%20Module.md) (written after the build, with six decisions for the maintainer); it added `ctx.surface.show(use=None, *, hide_after=None)` to the module contract |
| M7d version policy and migrate | PR #61: CI found a real regression (the reload client imported `tess_dl`) and a latent race in `test_kill_strays` (it now waits); both fixed |
| M7a security model | Merged (`tess-shell` PR #63, CI green): posture A, controls 1 to 8, `check --strict`, `path-outside-config`, per-module failure back-off, the user-facing statement in the guide and README; five questions from the build in [Security Model](../60%20Quality/Security%20Model.md). M7b is in a PR (CI running); the M7a2 prototype is being built |
| M7b crash recovery | Merged (`tess-shell` PR #67, CI green): the watchdog, `WatchdogSec=15`, the crash record, safe start, registry written within 0.2 s, exit 69 for a lost compositor; observed in a private systemd user manager ([Crash Recovery and Watchdog > As Built (code session's report of `tess-shell` PR #67, merged 2026-11-17, CI green; not run in the vault)](../60%20Quality/Crash%20Recovery%20and%20Watchdog.md#as-built-code-sessions-report-of-tess-shell-pr-67-merged-2026-11-17-ci-green-not-run-in-the-vault)) |
| M7f second half | Merged (`tess-shell` PR #69, CI green): the import of another `_Shell.tdl`, schema 1.11 ([Shell File > Importing Another Shell File (Built in M7f, code session's report of `tess-shell` PR #69, 2026-11-17; not run in the vault)](../41%20TDL%20Reference/Shell%20File.md#importing-another-shell-file-built-in-m7f-code-sessions-report-of-tess-shell-pr-69-2026-11-17-not-run-in-the-vault)) |
| M7d version policy and migrate | Merged (`tess-shell` PR #61, CI green): `tesserae-shell migrate` with the 0.1 to 0.2 step and the shell's own scanner, `shell-too-old`, `tdl-old-version`, the deprecation machinery (empty table); no schema bump ([Version Policy and Migration](../70%20Delivery/Version%20Policy%20and%20Migration.md)) |
| M7a2 process per module | Prototype and harness merged (`tess-shell` PR #71, CI green); no result yet. A smoke run (indicative only): B +360 MB (over the 150 MB threshold), start +180 to 270 ms, latency about 1 ms p95, containment works, C equals A for the default shell. One question for the maintainer before the full run: add a lean B ([Module Process Test](../60%20Quality/Module%20Process%20Test.md)) |
| M7c idle budgets | PR #75 in CI (it had two faults of its own, fixed); its reading and M7a2's full run (about 80 minutes) go alone on an idle machine once the merges are done |
| M7i, M7j | Wait for tre's release of 022 and 023 |
| M7k click-away | Started from tre's answer to 024 |

## State this plan starts from

Read from `tess-shell` `origin/main`, PyPI and the vault on 2026-11-17; the code session's reports, not run in the vault.

| Area | State |
|---|---|
| Milestones | M0 to M6 built; the work plan of [Next Work Plan](Next%20Work%20Plan.md) done (install-session, Tasks and KWin, the launcher, the accessibility pass, the user guide, portal follow-ups, the self-running hand-check kits) |
| Surfaces and modules | Bar, Frame, Panel, Popup; every v1 module of [V1 Scope](../10%20Vision/V1%20Scope.md) (Clock, Workspaces, Tasks, Tray, Audio, Network, Battery, Media) plus the Launcher; the volume OSD exists as a Panel pattern in the README, not as a shipped module |
| Release | 0.1.2 on PyPI (pure Python wheel and sdist, Trusted Publishing); schema export 1.9 |
| Quality | Accessibility note written and built; the security model and crash recovery are not written ([Development Readiness](Development%20Readiness.md), Quality row); performance budgets exist but have not all been read on an idle machine (D-045) |
| Known gaps (code session) | Importing another `_Shell.tdl` is not built; a Bar's `Reveal_Key` does nothing useful; Clock `hour_cycle: desktop` means 24 h; the README's "Not built yet" paragraph and the Tray module header are stale; no click-outside hiding for the Launcher (decided, nothing to build) |
| Engine pin | `tesserae-engine>=0.6.9,<0.7` (PR #56, 2026-11-17); `ctx.announce` is in the module contract |
| Waiting on tre | [TRE-REQ-022 Content-Sized Layer Surface](../80%20Requests/TRE-REQ-022%20Content-Sized%20Layer%20Surface.md), [TRE-REQ-023 Active Descendant](../80%20Requests/TRE-REQ-023%20Active%20Descendant.md) and [TRE-REQ-024 Outside Press and Keyboard Leave on Layer Surfaces](../80%20Requests/TRE-REQ-024%20Outside%20Press%20and%20Keyboard%20Leave%20on%20Layer%20Surfaces.md) (drafts, 2026-11-17). 020 and 021 are built in tre 0.6.9 |

## M7: Hardening (the release is 0.2.0)

Design first, then build. The vault session writes the two missing specs; the code session builds from them.

| Part | What | Owner | Closed when |
|---|---|---|---|
| M7a | The security model for user Python: posture A, trusted code in the shell's process (decided 2026-11-17): what a user module may do, how it is loaded, what `check` warns about, how a hung module is contained. Written so that posture B (a separate process per module) can replace it behind the same module contract. Closes R-19 or defers it by ADR | Vault writes the spec; code session builds | The spec is `accepted`; the behaviours it names are tested headless; R-19 is closed or points at the ADR |
| M7a2 | A performance test for each posture (maintainer, 2026-11-17): the module host measured in process (A) and as one process per module (B), on the same default shell of eight modules. B needs a prototype good enough to measure, not a finished feature | Code session | The numbers for both are side by side in the build log: idle wake-ups, memory, start time, value-to-screen latency, a hung module contained or not. The decision rule below is applied; if B's cost is insignificant, the shell moves to B before 1.0 |
| M7b | Crash recovery and the watchdog: the shell's watchdog pings systemd (`WatchdogSec=`, `WATCHDOG=1`), so a hung loop is restarted and not only logged; what is kept across a restart (the registry, saved widget positions); a crash loop stops after the limit already in the unit; the log says why | Vault writes the spec; code session builds | A deliberately hung fake module is detected and the shell restarts under a private systemd user manager (the self-running kits already provide one); state survives the restart |
| M7c | The performance budgets read on an idle machine ([Performance Budgets](../60%20Quality/Performance%20Budgets.md), D-045): idle CPU and wake-ups, memory per surface, frame time, start time; a regression test for each number that can be measured headless | Code session | Every budget has a recorded measurement or a stated reason; failures are fixed or the budget is changed by the maintainer |
| M7d | Upgrades: a version policy (what 0.x and 1.x promise for the command line, the schema export, the TDL files and the module contract), a `Shell:` version check with a clear error, and `tesserae-shell migrate` that wraps `tess-dl`'s slot migration for a user's files (the 0.1 to 0.2 slot change was done by hand) | Vault writes the policy; code session builds | A 0.1-era config folder is migrated by the command and passes `check`; the policy is in [Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md) |
| M7e | Licensing and third-party notices: the wheel carries a notice for every bundled or required asset (the icon set, tre's bundled Roboto font, the dependencies' licences) and CI checks the list | Code session | A `NOTICE` file in the wheel, checked in CI |
| M7f | The known gaps above: import of another `_Shell.tdl`, `Reveal_Key`, Clock `hour_cycle`, the stale README and Tray text | Code session | Each is built or removed from the schema and the docs, with a test |
| M7g | The real-hardware lines: three checks that need a physical device and so cannot run in the sandbox, listed in [What the Real-Hardware Lines Are](#what-the-real-hardware-lines-are) ([Hand Checks](Hand%20Checks.md)). Each line is written as exact steps (what to start, what to press or plug in, what to listen for or read, the literal expected result, how to report pass or fail) so the maintainer does only the device part. Multi-monitor and hot-plug are tested in the sandbox on virtual outputs, never on his monitors (R-33) | Code session builds the kit; the maintainer runs the three lines | Every line has a result in the build log |
| M7h | The volume OSD, a shipped module (maintainer, 2026-11-17: yes): shown when the Audio module's volume or mute changes, a click-through Panel that disappears after a moment; brightness is added when a brightness service is | Code session | The module's criteria pass headless; an example in the guide |
| M7i | Content-sized Panels that follow their content, padding included, and the Launcher on `Height: AUTO` (maintainer, 2026-11-17: "I want these built"). Waits for tre's release: [TRE-REQ-022 Content-Sized Layer Surface](../80%20Requests/TRE-REQ-022%20Content-Sized%20Layer%20Surface.md) is built on a local branch (2026-11-17). Shell side: [Panel > Content-Sized Panels That Follow Their Content (Decided 2026-11-17; Needs TRE-REQ-022)](../40%20Specifications/Surfaces/Panel.md#content-sized-panels-that-follow-their-content-decided-2026-11-17-needs-tre-req-022) | Code session, after tre | A Launcher with 3 results is shorter than with 10; the padding stays at every size; no flicker in a screenshot sequence |
| M7j | The active-descendant relation: the Launcher and any text field with a list name the selected row. Waits for tre: [TRE-REQ-023 Active Descendant](../80%20Requests/TRE-REQ-023%20Active%20Descendant.md) | Code session, after tre | the focused-state move to the selected row in a test through the accessibility tree (tre's AccessKit expresses the relation that way, not by `ActiveDescendantChanged`); the polite message stays as the fallback |
| M7k | Click-away closing for the Launcher, built shell-side from tre's answer to [TRE-REQ-024 Outside Press and Keyboard Leave on Layer Surfaces](../80%20Requests/TRE-REQ-024%20Outside%20Press%20and%20Keyboard%20Leave%20on%20Layer%20Surfaces.md): the `active` event (keyboard taken away) and the popup-grab recipe (a click elsewhere, which swallows the click, is one-shot and misses the shell's own surfaces). Works with tre 0.6.9, no release needed | Code session, now | A click on the desktop or another application closes the Launcher in a private sway; KWin is a hand-check line

Suggested order: the M7a and M7b specs (vault) while M7c, M7e, M7f and M7h are built; then the M7a2 test, which settles the posture; then the M7a, M7b and M7d builds; M7g last.

### What the Real-Hardware Lines Are

Almost every check now runs by itself in a sandbox: a private session bus, a real KWin started as `kwin_wayland --virtual`, a real systemd user manager and a private sway, with fakes for the devices ([Hand Checks](Hand%20Checks.md)). "Real-hardware lines" are the few left that need a physical device the sandbox cannot be. After the maintainer's answer of 2026-11-17 there are three; each is written as exact steps by the code session:

| Line | What he does | Notes |
|---|---|---|
| Orca | Start the Orca screen reader and listen to the announcements: Network, Battery critical, the Launcher's selected row | The kit gives the exact command, the order of actions, and the literal text Orca should speak |
| Real Wi-Fi (the captive portal is covered by the fake) | Join his Wi-Fi network with the wired connection kept; the kit checks it is unchanged | He uses a wired connection normally. The kit gives steps that do not break his wired session and that return it exactly; the captive-portal part needs a network that shows a login page, and is run only if he has one |
| Real audio and Bluetooth | Switch the output between the monitor or system speakers and his Bluetooth phone headset; change the volume | The kit gives the steps and what the Audio module must show for each device |

Not a line, by the maintainer's decision: two outputs and a physical hot-plug. He has declined it before: the M3c hot-plug checklist of 2026-11-08 offered "unplug DP-1 (cable, or off in System Settings)", and he recorded a hard power-off and power-on of the monitor instead ([M3 Build Log](M3%20Build%20Log.md)). The wording "cable" in that checklist and in its kit (`prepare_m3c_hotplug.py`) is to be removed; no kit offers a cable pull. He will not plug or pull a monitor cable or power, because of the risk of an electrical surge ruining a monitor ([Risk Register](Risk%20Register.md) R-33). Multi-monitor and hot-plug are tested on virtual outputs in the sandbox, and that is the best that can be done. His power and switch tests on the real monitors (off and on, power removed and restored) all worked as expected, and the shell came back each time.

## M8: The Use-Case Sweep (to be decided after M7)

[V1 Scope](../10%20Vision/V1%20Scope.md) promises UC1 to UC11 ([Personas and Use Cases](../10%20Vision/Personas%20and%20Use%20Cases.md)). M8 proves each one with a runnable example in `guide/examples/` and a test, and builds what turns out to be missing.

| Part | What | Closed when |
|---|---|---|
| M8a | A table of UC1 to UC11 against the guide, the examples and the tests; each row is Done, Partly or Missing | The table is in the build log; no row is silently skipped |
| M8b | The OSD (UC3): the volume OSD moved to M7h; M8b keeps brightness if a service is built | A decision is recorded |
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

1. [x] Is "1.0" the end of M7 and M8, or earlier? Answered by the maintainer on 2026-11-17: M7 completes as release 0.2.0, and M8 is decided after seeing how M7 goes. Version 1.0 and its criteria wait for that.
2. [x] What is the security stance for user Python (M7a)? Answered by the maintainer on 2026-11-17: posture A as recommended (trusted code, plainly written down), with one addition: a performance test for each posture (M7a2). If the separate process per module is insignificant in cost, the shell moves to that posture before 1.0.
3. [x] Does a restart after a hang count as recovery (M7b)? Answered by the maintainer on 2026-11-17: as long as the files and the registry survive, what is open or not does not matter.
4. [x] Is the volume and brightness OSD shipped? Answered by the maintainer on 2026-11-17: yes. Placed as M7h (volume first; brightness when a brightness service exists). This is my placement; the maintainer can move it to M8.
5. [x] Which real-hardware lines gate 1.0, now that M8 and 1.0 wait? Answered by the maintainer on 2026-11-17: the two-outputs and hot-plug line is not done on hardware (he will not risk his monitors; he switched monitors off and on and removed and restored their power, and the shell came back each time, as expected); Orca is his to run if the test and exact steps are given; Wi-Fi he can run (he uses a wired connection normally); audio he can run with his monitors' and system's small speakers and possibly his Bluetooth phone headset. He did not say which lines gate a release. Recommendation kept: Orca gates 0.2.0; Wi-Fi and audio are run once and recorded without blocking a release. Say if you want them to gate.
6. [x] What counts as "insignificant" for the separate process per module (M7a2)? Context: eight modules at a Python process each cost memory and start time. Recommendation, to be argued with the numbers: B is accepted if the whole default shell starts no more than 300 ms slower, idle wake-ups do not rise beyond the modules' own ticks, a module's value reaches the screen within one frame (16 ms) at p95, and total memory grows by no more than 150 MB; otherwise A stays and B is kept as an option. The numbers are the maintainer's to change. Settled by the maintainer's acceptance of [Module Process Test](../60%20Quality/Module%20Process%20Test.md) on 2026-11-17: the starting values in its decision rule stand (start +300 ms, wake-ups +2 per second, value to screen within 16.7 ms at p95, memory +150 MB, and containment), and he can change them after seeing the numbers.

## Questions After Testing

1. [ ] Which idle budgets does the shell meet on the maintainer's machine? Context: measured on an idle machine (D-045), not a loaded one. Recommendation: read the numbers in M7c and keep a budget only where it is met or consciously changed. Answered by: the M7c measurements.

## Acceptance Criteria

- [ ] Every M7 part has its closing evidence in the [M5 Build Log](M5%20Build%20Log.md) or an M7 build log.
- [ ] The security model and the crash recovery notes are `accepted`, and the M7a2 numbers decide the posture.
- [ ] A 0.1-era configuration folder is migrated and passes `check`.
- [ ] The release 0.2.0 is named by the maintainer. M8 and 1.0 are planned after it.

## Links

[Development Readiness](Development%20Readiness.md) · [M6 Brief](M6%20Brief.md) · [Next Work Plan](Next%20Work%20Plan.md) · [V1 Scope](../10%20Vision/V1%20Scope.md) · [Risk Register](Risk%20Register.md) · [Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md) · [Hand Checks](Hand%20Checks.md)

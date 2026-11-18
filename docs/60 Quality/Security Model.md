---
title: Security Model
aliases: [Security, User Python Security, Module Trust, R-19]
type: quality
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [quality, security, needs-verification]
---

# Security Model

> [!NOTE]
> **Accepted by the maintainer on 2026-11-17**
> Sent to `tess-shell` by the vault session the same day, on the maintainer's standing order; accepted by him afterwards. Open questions below are answered as recommended unless a line says otherwise.

> [!NOTE]
> The shell runs as the user, with the user's rights and no privileges of its own. Shell files in TDL cannot run code: TEL is sandboxed and TDL has no statements. A module's Python file can do anything the user can. For the 0.2.0 release the maintainer chose posture A: a module is trusted code, as trusted as a script the user runs, and the vault says so plainly. This note defines what that means, the controls the shell adds around it, what it does not promise, and the second posture (a process per module) that [Module Process Test](Module%20Process%20Test.md) measures against it. M7a of [M7 Brief](../00%20Home/M7%20Brief.md); decided 2026-11-17 by the maintainer ("as recommended, but a performance test for each stance"). It closes risk R-19 for 0.2.0 by stating the posture.

## Purpose and scope

- In: what is trusted, what is not, the threats considered, the controls built in 0.2.0, how a module that hangs or fails is contained, what `check` and start warn about.
- Out: a sandbox for untrusted Python (not promised; see [Posture B and What It Does and Does Not Give](#posture-b-and-what-it-does-and-does-not-give)); loading shells written by other people from a shared place, which is after v1 ([V1 Scope](../10%20Vision/V1%20Scope.md), "Sharing shells").

## What Is Trusted

| Thing | Trust | Why |
|---|---|---|
| The shell package and its shipped modules | Trusted | Installed by the user from a PyPI release (published with Trusted Publishing, [Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md)) or a distribution package |
| A TDL file (shell, module layout, style, theme, stylesheet, settings) | Cannot run code | TDL has no statements, variables or tags; every `<\| \|>` slot goes to TEL, whose whitelist, evaluator and limits are the sandbox ([Expression Language Requirements](../40%20Specifications/Runtime/Expression%20Language%20Requirements.md), [ADR-0008 Tesserae Expression Language](../30%20Decisions/ADR-0008%20Tesserae%20Expression%20Language.md)) |
| A user module's `<Name>_Module.py` in the config directory | Trusted: it runs with the user's rights, in the shell's process, and can read files, start processes and use the network | Posture A, decided 2026-11-17: as trusted as any script the user puts in their home directory |
| A module or shell obtained from someone else | Not trusted, and not supported in 0.2.0 | The user must read a module's Python before adding it; the guide says so ([The User-Facing Statement](#the-user-facing-statement)) |
| Another process of the same user | Trusted as the user | It can already do everything the shell can; the control interface and the config directory are not defended against it |
| Another user, or the network | Out of reach | The shell opens no network port and owns only names on the user's session bus |

## Threats Considered

| # | Threat | Answer in 0.2.0 |
|---|---|---|
| S1 | A TDL file, from any source, runs code | Not possible: no code in TDL; TEL limits ([Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md)) |
| S2 | A module's Python is replaced or edited by something other than the user | Controls 1 and 2 below: the shell loads from the config directory only and warns when others can write there |
| S3 | A module hangs or loops, so every surface freezes ([ADR-0003 Process Model > Consequences](../30%20Decisions/ADR-0003%20Process%20Model.md#consequences)) | Control 5 and [Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md): the stall is named, logged, and recovered by restart; posture B or C ([Module Process Test](Module%20Process%20Test.md)) would contain it |
| S4 | A module raises, leaks threads or floods the loop | Controls 5 and 6 |
| S5 | An `Import:` or a path in a shell file reaches a file outside the config directory | Control 3 |
| S6 | Another local process drives the shell through its control interface | Accepted: the session bus is per-user, so the same trust as the user; `Call` reaches only methods marked `@action` ([Module Contract](../42%20Python%20API/Module%20Contract.md)) |
| S7 | Logs leak private content | Control 7 |
| S8 | A shell file is read as a module (the other way round) | Not possible: a module is a `.py` file next to its `_Module.tdl`; a TDL file never names a Python path |

## Controls in 0.2.0

Every control is testable headless. None is a sandbox.

1. **Load from the config directory only.** A user module's Python is imported by file path from `Modules/<module_name>/` of the configured directories ([Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md)) and never through the process's general import path; the shell does not add the config directory to `sys.path`. A module imports its own helpers from its own folder only. #needs-verification (how the code session builds the import: the vault has not read it).
2. **Permissions warning.** At start, at reload and in `check`, a config directory, a module folder or a module file that is writable by group or others, or not owned by the user, gives the finding `insecure-permissions` with the path, once per path. It is a warning, not an error ([Open Questions](#open-questions) 1). Reason: write access to a module file is code execution as the user.
3. **No escape from the config directory.** `Import:` and any path-valued key (`Source`, a settings path) resolve inside the configured directories; a path that leaves them after resolving `..` and symbolic links is the error `path-outside-config` with `file:line:column`. Shipped files from the package are the one exception, by name.
4. **A narrow context.** A module gets `ctx` and nothing else the shell holds: no tre nodes, windows or surfaces, no registry, no config loader, no TEL ([Module Context > What the Context Does Not Give](../42%20Python%20API/Module%20Context.md#what-the-context-does-not-give)). Python can still import anything; the narrow context keeps the shell's own state consistent, it does not stop a determined module.
5. **A running callback is named.** The module host records, for the callback that is running on the loop, the module, the entry point and a monotonic start time. The watchdog reads it, so a stall names the module ([Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md)). A callback over its budget (4 ms, [Performance Budgets](Performance%20Budgets.md)) is logged at debug with the module name; a module that exceeds it more than 100 times in a minute gets one warning `slow-module` per minute with its name and the entry point.
6. **Faults are per module.** An exception in `start` or a callback marks only that module failed and logs it with the module name and UID; the rest continue ([Process Model and Threading > Failure and Recovery](../20%20Architecture/Process%20Model%20and%20Threading.md#failure-and-recovery)). A failed module restarts with a back-off (1, 2, 4 … up to 60 seconds, at most 5 tries) and then stays failed until a reload. A module with more than 16 live threads of its own gets the warning `many-threads` once.
7. **No content in logs.** A module's `ctx.log` is the module's own to fill. The shell's own log lines carry names, keys, counts and positions, never window titles, notification text, clipboard content or file contents ([Tasks Module](../40%20Specifications/Modules/Tasks%20Module.md): the shell logs no title; [Logging](../40%20Specifications/Runtime/Logging.md)).
8. **Processes it starts.** The Applications module starts only what a desktop entry says, detached, and logs the application's id and never its arguments' values ([Applications Module](../40%20Specifications/Modules/Applications%20Module.md)).

## Posture B and What It Does and Does Not Give

Posture B runs each module's Python in its own child process, which talks to the shell over a pipe. The module still runs as the user. So:

- B gives **fault containment**: a hung or crashed module takes down only its own process; the surfaces keep painting; the shell can kill and restart it.
- B does **not** give security isolation by itself. A child running as the same user can read the same files and start the same processes. Real isolation needs more (a namespace sandbox such as `bwrap`, a seccomp filter or Landlock), which is a larger decision and is not promised.
- B costs memory, start time and a hop for every value ([Module Process Test](Module%20Process%20Test.md) measures exactly this).

The maintainer's rule (2026-11-17): if the cost of B is insignificant, the shell moves to B before 1.0. Posture C is the pragmatic middle: the shipped modules stay in process (they are the package's own code), and user modules run in child processes. Its benefit lands where the risk is: S3 and S4 for code the shell did not ship.

## The User-Facing Statement

To go in the guide and the README, in this wording (decided with posture A):

> A module is Python that runs inside the shell with your rights. It can read your files and start programs. Write modules yourself or read them before you add them. TDL files cannot run code. Keep your configuration folder writable by you only: the shell warns if it is not.

## Python Contract

No new public API in 0.2.0. The module host gains an internal record of the running callback (control 5), and `check` gains two rules (`insecure-permissions`, `path-outside-config`) and the slow-module and many-threads warnings.

## Integration

- Config discovery, the registry and imports: [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md).
- Process model and the watchdog: [Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md), [Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md).
- Reload keeps the old instance when a module's new file fails ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md)).

## Failure modes and recovery

| Failure | Result |
|---|---|
| Config directory writable by others | Warning `insecure-permissions`; the shell starts |
| `Import:` leaves the config directory | Error `path-outside-config`; that file is refused, with its position |
| A module raises in a callback | Module marked failed, others continue, back-off restart |
| A callback never returns | Stall logged with the module name at 2 s, recovered by restart at 10 s ([Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md)) |
| A module floods the loop | `slow-module` warning naming it |

## Performance budget

The controls add no work to the loop beyond one record per callback (two stores and a clock read). The permission and path checks run at load and reload, never per frame. Measured against the budgets in [Performance Budgets](Performance%20Budgets.md) by M7c.

## Open Questions

1. [x] Is `insecure-permissions` a warning or an error? Context: write access to a module is code execution as the user, but an error would stop a shell on a shared or network home. Recommendation: a warning, shown once per path in the log and by `check`; `check --strict` turns warnings into a failing exit. Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.
2. [x] Should the shell warn about a module that imports `subprocess`, `os.system` or `ctypes`? Context: it would warn about most useful modules and give a false sense of safety. Recommendation: no. Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.
3. [x] Is the user-facing statement above the wording the maintainer wants in the guide? Recommendation: yes; it is short and states the risk without alarm. Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.

### Questions from the Build (code session's report of `tess-shell` PR #63, 2026-11-17)

4. [ ] Is a path outside the config folder to be allowed for images, SVG and styles, by a list? Context: control 3 is built as written, so an absolute or `~/` path to an image, SVG or style outside the config folder (for example `~/Pictures/wall.png`) is now `path-outside-config` and the reload is refused. Only the M4b gallery kit used one (it now copies its images into the config folder), but a user's wallpapers and icons elsewhere stop working. Recommendation: an allow-list in `settings.tdl` of extra read-only folders for assets (`Asset_Directories`), named by the user, never for `Import` and never for module Python; `~/Pictures` is one line to add.
5. [ ] Should a module's sibling helper imports be built? Context: the note says a module may import its own helpers from its own folder; none work today (the code session left it). Recommendation: build it, from the module's folder only, as control 1 says.
6. [ ] Should DEBUG lines avoid titles and typed text too? Context: control 7 says logs carry no content. One DEBUG line in `binder/build.py` prints a block's accessible label, which for a Tasks entry is a window title, and two Applications DEBUG lines log typed text and keys; live tests use them. Recommendation: remove the content from those lines now and let the tests read the state another way; a DEBUG level is still on a user's disk when they report a bug.
7. [ ] Is group-write a warning when the group is the user's private group? Context: with umask 002 and user-private groups every new file is group-writable and warned. Recommendation: refine: a file or folder writable by its group is fine when that group is the user's private group (the group has only the user as a member); warn for any other group or for others.
8. [ ] Should an unchanged `insecure-permissions` warning repeat on every hot reload? Context: it is logged again on each save. Recommendation: log once per path until the finding changes, and again at the next start.

## Questions After Testing

1. [ ] Does a callback record cost anything measurable on the loop? Context: it is two stores and a clock read per callback. Recommendation: measure in M7c; keep it unless it is over 1% of the 4 ms callback budget. Answered by: the M7c measurement.

## As Built (code session's report of `tess-shell` PR #63, merged 2026-11-17, CI green; not run in the vault)

Posture A is built from this note. Controls 2, 3, 5, 6, 7 and 8 are built; controls 1 and 4 were verified and not changed (modules were already imported by file path, a `json.py` beside a module does not shadow the standard library, `sys.path` is untouched, `ctx` gives no tre node or window).

- `insecure-permissions` is a warning for the config directory, the module search folders, each user module's folder and file, once per scan, at start, at reload and in `check`; a new `check --strict` turns warnings into exit 1; the shell starts.
- `path-outside-config` is an error with `file:line:column` from one helper (`config/confine.py`) behind `Import`, `Style`, SVG and Bitmap `Source`, path params and icon files.
- The running-callback record is `host.callbacks.running()` giving the module, the entry point and a monotonic start time, readable from any thread (M7b's watchdog uses it). A callback over 4 ms is logged at debug; more than 100 overruns a minute gives the `slow-module` warning naming the module and the entry point most often over.
- A lifecycle failure (start, stop, reload, `use_added`, `use_removed`) marks only that module failed, logged with its UID; it restarts from a fresh import after 1, 2, 4, 8 and 16 seconds (cap 60, five tries) and then stays failed until a reload. `many-threads` warns once. An exception in an action, a tick, a `call_soon` or a service callback is logged with the module name and the module keeps running (the Module Contract's failure table says so; failing a Clock because a click handler raised would be wrong).
- `ctx.announce` no longer logs the spoken text; the Applications service logs ids only, tested with secret `Exec` arguments on all four start paths.
- The user-facing statement is verbatim in `guide/02` (a "Trust and security" section) and the README, with a test; the four codes are in the troubleshooting page. 13 deliberate bugs were each caught by the new tests. Two public handles remain (`ctx.log` is a loguru logger with `add` and `remove`; `ctx.dbus.layer` is the shell-wide D-Bus layer) and were left.
- Absolute paths in `settings.tdl` (`Registry`, `Logging.Directory`, `Directories`) are not confined; shipped files are exempt because they live under `shipped/`. The back-off granularity is the 1 s tick.
- A behaviour change the maintainer must know: an absolute or `~/` path to an image, SVG or style outside the config folder is now an error and the reload is refused (question 4).

## Acceptance criteria

- [ ] A user module is imported by path from its folder and the config directory is not on `sys.path`.
- [ ] A config directory, a module folder and a module file with group or other write access each give `insecure-permissions` once, in the log and in `check`, and the shell starts.
- [ ] An `Import:` that leaves the config directory (by `..` or a symbolic link) is `path-outside-config` with the position.
- [ ] A module that sleeps in a callback is named in the stall log of [Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md).
- [ ] A module that raises is marked failed alone and restarts with back-off, five tries, then stays failed until a reload.
- [ ] `slow-module` and `many-threads` fire once with the module's name.
- [x] The guide and README carry the user-facing statement (built, PR #63).
- [ ] [Risk Register](../00%20Home/Risk%20Register.md) R-19 points at this note and says "posture A, decided 2026-11-17".

## Links

[M7 Brief](../00%20Home/M7%20Brief.md) · [Module Process Test](Module%20Process%20Test.md) · [Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md) · [Module Contract](../42%20Python%20API/Module%20Contract.md) · [Module Context](../42%20Python%20API/Module%20Context.md) · [Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md) · [Risk Register](../00%20Home/Risk%20Register.md) · [60 Quality](60%20Quality.md)

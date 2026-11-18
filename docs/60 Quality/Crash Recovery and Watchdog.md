---
title: Crash Recovery and Watchdog
aliases: [Crash Recovery, Watchdog, Supervisor, M7b]
type: quality
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [quality, needs-verification]
---

# Crash Recovery and Watchdog

> [!NOTE]
> **Accepted by the maintainer on 2026-11-17**
> Sent to `tess-shell` by the vault session the same day, on the maintainer's standing order; accepted by him afterwards. Open questions below are answered as recommended unless a line says otherwise.

> [!NOTE]
> What happens when the shell hangs or dies, and what survives. A watchdog thread already logs a stalled loop; this note makes systemd restart a hung shell (a `WatchdogSec=` ping that stops when the loop stops), makes the files and the registry survive any restart (the maintainer's requirement of 2026-11-17: open surfaces need not survive), keeps the evidence of a crash, and stops a crash loop from hiding its cause. M7b of [M7 Brief](../00%20Home/M7%20Brief.md). The supervisor that [Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md) and [Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md) called "a later item" is systemd: the session unit already restarts a crashed shell ([Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md)).

## Purpose and scope

- In: detecting a hang, restarting from it, what is written when, what survives, a crash loop, the crash record, a lost compositor, the exit codes.
- Out: restoring open Popups, a Panel's shown state or a module's in-memory values after a restart (not required); a supervisor other than systemd (the shell can be started by any autostart that runs `tesserae-shell run`, and then a hang is only logged).

## What Exists

| Piece | State |
|---|---|
| Watchdog thread | Checks the loop is ticking; logs a stall. Built (the budgets say a stall of 2 s logs, and a restart at 10 s "to confirm with the supervisor design", [Performance Budgets](Performance%20Budgets.md)) |
| `Restart=on-failure`, `RestartSec=2`, `RestartPreventExitStatus=1 2 4`, a start limit of 5 in 60 s in `[Unit]` | In the unit that `install-session` writes ([Packaging and Session Start > The Session Unit](../70%20Delivery/Packaging%20and%20Session%20Start.md#the-session-unit)) |
| `Type=notify`, `READY=1` and `STOPPING=1` | Built (the shell sent neither until `install-session` was built) |
| Exit codes | 0 stop; 1 configuration; 2 environment; 4 already running; 70 internal; 130 forced stop ([Shell Start and Stop > Exit Codes](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#exit-codes)) |
| Registry written | At stop only ([Process Model and Threading > Lifecycle (Proposed)](../20%20Architecture/Process%20Model%20and%20Threading.md#lifecycle-proposed)): a crash loses what changed since the start |

## Detecting a Hang

The loop cannot interrupt itself, so a separate thread watches a heartbeat.

1. The loop bumps a counter and a monotonic time from a timer that already exists for this (`window.every`), at most once a second.
2. The watchdog thread reads it every second.
3. **Stall of 2 s:** one warning `loop stalled for N s`, naming the module, the entry point and how long it has been running, from the record the module host keeps for the running callback ([Security Model > Controls in 0.2.0](Security%20Model.md#controls-in-020), control 5). Then once every 5 s while it lasts. The Python tracebacks of every thread go to the log with `faulthandler.dump_traceback`.
4. **Stall of 10 s (and the budget's restart):** the shell asks to be restarted. Under systemd with a watchdog it sends `WATCHDOG=trigger` on `NOTIFY_SOCKET`, which makes the service manager act as if the keep-alive had been missed. With no watchdog configured, or no systemd, it only logs `loop stalled for 10 s, no supervisor can restart it` and keeps dumping tracebacks every 30 s; there is nothing else a shell can safely do.

### The systemd side

Read from the systemd manual (2026-11-17, [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) and [sd_notify](https://www.freedesktop.org/software/systemd/man/latest/sd_notify.html)): `WatchdogSec=` in a service makes the service manager expect `WATCHDOG=1` keep-alive pings, passes the interval in the environment variable `WATCHDOG_USEC=`, and when two pings are further apart than the interval it puts the service in a failed state and terminates it with `SIGABRT` (or the signal in `WatchdogSignal=`); with `Restart=` set to `on-failure`, `on-watchdog`, `on-abnormal` or `always` it restarts. `WATCHDOG=trigger` tells the manager that the service detected an internal error and triggers the same behaviour. #needs-verification: that this holds for a user manager and a `Type=notify` service; the self-running kits run a real private user manager, so it is tested ([Acceptance criteria](#acceptance-criteria)).

- The unit gains `WatchdogSec=15` (the interval is 1.5 times the 10 s stall, so a real stall is caught by the shell first and the manager is the backstop). `install-session` writes it; [Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md) is updated with it.
- The shell reads `WATCHDOG_USEC`; when it is set, the watchdog thread sends `WATCHDOG=1` every half interval, only while the heartbeat is fresh (under 5 s old). A stalled loop therefore stops the pings by itself, even if the shell never reaches the 10 s decision.
- The default `SIGABRT` is wanted: `faulthandler` (enabled at start) writes every thread's traceback to the crash file and the journal as the process dies ([The Crash Record](#the-crash-record)).

## What Survives a Restart

The maintainer's rule (2026-11-17): the files and the registry survive; what is open does not need to.

| Survives | How |
|---|---|
| The configuration files | The shell never rewrites a user's TDL file except to write a missing `UID:` once ([Config Discovery and Registry > Writing the UID into a File](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md#writing-the-uid-into-a-file)), atomically: a temporary file in the same folder, then a rename |
| The registry | Written within 1 s after any change (debounced) with the same temporary-file-and-rename, not only at stop. Today it is written at stop, so a crash loses a moved Panel's position; this note changes that. A corrupt or missing registry is rebuilt from the UIDs in the files and saved state is lost, as already decided ([Config Discovery and Registry > The Registry File](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md#the-registry-file)) |
| Module state under `ctx.state_dir` | The module's own business; the shell never deletes it |
| Open Popups, a shown Panel, a module's in-memory values | Do not survive; a Panel starts as its file says (`Visible`), a module starts fresh |

## The Crash Record

- At start the shell opens `crash.log` in its state directory and calls `faulthandler.enable(file=...)`, with all threads. The previous file is kept as `crash.log.1` (and one older); no more.
- A fatal signal, a watchdog `SIGABRT` or an unhandled exception that reaches the top writes the tracebacks there. The shell's last log lines are in the journal as usual.
- An unclean-exit marker, `running`, is written to the state directory at start and removed at a clean stop. A start that finds it records `previous run ended uncleanly` at warning level with the file's time, and counts it.
- `tesserae-shell status` prints the count of unclean starts since the last clean stop, and the time of the last crash (information, not an error).

## A Crash Loop

The unit already stops after 5 starts in 60 seconds, and a stopped unit hides the cause. Two additions:

- **Evidence stays.** `journalctl --user -u tesserae-shell` shows the log; `crash.log` shows the traceback; `status` shows the count.
- **Safe start (decided by the maintainer, 2026-11-17, [Open Questions](#open-questions) 1).** After 3 unclean starts in a row within 10 minutes, the next start loads shipped modules only and skips every user module's Python, with a warning that names which user modules were skipped and why. The user's files are untouched. A clean stop of that start resets the count; `tesserae-shell status` says the shell is in safe start, and the next start after a reload or a restart from the user tries the user modules again. The cause is usually a user module, and this keeps a bar on the screen while the user fixes it.

## A Lost Compositor

If the Wayland connection is lost (KWin restarted or crashed), tre's windows close and the loop ends. The shell exits with a non-zero code that is not 0, 1, 2 or 4, so `Restart=on-failure` restarts it: the proposed code is 69 (`EX_UNAVAILABLE` of `sysexits.h`; a table row for [Shell Start and Stop > Exit Codes](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#exit-codes)). #needs-verification: what the shell does today when the connection drops (the vault has not read it; if it already exits with 70, this note keeps 70 and drops 69).

## A Failing Module

Covered by [Security Model > Controls in 0.2.0](Security%20Model.md#controls-in-020), control 6: the module alone is marked failed, restarts with back-off 1, 2, 4 … up to 60 seconds for at most 5 tries, then stays failed until a reload. The shell as a whole is not restarted for a module that raises.

## Python Contract

No change for a module author. The module host gains the running-callback record, a `WATCHDOG=1` writer next to the existing `READY=1` and `STOPPING=1` writer, and the crash and marker files.

## Integration

- `sd_notify` over `NOTIFY_SOCKET` (path and abstract sockets) is already built by the shell; `WATCHDOG=1` and `WATCHDOG=trigger` are two more messages.
- Files: `crash.log`, `crash.log.1`, `running` in the shell's state directory; the registry in the config directory.
- Threads: the watchdog thread reads the heartbeat and writes to `NOTIFY_SOCKET`; it never touches nodes.

## Failure modes and recovery

| Failure | Result |
|---|---|
| A callback hangs | Stall logged at 2 s naming the module; at 10 s `WATCHDOG=trigger`; systemd terminates with `SIGABRT` and restarts after 2 s; tracebacks in `crash.log` and the journal |
| The loop hangs and there is no systemd | Logged and tracebacks dumped; nothing else the shell can do |
| The shell is killed (`SIGKILL`, the out-of-memory killer) | systemd restarts it; the marker `running` marks the next start unclean |
| Three unclean starts in a row | Safe start: user modules skipped, named in a warning |
| Five starts in 60 s | systemd stops the unit; the evidence is in the journal, `crash.log` and `status` |
| The registry is corrupt | Rebuilt from the UIDs in the files; saved positions are lost, with a warning |
| The compositor goes away | Exit with a code that restarts; the surfaces return on the new compositor |

## Performance budget

The heartbeat is one timer at most once a second and one store; the watchdog thread wakes once a second and, under systemd, writes one datagram every `WatchdogSec / 2` (7.5 s). That is about 2 wake-ups per second of its own, against an idle budget of 5 for the whole shell, of which tre's own watcher and the Clock already use some ([Performance Budgets](Performance%20Budgets.md)); M7c measures the total and the heartbeat is slowed (to every 2 s, with a 10 s decision unchanged) if the budget is at risk. The registry write is debounced to one per second and runs off the loop.

## Open Questions

1. [x] Does the shell start in safe start after repeated crashes (above)? Answered by the maintainer on 2026-11-17: yes, we want a safe start; it is built as written (3 unclean starts in 10 minutes, user modules skipped and named). The code session already proceeds on this recommendation, so nothing changes for it. Original text: Context: a crash loop is most often a user module; without it the user has no bar while they fix it. Recommendation: yes, 3 unclean starts in 10 minutes, user modules skipped, clearly logged.
2. [x] Is `WatchdogSec=15` right? Context: the shell decides at 10 s and systemd backs it up at 15 s; a slow machine or a long blocking start could trip it. Recommendation: 15 s, with the heartbeat started only after step 12 of the start sequence so that startup is not judged ([Shell Start and Stop > Start Sequence](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#start-sequence)). Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.
3. [x] May the heartbeat be slowed to once every 2 s if M7c shows the idle wake-up budget at risk? Context: about 2 wake-ups per second of its own against a budget of 5 for the shell. Recommendation: yes; a 10 s stall decision needs no finer resolution than 2 s. Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.

## Questions After Testing

1. [x] Does a user manager restart a `Type=notify` service that misses `WATCHDOG=1`, with `SIGABRT` and a restart after 2 s? Answered 2026-11-17 in a private systemd user manager: `SIGABRT` at 15.06 s and a restart 2.27 s later (see As Built). Context: read from the manual, not run. Recommendation: test it in the private user manager of the kits with a module that sleeps 20 s. Answered by: the M7b kit line.
2. [x] What does the shell do today when the Wayland connection drops, and with which exit code? Answered 2026-11-17: it exited 2 with no stop sequence, which the unit never restarts; now it exits 69 after a stop sequence. Answered by: reading the code, then a kit line that kills the private KWin.

## As Built (code session's report of `tess-shell` PR #67, merged 2026-11-17, CI green; not run in the vault)

- **Watchdog.** `watchdog.py`: a heartbeat and a watchdog thread, started on the loop's first turn (after start step 12). A stall of 2 s logs one warning naming the module, the entry point and how long (from M7a's `host.callbacks.running()`) with every thread's traceback (`faulthandler`), again every 5 s while it lasts. At 10 s it sends `WATCHDOG=trigger` when `NOTIFY_SOCKET` and `WATCHDOG_USEC` are set, else it logs "loop stalled for 10 s, no supervisor can restart it" and dumps tracebacks every 30 s. With `WATCHDOG_USEC` unset nothing goes to `NOTIFY_SOCKET`. `WATCHDOG=1` is sent every half interval only while the heartbeat is under 5 s old. A test-only variable scales the times.
- **Unit.** The unit `install-session` writes has `WatchdogSec=15` in `[Service]`; the start-limit keys stay in `[Unit]`, and the existing test still fails if one moves. The guide and README are updated.
- **Crash record.** `recovery.py`: `crash.log` in the state directory (`faulthandler`, all threads; `.1` and `.2` kept); the `running` marker written after the instance lock and removed at a clean stop; "previous run ended uncleanly" logged and counted; `status` shows the count, the last crash and safe start, also when no shell runs.
- **Safe start (built as decided).** Shipped modules only, with the skipped user modules named in one warning; a reload or `SIGHUP` ends it; a clean stop resets the count; it fires on the start that finds the marker of the third run that ended uncleanly within 10 minutes.
- **Registry.** Written within 0.2 s of any change, off the loop, with a temporary file and a rename (the `UID:` writes already were; now tested).
- **Lost compositor.** Before this the shell exited 2 with no stop sequence, which the unit never restarts. Now it stops the modules, saves the registry and exits 69 (`EX_UNAVAILABLE`), which the unit restarts; 69 is in the exit-code table and the guide.
- **Observed in a private systemd user manager** (kit `tests/kwin/prepare_m7b_watchdog.py`, 9 of 9 steps in 3 runs; the first two exposed kit bugs, fixed): a `Type=notify` service that never pings gets `SIGABRT` 15.06 s after it starts and is restarted 2.27 s later (`Result=watchdog`); the shell with a module sleeping 20 s is named at 2 s (module and entry point), asks systemd at 10 s with `WATCHDOG=trigger`, and is back with its surfaces 12.8 s after the call (the manager acts at once on a trigger, so the restart is not at 15 s); `crash.log.1` holds the traceback; a killed private sway makes the shell exit 69 (`status=69/UNAVAILABLE`), restarted 2.7 s later and not counted as a crash. 13 of 14 mutations were caught outright; the 14th needed an added test with a `SIGKILL`ed run.
- **Limit:** a loop blocked in a C extension that holds the GIL cannot be seen by a Python thread; the abort-time traceback goes only to `crash.log`, not the journal.

### Decisions from the build (code session's list)

- A corrupt `registry.json` is moved aside as `registry.json.corrupt-<time>` and rebuilt. This note says rebuild; [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md) and [Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md) say exit 1; a registry from a newer shell is still refused. Recommendation: as built; those two notes are to be corrected.
- `status` with no shell running keeps exit 3 and prints the crash lines to stderr only when there is something to say.
- The heartbeat uses `call_soon`, not `window.every`, because a shell with no windows has no timer. Wake-ups are not measured yet (M7c).
- After a lost compositor the restarted shell exits 2, and the unit stays down if no compositor is up within `RestartSec=2`. A longer delay or a polling wait is open; [TRE-REQ-026 Lost Connection Signal and Layer Shell Re-Probe](../80%20Requests/TRE-REQ-026%20Lost%20Connection%20Signal%20and%20Layer%20Shell%20Re-Probe.md) is the engine side. The report's "not built" item was cut off in what the vault read.

## Acceptance criteria

- [ ] A fake module whose callback sleeps 20 s is named in the 2 s warning (module and entry point), tracebacks are in the log, and under a private systemd user manager the shell is restarted by the watchdog and comes back with its surfaces.
- [ ] With `WATCHDOG_USEC` unset, the same hang is logged and nothing is sent to `NOTIFY_SOCKET`.
- [ ] Pings stop while the heartbeat is older than 5 s.
- [ ] A moved Panel's position is in `registry.json` within 1 s of the move and survives `SIGKILL` of the shell.
- [ ] The registry and any `UID:` write use a temporary file and a rename; killing the shell during a write leaves a complete old or new file.
- [ ] `crash.log` receives the tracebacks of a `SIGABRT`; the previous one is kept as `crash.log.1`.
- [ ] After `SIGKILL`, the next start logs `previous run ended uncleanly` and `status` shows the count.
- [ ] Three unclean starts in a row start the shell with user modules skipped and named.
- [ ] The unit that `install-session` writes has `WatchdogSec=15` and its test still fails if a restart-limit key moves to `[Service]`.
- [ ] Killing the private compositor makes the shell exit with a restart-worthy code and systemd restarts it.

## Links

[M7 Brief](../00%20Home/M7%20Brief.md) · [Security Model](Security%20Model.md) · [Module Process Test](Module%20Process%20Test.md) · [Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md) · [Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md) · [Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md) · [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md) · [Risk Register](../00%20Home/Risk%20Register.md) · [60 Quality](60%20Quality.md)

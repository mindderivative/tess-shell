---
title: Logging
aliases: [Shell Logging, Log Files, Loguru Spec]
type: spec
status: review
owner: phil
created: 2026-10-28
updated: 2026-10-29
tags: [spec/runtime, needs-verification]
related: ["[[Runtime]]", "[[Logging with Loguru]]", "[[Settings File]]", "[[Validation and Errors]]", "[[Shell Start and Stop]]", "[[IPC and CLI]]", "[[Module Context]]", "[[Process Model and Threading]]"]
depends_on: ["[[Settings File]]", "[[Logging with Loguru]]"]
---

# Logging

> [!summary]
> What the shell writes to its log, where, in what shape, and how fast. Loguru is the logger (the maintainer called it a great option on 2026-10-25; formally chosen 2026-10-28). Already decided: the log directory `logs/` in the config directory, one file per local day named `log_yyyy-mm-dd.log`, the sink swapped at local midnight, retention left to the user, the keys `level`, `directory` and `retention` under `logging`, a bad settings file logs to the default directory, and a runtime `SetLogLevel` call ([[Settings File#Log files]], [[Shell Start and Stop]], [[IPC and CLI]]). This note adds the record shape, the levels, the sinks, the routing of everything that does not use Loguru, the safety rules and the cost, as proposals with recommendations.

## Purpose and Scope

- Define the logger, the sinks, the level policy, the record fields, how modules, libraries and tre feed the log, and how secrets stay out.
- Not in this note: the wording of validation errors ([[Validation and Errors]]), the start order ([[Shell Start and Stop]]), and the file naming and retention, which are in [[Settings File#Log files]] and are not repeated.

## Behaviour

### The Logger

Loguru, one process-wide logger ([[Logging with Loguru]]). Checked on this machine on 2026-10-28 with Loguru 0.7.3 on Python 3.14.8: it imports, and the tests below ran. Its newest release is 0.7.3 (2024-12-06) and the repository is active ([[Logging with Loguru#What to check]]). Pin the version and test each release on the supported Python. The maintainer chose Loguru formally on 2026-10-28 (question 1).

### Sinks

| Sink    | Where                                     | Format                                             | When                                     |
|---------|-------------------------------------------|----------------------------------------------------|------------------------------------------|
| File    | `log_yyyy-mm-dd.log` in the log directory | One line per record, plain text, no colour         | Always, once the log directory is usable |
| Console | stderr                                    | The same line, in colour when stderr is a terminal | Always; shorter under systemd            |

- **Started at step 4** of the start sequence, after `settings.tdl` is read ([[Shell Start and Stop#Start sequence]]). Until then, and if the file sink cannot start (a read-only directory), records go to the console only and the shell says so; it does not stop ([[Shell Start and Stop]]).
- If `settings.tdl` fails, the error goes to the console and to the default log directory, `logs/` in the config directory ([[Settings File#A bad settings file stops the shell]]).
- **The file sink swaps at local midnight:** a loop timer fires once a day, adds the next day's sink and removes the old one. It is the only periodic wake the logger adds. A restart on the same day appends ([[Settings File#Log files]]).
- **Permissions.** The log directory is created with mode 0700 and files with 0600: records name files, modules and surfaces (decided 2026-10-28).
- **Under systemd** the console line can drop the timestamp, because the journal adds its own. The shell uses the environment variable `JOURNAL_STREAM`, which systemd sets for a service whose output goes to the journal, to decide (decided 2026-10-28). #needs-verification of the variable's meaning in `systemd.exec(5)`.

### Levels

| Loguru level | Used for                                                                                                               |
|--------------|------------------------------------------------------------------------------------------------------------------------|
| `DEBUG`      | Diagnostics: which file was loaded, a reload's diff, a D-Bus call                                                      |
| `INFO`       | The normal story: start, ready, a reload applied, stop                                                                 |
| `WARNING`    | Something is off and the shell continues: a validation `warning`, a target that disappeared, a rebuilt registry record |
| `ERROR`      | A failure the shell survives: a validation `error` on a reload, a module that raised, a surface that failed to open    |
| `CRITICAL`   | The shell cannot continue: an unhandled exception outside a callback (exit code 70)                                    |

`TRACE` and `SUCCESS` are not used. A validation finding's `severity` maps to the same-named level, so the log and the console agree ([[Validation and Errors#The error record]]). The default level is `INFO` (`logging.level`, [[Settings File]]); the `--verbose` option of the command line is `DEBUG` for that run. `SetLogLevel` changes the level until the next reload of `settings.tdl`, which applies the file's `level` again ([[IPC and CLI]]).

### The Record

One line, in this order, separated by ` | `:

```
2026-10-28 09:14:03.512 | ERROR   | shell | Shells/Main_Shell.tdl:12:9 unknown-key | unknown style key 'colour' on bar 'top_bar'
2026-10-28 09:14:04.001 | INFO    | module:Clock | - | started with 2 uses
```

| Field    | Meaning                                                                                                        |
|----------|----------------------------------------------------------------------------------------------------------------|
| time     | Local time, with milliseconds                                                                                  |
| level    | As above, padded                                                                                               |
| source   | `shell`, `module:<name>`, `lib:<name>` (a library through the standard `logging` module), `warnings`, or `tre` |
| location | `file:line:column rule` for a finding with a position, otherwise `-`                                           |
| message  | The text                                                                                                       |

Behind the line, each record carries structured fields (`file`, `line`, `column`, `rule`, `severity`, `module`, `uid`) through Loguru's `bind`, so a file in JSON form keeps them ([[Validation and Errors#The error record]]). `logging.format: json` writes one JSON object per line with `serialize=True` (decided 2026-10-28); the default is text. A test on 2026-10-28 showed `serialize` keeping the bound fields (`rule`, `file`, `line`, `column`) in the record's `extra`.

### Who Writes

- **The shell** logs with source `shell`.
- **A module** logs through `self.ctx.log`, a logger bound to the module's name and UID ([[Module Context]]). The module does not touch sinks or levels. An exception in a callback or a `ctx.thread` function is logged by the shell with the module's name ([[Process Model and Threading#Failure and recovery]]).
- **A library** that uses the standard `logging` module (for example `dbus-fast`) is routed into Loguru by one handler on the root logger, at `WARNING` and above by default. A test on 2026-10-28 showed the routing: a `dbus_fast` warning appeared as `lib:dbus_fast | WARNING | bus closed`.
- Python's `warnings` are routed the same way, with source `warnings`. A test showed a `DeprecationWarning` arriving as a `WARNING` record with the file and line.
- **TEL** never imports Loguru. It raises errors that carry file, line and column, or uses the standard `logging` module, and the shell turns them into records ([[Logging with Loguru#What to check]], [[ADR-0008 Tesserae Expression Language]]).
- **tre** writes its own errors to stderr through Rust's tracing, not through Python's `logging`. A test on 2026-10-28 made a click listener raise and got, on stderr only: `ERROR engine_py::dispatch: uncaught exception in a Python callback traceback=...`, with colour codes; nothing reached a Python `logging` handler. So tre's errors are not in the log file unless the shell forwards them. Decided 2026-10-28: the shell wraps every callback it registers in a guard that logs the exception with Loguru, so tre's own message becomes a last resort; and it forwards the process's stderr into the log as source `tre`, through a pipe and a reader thread, falling back to leaving stderr alone if that cannot be set up. #needs-verification that the forwarding cannot block the process.

### Safety

- **No secrets.** Tracebacks are written with `diagnose=False` by default. A test on 2026-10-28 showed why: with `diagnose=True` Loguru prints the value of each variable in a failing frame (a variable holding `hunter2` appeared in the log), and with `diagnose=False` it did not. `logging.diagnose: true` is a switch for debugging (decided 2026-10-28).
- **No param values.** The shell and the standard modules do not log a module's params or a config value that might be private; the rule that `Status` follows ([[IPC and CLI#Security]]). A module author is told the same in the module contract.
- **No per-frame logging.** Logging is for events. A `DEBUG` message in a hot path is still cheap when filtered out (0.13 µs per call in a test), but the shell keeps frames free of it ([[Goals and Non-Goals]] G4).
- **Format with arguments,** not f-strings, so a filtered-out message costs nothing to build (`logger.debug("loaded {}", name)`).

### Threads and Speed

Measured on this machine on 2026-10-28 (Loguru 0.7.3, a file sink, 20,000 calls):

| Setting                                      | Cost per call |
|----------------------------------------------|---------------|
| A synchronous sink                           | 6.7 µs        |
| `enqueue=True` (a queue and a writer thread) | 27.2 µs       |
| A message below the sink's level             | 0.13 µs       |

Loguru's sinks are safe to call from any thread. The loop thread must not block on disk or on a full pipe ([[Process Model and Threading#The rules]]), so the shell uses `enqueue=True` for both sinks: the call costs a few tens of microseconds and the write happens on Loguru's own thread. Decided 2026-10-28. At stop, `logger.remove()` ends the sinks and waits for the queue, so the last records are written ([[Shell Start and Stop#Stop sequence]]). #needs-verification that `remove` flushes the queue.

### Crashes

- `sys.excepthook` and `threading.excepthook` log an unhandled exception at `CRITICAL` before the process ends; the asyncio loop on the service thread has an exception handler that does the same ([[Process Model and Threading#Threads]]).
- A failure to write a log line never raises into the caller; Loguru's `catch=True` is its default.

## Configuration

`logging` in `settings.tdl` ([[Settings File]]):

| Key              | Meaning                                                 | Status                              |
|------------------|---------------------------------------------------------|-------------------------------------|
| `level`          | The minimum level; default `INFO`                       | Decided                             |
| `directory`      | The log folder; default `logs/` in the config directory | Decided                             |
| `retention`      | Days to keep daily files; unset keeps all               | Decided that it exists (2026-10-27) |
| `format`         | `text` or `json` for the file                           | Decided (2026-10-28); default `text`            |
| `diagnose`       | Show variable values in tracebacks; default false       | Decided (2026-10-28)                            |
| `console`        | Write to stderr; default true                           | Decided (key name accepted 2026-10-29) |
| `capture_stderr` | Forward the process's stderr into the log; default true | Decided (2026-10-28)               |

The reload rule is already decided: a change to `logging` applies at once ([[Settings File]]).

## Python Contract

`self.ctx.log` is a Loguru logger bound with `module` and `uid`. A module calls `self.ctx.log.info("started with {} uses", n)`; it never configures Loguru and never calls `logger.remove`. The module contract says what not to log ([[Module Context]], [[Module Contract]]).

## Integration

- Loguru; the standard `logging` and `warnings` modules; Rust's tracing output on stderr from tre; systemd's journal when the shell runs as a service ([[Shell Start and Stop#Telling systemd (decided 2026-10-28)]]).
- Threads: any thread may log; the sinks have their own writer thread ([[Process Model and Threading#Threads]]); the midnight swap runs on the loop.
- The command `tesserae-shell log-level` and the `SetLogLevel` call ([[IPC and CLI]]).

## Design

Plain text, one record per line, no colour in the file, no emoji ([[AGENTS#10. Writing style]]). Colour on the console only when stderr is a terminal.

## Accessibility

A plain-text log is readable by a screen reader and `grep`. The console keeps the same wording as the file.

## Performance Budget

- A record costs about 27 µs on the calling thread with `enqueue=True`; the shell logs events, not frames.
- The logger adds one timer a day (the midnight swap) and one writer thread that sleeps until a record arrives ([[Goals and Non-Goals]] G4). Measured in testing.
- Disk use is the user's to manage (retention, [[Settings File#Log files]]); a typical day at `INFO` is small. Not measured.

## Failure Modes and Recovery

| Failure                                        | Result                                                                                    |
|------------------------------------------------|-------------------------------------------------------------------------------------------|
| The log directory cannot be created or written | Console only; a warning names the path                                                    |
| The disk is full                               | Loguru's write error is swallowed; the shell continues; the console still has the record  |
| A reload changes `logging` to a bad value      | The old logging stays and the error is reported ([[Validation and Errors]]) |
| The midnight swap fails                        | The old file keeps being used; a warning names the reason                                 |
| tre writes to stderr and forwarding fails      | The text stays on stderr (journal or terminal)                                            |
| A very noisy library                           | Its level is raised for its source (a later feature); the cap is the sink's level                |
| Two shells                                     | Prevented by the lock ([[Shell Start and Stop#Process rules]])                           |

## Open Questions

All nine were answered on 2026-10-28, as recommended.

1. [x] The logger: Loguru, as a formal decision.
2. [x] `enqueue=True` for both sinks.
3. [x] tre's stderr: forward it into the log.
4. [x] `diagnose` off by default, with a key to turn it on.
5. [x] A JSON file format as an option, text by default.
6. [x] File permissions: directory 0700, files 0600.
7. [x] Library records at `WARNING` and above by default.
8. [x] Per-source levels: later, not v1.
9. [x] Under systemd, a shorter console line without the timestamp.
- [ ] To verify: that `logger.remove()` flushes the queue at stop; that forwarding stderr cannot block the process; the meaning of `JOURNAL_STREAM` in `systemd.exec(5)`.
- [ ] Not asked: the `console` key.

## Acceptance Criteria

- [ ] With the defaults, the shell writes `log_yyyy-mm-dd.log` in `logs/` and the same lines on stderr; a file with an error appears in both with `file:line:column` and the rule.
- [ ] A module's `ctx.log.info` line shows `module:<name>` as its source.
- [ ] A `dbus-fast` warning and a Python `DeprecationWarning` appear in the file as `WARNING` records with their sources.
- [ ] An exception in a shell-registered callback is logged by the shell with a traceback and no variable values.
- [ ] With `logging.diagnose: true` a traceback shows variable values; with it off it does not.
- [ ] With the shell running across local midnight, the next record goes to the new day's file and the old file is whole.
- [ ] With the log directory read-only, the shell starts, warns, and writes to the console.
- [ ] `tesserae-shell log-level debug` makes `DEBUG` records appear until `settings.tdl` is reloaded.
- [ ] A burst of 10,000 log calls from a module thread does not delay the loop by more than a frame (measured).
- [ ] After a normal stop, the last record written before stop is in the file.
- [ ] An unhandled exception on a module thread is logged at `CRITICAL` before the process ends.

## Links

- [[Runtime]] · [[Logging with Loguru]] · [[Settings File]] · [[Validation and Errors]] · [[Shell Start and Stop]] · [[IPC and CLI]] · [[Module Context]]

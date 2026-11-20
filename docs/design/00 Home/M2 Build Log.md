---
title: M2 Build Log
aliases: [M2 Log]
type: moc
status: draft
owner: phil
created: 2026-11-04
updated: 2026-11-04
tags: [moc, build-log]
---

# M2 Build Log

> [!NOTE]
> The log of milestone M2, live and modular. The `tess-shell` code session owns this note ([Build Logs](Build%20Logs.md)). The vault session had not created it when M2a was built, so the code session wrote the first version on 2026-11-04 in the layout of [M1 Build Log](M1%20Build%20Log.md); please link it from [Build Logs](Build%20Logs.md). M2a (live values) and M2b (structure and reload) are built; the KWin checks are the maintainer's.

## Tasks

| Task | State | Commits in `tess-shell` | Note |
|---|---|---|---|
| A1 `Import` and module calls | Built | 7cb2210 | `Import: <path>_Module.tdl` (one file or a list, relative to the importing file) embeds a module at that position; a module may call or import another; modules are read in two passes (names and params, then layouts), so the order of files does not matter; a circle is `import-cycle` naming the chain. `Import` of a shell file is `not-built` |
| A2 File UID write | Built | b8dbb15 | `UID:` is added to a user's module and shell files on first registration, one line, after the version lines, no other byte changed; a backup first under `$XDG_STATE_HOME/tesserae-shell/backups/<path>.<timestamp>`; the registry keeps `file:<path>` and use entries; shipped files are never edited |
| A3 Module host | Built | dbc0495 | `modules/host.py`: imports `<Name>_Module.py`, one `Module` class, `ctx` set before `start()`, `validate_use`, failures isolated. Missing `.py`, no or two classes, an import error and a raising `start()` each give a finding naming the files and the line; other modules keep running |
| A4 Value store | Built | 2dada66 | `model/store.py`: thread-safe `send`, one wake per turn, latest value per use and key, plain data only (strings, numbers, booleans, lists and dicts of those), a copy of the value, a value sent back inside one turn is not a change |
| A5 TEL scope, slots, links | Built | 354b8e8, 2dada66 | `{{ }}` in a value becomes a `SlotValue` whose parts keep the origin of the slot text; `model/live.py` compiles each slot with that origin, evaluates in the use's scope (`params`, the sent values), records `reads`, and re-evaluates only the links a changed key touches; an error keeps the last value and logs `file:line:column` with the nearest name |
| A6 Binder `SlotValue`, `View.update` | Built | d1932ac | `View.update([(node id, key, typed value)])` converts with the key's own table row, skips a value the node already has, and makes one `Window.apply` |
| A7 Clock with `ctx.on_tick` | Built | dbc0495 | `shipped/Clock/`; `format`, `hour_cycle`, `timezone`; `--:--` fallback for a bad format; `modules/ticks.py` is the shared wall-clock source (one thread, woken only at a subscribed second or minute, recomputed from the wall clock each time; a clock moved back is handled) |
| A8 Tests, KWin check, idle measurement | Partly | 7cb2210 | Tests and the idle measurement are done; the KWin check of the Clock is the maintainer's |
| B1 `If`/`Else` and `For` | Built | 56ff20c, 42066ee | The schema types them (inside `Children`, in shell and module layouts); `model/live.py` evaluates the condition (`select_tracked`) and the repeater (`compile_repeater_parts`, `reconcile_tracked`, a `RepeaterState` kept between resolves, entries named `<head>_0001` and never reused). A use that has structure is resolved again and handed to `View.rebuild` when anything its slots, conditions or headers read changes; a key nothing reads causes no rebuild. A module call or `Import` inside `If`/`For`, and `If`/`For` outside a module, are `not-built` |
| B2 File watcher | Built | 250e689 | `watch.py`: one thread blocked in `select` on one inotify descriptor (`inotify_simple` 2.0.1), close-write, moved-to, moved-from and delete; ignores dot files, `~`, `.swp`, `.tmp`, `.bak` and the `schemas`, `logs`, `backups` folders; watches folders created later; one callback with the set of paths after 200 ms of quiet; a watch that cannot be added turns `ok` off with a warning |
| B3 Reload by keyed diff | Built | 42066ee, 039caf5 | `View.rebuild` (identity: `Name`, else block word and position; kept nodes get their changed properties in one `Window.apply`; new subtrees through `Window.build`; `set_children` for order; removed nodes freed; a changed block word or a property the new tree no longer sets is a replacement; a bad value changes nothing). `reloader.py` validates on the watcher thread and applies on the loop: modules first (`ModuleHost.sync`: a module no longer used is stopped, a new one loaded and started, a changed `.py` imported first and replacing the instance only if the import works, a changed module or style TDL calls `reload()` and keeps the instance, `use_added`/`use_removed`), then each Bar kept (rebuilt, geometry set live in one `set()`) or closed or opened. An error anywhere changes nothing and is reported at `file:line:column`. `SIGHUP` reloads everything |
| B4 Module style files | Built | 257179f | `Style: <Name>_Style.tdl` (relative to the module file) or an inline `Style { }` in a module; `Classes { name { Kind: Text, ... } }` and per-type defaults; `Class:` (one name or a list) on a block. Priority: the file's type default, then its classes, then the block's inline `Style`, then keys written on the block. Missing class, class of another block type, missing or bad style file: errors at their own file and line. The shipped Clock takes its look from `Clock_Style.tdl` |
| B5 Icon sets | Built | 82b1533 | `SVG { Icon: "mdi:account" }`: Iconify-style JSON in the config `Icons` folder, then `Directories { Icons: [...] }`, read on the first lookup (the real 7,447-icon `mdi` file: 5 ms); a prefix selects a set, no prefix looks in `mdi` first; `Color` tints it; an unknown icon is an error at its value with the nearest names; an SVG needs `Source` or `Icon`, not both |
| B6 Tests, reload time | Built | 039caf5, a27c950 | Unit and live tests; `tests/perf/reload-results.md`. The KWin check of the reload cases is the maintainer's |

## KWin Checklist

To run by hand on the maintainer's session (written by the code session; the brief asks for "a KWin check of the Clock and the reload"). Scratch configs and scripts are in `/tmp/tess-kwin-m2`; `run.sh <variant>` starts one with a private state directory. Results are recorded below the list when reported.

- [x] **Clock, local time.** `run.sh clock`: the left clock shows `HH:MM:SS` and changes every second, none skipped.
- [x] **Clock, two uses.** The second clock shows the time in Tokyo (`HH:MM Tokyo`), different from the first, from the one module instance.
- [x] **Clock, minute.** With `run.sh todo` the Clock (default format) changes at the start of a minute.
- [x] **For list.** `run.sh todo`: yellow items `item 1`, `item 2`, ... appear one per second and the list starts over after six; the earlier items do not flicker.
- [x] **Icons.** `run.sh icon`: a green charging battery and a blue account icon, 18 px, in the Bar's colours.
- [x] **A bad icon.** `/tmp/tess-kwin-m2/check.sh` (the config names `mdi:acount`): `no icon named mdi:acount` with the hint `did you mean account, counter, account-tie?`, exit code 1.
- [x] **Idle between ticks.** `run.sh todo` stopped, then `run.sh icon` (minute clock only): `top -p $(pgrep -f 'tesserae-shell run')` near 0 %; the report of the wake-ups on a real GPU for D19 is welcome.
- [x] **Reload, height.** `run.sh live`, then in a second terminal `/tmp/tess-kwin-m2/edit-height.sh`: within about a quarter of a second the Bar grows to 48 px and maximised windows stop below it; the log prints `reloaded (Main_Shell.tdl)`. Run it again to go back.
- [x] **Reload, module style.** `edit-style.sh`: the `probe v1` text changes colour and the log prints `probe reload() called` once, with no `probe started` after it.
- [x] **Reload, module code.** `edit-python.sh`: the text becomes `probe v2`; the log shows `probe stopped`, then `probe started (v2)`.
- [x] **A bad file.** `edit-bad.sh` (writes `Edge: top`): the Bar does not change and the log prints `Shells/Main_Shell.tdl:15:23: error` with `write TOP`; then `edit-fix.sh` and the next change reloads.
- [x] **Bad module code.** `edit-syntax.sh`: the log names `Probe_Module.py:2`, the old `probe v2` keeps running; `edit-restore.sh` brings back v1.
- [x] **SIGHUP.** `edit-hup.sh`: the log prints `reloaded (everything)`.
- [x] **The shell's own write.** The first start of any variant adds a `UID:` line to its files; the log must not print `reloaded` because of it.
- [x] **Stop.** SIGTERM, then `echo $status` in fish: 0 and the Bar goes away.

### KWin Results

Reported by the maintainer, 2026-11-04, on `/tmp/tess-kwin-m2` (first pass, before the width fix below):

| Line | Result |
|---|---|
| Clock, local time | Ticks every second. The two clocks overlapped (bug, below) |
| Clock, two uses | Different text from one instance, but overlapping the first |
| For list | Pass: one item per second, restarts after six, no flicker on the earlier items. The Clock overlapped the yellow items (same bug) |
| Icons | Pass: a green charging battery and a blue account icon, side by side. They overlapped the Clock (same bug) |
| A bad icon (`check.sh`) | Pass: `no icon named mdi:acount`, the hint `did you mean account, counter, account-tie?`, exit code 1 |
| Reload, height (`edit-height.sh`) | Pass (from the log, 2026-11-04 21:14): `size (0, 48) zone 48`, `reloaded (Main_Shell.tdl) in 7 ms`, then `configured 1920x48` |
| Reload, module style | Pass: `probe reload() called` once, `1 changed`, no `probe started` after it |
| Reload, module code | Pass: `probe stopped`, `the code was replaced`, `probe started (v2)`, `reloaded (Probe_Module.py) in 5 ms` |
| A bad file | Pass: `Shells/Main_Shell.tdl:15:23 bad-value`, `reload refused`, the Bar kept running (the same refusal repeated four times, the file being rewritten unchanged). The accepted-again step after `edit-fix.sh` is not in the log |
| Own write | Pass for the first start: the UID lines caused no reload. A UID written during a reload is covered by a live test, not yet seen on KWin |
| Clock tick in the log | One update per second about 5 ms after the boundary, none skipped, about 2.7 minutes |
| Stop (log) | `closed (stopped)`, `stopping`, `probe stopped`, `stopped`; the exit code was not reported |
| Second live run (21:25 to 21:27) | Pass: `edit-height` back to 32 (9 ms), bad file refused then `edit-fix` accepted (6 ms), `edit-syntax` located at `Probe_Module.py:2:1` with the running module kept, `edit-restore` restarted it (v1), SIGHUP twice gave `reloaded (everything)` in 6 to 7 ms, clean stop. Starting on a bad file refuses to run. |
| Stop and idle | Pass (maintainer, 2026-11-04): exit code 0 after SIGTERM; `run.sh icon` stayed at 0 % CPU for 2 min. The minute tick (checklist line 3) was not reported on its own and the `todo`/`icon` logs run at INFO, so they hold no tick evidence; the maintainer then watched `run.sh icon` across a minute boundary and the clock changed exactly at the minute change (pass). Wake-up count not measured on KWin. |
| Finding | Finding: after a module syntax error the log says `reloaded (Probe_Module.py)` right after the ERROR, which reads as success though the module is kept |

The overlap was a binder bug found by the maintainer and reproduced headless: tre lays a text node with no `width` out at width 0, so two texts in a row sat on top of each other (the M1 sample has one text, which hid it). A `Text` now defaults to `width: "fit-content"` (commit `4e08b54` in `tess-shell`, with a layout test); the two clocks measure 56 px each at x 4 and 68. The lines marked overlapping were re-run after the fix: the maintainer reports that all pass (2026-11-04), so the Clock (two uses, per second), the For list and the icons are confirmed on KWin. The maintainer says tre has been directed to measure an unset text width to its content; until that release the `fit-content` default stays, and after it the code session re-runs the width and reference-image tests on the new tre and removes the default if the result is the same.

## Measurements

| What | Result | Date and conditions |
|---|---|---|
| Tests | 663 passed, `ruff` and `mypy` clean (579 at the end of M2a) | 2026-11-04, `uv run pytest`; Python 3.14.9 with the GIL, tre 0.6.1 |
| The Clock ticks on the Bar | With `format: "%H:%M:%S"` the text changes every second for four ticks in a row, none skipped or repeated (live sway test, from the DEBUG log) | private headless sway |
| Idle with the Clock shown, 60 s window | 0.017 % of one core; 8.07 wake-ups per second (budget 5), 73 threads | private headless sway, Python 3.14.9, `tests/perf/idle-results-clock.md`, reported not enforced |
| Where the wake-ups are | Between ticks, 2 per second (tre's own `blocking-1` thread: 133 of 474 switches in 66 s). One minute tick in the window adds a burst of about 340 switches, almost all on tre's `llvmpipe` software-renderer threads (12 threads, 14 to 15 switches each); the Python main thread has 21. The shell's own time-source thread wakes once a minute | same, per-thread counts from `/proc/<pid>/task/*/status` |
| Reload time | A saved `Height` is applied a median of 206 ms after the save (best 205, worst 208 over 10 saves): the 200 ms debounce plus about 5 ms to validate, diff and set (5 to 7 ms). The Bar's reserved zone follows in one reflow | private headless sway, `tests/perf/measure_reload.py`, `tests/perf/reload-results.md` |
| Idle with the Clock and the watcher, 60 s window | 0.000 % of one core; 7.75 wake-ups per second (8.07 before the watcher), 74 threads (73 before): the watcher blocks in `select` and wakes only on a file event, so it adds none; the number is the minute tick's burst on the software renderer (D19) | same, `tests/perf/idle-results-clock.md` |
| Value changes to nodes | One `Window.apply` per Bar per turn; a send that changes nothing a slot reads makes no node call; two sends of one key in one turn make one change (tests in `tests/test_model_live.py`, `test_model_store.py`) | headless `tess_re` window |

## Differences from the Specs

- Clock: `locale`, `tooltip_format` and the `ctx.after` form are not built (G7). `hour_cycle: desktop` follows 24 hours, because how KDE exposes the regional setting is still open in [Clock Module](../40%20Specifications/Modules/Clock%20Module.md); `12` gives `%I:%M %p`. The use of a bad `format` or `timezone` is rejected in `validate_use` and shows `--:--`.
- The Clock's layout is a `Text` with an inline `Style`, not a Label module with a style file (module style files are B4, M2b).
- A slot outside a module (in a shell file) is `not-built`: M2a reads only module values and `params`; the file's name tree comes later ([TEL Integration](../20%20Architecture/TEL%20Integration.md) open question 2: only the module's own values and `params`).
- A slot in a module call's param is `not-built`.
- A module's ids: every named node inside a use is prefixed with the use key (`Clock@<uid>/Face`) so two uses of one module never share an id; a node with a slot and no name gets `<use key>/#<n>`.
- A module's `Params` allow `string`, `number` and `boolean` with defaults, as decided (G6); `color`, `size`, `list`, `mapping` are not read.
- A module's Python file is found next to its TDL file by name (`Clock_Module.tdl`, `Clock_Module.py`); `ctx.config` holds only the module's name in M2a; `ctx.tdl`, `ctx.thread`, `ctx.dbus`, `ctx.data_dir` and `ctx.state_dir` are not built.
- The registry keys: `file:<path relative to the config>` for files and the dotted use path for uses, each with a UUIDv7 `uid`; the use key is `<Module>@<uid>`. Nothing prunes the registry yet.
- Where the code lives: `model/` (store, expand, live, uses), `modules/` (host, context, ticks), `schema/graph.py` (cycles), `config/uids.py`. `modules` imports `model` and `schema`, never `tess_re`; `surfaces/manager.py` imports `model`.

M2b, where it departs from the specs:

- Reload validates every file again, not only the affected set ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md) says "the affected set"): a rescan costs about 5 ms, so the map from a file to its importers is not built. Because of that, a removed file that something imports is simply the importer's own error (`import-not-found`) and the old state is kept.
- TEL compiles on the loop thread, at resolve time, not on the watcher thread (Hot Reload and T16 say the worker thread): compiling a slot is microseconds. Validation of slot syntax therefore happens when the surface is resolved, not in `check`; a slot error is logged and the property stays as it was.
- A use whose layout has `If` or `For` is resolved again whole, and the keyed diff keeps what is the same, instead of per-slot links as for a use without structure. `For` entry names restart on a reload (the `RepeaterState` is dropped, because the compiled expressions may have changed); the diff then matches entries by those names.
- The keyed diff: a kept node that loses a property is a replacement (tre has no way to unset a property); a moved child with a changed `Name:` is a replacement (the note's recommendation).
- A Bar window is kept when its key (the dotted path, with the output when a block opens on several), output, `Layer` and exclusive edge are unchanged; `anchor`, `size`, `margin` and `exclusive_zone` are set live in one `set()`. `exclusive_edge` is not one of `LayerWindow.set`'s keys, so a change of it recreates the window. A Bar that is renamed is a different key and is recreated.
- `settings.tdl` gains `Hot_Reload` (default true) and `Reload_Debounce` (milliseconds, default 200), as the note decided. `Directories`, `Registry` and `Main_Shell` changes are reported as needing a restart; `Logging` applies at once.
- The shell's own UID write: the proposal in [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md) is built as proposed (the hash of what the shell wrote is compared when the event arrives, then forgotten), with two additions: a record expires after 5 seconds, and the records are cleared when the watcher starts, because the writes of the start made no event. Without them, restoring a file to the content the shell once wrote was dropped as the shell's own write.
- `SIGHUP` reloads everything (every module's code is replaced), also with `Hot_Reload: false`. The D-Bus `Reload` call is not built.
- Icons: the key on `SVG` is `Icon` (the note only says it is not `Name`). The lookup order is the config `Icons` folder, then `Directories { Icons }`; the shipped set and the freedesktop icon theme (rows 1 and 2 of the note) are not built, and no set ships in the package, so a user copies `material-design-icons.json` into `Icons/`. The licence texts travel with the files.
- Styles: no theme or stylesheet (M3); a `Style:` file is named in a module (a block's own `Style:` file is `not-built`); `Class` works on every block.
- Module Python is compiled from source on each load, never from a bytecode cache.
- Where the code lives: `watch.py`, `reloader.py`, `scanner.py` (what `check`, `run` and a reload share), `files/icons.py`, `schema/style.py`, `binder/rebuild.py`.

## Facts About tre, TEL and tess_dl

Found by calling the installed packages on 2026-11-04 (tre 0.6.1, `tess_el` 0.1.2, `tess_dl` 0.1.1):

- `tess_el`: `compile_expression(source, language="0.1", origin=Origin(file, line, column))` and `Expression.evaluate_tracked(scope)` work as [TEL Integration](../20%20Architecture/TEL%20Integration.md) says. A source with leading spaces keeps the right columns: `" time "` with origin at the space reports an undefined `time` at the column of the name, with `did you mean 'tme'`. `reads` of a conditional expression follow the branch taken: `a if flag else b` reads `{flag, a}` then `{flag, b}` (open question 3 of the note: confirmed). A `TelEvaluationError` has `reads`, `hint`, `file`, `line`, `column`.
- `tess_dl`: a `Slot` has `text` and `text_origin` (the text after `{{`, spaces included); a `Template` (an unquoted value with slots) has `parts` of `str` and `Slot`; a quoted string with `{{ }}` inside is a plain `String`, not a template. `Document.with_metadata("UID", value)` adds the line after the last version line and changes no other byte (tested with comments and a CRLF line).
- tre: `Window.root` of a `LayerWindow` has no padding. `Window.build` refuses an unknown key in a spec node, so the binder keeps block words outside the spec.
- tre: a text node with no `fill` is invisible on the default background (also in M1). A text node with no `width` is laid out at width 0 (so a row of texts overlaps); `width: "fit-content"` gives its content width.
- tre timers (`Window.after`, `every`) belong to a window, so a shell with no window has none; the shared time source is therefore a thread that sleeps until the next second or minute and wakes the loop with `call_soon`. A callback queued with `call_soon` before `App.run()` waits for the next wake ([TRE-REQ-011 Drain call_soon at Loop Start](../80%20Requests/TRE-REQ-011%20Drain%20call_soon%20at%20Loop%20Start.md), unchanged on 0.6.1), so the store holds sends made while the modules start and the shell flushes them before the first build.
- Python 3.14: `uuid.uuid7()` exists and is used for UIDs.

Found while building M2b (same versions, 2026-11-04):

- `tess_el` repeaters: `compile_repeater_parts(names, items, key=, name=, language=, ...origins)` and `Repeater.reconcile_tracked(scope, state)` return the entries with `name` (`Row_0001`, `Row_0002`), `status` (`new`, `kept`), `key` and `index`; a reorder gives `moved` keys, a removal `removed`; a returning key gets a new name, never an old one. `Entry.scope(parent)` gives a scope where the loop variable is the item and the parent's names still resolve. A read through the item comes back as written (`w.title`), and `reads` of the header include the items path and the key path.
- `tess_el`: `select_tracked([condition], scope).value` is the index of the first condition that holds or `None`; the reads stop at the condition that decided (`flag and n > 1` with `flag` false reads only `flag`).
- tre: `Window.build` and `Window.apply` check a whole description before changing anything, so a refused value changes nothing; `Node.set_children` replaces a parent's children in one call; there is no way to unset a node property (so the diff replaces the node); `LayerWindow.set` takes `layer`, `anchor`, `size`, `exclusive_zone`, `margin` and the other live keys but not `exclusive_edge`.
- `inotify_simple` 2.0.1: an atomic save (write a temporary file, rename over the target) arrives as moved-to on the real name; the module has no stubs and no `py.typed`, so mypy needs a `module` override for it.
- A callback queued with `call_soon` after `App.run()` has started runs at once (the reload apply and the store's wake rely on this); the pre-run case is still TRE-REQ-011.
- tre: the `Node.set` docstring says optional properties take `None` to clear. On 0.6.1 only some do: `label`, `align_self`, `aspect_ratio` and `margin_top` accept it; `width`, `min_width`, `max_width`, `fill`, `font_size`, `padding_top`, `opacity`, `stroke_color`, `stroke_width`, `flex_grow`, `corner_radius`, `z_index` and `gap` refuse it. So the diff replaces a node that loses a property (D28); a `TRE-REQ` could ask that every optional property clear.
- Python's bytecode cache keys on the source's modification time and size: a file saved twice in one second at the same size loads the old code. Module code is compiled from source for that reason.

## Decisions Needed

None open. Choices made in the code that no spec states; each is a question until the maintainer answers:

| # | Question | Recommendation |
|---|---|---|
| D19 | The wake-up budget of 5 per second against the Clock: the 60-second window with one tick measures 8 per second on the software renderer, 2 between ticks | Read the budget as "between ticks" for a module that ticks, as the [Clock Module](../40%20Specifications/Modules/Clock%20Module.md) says ("no wake-ups between ticks"), and measure the tick burst separately on a real GPU in the KWin check |
| D20 | `hour_cycle: desktop` follows 24 hours until the KDE setting is read | Accept for M2; read KDE's regional format with the `locale` param in M3 |
| D21 | `Import: <module file>` embeds the module with its default params and no `Name` | Accept; to pass params or a name write the call (`Clock { format: ... }`) |
| D22 | Modules are registered by their metadata `Name`; two user modules with one name are `name-duplicate`, a user module overrides a shipped one silently | Accept as the TDL Language note says |
| D23 | The UID is written into the shell file and the module files, not only the module's | Accept (G8): both are registered files |
| D24 | Reload re-validates every file, not the affected set, and keeps no map from a file to its importers | Accept: a rescan takes about 5 ms; build the map only if a big config makes it slow |
| D25 | TEL compiles on the loop thread at resolve time, not on the watcher thread (T16) | Accept for M2: compiling a slot takes microseconds; a slot's syntax error is then reported when the Bar is resolved and `check` does not see it. Say if `check` must compile slots too (it would need the same compile step without a window) |
| D26 | Icons: the key is `Icon` on `SVG`; no set ships in the package (a user copies the `mdi` JSON into the `Icons` folder); the freedesktop theme is not read | Accept for M2; decide before M3 whether `mdi` ships (the licence texts must then ship too) |
| D27 | A use with `If` or `For` is resolved whole and rebuilt by the diff when anything it reads changes | Accept: it is correct and cheap; per-entry links are an optimisation for a very long list |
| D28 | A kept node that loses a property is replaced, because tre cannot unset one | Accept; ask tre for an `unset` only if a case shows a visible flicker |
| D30 | The `RepeaterState` of a `For` is dropped on a reload (design step 6 of the keyed diff says it stays): the compiled expressions may have changed, so a kept state could pair old keys with new code | Accept: entries are matched by the names TEL then gives, and the diff keeps what has the same name; keep the state only for a file whose `For` header and key text are unchanged, if a list's node identity across reloads matters |
| D29 | A module call inside `If` or `For` is not built (a use would have to start and stop modules while the shell runs) | Accept for M2; design it with the first module that needs it |

Answered by the maintainer on 2026-11-04: **accept all of D19 to D30** with the recommendations as written (D25: `check` does not compile slots; D26: no icon set ships in M2, decide before M3; D30: the `RepeaterState` is dropped on reload).

## For the Vault Session

- Please link this log from [Build Logs](Build%20Logs.md).
- [Module Context](../42%20Python%20API/Module%20Context.md) lists `ctx.send(key, value, use=None)`; the code takes a use record or its key string for `use`.
- [TEL Integration](../20%20Architecture/TEL%20Integration.md) open question 3 is confirmed (see the facts above); open question 4 (first build with a slot error): the property is left unset and the error logged, as recommended.
- The self-write rule is built as proposed in [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md), plus the expiry and the clear at start (see Differences). Please add both to the note.
- [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md): reload validates every file again (D24) and compiles slots on the loop thread (D25); say so in the pipeline description. `Hot_Reload` and `Reload_Debounce` are built; `SIGHUP` is built, the D-Bus call is not.
- [Block Reference](../41%20TDL%20Reference/Block%20Reference.md): `SVG` has an `Icon` key (a name) beside `Source`, exactly one of them; icon sets are read from the config `Icons` folder then `Directories { Icons }`.
- [Style, Theme and Stylesheet Files](../41%20TDL%20Reference/Style%2C%20Theme%20and%20Stylesheet%20Files.md): a module names its style with `Style:` inside `Module { }`; `Class:` takes one name or a list; the order of priority as built is in B4 above.
- [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md): `View.rebuild` is built as the keyed diff describes; the facts above (no unset, `set_children`, atomic `apply`) bear on it.

## Links

- [Build Logs](Build%20Logs.md) · [M2 Brief](M2%20Brief.md) · [M1 Build Log](M1%20Build%20Log.md) · [TEL Integration](../20%20Architecture/TEL%20Integration.md) · [Clock Module](../40%20Specifications/Modules/Clock%20Module.md)

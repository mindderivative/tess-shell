# 10. Troubleshooting

## Start with these four things

1. **Run the shell in a terminal**, not from the session, so you see its messages: `tesserae-shell run`.
2. **Ask `check`** whether your files are valid: `tesserae-shell check`. Every finding has a file, line and column.
3. **Ask the running shell** what it has: `tesserae-shell status` lists its monitors (with the output each got), its surfaces (shown or hidden), the modules it runs and the last errors. `--json` prints the same as data.
4. **Turn up the log**: `tesserae-shell log-level DEBUG` changes the level of the running shell until the next reload of `settings.tdl`, or set `Logging { Level: DEBUG }`.

## Where the log is

* In the terminal you started it from (`Logging { Console: true }`, the default; `--quiet` limits it to warnings and errors).
* In a file, one for each day: `~/.config/tesserae-shell/logs/log_YYYY-MM-DD.log` (or the `Directory` of the `Logging` block). A line reads `time | LEVEL | source | location | message`.
* When the shell was started by `systemd` (see [Install and start](01-install.md#starting-with-your-session)): `journalctl --user -u tesserae-shell`.

## The messages

Messages are written `level: text`. **ERROR** and **WARNING** need your attention; **INFO** and DEBUG tell you what the shell decided. A fault in a file is reported as `file:line:column` with the line and a hint; the others name the part of the shell that spoke (`kwin:`, `shortcuts:`, `portal:`, `dbus:`).

### Starting

| Message | What it means and what to do |
|---|---|
| `tesserae-shell needs Python 3.14 or newer` | The environment's Python is older. Reinstall with Python 3.14 ([Install and start](01-install.md#install)). Exit code 2. |
| `no Wayland compositor with layer-shell (WAYLAND_DISPLAY=...)` | `run` was started outside a Wayland session, or the compositor does not offer layer-shell. Start it from a terminal inside your Plasma Wayland session. Exit code 2. |
| `XDG_RUNTIME_DIR is not set` (or `... is not an absolute path`, `... is not owned by the current user`) | The session's runtime folder is missing; a login session sets it. Exit code 2. |
| `<folder> is not mode 0700` (warning) | The runtime folder is more open than it should be; the shell runs anyway. |
| `another tesserae-shell is already running (pid N)` | One shell per session. Quit the other (`tesserae-shell quit`) or stop the `systemd` unit. Exit code 4. |
| `config directory does not exist: ...` | `check` was given a folder that is not there. Exit code 2. |
| `previous run ended uncleanly (its marker is from ...); unclean starts since the last clean stop: N` (warning) | The run before this one did not stop cleanly: it was killed, crashed or was ended by the watchdog. See [when the shell hangs or crashes](#when-the-shell-hangs-or-crashes). |
| `safe start: N unclean starts in a row within 10 minutes, so the Python of user modules was not run: ...` (warning) | The shell started without your modules after crashing three times in a row; it names the modules. See below. |
| `registry: ... was rebuilt because ...; the UIDs the files carry are kept, the saved positions are lost` (warning) | `registry.json` was not valid JSON. The unreadable file is kept next to it as `registry.json.corrupt-<time>`; panels you had moved are back at their file positions. |
| `the Wayland connection was lost (...); stopping with exit code 69 so that a supervisor restarts the shell` (error) | The compositor went away. The shell stopped what it runs and exited; the `systemd` unit starts it again. |
| `no Main_Shell.tdl found; nothing to show` | The shell runs with no shell file. Write `Shells/Main_Shell.tdl` ([Your first Bar](03-first-bar.md)). |
| `no outputs: no surface was opened` (warning) | The compositor reported no monitor. |
| `control: no commands: the session bus is not reachable (...)` (info) | There is no session bus, so the shell runs without its control commands (`status`, `reload`, `toggle`, ...) and without the desktop services. A normal desktop session has one. |

### Files

| Finding | What it means and what to do |
|---|---|
| `tdl-old-version`: "this file is written for TDL 0.1; the shell reads TDL 0.2" | The file's metadata says an older language version. Migrate it (the hint says how: a slot is written `<\| expression \|>`) and write `TDL: 0.2`. |
| `version-pin`: "this file needs TDL ... or newer" | The file needs a newer shell or `tesserae-dl`. Upgrade the package. |
| `unknown-key` ("unknown key in Bar Colour", hint "did you mean ...?") | A typo or a key that does not exist. The hint lists the nearest keys; the tables in this guide list all of them. |
| `not-built` ("the Bar key Auto_Hide is not built in M1") | The key exists in the design but is not built yet. Remove it. |
| `import-cycle` | Files import each other in a circle, or a file imports itself. The message prints the chain of files; remove one import. |
| `import-not-found`, `import-failed` | A shell file named in `Import:` does not exist (the message gives the path that was looked at, relative to the file that writes the `Import:`), or exists and has errors, which are listed at that file's own line and column ([page 4](04-surfaces.md#a-shell-in-several-files)). |
| `import-twice`, `import-monitor`, `import-misplaced`, `main-shell-surfaces` | A file of surfaces is imported once into a shell (a `Name` is unique across it); an imported file holds surface blocks, not a `Monitor`; a shell file is imported in a `Monitor`'s `Children` and a module in a surface's; and `Main_Shell` needs a `Monitor`. |
| `shell-root-suffix` | The root block does not match the file's ending (a `Theme { }` in a `_Shell.tdl`). |
| `name-duplicate` | Two of your files have the same `Name`. |
| `theme-not-found`, `stylesheet-not-found` | `Appearance` names a theme or stylesheet no file has as its `Name`. The hint lists the ones there are. |
| `main-shell-not-found` | `Main_Shell` names a file that is in no `Shells` folder. |
| `missing-directory`, `unresolved-path`, `relative-path` | A path in `settings.tdl` is not a folder, uses a variable that is not set, or is not absolute. |
| `icon-not-found` (warning) | No icon set has that icon name. The hint offers close names. At run time the shell shows a broken-image icon and logs `no icon named ...; showing the broken-image icon`. |
| `icon-set-invalid` (warning) | A `.json` file in an `Icons` folder cannot be read as an icon set; it is skipped. |
| `insecure-permissions` (warning) | Your configuration folder, a folder that holds modules, a module's folder or its Python file can be written by group or others, or belongs to another user. Write access to a module's Python is code execution as you: `chmod go-w PATH`. The shell starts anyway; `check --strict` fails on it ([page 2](02-configuration-folder.md#trust-and-security)). |
| `path-outside-config` | An `Import:`, `Style:`, `Source:` or a `path` param names a file outside your configuration folder (after `..` and symbolic links are resolved). Put the file inside the folder, or add its folder to `Directories`. |
| `uid-write` (warning) | The shell could not add the `UID:` line to a file; your file is unchanged ([page 2](02-configuration-folder.md#identifiers-and-backups)). |
| `reload refused (N errors); the shell keeps what it shows` (error) | A reload found errors in some file and changed nothing. Fix them; they are printed just above and listed by `status` under "last errors". |
| `settings.tdl: Debug applies after a restart` (also `Directories and Registry`, `Main_Shell`, `Appearance.Follow_Desktop`) | A setting that a reload cannot apply. Restart the shell. |
| `some folders are not watched; SIGHUP still reloads everything` (warning) | The system's limit on file watches is reached, so saving a file does not reload by itself. Use `tesserae-shell reload`, or raise `fs.inotify.max_user_watches`. |

### The desktop

| Message | What it means and what to do |
|---|---|
| `portal: the Settings portal is not available (...); using the default appearance` (warning, once) | The desktop's Settings portal did not answer, so the shell uses the theme's default look and keeps trying when the portal appears. Without it the shell cannot follow light and dark or the accent colour. Check that `xdg-desktop-portal` runs. |
| `portal: Register failed (...); reading the settings anyway` (warning) | The shell announces itself to the portal with its application id, `io.github.mindderivative.TesseraeShell`, and the call failed. The portal wants a desktop file of that id, which the package does not install by itself: **run `tesserae-shell install-session`** ([Install and start](01-install.md#starting-with-your-session)). The shell reads the settings anyway, so this is harmless to the look. Whether Plasma's portal refuses the call without the file has not been checked on KWin. |
| `kwin: org.kde.KWin is not on the session bus (...): another compositor? fullscreen hiding and the window list are off` (info) | The shell did not find KWin, so it does not load its script: Bars are not hidden for a fullscreen window and the Tasks module stays empty. Normal on another compositor. |
| `kwin: ...: fullscreen hiding and the window list are off` (warning) | KWin is there but the script could not be loaded or KWin did not answer. The text says why (the script file is missing, KWin refused it, a call failed). Everything else works. See [`settings.tdl`](07-settings.md#kwin). |
| `kwin: the script is off (KWin { Script: OFF })` (info) | You switched it off. |
| `dbus: org.freedesktop.UPower left the system bus` (and the same for `org.kde.KWin`, NetworkManager ...) | The service went away; the module that depends on it hides and returns with the service. One warning for each service in a minute. |
| `tray host: could not register with org.kde.StatusNotifierWatcher (...)` (warning) | The Tray module found no watcher; it shows nothing. Plasma normally provides one. |

### Shortcuts

| Message | What it means and what to do |
|---|---|
| `shortcuts: no org.kde.kglobalaccel on the session bus: no global keys; the shell runs and tesserae-shell toggle <name> still works` (warning) | KDE's shortcut service is not on the bus (another desktop, or a bare session). Bind `tesserae-shell toggle NAME` to a key in your desktop's own settings instead. |
| `shortcuts: <action>: the key <keys> is taken by the desktop or another application: the action is registered with no key (choose one in System Settings)` (warning) | The desktop already uses that key. Pick another in the file or in System Settings, Shortcuts. |
| `shortcuts: <action>: the file writes <keys> but the service uses <keys>: a key kept from an earlier run or chosen in System Settings wins over the file, which only gives the default` (info) | You (or an earlier run) changed the key in System Settings; that choice stands. Clear it there to use the file's key again. |
| `shortcuts: could not register <action> (...); it is skipped` (warning) | The service refused one action; the others still work. |
| `shortcuts: Global_Shortcuts is false: nothing is registered` (info) | You switched them off. |
| `the shortcut X is written twice`, `unknown shortcut X`, `X is written as a block, which is a handler of your own ...` | A mistake in the `Shortcuts` block; the message says which. |
| `shortcut mode: the compositor did not give <surface> the keyboard (...) within ... ms, so the keys of the mode do not arrive` (warning) | Try `Debug { Mode_Keyboard: ON_DEMAND }` and restart ([Keyboard and shortcuts](08-keyboard.md#shortcut-mode)). Not yet checked on KWin which one it needs. |

### Surfaces, keyboard and Popups

| Message | What it means and what to do |
|---|---|
| `Monitor X names DP-1, which Monitor Y already took; Y wins and X opens nothing` (warning) | Two `Monitor` blocks match the same screen. Use `Connector`, or make `Index` distinct. |
| `Bar Top_Bar is not created: ...` (warning) | The message says why (a size of 0, for one). |
| `Keyboard: NONE is written, but it holds a text field; the surface takes the keyboard on_demand` (warning) | A text field needs the keyboard, so the shell overrides `NONE`. Write `ON_DEMAND`. |
| `... no Popup named X on Monitor ...` (error) | A button or a module opens a Popup that this Monitor does not have. Add a `Popup` block with that `Name` to the same `Monitor`. |
| `Popup X is not opened: ...` / `Popup X: the caller has no laid-out rectangle yet; not opened` | The Popup could not be placed or built; the text says why. |
| `Popup X: its content is 0 px width: a Text in a Popup with AUTO width needs Height: AUTO (and Width: AUTO) to take its own size` (warning) | The Popup's content measured nothing. Give the content a size, or `Width: AUTO, Height: AUTO` on a `Text`. |
| `X is a Popup: no command opens a Popup ...` | The `show` and `toggle` commands cannot open a Popup; use a button or a key press in the shell. |
| `X is a Bar: a Bar cannot be hidden` | `hide` and `toggle` take a Panel or a Frame. |
| `no surface named X (did you mean Y?)` | A command named something that is not a Panel, Frame, melded Panel or strip. |
| `X stays hidden: see the log` | The Panel's `Attach_To` target is hidden, so it cannot show. |

### Modules

| Message | What it means and what to do |
|---|---|
| `a Button with only an icon needs a Label, so assistive technology can name it` (warning) | Add `Label: "..."` to the button. |
| `locale 'xx_XX' is not installed (see `locale -a`): the Clock shows the default month and day names` (warning) | The `locale` of a Clock is not generated on your system. |
| `Call: the module M is not loaded, so A cannot run` / `Call: the module M has no action A` (error) | A handler names a module that no Bar or Panel uses, or an action it does not have. The hint lists the module's actions. |
| `slow-module` (warning) | More than 100 callbacks of the module took over 4 ms on the loop in a minute; the message names the entry point. Hand slow work to a thread and bring the result back with `ctx.call_soon`. |
| `many-threads` (warning) | The module has more than 16 live threads of its own. Join or stop the ones it no longer needs. |
| `module M (UID u) failed: restart N of 5 in S s`, then `failed again after 5 restarts; it stays failed until a reload` | The module's `start()` (or another lifecycle method) raised; the shell starts it again with a back-off and gives up after five tries. Fix the Python and save it: a reload tries again. |
| An error with a traceback, "module M: ... raised" | A module's Python failed. The shell keeps running and the traceback is in the log; the last errors also show in `tesserae-shell status`. If it is a shipped module, report it ([below](#reporting-a-bug)). |

## Common problems

**Nothing appears.**

* Is the shell running? `tesserae-shell status` says `no shell is running` (exit 3) if not.
* Is there a `Shells/Main_Shell.tdl`, and does `tesserae-shell check` pass? The `status` output lists the surfaces the shell opened.
* Does a `Monitor` block match your screen? `Index: default` matches every monitor that no other block names; `Index: 0` the first. Run `tesserae-shell status` for the outputs' names (`eDP-1`, `DP-1`) if you use `Connector`.
* Is another Plasma panel in the way? The shell runs beside Plasma's panels and does not remove or move them: if the two collide, remove or move yours in Plasma's own edit mode. The opt-in window rule that keeps the shell's surfaces above Plasma's panels is `tesserae-shell kwin rule` ([page 9](09-command-line.md#the-kwin-commands); not yet checked on KWin).

**I saved a file and nothing changed.** Hot reload may be off (`Hot_Reload: false`), the file may not be in a folder the shell watches or may not end in the right suffix (`_Shell.tdl`), or the reload was refused because of an error: run `tesserae-shell reload` to see it. A file that is not the main shell is checked but not shown.

**Text has the wrong colour or size, or a widget looks unstyled.** The `Default` stylesheet is not named: add `Appearance { Stylesheets: [Default] }` to `settings.tdl` ([Styling and themes](06-styling.md)).

**A module is missing.** Battery, Workspaces, Network, Media, Audio, Tray and Tasks hide themselves when their service is not there, and take no space ([page 5](05-modules.md#using-a-module)). `tesserae-shell status` lists the modules that are loaded. The log has a line when a service leaves or is missing.

**A key does nothing.** See [Shortcuts](#shortcuts) above; check System Settings, Shortcuts for the `tesserae-shell` component; try `tesserae-shell toggle NAME` from a terminal, which does the same as the key.

**A Panel or Launcher does not take typing.** A Panel takes the keyboard only if it says so (`Keyboard: ON_DEMAND` after a click, or `EXCLUSIVE`), and a surface that holds a text field takes it on demand. The Launcher asks for `EXCLUSIVE` because a global key does not give focus to an `ON_DEMAND` layer surface on every compositor; whether KWin does is not yet checked. A click outside the Launcher does not close it: press Escape or the key.

**The shell does not start with the session.** Run `tesserae-shell status` (it warns about a stale unit), `systemctl --user status tesserae-shell.service` and `journalctl --user -u tesserae-shell`. After moving or reinstalling the shell, run `tesserae-shell install-session --force`. The unit does not restart after exit code 1, 2 or 4, so a file error needs fixing first (`tesserae-shell check`). Not yet checked on a real session.

## When the shell hangs or crashes

**A hung loop.** A thread watches the shell's event loop once a second. When a callback keeps the loop for 2 seconds the log has one warning, `loop stalled for 2 s: module NAME, entry point ENTRY, running for N s`, followed by the Python traceback of every thread, and the warning again every 5 seconds while it lasts. At 10 seconds, under the `systemd` unit that `install-session` writes, the shell asks `systemd` to restart it (`WATCHDOG=trigger`) and `systemd` ends it with `SIGABRT` and starts it again two seconds later. Without a `systemd` watchdog (the shell started by hand or by another autostart) nothing can restart it: the log says `loop stalled for 10 s, no supervisor can restart it` and dumps the tracebacks every 30 seconds. A module whose callback blocks for long should do the waiting on a thread of its own.

**The record of a crash.** In `$XDG_STATE_HOME/tesserae-shell` (default `~/.local/state/tesserae-shell`):

* `crash.log` holds the traceback of every thread when the process gets a fatal signal (including the watchdog's `SIGABRT`) and the traceback of an exception that reaches the top. The previous file is kept as `crash.log.1` and the one before as `crash.log.2`; a run that stops cleanly leaves no `crash.log`.
* `running` exists while the shell runs and is removed when it stops. A start that finds it logs `previous run ended uncleanly` and counts it. `tesserae-shell status` shows the count since the last clean stop and the time of the last crash, also when no shell runs.
* `journalctl --user -u tesserae-shell` has the log lines (the stall warning with its tracebacks is there).

**A crash loop and safe start.** After three unclean starts in a row within 10 minutes the next start is a safe start: the Python of your own modules is not run (the shipped modules are), the warning names the modules left out, and your files are not touched. `status` says `safe start` and names them. Fix the module, then run `tesserae-shell reload` (or restart the shell with `systemctl --user restart tesserae-shell`); the reload loads your modules at once, and a clean stop of the shell ends the count. Without this, `systemd` stops the unit after five starts in 60 seconds and the bar is gone while you work on it.

**The registry.** `registry.json` is written within a second of any change (a Panel you moved, a new UID) and replaced as a whole, so killing the shell never leaves half a file. A `UID:` line the shell adds to one of your files is written the same way, after a backup in the state folder.

## Reporting a bug

Open an issue on the project's repository, <https://github.com/mindderivative/tess-shell>, and include:

* what you did and what you expected, and what happened;
* the output of `tesserae-shell version`;
* the output of `tesserae-shell check` (or `check --json`) on your configuration folder;
* the lines of the log around the problem: the file `~/.config/tesserae-shell/logs/log_<date>.log`, ideally after `tesserae-shell log-level DEBUG`. Read it before you send it: the log names your files and your applications;
* `tesserae-shell status --json` if the shell is running; it lists only names, kinds and flags, never a parameter value or a line of the log;
* the smallest shell file that shows the problem.

If the shell crashes, the log has a line `unhandled exception` or `unexpected error` with a traceback; include it, and `crash.log` from the state folder ([above](#when-the-shell-hangs-or-crashes)). Exit code 70 means the shell hit an unexpected error.

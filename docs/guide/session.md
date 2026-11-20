# Start with your session

[Install and start](install.md) gets the shell running in a terminal. This page makes it part of your login: it starts with your session, a hang or a crash restarts it, and a crash loop cannot leave you without a bar while you fix the cause. It also says how to stop it and how to take it all away again.

> `install-session` is covered by tests that write into temporary folders and use a recording stand-in for `systemctl`. Starting the shell from the unit on a real Plasma session has not been confirmed by the maintainer's hand checks yet. The watchdog, the crash record and safe start were run in a private systemd user manager by the code session's test kit; the maintainer has not repeated them. Try `--print` first, and keep your Plasma panel until you have seen the shell start from the unit.

## Install the package

Any of these puts a `tesserae-shell` command on your `PATH`; [Install and start](install.md#install) has them with the Python it needs (3.14 or newer):

```sh
uv tool install --python 3.14 tesserae-shell
pipx install --python python3.14 tesserae-shell
~/.local/share/tesserae-shell-venv/bin/pip install tesserae-shell   # in a venv of your own
```

`install-session` is newer than the 0.1.1 release; if the command is unknown to you, [install the current code](install.md#what-is-newer-than-the-011-release).

## Write the session files

```sh
tesserae-shell install-session --print    # show both files and their paths; write nothing
tesserae-shell install-session            # write both files; enable and start nothing
tesserae-shell install-session --enable   # also run: systemctl --user enable tesserae-shell.service
```

Run `--print` first. It prints each file under a line that says where it would go and whether it is `absent`, and changes nothing. With the shell installed in a `uv tool` environment, it looks like this (the paths are yours):

```text
# ~/.local/share/applications/io.github.mindderivative.TesseraeShell.desktop (absent)
[Desktop Entry]
Type=Application
Name=Tesserae Shell
Comment=Bars, panels and widgets beside the desktop
Exec=/home/you/.local/bin/tesserae-shell run
Icon=io.github.mindderivative.TesseraeShell
NoDisplay=true
X-KDE-Wayland-Interfaces=

# ~/.config/systemd/user/tesserae-shell.service (absent)
[Unit]
Description=Tesserae Shell
PartOf=graphical-session.target
After=graphical-session.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=notify
NotifyAccess=main
WatchdogSec=15
ExecStart=/home/you/.local/bin/tesserae-shell run
Restart=on-failure
RestartSec=2
RestartPreventExitStatus=1 2 4
Slice=session.slice

[Install]
WantedBy=graphical-session.target
```

What the two files do:

* **The desktop file** gives the shell its application id, `io.github.mindderivative.TesseraeShell`, in `$XDG_DATA_HOME/applications/` (`~/.local/share/applications/` by default). `NoDisplay=true` keeps it out of your application menu. The desktop's Settings portal looks for a desktop file with the id the shell registers; without it the shell may log a warning about the portal and still works.
* **The unit** is a systemd user service in `$XDG_CONFIG_HOME/systemd/user/` (`~/.config/systemd/user/` by default). It runs `tesserae-shell run` as part of `graphical-session.target`, so it starts when your graphical session does. `Type=notify` means the shell tells systemd when it is ready and when it is stopping.

Both files carry the absolute path of the `tesserae-shell` command that wrote them, because neither the desktop nor systemd looks on your `PATH`. Run `install-session` from the installation you want the session to use. If you move or reinstall the shell, run it again with `--force`; `tesserae-shell status` warns when the unit points at a path that no longer exists. `--config-dir PATH`, if given, is written into both files, so the session uses that folder.

A file that exists with other content is left alone: the command names it, changes nothing and exits 1; `--force` replaces it. A file that already has exactly this content is reported as unchanged, so running the command twice is safe. `--json` prints one JSON object. The command's options and exit codes are in [The command line](command-line.md#install-session).

`--enable` only enables the unit, so the shell starts at your next login. To start it now:

```sh
systemctl --user start tesserae-shell.service
```

The log then goes to the journal as well as to the log file: `journalctl --user -u tesserae-shell`. A system with no systemd user session still gets both files, and the command says the unit cannot be enabled; start `tesserae-shell run` from whatever autostart your session has instead.

## On KDE Plasma

The shell runs beside Plasma. It does not replace `plasmashell`, take its D-Bus names or touch its panels. Your Plasma panel stays where it is until you remove it in Plasma itself, and the session unit changes nothing about that.

So there are two ways to go:

* **Keep the panel.** Put the shell's Bars on an edge the panel does not use, or make the shell's surfaces something the panel does not cover: the panel and the Bar are both layer-shell surfaces and the compositor decides how two on one edge sit. A Panel, a Popup or the [Launcher](keyboard.md#the-launcher) works well beside it. To keep the shell's surfaces above Plasma's panels there is one opt-in window rule: `tesserae-shell kwin rule show` prints it, and [The command line](command-line.md#the-kwin-commands) has the rest. It has not been checked on KWin by hand yet.
* **Replace the panel.** When your first Bar does what the panel did, remove the panel in Plasma (its edit mode) and let the shell have the edge. Nothing in the shell needs the panel to go first, so do it only when you are ready.

Keep the panel until you have seen the shell start from the unit, and test the unit with `systemctl --user start` before you enable it.

## What the unit does when something goes wrong

* **A crash or a kill.** `Restart=on-failure` with `RestartSec=2` starts the shell again two seconds later. At most five starts in 60 seconds are allowed (`StartLimitBurst=5`, `StartLimitIntervalSec=60`); then systemd leaves the unit stopped, and `systemctl --user reset-failed tesserae-shell.service` clears that.
* **Exit codes that do not restart.** `RestartPreventExitStatus=1 2 4`: code 1 (your files have errors), 2 (the machine cannot run the shell) and 4 (another shell is running) mean a restart would only fail again. The exit codes:

<!-- BEGIN generated: exit-codes -->
| Code | Name | Meaning |
|---|---|---|
| 0 | `OK` | Done. |
| 1 | `CONFIG` | The files have errors (`check`, `run`, `reload`), a control command ran and failed (an unknown name, an action that raised), `install-session` kept a file that differs, or `migrate --check` found files to change. |
| 2 | `ENVIRONMENT` | The machine cannot run it: no Wayland compositor with layer-shell, no session bus, `XDG_RUNTIME_DIR` unusable, the config folder missing (`check`, `migrate`), `systemctl` missing or refusing (`install-session`), or a file `migrate` could not migrate. |
| 3 | `NOT_RUNNING` | A control command found no running shell. |
| 4 | `ALREADY_RUNNING` | A second `run`: another shell holds the instance lock. `migrate` refuses for the same reason, unless `--force`. |
| 5 | `TIMEOUT` | A control command got no answer within `--timeout` seconds. |
| 69 | `LOST_COMPOSITOR` | The Wayland connection was lost (the compositor went away). The shell stops what it runs first, then leaves with this code so that `Restart=on-failure` of the systemd unit starts it again. |
| 70 | `INTERNAL` | An unexpected error inside the shell (it is in the log). |
| 130 | `FORCED` | A second signal made the shell leave at once. |

<!-- END generated: exit-codes -->

* **A hang.** The shell has a watchdog thread that checks, once a second, that its event loop is turning. After 2 seconds without a turn it logs `loop stalled for N s`, naming the module and the callback that is running, with the traceback of every thread; it repeats the warning every 5 seconds. After 10 seconds, under systemd, it asks systemd to restart it (`WATCHDOG=trigger`). The unit's `WatchdogSec=15` is the backstop: the shell sends keep-alive pings only while its loop is turning, and systemd ends a shell that has sent none for 15 seconds with `SIGABRT` and starts it again. Without systemd, a stall of 10 seconds is only logged (`loop stalled for 10 s, no supervisor can restart it`), with tracebacks every 30 seconds; nothing can safely restart the shell for you.
* **A hang in a module of yours.** That is not a stall of the loop: your module's Python runs in a process of its own. The shell's watchdog names the callback after 2 seconds and kills that process after 5, and the module starts again with the back-off ([Security](security.md#when-a-module-misbehaves)). The shell's own modules run in the shell, so a hang in one of them is the stall above.
* **A lost compositor.** If KWin restarts or crashes, the shell stops what it runs, saves the registry and exits with code 69, which the unit restarts. If no compositor is up yet when the shell starts again, it exits with code 2 and the unit stays down; start it with `systemctl --user start tesserae-shell.service` once the session is back.
* **A module that raises or crashes.** Only that module fails; the shell keeps running, and for a module of yours its process ends and starts again. See [Trust and security](security.md).

What survives a restart: your files, the registry (a Panel you moved is saved within a second of the move and replaced as a whole, so a kill never leaves half a file), and whatever a module of yours writes to files of its own. What does not: open Popups, a shown Panel (it starts as its file says), the processes of your modules (they start again with the shell) and a module's values in memory.

## The crash record

The shell keeps three small files in its state folder, `$XDG_STATE_HOME/tesserae-shell` (`~/.local/state/tesserae-shell` by default):

* `crash.log` holds the traceback of every thread when the process gets a fatal signal (including the watchdog's `SIGABRT`) and the traceback of an exception that reaches the top. The previous one is kept as `crash.log.1` and the one before as `crash.log.2`; a run that leaves nothing in it removes it, so clean runs never push a real record out.
* `running` exists while the shell runs and is removed when it stops in a way it chose. A start that finds it knows the run before ended uncleanly (`SIGKILL`, the out-of-memory killer, a crash, the watchdog), logs `previous run ended uncleanly` and counts it.
* `recovery.json` keeps the times of the unclean starts since the last clean stop.

`tesserae-shell status` shows what the shell knows, also when no shell is running:

```text
unclean starts since the last clean stop: 1
last crash: <time>
```

and, in a safe start, a `safe start:` line. [Troubleshooting](troubleshooting.md#when-the-shell-hangs-or-crashes) has the messages.

## Safe start after crashes

A crash loop is most often a module of your own. So that you are not left without a bar while you fix it, the third unclean start within ten minutes is a *safe start*: the shipped modules run, the Python of your own modules does not, and the shell says so once:

```text
safe start: 3 unclean starts in a row within 10 minutes, so the Python of user modules was not run: Greeter (/home/you/.config/tesserae-shell/Modules/Greeter/Greeter_Module.py). The files are untouched; `tesserae-shell reload` or a restart tries them again.
```

Your files are not changed. Fix the module, then run `tesserae-shell reload` (or restart the shell with `systemctl --user restart tesserae-shell.service`): your modules load at once. A clean stop resets the count.

## Stop, restart and uninstall

* **Stop the shell for now:** `tesserae-shell quit`, or `systemctl --user stop tesserae-shell.service`. A clean stop exits with code 0, which the unit does not restart, and ends the count of unclean starts. In a terminal, `Ctrl+C`.
* **Restart it:** `systemctl --user restart tesserae-shell.service`. Needed for the settings a [hot reload](hot-reload.md#what-is-applied-at-once-and-what-needs-a-restart) cannot apply.
* **Do not start with the session any more:** `systemctl --user disable tesserae-shell.service`, or `tesserae-shell install-session --remove`, which disables the unit if it is enabled and removes both files. It does not stop a running shell (use `quit`) and it leaves `~/.config/tesserae-shell` alone.
* **Uninstall the package:** `uv tool uninstall tesserae-shell`, `pipx uninstall tesserae-shell` or `pip uninstall tesserae-shell`. Do `--remove` first, while the command still exists.
* **Your data** is never removed by any of this: the configuration folder holds your files and `registry.json`, the state folder `crash.log`, the backups the shell made before it edited a file, and the recovery files. Delete them yourself when you are sure.

For the reasoning see [Packaging and Session Start](../design/70%20Delivery/Packaging%20and%20Session%20Start.md) and [Crash Recovery and Watchdog](../design/60%20Quality/Crash%20Recovery%20and%20Watchdog.md) in the design section.

Next: [security and trust](security.md).

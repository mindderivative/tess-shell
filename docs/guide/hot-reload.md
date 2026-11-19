# Hot reload

You do not restart the shell to try a change. While it runs, it watches your files; when you save one, it checks the whole folder and, if every file is valid, changes what is on screen. If a file has an error, nothing changes and the shell tells you why. The [configuration folder](configuration-folder.md#hot-reload) page has the short version; this page has the details.

## What saving a file does

1. **The watcher notices.** The shell watches `settings.tdl`, `Shells/`, `Modules/` and the module folders in it, `Styles/`, `Themes/`, `Stylesheets/`, and the folders `Directories` names. It ignores `schemas/`, `logs/` and `backups/`, and files whose names start with a dot or end in `~`, `.swp`, `.tmp` or `.bak`, so an editor's temporary and backup files do not count. A file one of your shell files imports counts too, even when it lies in a folder the shell does not otherwise watch.
2. **It waits for quiet.** A change is acted on 200 milliseconds after the last event. An editor that writes a file in several steps, or saves several files at once, is one reload. An editor that saves by writing a temporary file and renaming it over the real one is fine. `Reload_Debounce` in `settings.tdl` sets the wait in milliseconds; the shell reads it when it starts.
3. **It checks everything.** The shell reads and validates every file in the folder exactly as it does at start, and only then looks at the result. The files the shell itself writes (the `UID:` line it adds, the registry) do not start a reload.
4. **If any file has an error, it changes nothing.** What is on screen stays; see [When a file has an error](#when-a-file-has-an-error).
5. **If every file is valid, it applies the difference.** Your new Bars, Panels and modules appear, changed ones are updated in place, removed ones close. The shell compares the new files with what runs by name, so a surface that did not change keeps its window.

The log says what happened: `reloaded (Main_Shell.tdl) in 120 ms`, naming the files that changed and how long the apply took. A reload with no shell file reports `reloaded: there is no main shell file; nothing to show`.

Hot reload is on by default. `Hot_Reload: false` in `settings.tdl` turns the watching off; `reload` and `SIGHUP` (below) still work then. If the system's limit of file watches is reached, the shell logs `some folders are not watched; SIGHUP still reloads everything` and saving does not reload by itself; see [Troubleshooting](troubleshooting.md).

## What is applied at once and what needs a restart

Applied at once on the next reload:

* the shell files: Bars, Panels, Popups, Frames, their sizes, edges, margins and styles. A change of a surface's size, edge or similar is set on the open window. Moving a surface to another monitor, or changing which monitor a `Monitor` block selects, closes the window and opens a new one on the right screen; the other monitors' windows are not touched ([Multiple monitors](monitors.md));
* modules: a module's layout (its `.tdl`) and its Python file. A change in the layout rebuilds the layout and keeps the module's running instance. A change in the Python file stops the old instance, loads the new code and starts it again; if the new code does not load, the old instance keeps running;
* themes, stylesheets, tokens, icons;
* `Logging`, `Appearance.Theme`, `Appearance.Stylesheets`, `Shortcuts` and `Global_Shortcuts`.

Needs a restart (the shell logs a warning naming the one you changed, such as `settings.tdl: Debug applies after a restart`, and keeps working with the old value):

* `Directories` and `Registry` (one warning for both), `Main_Shell`, the `Debug` block and `Appearance.Follow_Desktop`;
* `Control` and the `KWin` block.

[Settings](settings.md) has every key.

What a reload does with state:

* A module instance survives a change in its layout; the values it last sent stay until it sends new ones.
* A Panel's visibility (shown, hidden) survives, and so does a Panel you moved (the registry keeps its position).
* An open Popup that the change touches is closed; the next opening uses the new definition.
* A module that raised and stayed failed (after five restarts) gets five new tries.
* A reload you ask for with `tesserae-shell reload` or `SIGHUP` also ends a [safe start](session.md#safe-start-after-crashes) and tries your own modules again.

## When a file has an error

The shell prints each error to its standard error and writes it to the log. It does not stop, and the surfaces keep what they showed before. An error has the file, the line and the column, the line itself with a caret under the place, and a hint where there is one:

```text
Shells/Main_Shell.tdl:14:23: error: Edge: TOPP is not one of TOP, BOTTOM, LEFT, RIGHT
  14 |                  Edge: TOPP
     |                        ^
    hint: did you mean TOP?
```

then the log line `reload refused (N errors); the shell keeps what it shows`. Fix the file and save again; the next reload starts from the files as they then are, and nothing has to be undone. `tesserae-shell status` keeps the last errors under `last errors:`.

The shell does not send a desktop notification for a refused reload. If you work in an editor with no terminal beside it, run `tesserae-shell check` in a terminal, or follow the log (`journalctl --user -u tesserae-shell -f` when it runs from the [session unit](session.md)); the log's [location](troubleshooting.md#where-the-log-is) is on the troubleshooting page.

Two other cases look alike and are different:

* **`reload refused: a Bar's contents have errors; the shell keeps its state`.** All files are valid, but putting them together fails (a Bar uses a module that is not there, say). The message lists the errors; nothing was applied.
* **`reloaded with errors`.** The files were valid and were applied, but something that failed while applying (a module that raised in its `start()`) is listed. That module alone is marked failed and restarts with a back-off; the rest runs. See [Trust and security](configuration-folder.md#trust-and-security).

## Reloading and checking by hand

* `tesserae-shell check` reads and validates the folder, as a reload would, without a shell running and without a compositor. It creates nothing. It prints `ok: N files checked`, or the errors above with exit code 1. `--strict` makes a warning fail it too. Use it before you start the shell, in an editor's save hook or in a git hook. See [The command line](command-line.md#check).
* `tesserae-shell reload` asks the running shell to check and apply everything now, and answers after the apply: `reloaded (...) in N ms` with exit code 0, or the errors with exit code 1. Use it when watching is off or the watch limit is reached, or in a script. It exits 3 when no shell runs.
* `SIGHUP` to the shell process does the same as `reload`: `kill -HUP $(pgrep -f 'tesserae-shell run')`.

A reload you ask for covers every file, not only the ones the watcher saw change.

## What it does not do

* It does not restart the shell, so what needs a restart (above) needs `systemctl --user restart tesserae-shell` or `tesserae-shell quit` and `run`.
* It does not roll a half-applied change back: the checks come first so that none is needed. If applying fails (an error the checks cannot see, such as one the compositor reports for a window), the shell logs `applying the reload failed; check the Bars` and the answer to `reload` says so.

For the reasoning (why the checks come first, why the debounce is 200 ms, how the difference is found) read [Hot Reload](../design/40%20Specifications/Runtime/Hot%20Reload.md) in the design section; [Validation and Errors](../design/40%20Specifications/Runtime/Validation%20and%20Errors.md) has the pipeline.

Next: [start with your session](session.md).

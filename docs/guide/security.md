# Security and trust

The shell runs as you, with your rights and none of its own. This page says what it trusts, what it checks around that trust, what it does not protect, and how to read a module before you use it. The statement the project commits to is in [The configuration folder](configuration-folder.md#trust-and-security), and the reasoning is in [Security Model](../design/60%20Quality/Security%20Model.md) in the design section; this page does not repeat them, it explains them in use.

## What is data and what is code

| Thing | Can it run code? | What it can do |
|---|---|---|
| A TDL file: a shell, a module's layout, a style, a theme, a stylesheet, `settings.tdl` | No | Say what to draw. TDL has no statements. Every `<\| \|>` slot goes to an expression language that can only read the module's values, and it has limits. |
| A shipped module (Clock, Battery, Tasks ...) | Yes, it is the package's own Python | What the package says it does. It comes from the release you installed. |
| A module of your own: `Modules/<Name>/<Name>_Module.py` | **Yes** | Anything your user can do. It runs in a process of its own, as you. |
| Another program of yours | n/a | Anything your user can. The shell does not defend its folder or its control commands against it: the session bus is per user. |

So a shell file you got from someone else cannot run code, however odd it looks. It can only draw, and name modules. A module's Python is the part that matters.

## Your modules are trusted code in a process of their own

A module's Python file runs with your rights. It can read and write your files, start programs and use the network. That is the same trust as a script you put in your home folder, and **the shell does not sandbox it**. What changed in this release is where it runs: the modules that ship with the shell run inside it, and a module you write or add runs in **a child process of its own** (one process for each module file), so that a module that hangs or crashes does not freeze your bars. That is fault containment, not security: the child process is started by the shell and runs as you, with all the rights you have.

What follows from it:

* Write modules yourself, or read them before you add them. A module you got from someone else is not supported in this release; sharing shells is not a feature yet.
* A shipped module is not the same case: it is the package's code, and it runs in the shell.
* The process boundary protects the shell's state from a module's mistakes, not you from a module's intent. A module cannot reach the shell's windows, registry or configuration loader, because its `ctx` is a narrow set of calls that the shell answers; Python in the process can still import anything and open your files.
* `Debug { User_Modules_In_Process: true }` in `settings.tdl` puts your modules back in the shell's own process, as in earlier releases. The trust is the same; the containment is gone.

## What the shell checks around it

Every one of these is run at start, at every [reload](hot-reload.md) and in `check`.

### `insecure-permissions` (a warning)

Write access to a module's Python is code execution as you, so the shell looks at who can write to it. It checks your configuration folder, the folders that hold modules, each module's folder and each module's Python file. A path that group or others can write, or that another user owns, is reported once with its path and a hint. For example (a folder with mode 775):

```text
/home/you/.config/tesserae-shell:1:1: warning: the folder /home/you/.config/tesserae-shell is writable by group (mode 0775): write access to a module's Python is code execution as you
    hint: make it yours alone: chmod go-w /home/you/.config/tesserae-shell
```

The shell starts anyway, so that a shared or network home still works. Fix it with the `chmod go-w PATH` the hint gives.

### `check --strict`

```sh
tesserae-shell check --strict
```

`--strict` makes any warning fail the check: the warnings are printed, followed by `tesserae-shell: --strict: the warnings above fail the check`, and the exit code is 1 (without it, warnings are printed and the exit code stays 0). Use it in a git hook or a script that must keep a folder with no `insecure-permissions` or other warnings. With `--json` each finding has `file`, `line`, `column`, `severity`, `rule`, `message` and `hint`, so a script can pick out `insecure-permissions`. [The command line](command-line.md#check) lists the options.

### `path-outside-config` (an error)

A path that a shell file writes must end inside your configuration folder or a folder named in `Directories`, after `..` and symbolic links are resolved. That covers `Import:`, a module's `Style:`, a `Source:` of a `Bitmap` or `SVG`, a `path` param and its default, and an icon file. A path that leaves them is refused, and in `check`, as in a reload, nothing is applied:

```text
Shells/Main_Shell.tdl:31:21: error: ../../Other_Shell.tdl leaves the configuration folders: it points to /tmp/other/Other_Shell.tdl
  31 |              Import: ../../Other_Shell.tdl
     |                      ^
    hint: a path may name only files inside the configuration folder (or a folder of Directories), after .. and symbolic links are resolved
```

The effect is that a shell file you copy into your folder cannot make the shell read your `~/.ssh` or your photos by naming them. A symbolic link in your folder that points elsewhere counts as elsewhere, and so does an absolute path or a `~/` path. The fix is to copy the file into the folder (an `Images` folder of your own, say) and name it from there. The files the shell ships are the one exception, and absolute paths in `settings.tdl` are your own settings and are not checked.

### Where a module's Python comes from

The shell loads a module's `.py` by its file path from that module's folder in `Modules/` (or a folder `Directories` adds for modules), never through Python's general import path. It puts neither your folder nor a module's folder on `sys.path`, so a file named `json.py` beside a module cannot replace Python's own `json`. The process of one of your modules is started in Python's isolated mode (`-I`), which ignores `PYTHON*` environment variables and the user's site folder.

### When a module misbehaves

* **It raises** in `start()`, `use_added()`, `use_removed()` or `reload()`: that module alone is marked failed and restarts after 1, 2, 4, 8 and 16 seconds, then stays failed until a reload (which gives five new tries). The others keep running and its surfaces keep their last values. An exception in an `@action` or a callback is logged with the module's name and does not fail it.
* **It hangs or crashes.** For a module of yours, the process alone is affected. A callback that has run for 2 seconds is named in the log; at 5 seconds the process is killed (`module-process`) and the module starts again with the same back-off, five tries. A crash or an exit of the process is the same finding. The shell's loop does not wait for it, so your bars stay as they are. A hung callback of a shipped module is named by the [watchdog](session.md#what-the-unit-does-when-something-goes-wrong) at two seconds, and the shell is restarted at ten.
* **It is slow.** A callback that takes more than 4 ms is logged at debug level; a module with more than 100 of them in a minute gets a `slow-module` warning that names it and the entry point. The same count is kept inside the process of a module of yours.
* **It starts threads.** More than 16 live threads of its own gives one `many-threads` warning.
* **It asks the shell for something and gets no answer.** A call in the context that must answer at once waits 2 seconds, then raises `ShellCallTimeout`, which names the module and the call.
* **It adds actions the file does not show.** The shell reads the file's text to know the actions, and warns `module-actions` when the process, once it has imported the file, has others (added by assignment or `setattr`).

### What the logs hold

The shell's own log lines carry names, keys, counts and positions, not window titles, notification text, clipboard content or file contents. The Applications module logs an application's id and never the values of its arguments. A module's own `ctx.log` is for the module to fill, so a module can write whatever it likes there.

## What is not protected

Plainly:

* A module of your own can do anything you can: read your files, start programs, connect to the network, change the files of the folder it is in, including other modules and your shell files.
* Nothing in `check` or the shell reads a module's code and judges it. There is no warning for a module that imports `subprocess` or `os.system`: it would warn about most useful modules and give a false sense of safety.
* Another process of yours can reach the control commands (`reload`, `call`, `show`) through your session bus, and can write to your folder if its rights allow it. The shell does not defend against it; it is you.
* The shell opens no network port and owns only names on your session bus. Another user, or the network, cannot reach it that way.
* `path-outside-config` limits what a shell file names. It does not limit what a module's Python reads.
* An absolute or `~/` path to a picture outside the configuration folder is refused, even your own. That is a cost of the rule, not a bug.

## How to read someone else's module before you use it

A module is a folder in `Modules/` with a layout file, `<Name>_Module.tdl`, and a Python file, `<Name>_Module.py`. The layout is data; the Python is what you read. Do it before you copy the folder in, and again when you update it.

1. **Read the layout first.** The `.tdl` file shows what it draws and what params it takes. Check the `Style:` and `Source:` paths: they have to stay inside your configuration folder, or `check` refuses them.
2. **Read every import at the top of the `.py` file.** `subprocess`, `os`, `shutil`, `socket`, `urllib`, `http`, `requests`, `ctypes`, `pickle`, `importlib` and `eval`/`exec` are the ones that reach outside. A clock needs none of them. A module that imports a package you do not know needs a look at that package too.
3. **Find what it does when it starts.** Read the `start()` method and anything at the top level of the file: the top level runs when the module's process imports the file, as soon as the shell starts, before any click. `tesserae-shell check` does not run it; `check --import-modules` does, so use that option only on a module you have read.
4. **Read the actions.** An `@action` is what `tesserae-shell call` and a block's action can run. See what each does with its arguments.
5. **Look for the file system and the network.** Search for `open(`, `Path(`, `write_text`, `unlink`, `rmtree`, `connect(` and for any URL. The shell gives a module no place of its own for data: whatever it keeps, it keeps where it chooses.
6. **Check the folder for anything else.** Extra `.py` files, binaries, hidden files. A module needs one `.py` file and its layout.
7. **Run it where a mistake is cheap first.** `tesserae-shell check --config-dir ~/try-shell` and `tesserae-shell run --config-dir ~/try-shell` use a folder of their own; your real folder, and your files, are not touched. Keep it `chmod go-w` so the shell does not warn.

If you cannot read it, do not run it. [Modules](modules.md) and the [module contract](../design/42%20Python%20API/Module%20Contract.md) say what a module is meant to do, so that anything more stands out.

## Keeping yourself safe

* Keep the folder writable by you only: `chmod -R go-w ~/.config/tesserae-shell`.
* Run `tesserae-shell check --strict` after you add or change a module.

Next: [troubleshooting](troubleshooting.md), or the full list of controls and the threats they answer in [Security Model](../design/60%20Quality/Security%20Model.md).

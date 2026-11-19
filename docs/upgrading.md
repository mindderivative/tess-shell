# Upgrading

How to move to a newer Tesserae Shell, what a release promises about your files, and what to do when a file written for an older release is refused. Tesserae Shell is pre-alpha: before 1.0 a minor release (0.X.0) may change files, commands and the module contract, and each change is listed in the changelog.

## The short version

1. Read the [changelog](#changelog) for the releases between yours and the new one: *Changed* and *Removed* lines are what can touch your files.
2. Upgrade the package.
3. Run `tesserae-shell check`. If it is clean, you are done; restart the shell.
4. If it reports `tdl-old-version` or `deprecated-key`, run `tesserae-shell migrate --check` to see what would change, then `tesserae-shell migrate`.
5. If a module of yours (Python) stops working, the changelog names the contract change; migrate does not rewrite Python.

## Upgrade the package

Use the same tool you installed it with ([Install and start](guide/install.md#install)):

```sh
uv tool upgrade tesserae-shell       # installed with uv tool
pipx upgrade tesserae-shell          # installed with pipx
pip install --upgrade tesserae-shell # in a virtual environment of your own
```

Then confirm what you have:

```sh
tesserae-shell version
```

The shell needs Python 3.14 or newer and pins ranges of its libraries (the engine, the expression language and the TDL reader), which the package manager installs together; you upgrade one package. A shell that is running keeps running the old code until you restart it (`systemctl --user restart tesserae-shell` under the session unit, or stop it and run it again). After moving or reinstalling the shell, `tesserae-shell install-session --force` rewrites the unit so it points at the new command.

## What a release promises

The full policy is in [The command line](guide/command-line.md#versions-and-what-a-release-promises) and, with the reasoning, in the design note [Version Policy and Migration](design/70%20Delivery/Version%20Policy%20and%20Migration.md). In short:

* **A patch** (0.x.Y) fixes things and changes no file, command or API.
* **A minor before 1.0** (0.X.0) may change anything. Each change is in the changelog under *Changed* or *Removed*, with a `migrate` step when it touches your files.
* **From 1.0**, a minor only adds; a file valid for 1.X stays valid for 1.Y; a rename or removal waits for a major and is deprecated for at least two minors first.
* Several numbers move on their own: the TDL language version (`TDL:` in a file), the TEL language version, the schema export version, the module contract and the registry format. The table is in [Versions and what a release promises](guide/command-line.md#the-version-numbers).

## `migrate`

```sh
tesserae-shell migrate --check   # change nothing; exit 1 if any file would change
tesserae-shell migrate           # rewrite the files that need it
```

`migrate` brings your `.tdl` files to the current format with an ordered list of numbered steps. Each step rewrites text only and does nothing to a file that is already at its target. In 0.2.0 there are two:

* **Step 0001, TDL 0.1 to TDL 0.2:** a slot written `{{ expression }}` becomes `<| expression |>` and `TDL: 0.1` becomes `TDL: 0.2`. No other byte of the file changes. A slot whose text holds `|>` outside a quote cannot be written in the new form: it is reported and that file is left as it was.
* **Step 0002, renamed keys:** a deprecated key or block is written under its new name. Nothing is deprecated in 0.2.0, so this step has nothing to do yet.

What you see, for a file written for TDL 0.1 (this is `--check` on a copy):

```text
step 0001: TDL 0.1 to TDL 0.2: a slot is written <| expression |>, not {{ expression }}; TDL: 0.1 becomes TDL: 0.2
  would change: Shells/Main_Shell.tdl (2 edits)
1 file(s) to change, 0 not migrated
```

Exit code 1 means `--check` found work. Without `--check`, the changed files are listed, then the verdict of `check` on the result.

What it does to be safe:

* Before it writes, the originals are copied to `<configuration folder>/.migrate-backup/<timestamp>/` with their relative paths. Nothing is deleted, so a run that is interrupted leaves every original in the backup and a second run is safe.
* Each file is replaced through a temporary file and a rename: a file is either as it was or fully migrated.
* It writes only inside the configuration folders and never starts a shell.
* It refuses to run while a shell is running (exit code 4), because a reload would read half-migrated files. Stop the shell first, or pass `--force`. `--check` never refuses.
* It does not rewrite the Python of your modules.

The options and exit codes are in [The command line](guide/command-line.md#migrate); `--json` prints the result as data for a script. Start with `--check`, and keep your folder in version control if you can.

## The `Shell:` pin

A file's metadata block may say which shell release it needs:

```tdl
---
TDL: 0.2
Shell: 0.2
Name: Main_Shell
---
```

`Shell:` is the minimum release (major and minor). If it is newer than the shell you run, the file is refused with the error `shell-too-old`, at the `Shell:` line, and the hint says which release to install. Install it, or lower the pin if the file does not need it. A pin is how a file you share says what it was written for; leaving it out is fine.

The same block can pin `TDL:` (the language version; a version the installed library does not read is `version-pin`) and, for a file that needs them, `TRE:` and `TEL:` for the engine and the expression language. A file for an older language (today, TDL 0.1) is refused with `tdl-old-version` and the hint to run `migrate`; the shell does not read it and warn, because a file that parses differently from what its author wrote is worse than a clear stop. All of these are in [Messages](reference/messages.md#the-file-and-its-text).

## Deprecations

A key, block, parameter or command that is renamed or replaced keeps working under its old name for one minor before 1.0 (two after), with the warning `deprecated-key` (or `deprecated-command` on the command line) naming the replacement and the release that removes it. The schema export marks it, and `migrate` rewrites it.

**Nothing is deprecated in 0.2.0.** A removed key is an error, `removed-key`, whose hint says what to do; today that is a Bar's `Reveal_Key`.

## Changelog

Every release in order, oldest first, with *Unreleased* (the next release) at the end. It says what changed and what was removed.

--8<-- "CHANGELOG.md:3:"

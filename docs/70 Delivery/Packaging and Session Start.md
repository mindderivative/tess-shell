---
title: Packaging and Session Start
aliases: [Packaging, Autostart, Session Integration]
type: delivery
status: accepted
owner: phil
created: 2026-11-13
updated: 2026-11-16
tags: [delivery, needs-verification]
---

# Packaging and Session Start

> [!NOTE]
> The shell is one Python wheel, `tesserae-shell`, with one command. A second step, `tesserae-shell install-session`, writes the two files the desktop session needs: the desktop file that gives the shell its application id, and a systemd user unit that starts it with the graphical session. Decided by the orchestrator on 2026-11-13 ([Orchestration Log](../00%20Home/Orchestration%20Log.md) D-054); to be built as task T-055.

## Purpose and scope

- In: what the wheel contains and depends on, the desktop file, the session unit, the command that installs and removes them, upgrades.
- PyPI: the maintainer set up the project name `tesserae-shell` on PyPI on 2026-11-15 (his statement). PyPI returned 404 for it on the same day, as expected before a first upload: nothing is published yet. The release workflow is in the `tess-shell` repository (CI baseline, PR #5, by the code session's report).
- Out: publishing to PyPI, distribution packages (Arch, Flatpak), and version tags. These are the maintainer's.

## The Wheel (as it is in the repository, read 2026-11-13)

| Item | Value |
|---|---|
| Name, command | `tesserae-shell`; the command `tesserae-shell` runs `tess_shell.cli:main` |
| Python | 3.14 or later |
| Kind | Pure Python (`py3-none-any`) after PR #15, which removed the vendored compiled `tess_utils` ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md)); 0.1.0 on PyPI was a platform wheel (`manylinux_2_36`) |
| Depends on | `tesserae-engine` 0.6.8 up to 0.7 (the floor moved from 0.6.7 with the shell's PR #16, 2026-11-15), `tesserae-el` 0.1.2 up to 0.2, `tesserae-dl` 0.2.0 up to 0.3 (since `e30bfe3`, 2026-11-14), `tesserae-utils[image]` 0.2.1 up to 0.3 (from PyPI since the shell's PR #15, 2026-11-15; Pillow comes through the extra), `loguru`, `inotify-simple`, `dbus-fast`, `pillow`, `jeepney` |
| Licence | MIT |

The shell must run on the released versions named there. Work merged in tre and tess-dl after those releases is used only when present ([Orchestration Log](../00%20Home/Orchestration%20Log.md) D-051).

## Release Path (code session's report, 2026-11-15, not run in the vault)

`tess-shell` `main` is ready for version 0.1.0 (PRs #11 and #12, CI green). The workflow `release.yml` runs the tests, a build check, then a PyPI job that uses Trusted Publishing in the environment `pypi` (a reviewer approves it), then makes the GitHub release. The tag push is the maintainer's. The wheel is tagged `manylinux_2_36`: `auditwheel` found a glibc symbol (`GLIBC_ABI_DT_RELR`) in the vendored `tess_utils`, so a user needs glibc 2.36 or newer. By the shell's report of 2026-11-15 that floor goes away with the next release, because the wheel is pure Python once `tesserae-utils` comes from PyPI. Published on 2026-11-15 (the maintainer's statement, checked against PyPI's JSON page the same day): `tesserae-shell` 0.1.0, Python 3.14 or later, as the wheel `tesserae_shell-0.1.0-cp314-cp314-manylinux_2_36_x86_64.whl` (1.4 MB) and the sdist `tesserae_shell-0.1.0.tar.gz` (1.4 MB). The vault did not install it. `install-session` (T-055) is not built, so a user still writes the desktop file and the unit by hand.

## Why a Second Step

A wheel can carry data files, but where they land depends on how it is installed: a virtual environment or a `uv tool` or `pipx` install puts them under that environment, where the desktop and systemd do not look. So the wheel carries the two files as package data, and a command writes them to the user's own folders with the right path to the command in them.

## The Desktop File

`io.github.mindderivative.TesseraeShell.desktop`, the id the shell registers with the portal ([Portals > Identity of an Unsandboxed Caller](../40%20Specifications/Integration/Portals.md#identity-of-an-unsandboxed-caller) names the requirement) and its bus name ([IPC and CLI > The Bus Name](../40%20Specifications/Runtime/IPC%20and%20CLI.md#the-bus-name)).

```ini
[Desktop Entry]
Type=Application
Name=Tesserae Shell
Comment=Bars, panels and widgets beside the desktop
Exec=/absolute/path/to/tesserae-shell run
Icon=io.github.mindderivative.TesseraeShell
NoDisplay=true
X-KDE-Wayland-Interfaces=
```

- `NoDisplay=true`: the shell is not an application to start from a menu.
- Written to `$XDG_DATA_HOME/applications/` (default `~/.local/share/applications/`).
- The last line is left empty: the shell needs no restricted KWin protocol today. If the window list of the [Tasks Module](../40%20Specifications/Modules/Tasks%20Module.md) turns out to need one, the name goes here. #needs-verification

## The Session Unit

`tesserae-shell.service`, written to `$XDG_CONFIG_HOME/systemd/user/` (default `~/.config/systemd/user/`).

```ini
[Unit]
Description=Tesserae Shell
PartOf=graphical-session.target
After=graphical-session.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=notify
NotifyAccess=main
ExecStart=/absolute/path/to/tesserae-shell run
Restart=on-failure
RestartSec=2
RestartPreventExitStatus=1 2 4
Slice=session.slice

[Install]
WantedBy=graphical-session.target
```

- `Type=notify` uses the `READY=1` and `STOPPING=1` notices the shell already sends ([Shell Start and Stop > Telling systemd (decided 2026-10-28)](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#telling-systemd-decided-2026-10-28)).
- `Restart=on-failure` is the supervisor that [Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md) left as a later item: a crash restarts the shell after 2 seconds, at most 5 times in 60 seconds. A configuration error (exit code 1), an environment error (2) and "another shell is already running" (4) do not restart, because the same start would fail again; an internal error (70) and a kill by a signal do ([Shell Start and Stop > Exit Codes](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#exit-codes)).
- `StartLimitIntervalSec=` and `StartLimitBurst=` belong in `[Unit]`: the systemd manual lists them under `systemd.unit` (read 2026-11-16), and in `[Service]` systemd ignores them, which leaves the default limit of 5 starts in 10 seconds instead of 5 in 60. The first version of this note put them in `[Service]`. The session that built the command reported the mistake on 2026-11-16, put them in `[Unit]` in the shell and added a test that fails if they move back; the note was corrected the same day.
- `PartOf=graphical-session.target` stops the shell when the session ends.
- No `WatchdogSec`: the shell does not send watchdog pings, so a hung loop is logged by the shell's own watchdog and not restarted. Adding the ping is a later item, not part of this note.
- The directives are from the systemd manual ([systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html), [systemd.special](https://www.freedesktop.org/software/systemd/man/latest/systemd.special.html)); the unit was not run on a session. #needs-verification

## The Command

| Command | Does |
|---|---|
| `tesserae-shell install-session` | Writes the desktop file and the unit, with the absolute path of the running command. Prints each path written. Does not enable or start anything |
| `tesserae-shell install-session --enable` | Also runs `systemctl --user enable tesserae-shell.service` |
| `tesserae-shell install-session --remove` | Disables the unit when it is enabled and removes both files. Leaves the user's configuration folder alone |
| `tesserae-shell install-session --print` | Prints both files and the paths, and writes nothing |

- An existing file with different content is replaced only with `--force`; without it the command names the file, changes nothing and exits 1.
- All four accept `--json`, with the object shape of the other commands ([IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md)).
- The command writes to the user's real folders, so no test runs it against them (rule D-019, [Orchestration Log](../00%20Home/Orchestration%20Log.md)): tests set `XDG_DATA_HOME` and `XDG_CONFIG_HOME` to a temporary folder, the code refuses `--enable` and `--remove`'s `systemctl` call when a test hook replaces the runner, and the first real run is the maintainer's.

## Upgrades

- A new wheel replaces the old one in place. The path in the two files stays right while the install location stays the same; after moving the install (a new virtual environment), run `install-session --force` again. `tesserae-shell status` warns when the unit's `ExecStart` names a command that no longer exists.
- A shell file states the versions it needs in its metadata block ([TDL Language](../41%20TDL%20Reference/TDL%20Language.md)); a shell older than a file asks for is a checked error, not a crash.
- The running shell is not replaced by an upgrade: `systemctl --user restart tesserae-shell.service` or `tesserae-shell quit` and a new start.

## Failure modes and recovery

| Failure | Result |
|---|---|
| No systemd user session | `install-session` still writes both files and says the unit cannot be enabled; the shell can be started by any autostart that runs `tesserae-shell run` |
| A folder cannot be written | Exit 1 with the path and the error; nothing half-written (write to a temporary file, then rename) |
| The shell crashes at every start | systemd stops after 5 tries in 60 seconds; `journalctl --user -u tesserae-shell` has the log |

## Acceptance criteria

- [ ] `install-session --print` shows both files with the absolute path of the command that ran it.
- [ ] With the two XDG folders set to a temporary folder, `install-session` writes exactly two files there and nothing elsewhere; `--remove` removes exactly those.
- [ ] A differing existing file is kept without `--force`.
- [ ] The unit passes `systemd-analyze --user verify` on a copy in a temporary folder (a read-only check).
- [ ] The desktop file passes `desktop-file-validate`, when that tool is installed.
- [ ] No test calls `systemctl` or writes outside its temporary folder.
- [ ] A test fails if `StartLimitIntervalSec` or `StartLimitBurst` appears in the `[Service]` section of the generated unit, and passes with both in `[Unit]` (reported built 2026-11-16, not run in the vault).

## Checks Only the Maintainer Can Run

- Enabling the unit on his session and logging in again: the shell starts after KWin, and stops at logout.
- The portal accepts the registration with the desktop file installed.

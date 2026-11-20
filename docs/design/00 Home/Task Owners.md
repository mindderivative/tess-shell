---
title: Task Owners
aliases: [Owners File, Who Owns What]
type: moc
status: draft
owner: phil
created: 2026-11-13
updated: 2026-11-14
tags: [moc, process]
---

# Task Owners

> [!WARNING]
> **Withdrawn on 2026-11-14**
> The maintainer withdrew the [Tesserae Shell Directive](Tesserae%20Shell%20Directive.md) on 2026-11-14 and took the project back over. No task below is assigned by an orchestrator any more, and no session takes work from this note: it shows the state of the work when the directive ended. The maintainer assigns work himself.

> [!NOTE]
> Who owns which open task, written by the orchestrator. Every session of every project reads this note before it starts or resumes a task, because several sessions can run in one project folder and share one mailbox name, so a message reaches only one of them ([Orchestration Log](Orchestration%20Log.md) D-033, D-035). It replaces `/tmp/tess-shell-owners.md`, which the reboot of 2026-11-13 21:02 deleted with everything else in `/tmp`. Its path for a session outside the vault is `~/Projects/Obsidian/Tesserae Shell/00 Home/Task Owners.md`.

## Rules

1. One writer per checkout. Every task is built in its own git worktree with its own environment, never in a project's main checkout.
2. A worktree lives beside its repository (`../<repo>-t<task>`), never under `/tmp`: a reboot empties `/tmp`.
3. Process ids change at every restart, so a session knows its tasks by its own history: the owner column names the earlier tasks that session built.
4. A session that finds a branch, files or a commit for its task that it did not make stops and reports to `shell`.
5. Before a merge: rebase on `origin/main`, run the full suite, then merge. Commit work in progress to the task's branch at the end of every working step, so a restart loses nothing.
6. Reports to `shell` say which session is writing (by the tasks it built).
7. The safety rules D-019, D-025 and D-026 of [Orchestration Log](Orchestration%20Log.md) hold for every task.

## The tess-shell Sessions

Two processes can resume one conversation, so a session's history does not tell it apart either. A `tess-shell` session is named by the worktree it created and builds in (decided 2026-11-13 22:45):

| Name | Is the session that created and works in | Tasks |
|---|---|---|
| `focus` | `../tess-shell-t041` | Silent since the restart; its tasks went to `keys` on 2026-11-13 22:39 (D-055) |
| `tray` | `../tess-shell-t039` and `../tess-shell-t042` | Silent since the restart; T-045 and T-043 went to `m5`, T-049 is unclaimed |
| `keys` | `../tess-shell-t047`, and `../tess-shell-t041` taken over | T-053 done (`a3083ca`); T-041, then T-050, T-048, T-044 |
| `m5` | `../tess-shell-t045`, then `../tess-shell-t043` (claimed 22:42; it built M5a to M5d and held no worktree) | T-045, then T-043 |
| `guide` | Nobody yet | T-054, then T-055; T-049 (the launcher) is also unclaimed |

Why there are several: Orca starts a new session with `--continue` in every project folder each hour at :59:05, and each resumes the folder's newest conversation (read from the process list, 2026-11-13 23:16). The maintainer paused that hourly start on 2026-11-14. A session started that way holds no task until it claims a free one and the orchestrator confirms it; it never commits in the main checkout (D-057).

A session signs its reports with this name. A session that holds none of these worktrees and is not `guide` takes no task and says so.

## Open Tasks (2026-11-13 21:45)

| Task | Owner | Where | State |
|---|---|---|---|
| T-041 `feat/m6a-focus`: M6a of [M6 Brief](M6%20Brief.md) from [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md) | `keys` (taken over 22:39, D-055) | `../tess-shell-t041` (30 changed files there, not committed, survived the reboot) | In progress: commit the work in progress first |
| T-044 `feat/m5h-portal`: H1 and H2 of [M5 Brief](M5%20Brief.md) from [Portals](../40%20Specifications/Integration/Portals.md) | `keys`, after T-048 | Its own worktree | Assigned |
| T-045 `fix/media-two-players-race`: the flaky two-players Media test | `m5` | Its own worktree | Assigned |
| T-043 `feat/m5g-kwin`: G1 to G5 of [M5 Brief](M5%20Brief.md) from [Tasks Module](../40%20Specifications/Modules/Tasks%20Module.md) and [KWin Integration](../40%20Specifications/Integration/KWin%20Integration.md) | `m5` | Its own worktree | Assigned. Never the real KWin, the real `/Scripting` or the real `kwinrulesrc` |
| Phase C5 of [Configuration Application](../40%20Specifications/Configuration%20Application.md) | `tesserae`, after T-052 | Its own worktree | Assigned; the 16 ms budget for a selection is met by C5 |
| T-048 `feat/m6b-keys`: B1 of [M6 Brief](M6%20Brief.md) | `keys`, after T-050 | Its own worktree | Queued |
| T-049 `feat/m6d-launcher`: D2 of [M6 Brief](M6%20Brief.md) from [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) | Unclaimed (first free session) | Its own worktree | Queued |
| T-050 `feat/m6d-shortcut-mode`: D1 of [M6 Brief](M6%20Brief.md) | `keys`, after T-041 | Its own worktree | Queued |
| T-054 `feat/user-guide`: the user guide in the `tess-shell` repository, folder `guide/` (not `docs/`, which is generated from the vault): installing and starting, the configuration folder, a first Bar, every surface type, every shipped module with its params, styling and themes, `settings.tdl`, shortcuts, the command line, troubleshooting. Every TDL example in it is a file under `guide/examples/` that a test runs through `check`; the module and key tables are generated from the schema export so they cannot go stale | `guide` | `../tess-shell-t054` | Assigned |
| T-055 `feat/install-session`: [Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md) (the `install-session` command, the desktop file, the systemd user unit; temporary folders only in tests) | `guide`, after T-054, or the first free session | Its own worktree | Queued |
| T-057 `feat/schema-1.4`: the schema export gains a `module_only` flag on keys valid only in a module file (`Part`), `together` groups (Frame `Border_Width` with `Border_Color`; Panel `Attach`, `Attach_To`, `Meld`), a `refers_to` kind for names (`Class`, `Attach_To`, `Selector`), a `path` kind for files (`Source`, the settings paths), a kind for the 9 unbuilt keys and for the tokens `elevation.reach`, `motion.easing.standard`, `motion.easing.emphasized`; fix: a stylesheet Rule's `Text_Align` accepts no value. Fixtures regenerated; `tess-ui` told the new version | Unclaimed (first free session) | Its own worktree | Assigned |
| T-058 `fix/shortcuts-restart-flake`: the shortcut service restart test fails about 1 run in 8 | `keys`, after T-041 | Its own worktree | Assigned |
| T-059 `feat/tdl-0.2`: the shell on `tesserae-dl` 0.2.0 (slots written `<| |>`; migrate all `.tdl` files and examples with tess-dl's `tools/migrate_slots.py`; several `For` variables). To be done first after the reset: every open branch (`feat/m6a-focus`, the Media fix) must be rebased on it | First `tess-shell` session after the reset | Its own worktree | Written, not sent |
| T-060: the configuration application on `tesserae-dl` 0.2.0 | `tesserae` | Its own | Written, not sent |

Nothing is assigned to `tess-dl`, `tess-el`, `tre` or `tesserae` (T-056 closed, `c0a5d2d`, CI green) (T-051 is merged).

## Links

- [Orchestration Log](Orchestration%20Log.md) · [Tesserae Shell Directive](Tesserae%20Shell%20Directive.md) · [Home](Home.md) · [M5 Brief](M5%20Brief.md) · [M6 Brief](M6%20Brief.md)

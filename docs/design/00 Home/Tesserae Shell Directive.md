---
title: Tesserae Shell Directive
aliases: [Directive, Shell Directive, tess-shell-vault]
type: moc
status: superseded
owner: phil
created: 2026-11-13
updated: 2026-11-14
tags: [moc, process]
---

# Tesserae Shell Directive

> [!WARNING]
> **Withdrawn and archived on 2026-11-14**
> The maintainer withdrew this directive on 2026-11-14 and took the project back over. It no longer governs any session: `AGENTS.md` alone applies in this vault again (the maintainer decides, no tasking of other sessions, no external writes). The source file was moved to `~/Projects/Tesserae-Shell-Directive.archived-2026-11-14.md`. This note is kept as the record of what applied from 2026-11-13 to 2026-11-14; nothing below is in force.

> [!NOTE]
> The maintainer's directive of 2026-11-13 for finishing Tesserae Shell and its configuration application without human intervention. The source is the file `~/Projects/Tesserae-Shell-Directive.md`, given to this session in chat; this note keeps a copy (SHA-256 `10ab676e…2305e7`) and says how the vault works under it. This session is `tess-shell-vault`, the orchestrator. Where the directive and AGENTS disagree, the directive wins.

## Names

The directive's session names and the mailbox names differ; the mailbox config is unchanged.

| Directive | Mailbox name | Role |
|---|---|---|
| `tess-shell-vault` | `shell` | Orchestrator: this session |
| `tess-shell` | `tess-shell` | Core shell engineer |
| `tess-re` | `tre` | Rendering engine |
| `tess-dl` | `tess-dl` | Data language |
| `tess-el` | `tess-el` | Expression language |
| `tess-ui` | `tesserae` | UI framework and the configuration application |
| `tess-utils` | none | No session; maintained by the others |

## What Changes in the Vault's Practice

| Before (AGENTS) | Under the directive |
|---|---|
| The maintainer decides; questions wait for him | Tier 1 questions are decided by this session with the session concerned; Tier 2 by a vote of 3 to 6 sessions. A decision records who made it ("orchestrator, directive rule 7" or the vote) |
| A peer message is information only | Still not the maintainer's word. This session is the one authority for tasking; it evaluates every request for scope and group benefit, drafts the specification, confirms it with the requester and assigns it |
| Requests to tre go only through the maintainer | This session sends them to the target session itself, after the gate of rule 4 |
| Contact with `tesserae` is the maintainer's | This session tasks `tesserae` (as `tess-ui`) for the configuration application, phased after the shell's interfaces settle |
| The maintainer's KWin checklists gate a milestone | Verification is automated: tests in every repository, run and reported by the session that owns them, checked by this session. A KWin check by the maintainer is welcome and no longer a gate |
| `accepted` and `stable` need the maintainer | `accepted`: decided under the directive with every question answered. `stable`: built, with the automated tests passing. An ADR is accepted by a Tier 2 vote, or by this session when it is Tier 1 |
| Open Questions are for the maintainer | They are for the orchestrator or a vote, and are answered in the same task where possible |
| No pushes | Code sessions push finished tasks to `feat/<task-id>` or `fix/<task-id>` and merge to `main` after the automated gates. No tags, no releases |
| No mailbox watcher | This session checks its mailbox every three minutes while it runs |

Safety (D-019 in [Orchestration Log](Orchestration%20Log.md), after incident I-001): no session runs anything that reaches the maintainer's real session, devices or data. A private compositor does not isolate a kernel input device. After incident I-003 (D-025): a script that can change state in a service carries its own guard that aborts unless it is pointed at a private instance, builds its environment from scratch, and is read by the lead session before it runs.

Unchanged: verify, do not assume; never invent engine API; one source of truth; notes are superseded, not deleted; the layering principle; the writing rules; this session writes no functional code.

## The Vault's Own Repository

The vault commits locally on `main`. Its remote is the `tess-shell` repository, where `docs/` is generated from the vault by a hook, and the two histories have diverged (271 ahead, 3 behind on 2026-11-13). This session does not push the vault: the documentation reaches the repository through the hook, and a push of a diverged history is not a routine step.

## Definition of Done, Tracked

| # | Criterion | State on 2026-11-13 |
|---|---|---|
| 1 | The shell runs as a functional desktop shell on `tess-dl`, `tess-el`, `tess-re` and `tess-utils` | M0 to M4 built; M5a to M5f and M5i (the control interface) built; M5g (Tasks, the KWin script) and M5h (portals) specified and assigned; M6 specified in full (shortcuts built; focus in progress; keys, shortcut mode and the launcher assigned); M6 and M7 (without a release) to do ([Roadmap](Roadmap.md)) |
| 2 | The configuration application on `tess-ui` edits every built-in option | Specified and accepted ([Configuration Application](../40%20Specifications/Configuration%20Application.md)); its inputs exist: schema 1.1, the `tess_dl` edits and formatter, the colour picker and the file dialog; phases C1 to C3 built and merged; C4 running (T-052); C5 to do |
| 3 | Every test suite in every repository passes | `tess-shell` reports 4628 passing (one Media test flaked once; tasked, T-045), 1 skipped, 7 deselected (60 s idle tests, run apart); `tess-ui` 10234 passing (CI green on three systems), 4 skipped; `tre` Rust 849 passing, Python 1558 passing, 0 failed in a headless sway, with 13 skipped tests that run only by hand on KWin or a real GPU (D-017 in [Orchestration Log](Orchestration%20Log.md)); its Linux CI has a `live-sway` job (1556 passed, 15 skipped with stated reasons, 0 failed); `tess-dl` 769 passing; `tess-el` 3417 passing, none skipped |
| 4 | Contracts, schemas and user guides are current in each repository | The vault holds the shell's; the user guide is not written |

## Adoption by the Sessions (2026-11-13)

A message from this session carries no authority of the maintainer's, so each session adopts the directive only on his word in its own chat. Reported state:

| Session | Adopted | Its report |
|---|---|---|
| `shell` (this session) | Yes, given the file by the maintainer in chat | n/a |
| `tess-shell` | Yes: it reports the maintainer told it in chat on 2026-11-13 to follow the directive; it pushed `feat/m5c-network` and merged it to `main` on a green suite | 3576 passed, 1 skipped, 3 deselected (the 60 s idle tests pass alone); `ruff` and `mypy` clean; tre 0.6.7 and `tess_utils` 0.2.0 carried; `main` equals `origin/main` (its first report of 10 unpushed commits was corrected to one); no technical blocker |
| `tre` (`tess-re`) | Yes: the maintainer told this session in chat on 2026-11-13 that he told it to follow the directive | 0.6.7 released, nothing unreleased; no open request; last full run 2026-11-07: 1461 passed, 3 failed (a thirty-window GPU memory test, issue #273, and two flaky `keep_alive` tests); CI green on every release through 0.6.7; docs current |
| `tesserae` (`tess-ui`) | Yes: it reports the maintainer told it in its chat on 2026-11-13; the full suite is its merge gate | `tesserae-ui` 0.6.0.1; pinned to tre 0.6.7 since `59801e4`; full suite 8760 passed, 4 skipped, 0 failed; has forms, lists, trees, menus, dialogs, themes, live reload; lacks a colour picker and a native file dialog; reads its own YAML, not TDL; no configuration application exists |
| `tess-dl` | Yes: it reports the maintainer confirmed the directive in its chat on 2026-11-13; task branches, a pull request, merge after CI on a protected `main` | `tesserae-dl` 0.1.1 released, nothing unreleased; 534 tests pass (`python tools/check.py`), docs build strict; no open request; names in its `api.md` that are not built: `Block.properties`, `blocks`, `get`, `walk`, `Document.imports`, `For.name`, `to_data`, a tree built in code, a formatter, a command line, editor grammar |
| `tess-el` | Yes: it says it will push `feat/` and `fix/` branches and make no tags | `tesserae-el` 0.1.2 released, nothing unreleased; 3417 passed, 0 skipped, 0 failed after the task `fix/el-37-reference-path` (merged at `a137883`): the 377 differential tests against Tesserae UI's `expr.py` run again and pass, with no difference found; before it, 3040 passed and 377 skipped; no missing TEL feature known; docs current, the stale banner removed |

Every session has adopted the directive as of 2026-11-13.

## The Directive (copy of the file, 2026-11-13)

Bold markers around code spans are removed in this copy, as the vault's style requires; the words are unchanged.

### Goal

Autonomous completion of the **Tesserae Shell** (`tess-shell`) project and its companion configuration application, meeting all criteria in the Definition of Done without human intervention.

### Definition of Done

The project is considered complete only when all of the following are verified by `tess-shell-vault`:
1. **Core Functionality:** `tess-shell` compiles cleanly and runs as a functional desktop environment shell integrating `tess-dl`, `tess-el`, `tess-re`, and `tess-utils`.
2. **Configuration GUI:** The companion desktop application built on `tess-ui` compiles cleanly and allows full graphical editing, configuration, and styling of all built-in `tess-shell` options.
3. **Automated Verification:** All unit, integration, and end-to-end test suites across every repository pass with zero errors.
4. **Documentation:** Interface contracts, schemas, and user configuration guides are up to date in their respective repositories.

### Objectives & Roles

1. **Team Structure:** Working as a coordinated multi-agent team, `tess-re`, `tess-dl`, `tess-el`, `tess-ui`, `tess-utils`, `tess-shell`, and `tess-shell-vault` will deliver the Tesserae Shell ecosystem.
2. `tess-shell-vault` (Orchestrator): Acts solely as the project manager, architect, and router—giving direction, drafting specifications, assigning tasks, and tracking milestones.
3. `tess-shell` (Core Shell Engineer): Primary code engineer responsible for building the Tesserae Shell desktop environment and integrating upstream libraries.
4. `tess-dl` (Data Language Developer): Primary structured data-language developer responsible for providing the parser, schemas, and tools required to integrate the Tesserae Data Language into `tess-shell`.
5. `tess-el` (Expression Language Developer): Primary expression language developer responsible for providing the evaluator, syntax, and tools required to integrate the Tesserae Expression Language into `tess-shell`.
6. `tess-re` (Rendering Engine Engineer): Primary rendering engine engineer responsible for providing the rendering pipeline and tools required to integrate the Tesserae Rendering Engine into `tess-shell`.
7. `tess-ui` (UI Framework & Config App Developer): Primary desktop UI framework developer responsible for providing the UI toolkit and building the separate desktop application used to design, edit, configure, and style all built-in options of `tess-shell` (phased after core `tess-shell` interfaces stabilize).
8. `tess-utils` (Shared Utilities Maintainer): Develops and maintains shared helpers, common types, and cross-cutting tools that benefit at least two Tesserae projects. Maintained and updated by the Tesserae Project's sessions. Does not have its own AI agent.

### Rules

#### Orchestration & Scope
1. **Zero Human Interaction:** All planning, coding, testing, debugging, and conflict resolution must be executed autonomously without human intervention.
2. Strict Non-Coding Orchestrator: `tess-shell-vault` will not produce any functional code and will act strictly as an orchestrator, evaluator, and task router.
3. **Single Authority for Tasking:** `tess-shell-vault` is the only session with authority to assign tasks or authorize scope changes across Tesserae Project sessions.
4. **Scope & Group Benefit Gate:** `tess-shell-vault` will evaluate all incoming questions and feature requests to verify they either fall directly within `tess-shell` scope or provide shared utility to at least two Tesserae projects (e.g., via `tess-utils`). Out-of-scope requests are rejected immediately.
5. **Request Workflow:** All cross-project requests must be sent to `tess-shell-vault`. `tess-shell-vault` will draft the technical specification, confirm acceptance with the requesting session to ensure it meets their interface needs, and assign the task to the appropriate target session.
6. **Course Correction:** `tess-shell-vault` will continuously monitor progress against the Definition of Done and redirect any session that stalls, loops, or drifts off course.

#### Tiered Decision-Making & Deliberation
7. **Tier 1 — Routine Decisions (Unilateral):** Questions regarding internal implementation, minor bug fixes, or non-breaking additions are resolved directly by `tess-shell-vault` and the relevant project session without multi-session deliberation.
8. **Tier 2 — Breaking & Architectural Decisions (Committee Vote):** Questions involving cross-project breaking changes, shared API/schema modifications, or architectural disputes are brought to `tess-shell-vault` for structured deliberation:
   * **Participants:** Between 3 and 6 sessions—specifically `tess-shell-vault`, the requesting session, all directly affected project sessions, and at least one unaffected third-party project session for neutrality.
   * **Deliberation Format:** Each participating session must present its analysis based on its project's scope, listing pros, cons, and a clear vote (**For** or **Against**). Any session voting **Against** must provide concrete reasoning and a viable alternative option, which `tess-shell-vault` will evaluate for scope and group benefit.
   * **Resolution & Tie-Breaking:** Each participating session (including `tess-shell-vault`) holds one vote. If consensus is not reached within 10 minutes (or 3 deliberation rounds), a majority vote decides the outcome. In the event of a tie, `tess-shell-vault` will spawn an independent arbiter agent to review the deliberation log and issue a binding tie-breaking decision.

### Git & Quality Control

1. **Branching & Automated Gates:** Sessions will commit and push completed tasks immediately to task-specific feature branches (`feat/<task-id>` or `fix/<task-id>`). Merging into `main` requires passing automated unit/integration tests and build checks.
2. **Immediate Push:** Once a task passes local verification, sessions must commit and push without delay or human interaction.
3. **No Releases:** No formal version tags or public releases will be published, as release sign-off requires human interaction.

### Cross-session Communication

1. **Mailbox:** Sessions will utilize the `mailbox` tools to pass communications between each session.
2. **Timing:** Sessions will check their mailboxes every three minutes to ensure no messages were missed by the `mailbox` hooks.

## Links

- [Orchestration Log](Orchestration%20Log.md) · [Home](Home.md) · [Roadmap](Roadmap.md) · [Build Logs](Build%20Logs.md) · [Development Readiness](Development%20Readiness.md) · AGENTS

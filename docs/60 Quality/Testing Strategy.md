---
title: Testing Strategy
aliases: [Tests, Test Plan, Headless Testing]
type: quality
status: draft
owner: phil
created: 2026-11-02
updated: 2026-11-03
tags: [quality, testing, needs-verification]
---

# Testing Strategy

> [!NOTE]
> How the shell is tested: which layers get which kind of test, what runs without a display, what needs a compositor, how the budgets are checked, and what stays a manual checklist. Written before M0 so the first code has tests from the start ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). It leans on what tre offers for tests with no display (`App.simulate`, `Window.simulate`, `Window.advance`, `Window.snapshot`, `Window.frame_stats`, all seen in the installed tre 0.5.9 on 2026-11-02; the tre guide for each was not re-read, #needs-verification). Proposal for the maintainer.

## Purpose and Scope

- Give each layer a test kind, a marker and a place to run.
- Name what is checked automatically and what is checked by hand.
- Not in this note: the `tess_dl` corpus (owned by `tess-dl`, [TDL Library API](../42%20Python%20API/TDL%20Library%20API.md)), tre's own tests, and security testing (to follow the security model).

## Test Layers

| Layer | What is tested | How | Needs |
|---|---|---|---|
| Unit | Config discovery, the registry, validation, the schema, the value store, TEL scope and tracking, error records | `pytest` on plain Python; no tre | Nothing |
| Files | Loading a shell file from text: `tess_dl` parse, `Import`, names, the UID write, positions in errors | `pytest` with small `.tdl` strings and the `tess_dl` corpus | `tesserae-dl` |
| Binder | The block and key tables, the converters, links, update, rebuild by key, error positions | A headless `tess_re.Window` built in the test; read properties back from nodes; `Window.advance` for animation; `Window.snapshot` for a few reference images | tre, no display |
| Binder tables vs docs | The block and key tables agree with the "tre" columns of [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) and [Style Schema](../41%20TDL%20Reference/Style%20Schema.md) | A test parses the doc tables and compares | The vault notes (a copy under `tests/data/`, refreshed by a script) |
| Surfaces | Anchor, size, margin, exclusive zone computed for a Bar, Panel, Popup, Frame; monitor matching; output events | Unit tests on the geometry functions (pure Python), with `App.simulate("output_added", ...)` for outputs | Nothing for the maths; a compositor for the windows |
| Layer windows | A real `LayerWindow` appears, reserves space, takes input | A headless sway in CI, as tre does; a manual run on KWin | A wlroots compositor; KWin by hand |
| D-Bus | The service layer, the control interface, the KWin script's call | A private session bus (`dbus-daemon`), fake services written with `dbus-fast` | `dbus-daemon` |
| Modules | The module contract: start, stop, send, actions, a failing module | A fake context; a real `Clock` against a fake time source | Nothing |
| Hot reload | A file change reaches the screen with the keyed diff | Write a file, trigger the reload, assert the node changes and unchanged nodes are not touched | Binder test setup |
| Performance | The budgets in [Performance Budgets](Performance%20Budgets.md) | Scripts that time parse, bind and update; an idle-CPU measurement of a running shell | A normal desktop |
| Accessibility | Roles and names exist on the nodes the Block Reference promises | Read the node properties; later, tre's accessibility tree | tre |
| Manual | KWin behaviour, fullscreen hiding, multi-monitor, shortcut registration, portal changes | A written checklist per milestone, run by the maintainer | A KDE session |

## Markers and What Runs by Default

| Marker | Meaning | In the default run |
|---|---|---|
| (none) | Unit, files, module and geometry tests | Yes |
| `tre` | Needs a headless tre window | Yes, if tre imports; skipped with a clear reason otherwise |
| `dbus` | Needs `dbus-daemon` | Yes, if found |
| `compositor` | Needs a running Wayland compositor | No; run in the sway job and by hand |
| `perf` | Timing and idle-cost checks | No; run on request |
| `manual` | A checklist item | No; listed, never run |

## Where Tests Run

- Local: `uv run pytest` runs the default set.
- CI (GitHub Actions, later): lint, types and the default set on Linux; the `compositor` set in a job with a headless sway; `perf` on demand. macOS and Windows are not v1 ([V1 Scope](../10%20Vision/V1%20Scope.md)).
- Software drawing (`llvmpipe`) is the reference for reference images, so a snapshot differs from a GPU render by a tolerance. Reference images are few and set per block, not per screen. #needs-verification

## Conventions

- One behaviour per test; the name says what is expected.
- Every acceptance criterion in a spec is a test or a line in the manual checklist, tagged with the note it came from.
- A bug found by code is a test first, then the fix.
- No test needs the network or the user's real config; `--config-dir` points at a temporary directory ([IPC and CLI > The Command Line](../40%20Specifications/Runtime/IPC%20and%20CLI.md#the-command-line)).
- The `tess_dl` corpus is run as it ships; the shell adds cases by `TDL-REQ-###` to `tess-dl`, not to its own copy ([tess-dl First Slice](../41%20TDL%20Reference/tess-dl%20First%20Slice.md)).

## Configuration

None.

## Failure Modes and Recovery

| Problem | Handling |
|---|---|
| tre cannot create a window with no display | The `tre` tests skip with the error text; unit tests still run |
| Reference images differ across machines | Compare with a tolerance; regenerate only by a flag |
| A test depends on timing | Use `Window.advance(ms)`, not sleeps |
| The vault copy for the table test is stale | The test reports the date of the copy and fails if the doc table has keys the code does not |

## Open Questions

1. [ ] Which tolerance and which blocks get reference images.
2. [ ] Whether the table-vs-docs test reads the vault directly in the maintainer's environment, or a copy under `tests/data/` that a script refreshes (recommended: the copy, so CI works).
3. [ ] The headless sway job: recommend adopting tre's setup once the first `LayerWindow` is built.
4. [ ] How tre exposes the accessibility tree to a test.
5. [ ] A coverage target. Recommendation: none at first; report only.

## Acceptance Criteria

- [ ] `uv run pytest` runs the default set with no display.
- [ ] A new binder table row without a matching Block Reference entry fails the table test, and the reverse.
- [ ] The import rules of [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) are tested.
- [ ] The first Bar built at M1 has a test that reads its properties back from the tre nodes.
- [ ] Each milestone ends with its manual checklist written.

## Links

- [60 Quality](60%20Quality.md) · [Performance Budgets](Performance%20Budgets.md) · [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) · [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) · [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)

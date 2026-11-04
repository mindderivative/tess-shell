---
title: M1 Brief
aliases: [M1, Static Bar Brief, Shell M1]
type: moc
status: draft
owner: phil
created: 2026-11-03
updated: 2026-11-03
tags: [moc, roadmap, brief]
---

# M1 Brief

> [!NOTE]
> The plan for milestone M1, a static Bar: one `Bar` from a `.tdl` file shown on one monitor through the whole path, `tess_dl` to schema to binder to tre, with the Clock as a fixed string. It follows [M0 Brief](M0%20Brief.md). This is a plan for the maintainer; M1 starts when M0 is done and the maintainer says so ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). Written 2026-11-03 while M0 is in progress.

## Goal and Definition of Done

M1 is done when:

- A `Main_Shell.tdl` with one `Monitor` and one `Bar` holding a `FlexBox` of `Text`, `Rectangle`, `Box` and `Spacer` blocks opens a layer-shell surface on the matched monitor and shows the content as written.
- The Bar reserves its space on KWin (maximised windows stop below it), by the geometry in [Bar > Mapping to tre](../40%20Specifications/Surfaces/Bar.md#mapping-to-tre).
- `tesserae-shell check` reports schema errors (unknown key, wrong value type, bad block) as `file:line:column` with the nearest key names, as well as syntax errors.
- A wrong value in the file leaves the Bar empty and prints every error; the shell keeps running.
- The shell stops cleanly and the surface goes away.
- The checks below pass headless, and the KWin checklist is run by hand.

Not in M1: modules, slots and TEL, hot reload, `Import`, themes, tokens, style files, auto-hide, `Panel`, `Popup`, `Frame`, hot-plug, services, shortcuts, icons.

## Scope of the File

```
---
TDL: 0.1
Shell: 0.1
Name: Main_Shell
---

Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 32
                Style { Fill: "#1f1f1f" }
                Children {
                    FlexBox {
                        Flex: HORIZONTAL
                        Spacing: 8
                        Padding: 4
                        Children {
                            Text { Text: "14:05", Font_Size: 14 }
                            Spacer { }
                            Rectangle { Width: 12, Height: 12, Fill: "#89b4fa", Corner_Radius: 6 }
                        }
                    }
                }
            }
        }
    }
}
```

The Clock is the literal `"14:05"`. Style is inline only. This sketch is illustrative; the keys are those of [Shell File](../41%20TDL%20Reference/Shell%20File.md), [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) and [Style Schema](../41%20TDL%20Reference/Style%20Schema.md).

## Design Needed First

These must reach `review` before the code session starts M1:

| # | Note | State |
|---|---|---|
| 1 | [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) | Written (draft) 2026-11-03; needs the maintainer's answers below |
| 2 | The minimal schema: the keys, types and defaults of `Shell`, `Monitor`, `Bar`, `FlexBox`, `Box`, `Text`, `Rectangle`, `Spacer` and the inline `Style` | The key tables exist in [Shell File](../41%20TDL%20Reference/Shell%20File.md), [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) and [Style Schema](../41%20TDL%20Reference/Style%20Schema.md); they need one pass against tre ([Render Binder Design > What tre Accepts (Tested 2026-11-03)](../20%20Architecture/Render%20Binder%20Design.md#what-tre-accepts-tested-2026-11-03)) |
| 3 | The Bar geometry function | Decided in [Bar > Mapping to tre](../40%20Specifications/Surfaces/Bar.md#mapping-to-tre), with worked examples that become tests |
| 4 | Monitor matching for `Index`, `Connector`, `Description` | [Shell File](../41%20TDL%20Reference/Shell%20File.md) and [TDL Language > Monitors (Shell Schema)](../41%20TDL%20Reference/TDL%20Language.md#monitors-shell-schema) |
| 5 | Default look when no theme exists | Proposed: none; literal values only in M1 |

## Tasks

| # | Task | Done when | Spec |
|---|---|---|---|
| T1 | `binder/model.py`: the typed tree classes and `BindError` | Constructing and comparing nodes works; no import outside `binder` | [Render Binder Design > The Typed Tree](../20%20Architecture/Render%20Binder%20Design.md#the-typed-tree) |
| T2 | `binder/convert.py`: the converters (length, number, bool, text) and thin wrappers over `tess_utils` for color, enum, sides and radius ([tess-utils Brief](tess-utils%20Brief.md)) | Each converter has table-driven tests, including the error cases | [Render Binder Design > Converters](../20%20Architecture/Render%20Binder%20Design.md#converters) |
| T3 | `binder/tables.py`: the block and key tables for the M1 blocks | A test builds a node for every row on a headless `tess_re` window | [Render Binder Design > The Tables](../20%20Architecture/Render%20Binder%20Design.md#the-tables) |
| T4 | `binder/build.py`: walk, spec, path-to-origin index, `Window.build`, `View` with `dispose`; refuse `If` and `For` | A built tree can be read back from the nodes; a bad value gives `file:line:column` | [Render Binder Design > Building](../20%20Architecture/Render%20Binder%20Design.md#building) |
| T5 | `schema/`: the minimal schema checked in code ([ADR-0020 Validation in Code](../30%20Decisions/ADR-0020%20Validation%20in%20Code.md)), the typed tree from the `tess_dl` tree, errors with nearest names, the `Validation` settings | Unknown key, wrong type, wrong block and a missing required key each fail with the right message and position | [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md) |
| T6 | `files/`: load `Main_Shell` from the config directory, check the metadata, `shell-root-suffix`, name uniqueness | The file-type and name cases in [TDL Language > Acceptance Criteria](../41%20TDL%20Reference/TDL%20Language.md#acceptance-criteria) pass | [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md) |
| T7 | `surfaces/bar.py`: the geometry function (anchor, size, margin, exclusive zone) as a pure function, tested with the worked examples | Every row of the worked-examples table passes | [Bar > Mapping to tre](../40%20Specifications/Surfaces/Bar.md#mapping-to-tre) |
| T8 | `surfaces/manager.py`: read `App.outputs()`, match `Monitor`, create the `LayerWindow` with namespace `tesserae-shell.bar.<name>`, bind the children, open it; close it on stop | A Bar appears on the right monitor on headless sway and on KWin | [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md), [Shell Start and Stop > Start Sequence](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#start-sequence) steps 10 and 11 |
| T9 | `check` runs T5 and T6 | The M1 error cases print and exit 1 | [IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md) |
| T10 | Tests: unit tests for T1 to T7; a headless `tess_re` test that builds the example file and reads nodes back; one reference image for the example; the headless sway job for T8 | `uv run pytest` passes; the sway job passes | [Testing Strategy](../60%20Quality/Testing%20Strategy.md) |
| T11 | Manual KWin checklist, run by the maintainer | Every line passes | [KWin Checklist](#kwin-checklist) |
| T12 | A measurement: bind time of the example and of a 3,100-node tree; idle CPU with the Bar shown, written under `tests/perf/` | Reported against the budgets | [Performance Budgets](../60%20Quality/Performance%20Budgets.md) |

## KWin Checklist

To run by hand on the maintainer's session:

- [ ] The Bar appears at the top of the chosen monitor, 32 px high, full width.
- [ ] A maximised window stops below the Bar; closing the shell lets it expand again.
- [ ] The text, the spacer and the circle appear as written, with the right colours and sizes.
- [ ] `Gap: 8` adds 8 px above the Bar and the reserved space is 40 px.
- [ ] A Bar on `Index: 1` appears on the second monitor only.
- [ ] A wrong colour value shows an error with `file:line:column` and no Bar.
- [ ] `tesserae-shell check` prints the same error without starting.
- [ ] The shell stops on SIGTERM, the Bar disappears, and the exit code is 0.
- [ ] Idle CPU with the Bar shown stays near 0%.

## Depends on tess-utils

Colour, four-sided, radius and enum conversion come from `tess_utils` ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md), accepted 2026-11-03), vendored as a tagged copy. The maintainer creates the private repository `mindderivative/tess-utils`; the shell's code session builds 0.1 ([tess-utils Brief](tess-utils%20Brief.md)). Until `tess-utils` 0.1 is tagged, the code session may write the same functions in `binder/convert.py` as pure standard-library code and move them.

## Questions for the Maintainer

1. [ ] Scope: the blocks `Box`, `FlexBox`, `Text`, `Rectangle`, `Spacer`, inline `Style` only, one Bar. Agree?
2. [ ] The typed tree classes live in `binder/model.py` and `schema` imports them (the one new allowed import). Agree (recommended)?
3. [ ] The binder builds each surface with `Window.build` only, which needs `tesserae-engine` 0.6.0 or later (already the M0 minimum). Agree?
4. [ ] Theme tokens are resolved by the shell before binding, and M1 has none: literal values only. Agree?
5. [ ] The Block Reference "tre" columns are corrected against tre by a test at T3, and I fix the notes from its output. Agree?
6. [ ] Should M1 start only when M0 is done, or may the code session start T1 to T4 now, since they need no config or lifecycle code?

## Acceptance Criteria

- [ ] Every item under "Goal and Definition of Done" is true on a clean checkout, with the KWin checklist run.
- [ ] Tasks T1 to T12 each have a test or a recorded measurement.
- [ ] The binder imports only `tess_re` and the standard library, and a test shows it.
- [ ] The design gaps found are handed back to the vault session.

## Links

- [Development Readiness](Development%20Readiness.md) · [M0 Brief](M0%20Brief.md) · [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) · [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) · [Bar](../40%20Specifications/Surfaces/Bar.md) · [Testing Strategy](../60%20Quality/Testing%20Strategy.md)

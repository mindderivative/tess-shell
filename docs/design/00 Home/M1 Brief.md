---
title: M1 Brief
aliases: [M1, Static Bar Brief, Shell M1]
type: moc
status: draft
owner: phil
created: 2026-11-03
updated: 2026-11-04
tags: [moc, roadmap, brief]
---

# M1 Brief

> [!NOTE]
> The plan for milestone M1, a static Bar: one `Bar` from a `.tdl` file shown on one monitor through the whole path, `tess_dl` to schema to binder to tre, with the Clock as a fixed string. It follows [M0 Brief](M0%20Brief.md). This is a plan for the maintainer; M1 starts when M0 is done and the maintainer says so ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). Written 2026-11-03 while M0 is in progress.

## Goal and Definition of Done

M1 is done when:

- A `Main_Shell.tdl` with one `Monitor` and one `Bar` holding a `FlexBox` of `Text`, `Rectangle`, `Box`, `Spacer` and `SVG` blocks opens a layer-shell surface on the matched monitor and shows the content as written.
- The Bar reserves its space on KWin (maximised windows stop below it), by the geometry in [Bar > Mapping to tre](../40%20Specifications/Surfaces/Bar.md#mapping-to-tre).
- `tesserae-shell check` reports schema errors (unknown key, wrong value type, bad block) as `file:line:column` with the nearest key names, as well as syntax errors.
- A wrong value in the file leaves the Bar empty and prints every error; the shell keeps running.
- The shell stops cleanly and the surface goes away.
- The checks below pass headless, and the KWin checklist is run by hand.

`SVG` is in M1 (maintainer, 2026-11-03). Not in M1: modules, slots and TEL, hot reload, `Import`, themes, tokens, style files, auto-hide, `Panel`, `Popup`, `Frame`, hot-plug, services, shortcuts, icons.

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
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 8
                        Padding: 4
                        Children {
                            Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }
                            Spacer { }
                            SVG { Source: "dot.svg", Width: 16, Height: 16, Color: "#89b4fa" }
                            Rectangle { Width: 12, Height: 12, Fill: "#89b4fa", Corner_Radius: 6 }
                        }
                    }
                }
            }
        }
    }
}
```

The Clock is the literal `"14:05"`. Style is inline only. `dot.svg` sits next to the shell file; the shell reads it and gives the text to tre ([Block Reference > SVG](../41%20TDL%20Reference/Block%20Reference.md#svg)); an icon set (`mdi`) is not loaded until M2. The `FlexBox` has `Width: EXPAND` because a layer window's root is a horizontal flex container with no padding, and a child without it would not span the Bar (found while building T4, [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md)). This sketch is illustrative; the keys are those of [Shell File](../41%20TDL%20Reference/Shell%20File.md), [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) and [Style Schema](../41%20TDL%20Reference/Style%20Schema.md).

## Progress (Reported by `tess-shell`, 2026-11-04)

T1, T2, T3, T4 and T7 are built and committed locally in `tess-shell` (not pushed): the typed model, the converters, the tables and `build`, and the Bar geometry function; 421 tests pass, `ruff` and `mypy` clean. T5, T6 and T8 to T12 are not started: they needed the `Shell File` and `Surface Types` notes at `review`, which they now are. The converters (`parse_color`, `sides` and the rest) live in `binder/convert.py` as pure standard-library code, ready to move to `tess_utils`. A peer's report is information; the vault checked the tre facts that bear on the design ([Render Binder Design > More Forms Found While Building M1 (Reported by `tess-shell`, 2026-11-04; the vault checked the first column on `tess_re` 0.6.0)](../20%20Architecture/Render%20Binder%20Design.md#more-forms-found-while-building-m1-reported-by-tess-shell-2026-11-04-the-vault-checked-the-first-column-on-tess_re-060)).

## Design Needed First

These must reach `review` before the code session starts M1:

| # | Note | State |
|---|---|---|
| 1 | [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) | Written (draft) 2026-11-03; needs the maintainer's answers below |
| 2 | The minimal schema: the keys, types and defaults of `Shell`, `Monitor`, `Bar`, `FlexBox`, `Box`, `Text`, `Rectangle`, `Spacer`, `SVG` and the inline `Style` | The key tables exist in [Shell File](../41%20TDL%20Reference/Shell%20File.md), [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) and [Style Schema](../41%20TDL%20Reference/Style%20Schema.md); they need one pass against tre ([Render Binder Design > What tre Accepts (Tested 2026-11-03)](../20%20Architecture/Render%20Binder%20Design.md#what-tre-accepts-tested-2026-11-03)) |
| 3 | The Bar geometry function | Decided in [Bar > Mapping to tre](../40%20Specifications/Surfaces/Bar.md#mapping-to-tre), with worked examples that become tests |
| 4 | Monitor matching for `Index`, `Connector`, `Description` | [Shell File](../41%20TDL%20Reference/Shell%20File.md) and [TDL Language > Monitors (Shell Schema)](../41%20TDL%20Reference/TDL%20Language.md#monitors-shell-schema) |
| 5 | Default look when no theme exists | Proposed: none; literal values only in M1 |

## Tasks

| # | Task | Done when | Spec |
|---|---|---|---|
| T1 | `binder/model.py`: the typed tree classes and `BindError` | Constructing and comparing nodes works; no import outside `binder` | [Render Binder Design > The Typed Tree](../20%20Architecture/Render%20Binder%20Design.md#the-typed-tree) |
| T2 | `binder/convert.py`: the converters (length, number, bool, text) and thin wrappers over `tess_utils` for color, enum, sides and radius ([tess-utils Brief](tess-utils%20Brief.md)) | Each converter has table-driven tests, including the error cases | [Render Binder Design > Converters](../20%20Architecture/Render%20Binder%20Design.md#converters) |
| T3 | `binder/tables.py`: the block and key tables for the M1 blocks (including `SVG`: `Source` to `svg`, `Color` to `svg_color`) | A test builds a node for every row on a headless `tess_re` window | [Render Binder Design > The Tables](../20%20Architecture/Render%20Binder%20Design.md#the-tables) |
| T4 | `binder/build.py`: walk, spec, path-to-origin index, `Window.build`, `View` with `dispose`; refuse `If` and `For` | A built tree can be read back from the nodes; a bad value gives `file:line:column` | [Render Binder Design > Building](../20%20Architecture/Render%20Binder%20Design.md#building) |
| T5 | `schema/`: the minimal schema checked in code ([ADR-0020 Validation in Code](../30%20Decisions/ADR-0020%20Validation%20in%20Code.md)), the typed tree from the `tess_dl` tree, errors with nearest names, the `Validation` settings | Unknown key, wrong type, wrong block and a missing required key each fail with the right message and position | [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md) |
| T6 | `files/`: load `Main_Shell` from the config directory, check the metadata, `shell-root-suffix`, name uniqueness; read an `SVG` block's `Source` file (path relative to the file that names it) and put the text in the typed tree, with a missing or malformed file reported at the `Source` key | The file-type and name cases in [TDL Language > Acceptance Criteria](../41%20TDL%20Reference/TDL%20Language.md#acceptance-criteria) pass | [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md) |
| T7 | `surfaces/bar.py`: the geometry function (anchor, size, margin, exclusive zone) as a pure function, tested with the worked examples | Every row of the worked-examples table passes | [Bar > Mapping to tre](../40%20Specifications/Surfaces/Bar.md#mapping-to-tre) |
| T8 | `surfaces/manager.py`: read `App.outputs()`, match `Monitor`, create the `LayerWindow` with namespace `tesserae-shell.bar.<name>`, bind the children, open it; close it on stop | A Bar appears on the right monitor on headless sway and on KWin | [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md), [Shell Start and Stop > Start Sequence](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#start-sequence) steps 10 and 11 |
| T9 | `check` runs T5 and T6 | The M1 error cases print and exit 1 | [IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md) |
| T10 | Tests: unit tests for T1 to T7; a headless `tess_re` test that builds the example file and reads nodes back; one reference image for the example; the headless sway job for T8 | `uv run pytest` passes; the sway job passes | [Testing Strategy](../60%20Quality/Testing%20Strategy.md) |
| T11 | Manual KWin checklist, run by the maintainer | Every line passes | [KWin Checklist](#kwin-checklist) |
| T12 | A measurement: bind time of the example and of a 3,100-node tree; idle CPU with the Bar shown, written under `tests/perf/` | Reported against the budgets | [Performance Budgets](../60%20Quality/Performance%20Budgets.md) |

## KWin Checklist

To run by hand on the maintainer's session:

- [x] The Bar appears at the top of the chosen monitor, 32 px high, full width.
- [x] A maximised window stops below the Bar; closing the shell lets it expand again.
- [x] The text, the spacer, the SVG dot and the circle appear as written, with the right colours and sizes.
- [x] `Gap: 8` adds 8 px above the Bar. Measure the reserved space with a maximised window: the mapping sets the zone to 40 and the margin to 8; sway reserved 48 (zone plus margin), so record whether KWin reserves 40 or 48 (decision D10).
- [x] A Bar on `Index: 1` appears on the second monitor only.
- [x] A wrong colour value shows an error with `file:line:column` and no Bar.
- [x] `tesserae-shell check` prints the same error without starting.
- [x] The shell stops on SIGTERM, the Bar disappears, and the exit code is 0.
- [x] Idle CPU with the Bar shown stays near 0%.

## Depends on tess-utils

Colour, four-sided, radius and enum conversion come from `tess_utils` ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md), accepted 2026-11-03), vendored as a tagged copy. The maintainer creates the private repository `mindderivative/tess-utils`; the shell's code session builds 0.1 ([tess-utils Brief](tess-utils%20Brief.md)). Until `tess-utils` 0.1 is tagged, the code session may write the same functions in `binder/convert.py` as pure standard-library code and move them.

## Questions for the Maintainer

All six were answered on 2026-11-03. The `tess-shell` session reported the first five over the mailbox and the maintainer confirmed them in chat: "That is correct, I added SVG and agreed to M1 - M5. Yes, they can."

1. [x] Scope: the blocks `Box`, `FlexBox`, `Text`, `Rectangle`, `Spacer` and `SVG`, inline `Style` only, one Bar. `SVG` was added by the maintainer.
2. [x] The typed tree classes live in `binder/model.py` and `schema` imports them.
3. [x] The binder builds each surface with `Window.build` only.
4. [x] Theme tokens are resolved by the shell before binding; M1 has none (literal values only).
5. [x] The Block Reference "tre" columns are corrected against tre by a test at T3, and the notes are fixed from its output.
6. [x] The code session may start T1 to T4 before the design notes reach `review`.

## Decisions Raised by the Build (2026-11-04)

All nine were answered by the maintainer on 2026-11-04: D1 yes, D2 yes, D3 to D6 yes to all four, D7 fine, D8 and D9 ok. The recommendation in each row is the decision.

| # | Question | Recommendation |
|---|---|---|
| D1 (blocks T5) | `schema` (T5) needs the colour and length parsers that sit in `binder/convert.py` until `tess_utils` exists. The rule lets `schema` import only `binder.model` | Allow `schema` to import `binder.convert` until `tess_utils` is vendored, then both use `tess_utils` |
| D2 | A key given both as a property and inside `Style { }` | An error naming both places (as a repeated key is, D9); no precedence rule to learn. [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) R2 said "inline priority", which is ambiguous |
| D3 | A `Rectangle` is built as a rounded tre `box`, not a `path` | Accept; other shapes stay paths |
| D4 | `Spacer`: a `box` with `flex_grow` 1, common keys only | Accept; now in [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) |
| D5 | `Font_Family` list: tre takes one string; the binder joins the list with `", "` | Accept; check the fallback in the KWin checklist |
| D6 | The schema flattens a `Border { Width, Color }` block into `Border_Width` and `Border_Color` for the binder | Accept (matches D78 in [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)) |
| D7 | A `Text` with no `Foreground` is invisible (tre draws text with no `fill` invisibly) and no default is specified | M1: the sample file sets `Foreground`; a built-in default text colour is a theme question for M3 |
| D8 | `bar_geometry` (T7) was built beyond the waiver for T1 to T4 | Fine: it needs only [Bar](../40%20Specifications/Surfaces/Bar.md), which is at `review`; no need to hold it back |
| D9 | Corner radii: [Common Keys and Conventions](../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md) listed them as left, top, right, bottom; [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) and tre use top-left clockwise | Fixed: Common Keys now says corner radii are the exception |

### Raised by the Second Report (2026-11-04)

Answered by the maintainer on 2026-11-04 ("I did", confirming D10 to D18 as recommended; the code session reported the answers first, the maintainer confirmed them to the vault session): D10 keep zone = size + Gap until KWin is measured; D11 a warning naming both blocks, the first wins; D12 and D18 a 15 ms bind budget; D13 to D16 and D17 as in [M1 Build Log](M1%20Build%20Log.md).

| # | Question | Recommendation |
|---|---|---|
| D10 (answered: the Gap stays in the zone; KWin and sway reserve 48) | Gap and the reserved space. The mapping sets `exclusive_zone` to `T + Gap` and the margin to `Gap` ([Bar > Mapping to tre](../40%20Specifications/Surfaces/Bar.md#mapping-to-tre), D61). On sway a Bar with Height 32 and Gap 8 reserved 48, not 40: sway adds the margin to the zone. The protocol's `set_margin` says "The exclusive zone includes the margin" ([wlr-layer-shell](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)), which reads as the compositor counting the margin inside the reserved area, so the zone value would be `T` alone. KWin is not measured | Do not change D61 yet. The maintainer's KWin check (T11) measures the reserved space with `Gap: 8`; if KWin also reserves 48, the zone becomes `T` and the margin supplies the Gap. If KWin reserves 40, the two compositors differ and the rule needs a per-compositor note |
| D11 | Two `Monitor` blocks that select the same output at run time (for example `Connector: DP-1` and `Index: 0`) cannot be detected by `check`; the first wins and the second opens nothing, with only an info log. The spec calls two blocks naming the same monitor an error | `check` reports an error when two blocks give the same selector value; at start, a warning naming both positions when two blocks resolve to one output, and the first wins |
| D12 | The binder takes 12.6 ms (median) to bind a typed 3,100-node tree; tre's `build` alone is 5.3 ms, so the binder adds about 7 ms. The design said "a few milliseconds" | Set the budget at 15 ms for 3,100 nodes; the real number is in the log |

## Acceptance Criteria

- [ ] Every item under "Goal and Definition of Done" is true on a clean checkout, with the KWin checklist run.
- [ ] Tasks T1 to T12 each have a test or a recorded measurement.
- [x] The binder imports only `tess_re` and the standard library, and a test shows it.
- [ ] The design gaps found are handed back to the vault session.

## Links

- [Development Readiness](Development%20Readiness.md) · [M0 Brief](M0%20Brief.md) · [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) · [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) · [Bar](../40%20Specifications/Surfaces/Bar.md) · [Testing Strategy](../60%20Quality/Testing%20Strategy.md)

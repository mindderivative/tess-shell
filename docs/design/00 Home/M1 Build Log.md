---
title: M1 Build Log
aliases: [M1 Log]
type: moc
status: draft
owner: phil
created: 2026-11-04
updated: 2026-11-04
tags: [moc, build-log]
---

# M1 Build Log

> [!NOTE]
> The log of milestone M1, a static Bar. The `tess-shell` code session owns this note ([Build Logs](Build%20Logs.md)). The vault session wrote the first version on 2026-11-04 from the code session's mailbox reports and the repository history; the code session takes it over from here and keeps it current.

## Tasks

| Task | State | Commits in `tess-shell` | Note |
|---|---|---|---|
| T1 Typed model (`binder/model.py`) | Built | e99ba7f | Origin, values, Node, IfNode, ForNode, `BindError` |
| T2 Converters (`binder/convert.py`) | Built | 01cf78b | Pure standard library; includes `parse_color` and `sides`; movable to `tess_utils` |
| T3 Tables (`binder/tables.py`) | Built | a54c00a | Box, FlexBox, Text, Rectangle, Spacer, SVG; 217 table cases build a node on a headless `tess_re` window |
| T4 Build (`binder/build.py`) | Built | a54c00a | All errors collected with `file:line:column`; `If` and `For` refused |
| T5 Schema | Built | 54d8322 | `schema/`: blocks, values, `read_shell`; rules `unknown-key`, `bad-value`, `bad-sides`, `missing-key`, `bad-name`, `name-duplicate`, `monitor-duplicate`, `style-duplicate`, `shell-root`, `not-built`; `Border { }` flattened; the SVG `Source` file read by the loader |
| T6 Files | Partly | 54d8322, 699a516 | `files/header.py`: version pins (reported at the pin's own key; an absent `TEL` or `TRE` pin is not an error) and `shell-root-suffix`; `check` and `run` step 7 run stages 1 to 4. Not built: name uniqueness across several files, `Import`, stage 5 across files |
| T7 Bar geometry (`surfaces/bar.py`) | Built | 040c56f, 214f142 | All worked examples tested; the geometry accepted by a headless `LayerWindow` |
| T8 Surface manager | Built | 2bd635e | `assign()` (Connector, Description, Index), one `LayerWindow` per Bar with namespace `tesserae-shell.bar.<name>`, a bind error leaves that Bar empty |
| T9 `check` runs T5 and T6 | Built | 54d8322 | Schema errors print as `file:line:column` and exit 1; warnings print and do not fail |
| T10 Tests | Built | 2bd635e, c7f9ff8, 7c33d4a | Unit tests for T1 to T7, a read-back of the example, live sway tests, and the reference image `tests/snapshots/m1_example.png` (400x32, compared with a tolerance of 16 per channel on at most 2 % of the pixels; `UPDATE_SNAPSHOTS=1` regenerates it) beside pixel-position checks |
| T12 Measurements | Built | 9631c7a | `tests/perf/bind-results.md`, `idle-results-bar.md` |
| T11 KWin checklist | Built | none | Run by the maintainer on KWin 6.8.2, 2026-11-04, two monitors (HDMI-A-1 at 0,0 and DP-1 below it, 1920x1080, scale 1). All nine lines pass; the Gap line measured 48 px reserved, kept by decision D31; see the KWin results below |
| D2 and D5 applied | Built | cb479bd | Style-and-property error; `Font_Family` joined into one string |
| D11 applied | Built | 7c33d4a | A Monitor naming an output an earlier block took logs a warning naming both blocks at start; the first wins |

## Measurements

| What | Result | Date and conditions |
|---|---|---|
| Tests | 494 passed (at 7c33d4a; four runs in a row at c7f9ff8 with 492), `ruff` and `mypy` clean; the suite also passes with `WAYLAND_DISPLAY` and `DISPLAY` unset | 2026-11-04, `uv run pytest`; Python 3.14.9 with the GIL, tre 0.6.1 |
| Bind a typed 3,101-node tree | 12.6 ms median (tre's `build` alone 5.3 ms) | Private headless sway, Python 3.14.9 with the GIL (`tests/perf/bind-results.md`) |
| Bind the example (5 nodes) | 0.025 ms; typing the example file 0.067 ms | same |
| Idle with the Bar shown, 60 s | 0.000 % of one core, 2.65 wake-ups per second, 72 threads (tre's) | same (`tests/perf/idle-results-bar.md`) |
| Live proof on sway | The Bar is configured 1280x32; the workspace shrinks by the reserved zone and returns after SIGTERM (exit 0); a `Monitor` matching no output opens nothing; a bad SVG leaves the Bar empty and the shell runs | same |

## Differences from the Specs

The nine decisions D1 to D9 are in [M1 Brief > Decisions Raised by the Build (2026-11-04)](M1%20Brief.md#decisions-raised-by-the-build-2026-11-04), answered by the maintainer. Choices made in the schema (T5) that no spec states; each is a question until the maintainer answers (D13 to D16, answered below):

- A style key written directly on a block is accepted for every style key of that block, not only `Padding`, `Margin`, `Spacing` and `Opacity` as [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) R2 says. A key written both on the block and in its `Style` is `style-duplicate`.
- The Bar's inline `Style` takes `Fill`, `Background` and `Opacity`; `Fill` is an alias of `Background` there. Only the colour is applied in M1.
- The Bar keys `Auto_Hide`, `Auto_Hide_Delay`, `Reveal_Key`, `Exclusive_Zone`, `Keyboard`, `Input_Region`, `Visible`, `Attach_To`, `Meld`, `Animation`, `Text_Rotation`, `Padding` and `Class` are accepted with a `not-built` warning and ignored. `Import`, `Panel`, `Frame`, `Popup`, `If`, `For` and a `Style` file are errors (`not-built`).
- A missing `TEL` or `TRE` pin in the metadata is not an error ([TDL Language](../41%20TDL%20Reference/TDL%20Language.md) says a shell requires them; the M1 sample omits them).
- Two `Monitor` blocks with the same selector text are a `check` error (`monitor-duplicate`); two that resolve to one output at run time are not detected, the first wins (D11).
- Where the code lives: typed shell definitions (`ShellDef`, `MonitorDef`, `BarDef`) are in `schema/model.py`, and `surfaces/manager.py` imports them, because the layout's shell `model` package does not exist yet. `tess_dl` accessors moved from `files/tree.py` to `schema/tree.py`, because `schema` may not import `files`.

## Facts About tre, TEL and tess_dl

Recorded in [Render Binder Design > More Forms Found While Building M1 (Reported by `tess-shell`, 2026-11-04; the vault checked the first column on `tess_re` 0.6.0)](../20%20Architecture/Render%20Binder%20Design.md#more-forms-found-while-building-m1-reported-by-tess-shell-2026-11-04-the-vault-checked-the-first-column-on-tess_re-060). Open: the fallback of a font stack could not be seen headless (no text pixels for any family); check under a live compositor.

Found on tre 0.6.1, 2026-11-04, headless unless noted:

- A `LayerWindow` root has no padding and is a horizontal flex container (`padding_top` reads 0.0); a plain `Window` root has the default padding. A `FlexBox` in a Bar therefore needs `Width: EXPAND` to span it.
- A text node with no `fill` is not drawn visibly on the default background; `fill` colours text.
- The `configure` event gives `width` and `height` as floats (1280.0 by 32.0).
- `LayerWindow.get("anchor")` returns the edges in tre's own order, not the order given.
- On sway (private, headless, 1280x720), a Bar of height 32 with `Gap: 8` sets margin 8 and `exclusive_zone` 40, and sway reserves 48: sway adds the anchored edge's margin to the zone. KWin is not measured.
- `Output.name` is `HEADLESS-1` and `description` is `Headless output 1` on the private sway; outputs are readable before `App.run()`.
- A callback queued with `call_soon` before `App.run()` is not drained until the loop is next woken, on 0.6.0 and 0.6.1 ([TRE-REQ-011 Drain call_soon at Loop Start](../80%20Requests/TRE-REQ-011%20Drain%20call_soon%20at%20Loop%20Start.md)); the shell retries `stop()` every 50 ms after a stop request, and only then.

## KWin Results

Reported by the maintainer, 2026-11-04, KWin 6.8.2, `/tmp/tess-kwin-m1/run.sh <variant>` (configs generated from the M1 sample):

| Line | Result |
|---|---|
| Bar at the top of the chosen monitor, 32 px, full width | Pass |
| A maximised window stops below the Bar; closing the shell lets it expand | Pass |
| Text, spacer, SVG and circle as written | Pass |
| `Gap: 8`: reserved space | **KWin reserves 48 px**, measured with PixelKit: 8 px above the Bar, 32 px for the Bar, 8 px below it. The geometry sent is margin 8 and zone 40, so KWin, like sway, adds the margin to the zone |
| `Index: 1` | Pass: the Bar shows on DP-1 only |
| A wrong colour | Pass: `Shells/Main_Shell.tdl:17:31: error: Fill: not a colour: 'blue'`, the hint, and no Bar |
| `check` prints the same error without starting | Pass: the same `17:31` error, the source line, the caret and the hint, `exit code: 1`, nothing started (`/tmp/tess-kwin-m1/check.sh`) |
| SIGTERM: Bar disappears, exit code 0 | Pass: the Bar disappeared, the log shows `closed (stopped)`, `stopping`, `stopped`, and `echo $status` (fish) printed `exit code: 0` |
| Idle CPU | Pass: 0 % |

## Decisions Needed

Answered by the maintainer on 2026-11-04, from the KWin result:

| # | Decision | Effect in the code |
|---|---|---|
| D31 | The Gap stays part of the exclusive zone (zone = thickness + Gap, margin = Gap). The maintainer's reason: with a margin along the attached edge, a zone of the thickness alone would let maximised windows hide under the Bar, which is why the Gap is not a plain margin. Measured on KWin 6.8.2: the reserved space is 48 for `Height: 32`, `Gap: 8` (the zone 40 plus the margin 8), so there are 8 px between the Bar and the first window as well as 8 px above the Bar. Not tested: whether a zone of 32 would hide a window; the code session's reading of the 48 is that KWin adds the margin, so it would not | No change; the Bar note should say the reserved space is 48 on KWin and sway, and `Gap` adds that space on both sides of the Bar (kept, maintainer, 2026-11-04) |

Answered by the maintainer on 2026-11-04 (all as recommended):

| # | Decision | Effect in the code |
|---|---|---|
| D10 | Keep the zone as size plus Gap until KWin is measured | No change; the KWin checklist records the number |
| D11 | Log a warning naming both blocks; the first wins | Built (7c33d4a) |
| D12, D18 | The bind budget for 3,101 nodes is 15 ms; 12.6 ms passes | No change |
| D13 | Every style key of a block may be written on the block; `style-duplicate` if also in `Style` | As built |
| D14 | `Fill` is an alias of `Background` in a Bar's `Style` | As built |
| D15 | A Bar key M1 does not build is a warning; `Import`, other surfaces, `If`, `For` are errors | As built |
| D16 | A missing `TEL` or `TRE` pin is not an error in M1 | As built |
| D17 | Commit one reference PNG compared with a tolerance | Built (7c33d4a) |

## For the Vault Session

- Add `Foreground` to the Brief's sample file: its `Text { Text: "14:05", Font_Size: 14 }` builds but draws nothing visible on `#1f1f1f` (D7). The code's sample writes `Foreground: "#ffffff"`.
- The layout note should say where the typed shell definitions live (`schema/model.py` for now) and list `surfaces.manager` among the importers of `tess_re`; `tests/test_imports.py` encodes the rows used.
- The live tests need `swaymsg`; they skip with the reason when it is missing.

## Links

- [Build Logs](Build%20Logs.md) · [M1 Brief](M1%20Brief.md) · [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md)

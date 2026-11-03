---
title: Familiar Names Audit
aliases: [Naming Audit, Designer Vocabulary Audit]
type: tdl-ref
status: draft
owner: phil
created: 2026-11-02
updated: 2026-11-02
tags: [tdl-ref, naming, needs-verification]
---

# Familiar Names Audit

> [!NOTE]
> The maintainer's rule (2026-11-02, [ADR-0014 Shell File Language > Ninth-Round Decisions (2026-11-02)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#ninth-round-decisions-2026-11-02) D68): someone who knows another UI framework should expect a TDL name to work the same or similar. This note compares the shell's key, block and enum names with CSS, Flutter, SwiftUI, Compose, QML, Android, Figma and Material Design 3. **The comparisons come from a research agent working from its own knowledge; only Qt's alpha-first hex colour was checked against a source.** Treat each row as a lead to confirm, not a fact (rule 1). The maintainer answered on 2026-11-02 ([ADR-0014 Shell File Language > Tenth-Round Decisions (2026-11-02)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#tenth-round-decisions-2026-11-02), D71 to D83); the section "Outcome" below lists what was decided for each row.

## How to Read It

| Verdict | Meaning |
|---|---|
| Conflicting | The same word means something different elsewhere. This is the dangerous case: a designer guesses wrong without an error. |
| Similar | The idea matches; a detail differs and needs a sentence in the docs. |
| Same | No action. |

## Conflicting Names (Decide These First)

| #   | Ours                                      | Where                                    | Means here                                                                        | Means elsewhere                                                                                                               | Recommendation                                                                                                                                                                 |
| --- | ----------------------------------------- | ---------------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | `Gap`                                     | Bar, Panel, Popup; D49                   | Distance from a surface to what it attaches to                                    | CSS `gap`, Figma, Flutter, Compose and QML `spacing`: space between children                                                  | Rename. A Bar uses `Margin`; Panel and Popup use `Margin` or `Side_Offset`. This reopens D49                                                                                   |
| 2   | Four-sided order Left, Top, Right, Bottom | D50                                      | A list of four runs L, T, R, B                                                    | CSS runs T, R, B, L and allows 2 or 3 values; SwiftUI runs top, leading, bottom, trailing. Flutter, Qt and WPF run L, T, R, B | Keep D50 but correct its claim that LTRB is "the convention of other UI frameworks", make a 2- or 3-item list an error with a hint, and show the named-sides block in examples |
| 3   | `Flex: HORIZONTAL` or `VERTICAL`          | FlexBox                                  | Stack direction                                                                   | CSS `flex` is grow/shrink/basis; the direction is `flex-direction`. Flutter `direction`; Android and Qt `orientation`         | Rename to `Orientation`                                                                                                                                                        |
| 4   | `Frame`                                   | Surface type                             | A ring around the screen reserving all four edges                                 | Figma Frame and Qt `Frame` are plain containers                                                                               | Rename (candidates `Bezel`, `Screen_Frame`)                                                                                                                                    |
| 5   | `Panel`                                   | Surface type                             | A general surface: OSD, widget, launcher                                          | In Plasma a panel is what the shell calls a Bar                                                                               | Document now; the maintainer decides whether to rename (candidate `Window`)                                                                                                    |
| 6   | `Anchor` and `Anchor_To`                  | Panel, Popup                             | `Anchor` is the screen edges (layer-shell); `Anchor_To` is a target               | CSS Anchor Positioning: the anchor is the target element                                                                      | Rename Popup `Anchor_To` to `Attach_To` (Panel already has it); label `Anchor` as layer-shell vocabulary                                                                       |
| 7   | `Size`                                    | Panel `[w, h]`, text style, Terminal     | Two meanings                                                                      | CSS `font-size`, Flutter `fontSize`                                                                                           | `Font_Size`; Panel gets `Width` and `Height` as Bar has. Likewise `Weight` to `Font_Weight`, text `Align` to `Text_Align`                                                      |
| 8   | `Align`                                   | Panel, Popup, text style                 | Position along the shared edge, or text alignment                                 | CSS `text-align`                                                                                                              | One name for the surface form (`Alignment`, as Bar has)                                                                                                                        |
| 9   | `Border: true` and `Border { }`           | Style Schema, TDL Language               | Both forms appear                                                                 | CSS `border` is a shorthand                                                                                                   | Keep the block, drop the bool                                                                                                                                                  |
| 10  | `Border_Thickness`                        | Style Schema                             | Border width                                                                      | CSS `border-width`, Flutter `BorderSide.width`, QML `border.width`                                                            | `Border_Width`                                                                                                                                                                 |
| 11  | `On_Input`                                | TextField                                | Committed IME text                                                                | CSS `input` fires per edit                                                                                                    | Rename (`On_Text_Commit`) or document                                                                                                                                          |
| 12  | `Focused` state                           | Style states                             | Keyboard focus only                                                               | CSS `:focus`, Flutter, QML include mouse focus; `:focus-visible` matches ours                                                 | `Focus_Visible`, or document                                                                                                                                                   |
| 13  | `Position: RELATIVE`                      | Block Reference                          | In flow; offsets do nothing                                                       | CSS `relative` shifts by the offsets; in flow is `static`                                                                     | `STATIC` or `FLOW`                                                                                                                                                             |
| 14  | `Offset` (four-sided)                     | Panel, D51                               | Inset from anchored edges                                                         | CSS `inset`; Compose and SwiftUI `offset` shift without layout                                                                | `Inset`, or `Left/Top/Right/Bottom` as the absolute block uses                                                                                                                 |
| 15  | `Unfocus` in `On_Unfocus`                 | Block Reference                          | Focus lost                                                                        | CSS `blur`                                                                                                                    | `On_Blur`                                                                                                                                                                      |
| 16  | `Label`                                   | Module, accessibility name, `Type.Label` | Three meanings                                                                    | SwiftUI `Label` is icon plus text; HTML label captions an input                                                               | `A11y_Label` for the accessibility key                                                                                                                                         |
| 17  | `Hidden: true` on a surface               | Bar, Panel                               | Inverse of `Visible`                                                              |                                                                                                                               | Use `Visible` everywhere                                                                                                                                                       |
| 18  | `Emphasised` easing                       | Style Schema                             | British spelling                                                                  | M3 `emphasized`                                                                                                               | `Emphasized`; keys and tokens use US spelling                                                                                                                                  |
| 19  | `Elevation: 0..5`                         | Style Schema                             | A theme level                                                                     | Flutter, Compose, Android: continuous dp. M3 levels 0 to 5 map to 0, 1, 3, 6, 8, 12 dp                                        | Document "M3 level, not dp", or `Elevation_Level`                                                                                                                              |
| 20  | Border and box model                      | Box vs Frame                             | Border takes no layout space on a Box, adds to size on a Frame                    | CSS border-box takes space                                                                                                    | Document one box model: does `Width` include padding and border                                                                                                                |
| 21  | `EXPAND` and `AUTO`                       | Sizes                                    | `EXPAND` stretches (blocks: takes free space); `AUTO` is fit-to-content           | CSS `width: auto` stretches a block                                                                                           | Document both senses with a mapping table                                                                                                                                      |
| 22  | `Tooltip`                                 | Popup, CKC                               | `Tooltip: true` on a Popup, `Tooltip: <file>` elsewhere                           |                                                                                                                               | Split or document                                                                                                                                                              |
| 23  | Colour forms                              | CKC, TL                                  | `#RRGGBBAA` alpha last; `rgba(0 0 0 0.5)` with spaces; a bare word is a theme key | CSS alpha last; Qt (checked), Android and Flutter alpha first. CSS allows commas or `/`. CSS names such as `red`              | Keep, say "alpha is last"; accept comma and slash forms or give a hint; reserve `transparent` and CSS names or give a hint                                                     |
| 24  | `START` and `END` on surfaces             | Bar, Popup                               | Physical left or top                                                              | CSS, Compose, SwiftUI follow text direction                                                                                   | Document "left-to-right only in v1"                                                                                                                                            |

## Outcome (2026-11-02)

| Row | Decision |
|---|---|
| 1 `Gap` | Kept; documented as not CSS `gap` (D71) |
| 2 Four-sided order | Kept; claim corrected; a list of 2 or 3 items is an error with a hint (D72) |
| 3 `Flex` | Kept (D84) |
| 4 `Frame` | Kept (D84) |
| 5 `Panel` | Kept, and `Bar` kept (D73) |
| 6 `Anchor_To` | Popup uses `Attach_To` (D75) |
| 7 `Size`, `Weight`, `Align` | `Font_Size`, `Font_Weight`, `Text_Align`; Panel and Popup `Width` and `Height` (D76) |
| 8 `Align` | `Alignment` everywhere on surfaces (D77) |
| 9 `Border` | Block only (D78) |
| 10 `Border_Thickness` | `Border_Width` (D78) |
| 11 `On_Input` | `On_Text_Commit`, with `On_Changed` firing on every edit (D80) |
| 12 `Focused` | Kept and documented (D85) |
| 13 `Position` | `RELATIVE` and `ABSOLUTE` kept (D86) |
| 14 `Offset` | One signed number, positive towards the end; a Panel's four-sided position is `Inset` (D87, D89) |
| 15 `On_Unfocus`, 16 `Label` | Kept (D84) |
| 17 `Hidden` | `Visible` everywhere (D81) |
| 18 `Emphasised` | `Emphasized` (D82) |
| 19 `Elevation` | A percentage, 100% about 64 px (D88) |
| 20 Border and the box | A border takes layout space everywhere (D79); box sizing open |
| 21 `EXPAND`, `AUTO` | Kept and documented (D83) |
| 22 `Tooltip` | Kept and documented (D83) |
| 23 Colour forms | Kept and documented (D83) |
| 24 `START`, `END` | Kept; left-to-right only (D84) |

## Names to Align With Other Frameworks

| Ours                   | Proposed                                                                                    | Reason                                                   |
| ---------------------- | ------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `Bitmap`               | `Image`                                                                                     | Flutter, SwiftUI, Compose, QML                           |
| `ScrollBox`            | `ScrollView`                                                                                | Flutter, SwiftUI, Android, QML, and tre's own node kind  |
| `Toggle` (module)      | `Switch`                                                                                    | M3, Flutter, Compose, QML, Android (SwiftUI says Toggle) |
| `FlexBox`              | Add `Row` and `Column` shorthands                                                           | Compose, SwiftUI, QML, Flutter                           |
| `Box`                  | Keep; document "like Compose `Box`, SwiftUI `ZStack`, Flutter `Stack`"; maybe alias `Stack` |                                                          |
| `Kind`                 | `Applies_To`                                                                                | No framework uses `Kind` this way                        |
| `Shadow_Bleed`         | Document or rename (`Shadow_Space`)                                                         | "Bleed" is a print term                                  |
| Popup `Adjust: FLIP_X` | Document the mapping to Floating UI `flip` and `shift`                                      |                                                          |

## Where the Prose Assumes Insider Knowledge

Reference pages for designers should not say these; the right column is the plain wording. The engine and protocol words move to an "Under the hood" box or to a maintainer appendix.

| Jargon | Plain wording |
|---|---|
| layer surface, layer-shell, xdg-toplevel, compositor | A window the desktop pins to a screen edge, or above or below normal windows |
| exclusive zone | Reserved space: how far maximised windows stop from the edge |
| `Layer: BACKGROUND` to `OVERLAY` | Stacking level: wallpaper, below windows, above windows, above everything |
| `Keyboard: NONE`, `ON_DEMAND`, `EXCLUSIVE` | Does it take typing: never, when clicked, always |
| `Input_Region`, hit shape painted | The part that reacts to the mouse; only drawn pixels respond |
| painter, reserver, strip, hosted melding | The ring, an edge band, joined corners |
| registry, UID, `Clock@<uid>` | A unique name for each item; you rarely write it |
| bare word kept as a string until the schema types it | Write `true` or `false`; no quotes |
| slot, TEL, ViewModel, `@action` | A `{{ }}` expression; a Python function marked as an action |
| pins, minimum versions | The oldest version of each tool this file needs |
| decision numbers (D41), `#needs-verification`, a "tre" column in every table | Keep in a maintainer appendix, not in the user tables |

## Wording Rules for the Docs

1. Lead with the familiar name ("same as CSS `gap`", "like Figma Hug") and say plainly where TDL differs. Never reuse a familiar word with a different meaning.
2. Describe what you see, then what the system does ("windows stop 40 px from the edge", not "exclusive zone 40").
3. Show before telling: a three-line example with a before and after for each placement or sizing key.
4. State value rules once: unit (logical pixels, no suffix), side order, alpha position, angles in degrees, time in milliseconds, the box model. A wrong value gets an error that names the right form.
5. One word per concept, US spelling in keys and tokens (prose may say colour).

## Open Questions

1. [x] All rows are answered (D71 to D88). The Panel's key is `Inset` (D89); the elevation numbers are provisional until tre's shadows are seen (D90).
2. [x] `Panel` and `Bar` keep their names (D73).
3. [ ] Confirm the framework comparisons against the official docs before any rename is applied (rule 1).
4. [ ] Where the designer-facing docs live: the `tess-dl` language reference and a shell guide ([tess-dl Handover](tess-dl%20Handover.md)).

## Acceptance Criteria

- [ ] Every conflicting name is renamed, or documented with the difference beside it.
- [ ] No reference page for designers uses a term from the jargon table without the plain wording next to it.
- [ ] The framework comparisons are checked against the official docs.

## Links

- [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) · [Block Reference](Block%20Reference.md) · [Style Schema](Style%20Schema.md) · [Common Keys and Conventions](Common%20Keys%20and%20Conventions.md) · [TDL Library API](../42%20Python%20API/TDL%20Library%20API.md)

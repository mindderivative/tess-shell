---
title: Accessibility
aliases: [A11y, V1 Accessibility Note]
type: quality
status: accepted
owner: phil
created: 2026-11-08
updated: 2026-11-17
tags: [quality, accessibility, needs-verification]
---

# Accessibility

> [!NOTE]
> The short accessibility note for v1 that [Development Readiness](../00%20Home/Development%20Readiness.md) listed as design item 5 and [M4 Brief](../00%20Home/M4%20Brief.md) W7 asked for. It collects what is already decided in [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) (roles, names, states) and adds the rules for contrast, reduced motion and the order of announcements that every widget follows. The keyboard half, focus order and keyboard operation, is [M6 Brief](../00%20Home/M6%20Brief.md) and is not written here. The vault session wrote this note from the existing decisions; nothing here was tested with a screen reader. #needs-verification

> [!NOTE]
> **The active-descendant relation is requested (2026-11-17)**
> A focused text field with a list should name the selected row as its active descendant, with no focus move ([TRE-REQ-023 Active Descendant](../80%20Requests/TRE-REQ-023%20Active%20Descendant.md)). Until tre builds it the Launcher announces the selection with polite messages.

> [!NOTE]
> **tre 0.6.9 can announce without a node (2026-11-17)**
> `Window.announce(text, politeness)` exists in `tesserae-engine` 0.6.9 ([TRE-REQ-021 Announce Without a Node](../80%20Requests/TRE-REQ-021%20Announce%20Without%20a%20Node.md)). The 1x1 live Box per module that the shell uses today, and its zero-width-space toggle, can be replaced by it once the shell's engine floor is 0.6.9. A hidden module and a repeated message then announce correctly. Not heard with Orca yet.

## Purpose and Scope

- State the rules every block and module follows so [Standard Modules](../50%20Design%20System/Standard%20Modules.md) does not repeat them.
- Goal G7 of [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) (usable by everyone) is the reason: roles and names for assistive technology, reduced motion, high contrast.
- Out of scope: focus traversal and keyboard operation ([M6 Brief](../00%20Home/M6%20Brief.md)); what tre exposes to AT-SPI beyond the properties named here (tre's `role`, `label`, `live`, `a11y_hidden` and state flags, as read in [Block Reference > Accessibility](../41%20TDL%20Reference/Block%20Reference.md#accessibility)).

## Rules

| # | Rule | Source |
|---|---|---|
| 1 | Every interactive block or module has a role and a name. A block that shows text carries the `Label`, because a text node's words are not exposed alone | [Block Reference > Accessibility](../41%20TDL%20Reference/Block%20Reference.md#accessibility) |
| 2 | A control with only an icon must have a `Label`; the shell warns at load if it has none | [Standard Modules > Button](../50%20Design%20System/Standard%20Modules.md#button) |
| 3 | A decorative image, icon or shape is `A11y_Hidden` unless it has a `Label` | [Block Reference > Accessibility Defaults](../41%20TDL%20Reference/Block%20Reference.md#accessibility-defaults) |
| 4 | State flags (`checked`, `selected`, `expanded`, `pressed`, `value`) are set by the module that has them, never written by the author | [Block Reference > Accessibility](../41%20TDL%20Reference/Block%20Reference.md#accessibility) |
| 5 | `Enabled: false` sets the state `disabled` and the style state `Disabled` and makes the block ignore input | [Block Reference > State](../41%20TDL%20Reference/Block%20Reference.md#state) |
| 6 | `Live` marks a region whose changes are announced: `POLITE` for a status value (a clock, a volume), `ASSERTIVE` only for something the user must act on | [Block Reference > Accessibility](../41%20TDL%20Reference/Block%20Reference.md#accessibility) |
| 7 | An animation honours reduced motion: the state switches at once, with no slide or fade (the surface slide, Expander, Toggle, Marquee text, ProgressBar fill, peek and handles) | [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) G7, [Frame](../40%20Specifications/Surfaces/Frame.md) |
| 8 | Colour is never the only carrier of a state: a selected, checked or disabled widget differs in more than colour | WCAG 2.2, 1.4.1 (stated here as a v1 rule) |
| 9 | Text contrast of at least 4.5 to 1 against its background in the shipped themes, 3 to 1 for large text and for icons and widget edges | WCAG 2.2, 1.4.3 and 1.4.11 (the shipped themes are to be checked, which the code session does with a script in M4) |
| 10 | Under the desktop's high-contrast setting the shell follows it where the portal reports it; this desktop has no such setting, so it is tested headless only | [Portals](../40%20Specifications/Integration/Portals.md), M3 Build Log |
| 11 | A tooltip's text is also the block's description, so it is not the only way to learn what a control does | [Standard Modules > Tooltip](../50%20Design%20System/Standard%20Modules.md#tooltip) |
| 12 | A Popup or menu that opens returns the user to the opener when it closes (keyboard focus is [M6 Brief](../00%20Home/M6%20Brief.md); the pointer-only case needs nothing) | [Popup](../40%20Specifications/Surfaces/Popup.md) |

## What Is Not Decided

1. [x] The shell sets an accessible description, separate from the `Label`, from a tooltip (maintainer, 2026-11-10, as recommended; rule 11).
2. [x] Contrast checking: a script over the shipped themes (rule 9) in M4 and no runtime warning in v1 (maintainer, 2026-11-10, as recommended).
3. [x] A screen-reader test: one pass in M6, when the keyboard exists (maintainer, 2026-11-10, as recommended).
4. [x] High contrast and reduced motion on desktops other than KDE: build with the best estimate, test and tweak later (maintainer, 2026-11-10). The portal path reports both where the desktop does ([Portals](../40%20Specifications/Integration/Portals.md)).

## Disabled Blocks (Decided 2026-11-13)

A disabled block and its descendants take no hover, press, click or tooltip (a cut Marquee text keeps its whole-text tooltip), so assistive technology sees the state `disabled` and the pointer does nothing. The full rule is in [Standard Modules > As Built in M4 and Decided 2026-11-13](../50%20Design%20System/Standard%20Modules.md#as-built-in-m4-and-decided-2026-11-13).

## Acceptance Criteria

- [ ] Every interactive widget of [Standard Modules](../50%20Design%20System/Standard%20Modules.md) sets role, name and state, in a headless test that reads the accessibility tree (`window.simulate`, [Testing Strategy](Testing%20Strategy.md)).
- [ ] An icon-only control without a `Label` warns at load.
- [ ] Reduced motion switches every animated widget at once, in a test that sets the flag.
- [ ] The shipped themes meet rule 9, by a script that reports each pair.

## Links

- [60 Quality](60%20Quality.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [Standard Modules](../50%20Design%20System/Standard%20Modules.md) · [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) · [Portals](../40%20Specifications/Integration/Portals.md) · [M4 Brief](../00%20Home/M4%20Brief.md) · [M6 Brief](../00%20Home/M6%20Brief.md)

---
title: Personas and Use Cases
aliases: [Personas, Use Cases]
type: vision
status: stable
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [vision]
related: ["[[10 Vision]]", "[[Goals and Non-Goals]]", "[[V1 Scope]]", "[[Problem Statement]]"]
depends_on: []
---

# Personas and Use Cases

> [!summary]
> Three personas and eleven use cases. Personas are roles, not named people. Each use case names the surface it needs, so the surface specs under `40 Specifications/Surfaces/` have a reason to exist and a place to be tested.

## Personas

| ID | Persona       | Does                                                                                      | Needs from the tool                                                                                   |
|----|---------------|-------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| P1 | Shell user    | Runs a shell someone else configured, adjusts a colour, a clock format or a module order. | Readable YAML, hot reload, errors with `file:line:column` ([[AGENTS#3. Layering principle]]).  |
| P2 | Shell author  | Designs a whole shell: surfaces, themes, stylesheets, layout per monitor.                 | The full YAML reference, a theme system, per-output surfaces, live preview.                           |
| P3 | Module author | Writes Python that supplies data to a view (battery, media, weather).                     | A small module contract, service APIs, a clear thread rule ([[AGENTS#3. Layering principle]]). |

The maintainer is all three while the design is made. Separate personas keep the YAML surface small enough for P1 and the Python surface stable enough for P3.

## Use Cases

| ID   | Use case                                                                                                                   | Persona | Surface                                                                              | Depends on                                                 |
|------|----------------------------------------------------------------------------------------------------------------------------|---------|--------------------------------------------------------------------------------------|------------------------------------------------------------|
| UC1  | Show a top bar on every monitor that reserves space, so maximised windows stop below it.                                   | P1, P2  | Bar (`LayerWindow`, `exclusive_zone`)                                                | [[TRE-REQ-001 Layer Surface Window]]                    |
| UC2  | Click a tray icon or a bar button and get a menu or flyout that flips at the screen edge and closes on an outside click.   | P1      | Popup (`PopupWindow`)                                                                | [[TRE-REQ-001 Layer Surface Window#Popups]]                    |
| UC3  | Show a volume or brightness change as a brief on-screen display.                                                           | P1      | OSD (`overlay` layer, `input_region=[]`)                                             | [[TRE-REQ-001 Layer Surface Window]]                    |
| UC4  | Open a launcher with a keyboard shortcut and type into a search box.                                                       | P1      | Launcher (`overlay`, `keyboard="exclusive"`) [[ADR-0005 Global Shortcuts]] |                                                            |
| UC5  | Place a clock or system monitor on the desktop and drag it to a new place; the position is saved.                          | P1, P2  | Desktop widget (`bottom` layer, `drag_margin`, `moved`)                              | [[TRE-REQ-001 Layer Surface Window#Margin drag]]                    |
| UC6  | Slide a panel in from the screen edge and slide it out again.                                                              | P2      | Panel (`animate("margin_*")`)                                                        | [[TRE-REQ-001 Layer Surface Window#Animation]]                    |
| UC7  | Draw a rounded frame around the screen edge that lets clicks through to the interior.                                      | P2      | Frame (painter plus reservers, `input_region="auto"`)                                | [[TRE-REQ-001 Layer Surface Window#Use case: screen frame]]                    |
| UC8  | Edit a theme file and see the bar change at once.                                                                          | P1, P2  | All surfaces                                                                         | Shell hot reload ([[ADR-0007 Shell UI Layer]]) |
| UC9  | Add a module that reads the battery and shows it in the bar.                                                               | P3      | Module + bar                                                                         | Python module contract (to write in `42 Python API`)       |
| UC10 | Unplug a monitor, replug it, and have the surfaces come back.                                                              | P1      | All per-output surfaces                                                              | `output_added`, `output_removed` events                    |
| UC11 | Give each monitor its own surface set: the full shell on the main monitor, only a bar on the second, nothing on the third. | P1, P2  | All per-output surfaces                                                              | [[V1 Scope#Multi-monitor]]                    |

## Scenarios

**UC1 and UC10 together.** The shell starts, asks tre for the outputs, and opens one bar per output keyed on the connector name. When an output goes, its bar fires `closed` with reason `"output_removed"` and the shell drops it. When the output returns, an `output_added` event makes the shell open a new bar. A `LayerWindow` is dead after `closed` ([[TRE-REQ-001 Layer Surface Window#Lifecycle and events]]), so the shell never reuses the old object.

**UC2.** A tray button gets a click. The ViewModel builds a `PopupWindow` from the button's rectangle in the bar's coordinates. The compositor places it and `configure` reports the final position. An outside click closes it with reason `"dismissed"`; a click on another window of the same application reaches that window, so the shell listens and closes the menu itself.

## Open Questions

- [ ] Is a notification centre a v1 use case? It depends on the notification-server coexistence decision, which is not made. Placed outside v1 in [[V1 Scope]].
- [x] What does a newly plugged monitor get when the configuration does not name it? A configurable default section ([[V1 Scope#Multi-monitor]]).
- [x] Which persona writes the default shell? P2 (shell author), with the maintainer as the reviewer. Confirmed 2026-10-25 with the Vision.

## Links

- [[10 Vision]] · [[Problem Statement]] · [[Goals and Non-Goals]] · [[V1 Scope]]

---
title: V1 Scope
aliases: [v1, Version 1 Scope, Scope of v1]
type: vision
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [vision]
related: ["[[10 Vision]]", "[[Goals and Non-Goals]]", "[[Personas and Use Cases]]", "[[ADR-0001 Shell Surface Strategy]]"]
depends_on: ["[[ADR-0001 Shell Surface Strategy]]"]
---

# v1 scope

> [!summary]
> Recommendation: v1 is a working bar, popups, OSDs, a launcher and movable desktop widgets, on KDE Plasma 6 Wayland (KWin), with wlroots compositors best effort. Any monitor can host the shell, each configured separately in one configuration, with all, some or none of the surfaces ([[#Multi-monitor]]). It ships a default shell built from eight modules. Notification centre, screen frame and the Tesserae Shell package manager are after v1. Everything here is a recommendation until the maintainer accepts it.

## Target environment

| Item | v1 | Basis |
|---|---|---|
| Desktop | KDE Plasma on Wayland | [[AGENTS#1. What Tesserae Shell is]] |
| Compositor | KWin first. wlroots compositors (sway tested by tre) best effort, not a release gate. | tre tested KWin 6.8.1 and sway 1.12 ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]) |
| Engine | `tesserae-engine` 0.5.8 or later | PyPI, 2026-10-25 |
| Not supported | X11, GNOME, Windows, macOS | `LayerWindow` raises `UnsupportedPlatform`; GNOME decision deferred to testing ([[ADR-0001 Shell Surface Strategy#Open items]]) |

## Surfaces

| Surface | In v1 | Use case | Note |
|---|---|---|---|
| Bar | Yes | UC1, UC11 | On each monitor that lists it; reserves an exclusive zone. |
| Popup (menu, flyout) | Yes | UC2 | `PopupWindow`. Escape dismissal is untested in tre; the spec names it as a gap. |
| OSD | Yes | UC3 | Click-through overlay. |
| Launcher | Yes | UC4 | Needs the global shortcut decision. |
| Desktop widget | Yes | UC5 | Movable, position saved from `moved`. |
| Panel (slide-in) | Yes | UC6 | Margin animation. |
| Wallpaper | Later | none | `background` layer; no use case written. |
| Screen frame | Later | UC7 | The four-reserver plus painter layout was not tested together by tre. |

## Multi-monitor

Maintainer requirement (2026-10-25): any monitor can host the shell, each monitor is configured separately, and each monitor can have all, some or none of the surfaces. Separate configuration does not mean separate files: one configuration holds a section per monitor.

| Rule | Meaning |
|---|---|
| Equal monitors | No monitor is special to the tool. "Primary" is a configuration choice, not a built-in role. |
| Per-monitor surface set | Each monitor lists the surfaces it shows (bar, OSD, widgets and so on), their position and their modules. |
| All, some or none | A monitor may show every surface, a chosen subset, or nothing. A monitor with none gets no `LayerWindow` at all. |
| Hot-plug | Adding a monitor opens its configured surfaces. Removing one closes them, and the shell creates new windows on return because a closed `LayerWindow` is dead ([[TRE-REQ-001 Layer Surface Window#Lifecycle and events]]). |
| Identity | A monitor is matched by the connector name tre reports (`Output.name`, for example `DP-1`) ([[TRE-REQ-001 Layer Surface Window#Outputs]]). |

Every `LayerWindow` is bound to an explicit `Output`, never `output=None` ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]).

Open points for `20 Architecture` and `41 YAML Reference`; none is decided:

- [ ] How a configuration section names a monitor. Connector names can change between ports and docks. Recommended starting point: match by connector name, with an optional match on description, so one profile follows a particular display.
- [ ] What a monitor gets when no section names it. Recommended: a configurable default section, which may itself be "none".
- [ ] Whether surfaces can be shared across monitors in configuration (one definition, several monitors) to avoid repeating a bar. Recommended: yes, by reference, so the definition lives once ([[AGENTS#2. Hard rules]], rule 4).
- [ ] Mirrored outputs and output scale changes (`output_updated`) and how the surface set follows them.
- [ ] Which monitor holds a surface that needs one place only (launcher, OSD): the focused one, the pointer's, or a configured one.

## Modules in the default shell

Proposed eight. Every module is available on any monitor's surfaces. Each becomes a spec under `40 Specifications/Modules/`.

| Module | Needs | Open decision |
|---|---|---|
| Clock | Time source | none |
| Workspaces | KWin virtual desktops | Which protocol or D-Bus API; #needs-verification |
| Tasks (window list) | Foreign-toplevel or KWin interface | Same; #needs-verification |
| System tray | StatusNotifierItem | Who owns `StatusNotifierWatcher` when plasmashell runs: coexist, replace or proxy |
| Audio | PipeWire | none known |
| Network | NetworkManager D-Bus | none known |
| Battery | UPower D-Bus | none known |
| Media | MPRIS D-Bus | none known |

## After v1

| Item | Why it waits |
|---|---|
| Notification centre | Owns the `org.freedesktop.Notifications` name; coexistence with plasmashell is undecided. |
| Screen frame | Depends on an untested surface layout. |
| Wallpaper | No use case yet. |
| Other compositors, X11 | Out of scope until testing ([[Goals and Non-Goals]] N3). |
| Package manager for shared shells | A delivery question for `70 Delivery`. |

## Decisions to take

These need an ADR before the matching spec is `stable`. Recommendation first.

| Decision | Recommendation | Alternative |
|---|---|---|
| Relationship to Tesserae UI | Depend on `tesserae-ui` for the view language, reactivity and themes. | A smaller layer directly on `tre` with a second YAML dialect. |
| Process model | One process owning all surfaces and one event loop. | One process per surface. |
| Plasma coexistence per service | Coexist by default; replace only after a per-service ADR. | Replace plasmashell services wholesale. |
| Global shortcuts | KDE's global-accel service. | XDG portal. |

None of these has an ADR yet. They are the next decisions after Vision.

## Acceptance criteria

- [ ] The maintainer confirms or amends the target environment, surface list, module list and after-v1 list.
- [ ] Multi-monitor rules and open points above are confirmed or amended.
- [ ] Every surface in the table has a matching use case in [[Personas and Use Cases]].
- [ ] Every module row has a decision recorded or a `#needs-verification` tag.
- [ ] Each "Decisions to take" row has a `proposed` ADR.

## Links

- [[10 Vision]] · [[Problem Statement]] · [[Goals and Non-Goals]] · [[Personas and Use Cases]]
- [[ADR-0001 Shell Surface Strategy]] · [[TRE-REQ-001 Layer Surface Window]]

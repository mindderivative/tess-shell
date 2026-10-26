---
title: Goals and Non-Goals
aliases: [Goals, Non-Goals]
type: vision
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [vision]
related: ["[[10 Vision]]", "[[Problem Statement]]", "[[V1 Scope]]", "[[Personas and Use Cases]]"]
depends_on: []
---

# Goals and non-goals

> [!summary]
> Seven goals and eight non-goals. Each goal has a measure that a later spec turns into an acceptance criterion. Goals G1 to G7 and the non-goals are recommendations for the maintainer to confirm; none has been accepted yet.

> [!important] Proposed, not accepted
> The maintainer decides scope ([[AGENTS#2. Hard rules]], rule 5). Targets marked "proposed" are starting values for [[60 Quality]], not commitments.

## Goals

| ID | Goal | Measure (proposed) | Basis |
|---|---|---|---|
| G1 | Build a shell from YAML views and Python modules, with no Rust and no QML. | A bar with clock, workspaces and tray is defined in YAML plus Python only. | [[Problem Statement]] |
| G2 | Change a running shell live. | Saving a view, theme or stylesheet updates the open surfaces without restarting the shell. | Tesserae hot reload |
| G3 | Run beside Plasma without breaking it. | Starting and stopping the shell leaves the Plasma session usable; no shared D-Bus name is taken without an ADR. | [[AGENTS#4. Known constraints and gaps (seed list)]] |
| G4 | Cost nothing when idle. | An idle bar draws no frames and wakes the loop only for its own timers. | tre spike: 1 frame in 10 s, 0.0% CPU ([[TRE-REQ-001 Layer Surface Window#Upstream status (as of 2026-10-23, superseded by Delivered; kept as history)]]) |
| G5 | Stay small in memory. | Per-surface GPU memory budget set in [[60 Quality]]. Reference points from tre 0.5.8: a 1280 x 32 bar 18 MiB, a 200 x 100 window 31 MiB, a 4K full-screen overlay 177 MiB. | [[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]] |
| G6 | Treat every monitor as an equal place for the shell, each configured on its own. | Any monitor can host the shell. Each monitor's surface set is configured separately inside the one configuration, and can be all of the surfaces, some of them, or none. Unplugging a monitor closes its surfaces and replugging restores them. | Maintainer requirement, 2026-10-25; `App.outputs()`, `closed` reason `"output_removed"` |
| G7 | Be usable by everyone. | Keyboard operation, screen-reader names and roles, reduced motion, high contrast and light/dark follow the desktop. | [[60 Quality]] (to write) |

## Non-goals

| ID | Non-goal | Why |
|---|---|---|
| N1 | Replace the compositor, session manager or window manager. | Tesserae Shell supplements the desktop environment. |
| N2 | Be a general application framework. | `tesserae-ui` is the app framework; this project builds shells. |
| N3 | Run on X11, GNOME, Windows or macOS. | `LayerWindow` raises `UnsupportedPlatform` there. The GNOME decision is deferred to the testing phase ([[ADR-0001 Shell Surface Strategy#Open items]]). |
| N4 | Draw frames from Python. | tre owns every frame. |
| N5 | Replicate every Plasma applet. | v1 builds the modules in [[V1 Scope]]. Others are later work. |
| N6 | Ship a package, installer or release process during the design phase. | Delivery is designed in `70 Delivery`, not built. |
| N7 | Sandbox user Python against a hostile author. | User modules run with the user's rights. The security model is written in [[60 Quality]]; this non-goal is a proposal until that note exists. |
| N8 | Define a second view language. | The shell reuses the Tesserae view language and reactivity unless an ADR decides otherwise (decision pending, see [[V1 Scope#Decisions to take]]). |

## Success criteria for the design phase

Coding starts when every row of the checklist in [[AGENTS#12. Design completeness checklist]] is `stable` or deferred by an accepted ADR. This note counts as the Vision row once its goals and non-goals are `stable`.

## Links

- [[10 Vision]] · [[Problem Statement]] · [[Personas and Use Cases]] · [[V1 Scope]]

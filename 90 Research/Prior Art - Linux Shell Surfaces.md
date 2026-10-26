---
title: Prior Art - Linux Shell Surfaces
aliases: [Shell Surface Prior Art, Layer Shell Survey]
type: research
status: draft
owner: phil
created: 2026-10-18
updated: 2026-10-18
tags: [research, integration/wayland, spec/surface, needs-verification]
related: ["[[ADR-0001 Shell Surface Strategy]]"]
depends_on: []
---

# Prior art: how Linux shells create surfaces

> [!summary]
> Every shell surveyed places its bars and panels on `wlr-layer-shell` (`zwlr_layer_shell_v1`). None positions ordinary windows with compositor rules, and none uses KDE's own panel protocol. Toolkits differ in where the layer role is attached: a helper library for GTK, a built-in window type for Quickshell. Compositor-specific code is used for workspace and window state, not for the surface itself.

Feeds [[ADR-0001 Shell Surface Strategy]]. Surveyed 2026-10-18 from project pages; gaps are tagged `#needs-verification`.

## Survey

| Project                                                               | Stack                                | Surface mechanism                                                                                                                                                                                                                                          | Compositors                                                                                                  |
| --------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| [Fabric](https://github.com/Fabric-Development/fabric)                | Python, GTK3                         | `WaylandWindow` calls `GtkLayerShell` ([source](https://raw.githubusercontent.com/Fabric-Development/fabric/main/fabric/widgets/wayland.py)). Parameters: `layer`, `anchor`, `exclusivity` (`none`/`normal`/`auto`), `keyboard_mode`, `margin`, `monitor`. | Docs state "both X11 and Wayland" and native Hyprland support. Showcase shells target Hyprland, i3 and Sway. |
| [Quickshell](https://quickshell.org/)                                 | QML on Qt                            | `PanelWindow` is platform independent. On Wayland it carries a `WlrLayershell` attached object ([docs](https://quickshell.org/docs/v0.2.0/types/Quickshell.Wayland/WlrLayershell/)) using `zwlr_layer_shell_v1`.                                           | Site shows Wayland, Hyprland, Sway, X.Org and PipeWire integrations. Scope of each unconfirmed.              |
| [Astal / AGS](https://github.com/Aylur/astal)                         | Vala/C libraries, GTK, GJS scripting | Layer-shell library unconfirmed. Repo topics include `layer-shell`.                                                                                                                                                                                        | Not stated.                                                                                                  |
| [HyprPanel](https://github.com/Jas-SinghFSU/HyprPanel)                | AGS/Astal, GTK3                      | Inferred from AGS.                                                                                                                                                                                                                                         | Hyprland. Archived 2026-04-27; successor is Wayle.                                                           |
| [Wayle](https://github.com/wayle-rs/wayle)                            | Rust, GTK4, Relm4                    | `gtk4-layer-shell`. Requires a compositor implementing `wlr-layer-shell`.                                                                                                                                                                                  | Compositor modules for Hyprland, Niri, Mango; Sway planned. TOML config.                                     |
| [Caelestia](https://github.com/caelestia-dots/shell)                  | Quickshell, Qt6                      | Quickshell layer-shell path.                                                                                                                                                                                                                               | Requires Hyprland.                                                                                           |
| [DankMaterialShell](https://github.com/AvengeMedia/DankMaterialShell) | Quickshell UI, Go backend and CLI    | Quickshell layer-shell path.                                                                                                                                                                                                                               | Best on niri, Hyprland, Sway, MangoWC, labwc; others with reduced features.                                  |
| [Waybar](https://github.com/Alexays/Waybar)                           | C++, gtkmm3                          | Not confirmed from the project page. Lists wayland-protocols as a build dependency.                                                                                                                                                                        | Sway, River, Hyprland, Niri, Wayfire and others.                                                             |
| [eww](https://github.com/elkowar/eww)                                 | Rust, GTK3                           | Not confirmed from the project page.                                                                                                                                                                                                                       | Not stated.                                                                                                  |

## Toolkit layer-shell libraries

| Library | Toolkit | Supported | Unsupported | Notes |
|---|---|---|---|---|
| [gtk-layer-shell](https://github.com/wmww/gtk-layer-shell) | GTK3 | wlroots-based, KDE Plasma on Wayland, Mir-based | GNOME on Wayland, X11 | Maintenance mode; GTK4 version recommended for new projects. Popups and popovers work. |
| [gtk4-layer-shell](https://github.com/wmww/gtk4-layer-shell) | GTK4 | wlroots-based, Smithay-based (COSMIC), Mir-based, KDE Plasma on Wayland | GNOME on Wayland, X11 | MIT licensed. "If you link against libwayland, you must link libwayland after gtk4-layer-shell." |
| [LayerShellQt](https://invent.kde.org/plasma/layer-shell-qt) | Qt | KDE's component for `wl-layer-shell` | Not stated | KDE project. Users inside Plasma unconfirmed. |

## Patterns

1. **Layer-shell is the common surface protocol.** Compositor-specific code (Hyprland, Niri, Sway) covers workspaces, windows and layouts. The surface strategy and the state-integration strategy can be decided separately.
2. **The layer role is attached at the toolkit boundary.** GTK uses a helper library, Qt has `LayerShellQt` and Quickshell's own type. Fabric exposes the result to Python as constructor parameters. This is the shape of ADR-0001 Option A.
3. **Python sets properties; the toolkit draws.** Fabric follows the same split as the tre rule that Rust owns every frame.
4. **Platform-neutral wrapper.** Quickshell's `PanelWindow` works on Wayland and X11, with layer-shell properties on an attached object, and its docs recommend it over `WlrLayershell`. A tre window type could do the same.
5. **Popups need their own design.** gtk-layer-shell routes GTK popups through the protocol. Quickshell's `PopupWindow` positions with `anchor.window` and `anchor.rect`; the protocol mechanism was not stated on its page. Menus, tray menus and flyouts depend on this.
6. **No precedent for KWin rules or the Plasma shell protocol** among these projects.

## Unverified

- [ ] How gtk-layer-shell and Quickshell attach a layer role to a toolkit surface. Read the source; this informs Option B.
- [ ] Astal, Waybar and eww layer-shell usage.
- [ ] Whether Plasma's own components use LayerShellQt.
- [ ] The protocol mechanism behind Quickshell's `PopupWindow`.
- [ ] Quickshell exclusion-zone semantics. The `PanelWindow` page says `exclusiveZone` takes effect with 1 or 3 anchors, which matches the protocol. The `WlrLayershell` page does not cover exclusion.

## Links

- [[ADR-0001 Shell Surface Strategy]]
- [wlr-layer-shell-unstable-v1](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)
- [Quickshell PanelWindow](https://quickshell.org/docs/v0.2.0/types/Quickshell/PanelWindow/)

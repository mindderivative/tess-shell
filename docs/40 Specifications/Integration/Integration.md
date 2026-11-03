---
title: Integration
aliases: [Integration Specs]
type: moc
status: draft
owner: phil
created: 2026-10-28
updated: 2026-11-02
tags: [moc, spec/integration]
---

# Integration

How the shell talks to the desktop around it: the compositor, Plasma and the system services. Each note names the protocol or D-Bus interface, the thread, and what happens when it is missing.

| Note | Purpose | Status |
|---|---|---|
| [Wayland Protocols](Wayland%20Protocols.md) | The protocols the shell needs, what KWin 6.8.1 offers, and how the shell reaches protocols tre does not expose | draft |
| [KWin Integration](KWin%20Integration.md) | The KWin script, the window rule, the KWin D-Bus interfaces, the version check | draft |
| [Plasma Coexistence](Plasma%20Coexistence.md) | Who owns each shared D-Bus name today, the mode per service, start order with plasmashell | draft |
| [D-Bus Service Layer](D-Bus%20Service%20Layer.md) | The shared service thread, rules for calls, listening and missing services, the catalogue of services the modules read | draft |
| [Global Shortcuts](Global%20Shortcuts.md) | The `tesserae-shell` component with KDE's global-accel service, action names, key flow, fallbacks | draft |
| [Portals](Portals.md) | The Settings portal (colour scheme, accent, contrast, reduced motion), the portal app id, the GlobalShortcuts portal as fallback | draft |

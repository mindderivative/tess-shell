---
title: Modules
aliases: [Module Specs]
type: moc
status: draft
owner: phil
created: 2026-10-26
updated: 2026-11-13
tags: [moc, spec/module]
---

# Modules

Specs for the shell's modules. A module's structure is in [Module File](../../41%20TDL%20Reference/Module%20File.md) and [Module Contract](../../42%20Python%20API/Module%20Contract.md); these notes cover one module each, with its behaviour, params, thread, failure modes and acceptance criteria.

| Note                                    | Module                       | Status |
|-----------------------------------------|------------------------------|--------|
| [Clock Module](Clock%20Module.md) | Time; the simplest v1 module | review |
| [Battery Module](Battery%20Module.md) | Battery charge from UPower; the first service module | draft |
| [Workspaces Module](Workspaces%20Module.md) | KWin virtual desktops, switch on click | draft |
| [Network Module](Network%20Module.md) | NetworkManager: connection kind, state, Wi-Fi strength; read-only | accepted |
| [Media Module](Media%20Module.md) | MPRIS: the active player, controls, artwork, position and seek | accepted |
| [Audio Module](Audio%20Module.md) | The default output's volume and mute, an outputs menu; the shell's own sound-server client | accepted |
| [Tray Module](Tray%20Module.md) | StatusNotifierItem host: items, clicks, the menu drawn from dbusmenu, the icon theme lookup | accepted |
| [Tasks Module](Tasks%20Module.md) | The open windows from the shell's KWin script; activate, minimise, close | accepted |
| [Applications Module](Applications%20Module.md) | The launcher: desktop entries, search, a detached start; the shared application index | accepted |

Specified, not built: Tasks (M5g, [M5 Brief](../../00%20Home/M5%20Brief.md)) ([V1 Scope > Modules in the default shell](../../10%20Vision/V1%20Scope.md#modules-in-the-default-shell)); the launcher (Applications), which moved to M6 ([M6 Brief](../../00%20Home/M6%20Brief.md)). The standard modules in [Building Blocks](../../50%20Design%20System/Building%20Blocks.md) (Label, Button, Slider and the rest) are built in M4 ([M4 Brief](../../00%20Home/M4%20Brief.md)) and specified in [Standard Modules](../../50%20Design%20System/Standard%20Modules.md) (draft, 2026-11-08). Clock, Battery and Workspaces are the shell's modules written so far; Battery and Workspaces are built in M5b with the service layer they read.

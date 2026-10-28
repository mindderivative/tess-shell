---
title: Risk Register
aliases: [Risks, Technical Debt]
type: moc
status: draft
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [moc, risk]
related: ["[[Home]]", "[[Roadmap]]", "[[Open Questions]]"]
depends_on: []
---

# Risk register

> [!summary]
> Risks and technical debt gathered from the `> [!danger]` and risk callouts across the vault, with where each is discussed and what is planned. A new risk gets a `> [!danger]` callout in its own note and a row here ([[AGENTS#2. Hard rules]] rule 6). The first version was assembled on 2026-10-27 from the notes as they stand; no row has a probability or impact score, because none has been measured.

| ID | Risk | Source | Mitigation, and its state |
|---|---|---|---|
| R-01 | One hung Python callback blocks every surface (single process, one loop) | [[ADR-0003 Process Model]], [[Process Model and Threading]] | Conventions, the send entry point, thread helpers, a watchdog and a supervisor. None is built; the watchdog and crash recovery belong to `60 Quality` (not written) |
| R-02 | Two input sources: tre dialogs and layer surfaces handle seat, focus and clipboard separately, so behaviour can differ | [[TRE-REQ-001 Layer Surface Window]] | Test both paths for clicks, focus and clipboard. Not yet tested together |
| R-03 | The shell's own UI layer grows without limit | [[ADR-0006 Shell Independent of Tesserae UI]], [[ADR-0007 Shell UI Layer]] | Keep it to what bars, popups, OSDs and widgets need ([[Building Blocks]], [[V1 Widgets]]) |
| R-04 | The expression language grows into a programming language that runs from a configuration file | [[ADR-0008 Tesserae Expression Language]] | Keep it to values and structure with a sandbox; owned by the TEL project |
| R-05 | Two front-ends (YAML and Python) must give the same result, so every feature is built and tested twice | [[ADR-0007 Shell UI Layer]], [[Python Builder]] | A parity test per feature; not yet designed |
| R-06 | The shell edits user files (it injects the UID), so a bug can damage a file the user wrote | [[ADR-0007 Shell UI Layer]] | Back up before the first write; the rebuild-from-UIDs rule helps recovery ([[Settings File]]) |
| R-07 | A `top` surface and a Plasma panel share KWin's Above layer, so a Bar may not win | [[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]], [[ADR-0012 Keeping the Shell Above Plasma Panels]] | Do not rely on stacking in v1; opt-in KWin rule; test on KWin 6.8.1 |
| R-08 | A fullscreen window does not cover `overlay` surfaces; the shell needs a KWin script to detect fullscreen | [[ADR-0012 Keeping the Shell Above Plasma Panels]] | A small KWin script reports fullscreen to the shell; install and enable step is a delivery item; KWin scripting API may change |
| R-09 | A KWin window rule changes the user's desktop settings | [[ADR-0012 Keeping the Shell Above Plasma Panels]] | Opt-in, shown to the user, written as one group, removable; never automatic |
| R-10 | A seam between separate surfaces that move together (up to one frame) | [[Surface Types#Risks]], [[Frame#Hosted melding (decided 2026-10-27)]] | Hosted melding draws a melded entry in the Frame's surface; measure the remaining cases in testing |
| R-11 | Placing a Panel against another surface is computed by the shell, and can lag the target by up to a frame | [[Panel#Attachment geometry (decided 2026-10-27)]] | Recompute on every target move; measure |
| R-12 | Coupling to tre: the shell needs 0.5.9 or later, and tre's API can change | [[AGENTS#1. What Tesserae Shell is]], [[80 Engine Requests]] | Check live docs before citing; engine requests for gaps; version check at start |
| R-13 | Third-party dependencies (`dbus-fast`, `loguru`, `jsonschema`, TEL) go unmaintained or break on a new Python | [[ADR-0009 D-Bus Client Library]], [[Logging with Loguru]], [[JSON Schema and Editor Support]] | Pin and test per release; `jsonschema` is lazy and cached; `jeepney` is the D-Bus fallback |
| R-14 | Python 3.14 as the minimum narrows where the shell installs | [[ADR-0007 Shell UI Layer#UIDs and the registry (2026-10-25)]] | Accepted by the maintainer (2026-10-25) |
| R-15 | The Frame's input region can reach the 256-rectangle cap, and a 4K Frame with many joins is untested | [[Frame#Integration]] | tre coarsens the bands; test after the v1 build |
| R-16 | Shadow margins add buffer memory to every surface with a shadow, and shadows must stay out of the hit shape | [[ADR-0010 Surface Shadows]] | Compute the margin from the shadow; test the hit shape; measure at Frame size |
| R-17 | The design is KWin-first; protocol and layer behaviour on other compositors is untested | [[ADR-0001 Shell Surface Strategy]], [[V1 Scope]] | Deferred to the testing phase; other compositors are not v1 |
| R-18 | A corrupt or moved registry loses identities | [[Settings File]], [[ADR-0007 Shell UI Layer#UIDs and the registry (2026-10-25)]] | Rebuild each record from the UID in its file, with a warning; the rules for the rebuilt record are open |
| R-19 | User Python runs in the shell's process with the user's rights, so a bad module can read files or hang the shell | [[Module Contract]] | The security model is not written (`60 Quality`); keep modules to the documented context; whether to sandbox is not decided |

## Links

- [[Home]] · [[Roadmap]] · [[Open Questions]] · [[ADR-0003 Process Model]]

---
title: TRE-REQ-025 Third-Party Licence Notices in the Wheel
aliases: [TRE-REQ-025, THIRD_PARTY_NOTICES, font licences in the wheel, engine licence notices]
type: engine-request
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-19
tags: [engine-request, delivery, needs-verification]
---

# TRE-REQ-025: Ship the Licence Texts and Notices of What the Engine Bundles

> [!NOTE]
> **The maintainer reviewed it and passed it to tre himself; on 2026-11-19 he said tre is building it for 0.6.10.**
> The `tesserae-engine` wheel embeds fonts and compiled Rust crates under licences that ask for their text or copyright notice to travel with them, and its `dist-info/licenses` holds only the project's own MIT `LICENSE`. Tesserae Shell had to assemble a `NOTICE` for what the engine bundles from outside the wheel (M7e, `tess-shell` PR #58). The request: the engine ships the notices itself. Drafted on 2026-11-17 from the code session's report of the M7e work and offered to the maintainer to carry; not sent to tre.

## Shell Need

A package that redistributes the engine in its own wheel or application, as the shell does, must carry the licence notices of what the engine contains. Doing that from outside means reading the engine's build, with the risk of being wrong when the engine changes; the engine is the one that knows what it bundles.

## What Tre Ships Today

| Fact | Source |
|---|---|
| `tesserae-engine`'s PyPI licence expression is `MIT` | PyPI's JSON page for 0.6.9, read 2026-11-17 |
| The installed 0.6.7 wheel's `dist-info/licenses` holds one file, `LICENSE`, and a `sboms` folder exists beside it | Read in the shell's venv, 2026-11-17 (0.6.7, not 0.6.9) |
| The engine bundles the fonts Roboto Regular and Medium, Noto Sans Arabic and Hack Nerd Font Mono, which the code session confirmed are byte-identical inside the installed `_core` library; it also embeds 495 Rust crates and five shared libraries added by `auditwheel` | The code session's report on `tess-shell` PR #58, 2026-11-17. #needs-verification: the vault has not repeated the check |
| The code session's reading of the licences: the fonts are under licences such as the SIL Open Font Licence 1.1 and Apache-2.0, which ask for the licence text to accompany the font; the crates' copyright notices are not shipped as a third-party file | The same report |

## Proposed Change

tre implements this: the wheel carries (1) the licence text of each bundled font next to a file that names it; (2) a third-party notices file generated from the Rust dependency tree (a tool such as `cargo about` or `cargo deny`; tre's choice) that lists every crate with its licence and copyright; (3) the licences of the shared libraries `auditwheel` adds, taken from their upstream; (4) a licence expression in the package metadata that matches what is shipped. The files go under `dist-info/licenses` so that tools which read the standard location, and the shell's own `NOTICE` check, find them.

## Alternatives

None that is better: a consumer can maintain its own notice, as the shell does, and then has to re-verify it at every engine release.

## If Declined

The shell keeps a hand-built `NOTICE` section for the engine and re-reads it whenever the engine range moves (the shell's test forces the range to match).

## Acceptance

An installed wheel's `dist-info/licenses` lists the licence text of every bundled font and a notices file naming every bundled crate and shared library with its licence, and the package's licence expression covers them; the shell's `NOTICE` check can then read it instead of restating it.

## Links

[M7 Brief](../00%20Home/M7%20Brief.md) · [Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md) · [80 Requests](80%20Requests.md)

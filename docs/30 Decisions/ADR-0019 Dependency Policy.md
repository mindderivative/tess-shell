---
title: ADR-0019 Dependency Policy
aliases: [ADR-0019, Build or Buy, Third-Party Policy]
type: adr
status: accepted
owner: phil
created: 2026-11-03
updated: 2026-11-03
tags: [adr, process, dependencies]
---

# ADR-0019: Dependency Policy

> [!NOTE]
> A third-party library is used when building the same thing ourselves would need a completely separate project, such as Pillow for image decoding. Everything smaller is a few lines of our own code. Stated by the maintainer on 2026-11-03 and recorded as the rule for every Tesserae project.

## Context

While `tess-utils` was being shaped, the maintainer said (2026-11-03): "I do not think we should 3rd party everything, just the things that would be to much such as Pillow to build ourselves. I see it as; if it needs a completely separate project to make then we 3rd party it, otherwise we write a few lines of code to perform the specific function we need." The "100+" packages mentioned earlier were an example of where a project could drift over a long time, not a present count (the shell's planned dependencies resolve to 11 packages on 2026-11-03).

## Options

### Option A — Third-Party Only for What Would Be a Separate Project (Chosen)

- **For:** few dependencies, small installs, fewer upgrade breaks, fewer licences to carry; small code we own is easy to fit to the need.
- **Against:** we maintain the small helpers we write.

### Option B — Third-Party by Default

- **Against:** the dependency list grows without limit, each package brings its own breaking changes and transitive packages. Rejected.

## Decision

Accepted 2026-11-03 by the maintainer in chat, in the words quoted in Context: **Option A**.

How to apply it: ask of each dependency "would writing this ourselves be a project of its own?" If yes (an image codec, a D-Bus protocol client, a JSON Schema validator, a colour-science library), use a library. If no (parsing a colour string, expanding a four-sided value, watching a few directories), write the lines.

## Consequences

- The Tesserae libraries are held to it: `tess_el`, `tess_dl` and `tess_utils` have few or no dependencies; `tess_utils` maps third-party libraries only for work that would be a project of its own, as it does for Pillow ([ADR-0017 Shared Utilities](ADR-0017%20Shared%20Utilities.md)).
- Each dependency in [Shell Package Layout > Dependencies](../20%20Architecture/Shell%20Package%20Layout.md#dependencies) has a reason. The 2026-11-03 reading:

| Dependency | Would building it be its own project? | Verdict |
|---|---|---|
| `tesserae-engine`, `tesserae-el`, `tesserae-dl` | They are the Tesserae projects | Keep |
| `Pillow` | Yes: image codecs | Keep, reached only through `tess_utils` |
| `dbus-fast` | Yes: the D-Bus wire protocol ([ADR-0009 D-Bus Client Library](ADR-0009%20D-Bus%20Client%20Library.md)) | Keep |
| `inotify_simple` | No: a thin wrapper, chosen already for that reason ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md)) | Keep |
| `loguru` | Arguable: [Logging](../40%20Specifications/Runtime/Logging.md) chose it for its sinks and speed; the standard `logging` module is the alternative | Keep; the maintainer may revisit |
| `jsonschema` | A validator of a large specification would be its own project, but the shell checks in code and needs none | Dropped at run time ([ADR-0020 Validation in Code](ADR-0020%20Validation%20in%20Code.md), 2026-11-03) |
| `pyyaml`, `watchfiles`, `materialyoucolor` (Tesserae UI) | YAML, a native watcher, and colour science are each large | Tesserae UI's to review against this rule |

- A new dependency needs a sentence saying why building it would be a project of its own.

## Links

- [ADR-0017 Shared Utilities](ADR-0017%20Shared%20Utilities.md) · [ADR-0018 One Entry Form in tre](ADR-0018%20One%20Entry%20Form%20in%20tre.md) · [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) · [tess-utils Brief](../00%20Home/tess-utils%20Brief.md) · [30 Decisions](30%20Decisions.md)

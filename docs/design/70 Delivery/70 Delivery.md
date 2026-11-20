---
title: 70 Delivery
type: moc
status: accepted
owner: phil
created: 2026-11-13
updated: 2026-11-19
tags: [moc, delivery]
---

# 70 Delivery

> [!NOTE]
> How the shell reaches a machine and starts with the session. No release is made from here: publishing a version is the maintainer's ([Tesserae Shell Directive](../00%20Home/Tesserae%20Shell%20Directive.md)).

| Note | Covers |
|---|---|
| [Packaging and Session Start](Packaging%20and%20Session%20Start.md) | The wheel, what it depends on, the desktop file, the systemd user unit, the `install-session` command, upgrades |
| [Version Policy and Migration](Version%20Policy%20and%20Migration.md) | What each version number promises, deprecation, the `Shell:` pin, and the `tesserae-shell migrate` command; M7d |
| [Docs Publishing](Docs%20Publishing.md) | How a vault commit reaches the design site with no manual step: the hook, `tess-docs-publish`, the pull request, auto-merge |
| [Docs Site Plan](Docs%20Site%20Plan.md) | The public site rebuilt like tre's and Tesserae UI's, with the vault export as its Design section |

The user guide is written in the `tess-shell` repository under `guide/` (task T-054, [Task Owners](../00%20Home/Task%20Owners.md)).

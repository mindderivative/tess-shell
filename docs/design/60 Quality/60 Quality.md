---
title: 60 Quality
aliases: [Quality, Quality Index]
type: moc
status: draft
owner: phil
created: 2026-11-02
updated: 2026-11-17
tags: [moc, quality]
---

# 60 Quality

Budgets, accessibility, testing, security and crash recovery ([Vault Reference > Design completeness checklist](../00%20Home/Vault%20Reference.md#design-completeness-checklist)). Many specs say "set in 60 Quality"; this folder is where those numbers live.

| Note | Purpose | Status |
|---|---|---|
| [Performance Budgets](Performance%20Budgets.md) | The budget ledger: which numbers exist, which are measured, which are proposed, which conflict, which are missing | draft |
| [Testing Strategy](Testing%20Strategy.md) | Test layers, markers, what runs without a display, what needs a compositor, the manual checklist | draft |
| [Accessibility](Accessibility.md) | The v1 accessibility rules every widget follows: roles, names, states, contrast, reduced motion | draft |
| [Security Model](Security%20Model.md) | Posture A for user Python (trusted code), the controls the shell adds, posture B and C; M7a | draft |
| [Module Process Test](Module%20Process%20Test.md) | The performance test of a process per module against in process, and the decision rule; M7a2 | draft |
| [Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md) | Hang detection, the systemd watchdog, what survives a restart, the crash record, safe start; M7b | draft |

The security model ([Risk Register](../00%20Home/Risk%20Register.md) R-19) and crash recovery (R-01) are written as drafts (2026-11-17) and wait for the maintainer's acceptance.

## Links

- [Home](../00%20Home/Home.md) · [Roadmap](../00%20Home/Roadmap.md) · [Risk Register](../00%20Home/Risk%20Register.md)

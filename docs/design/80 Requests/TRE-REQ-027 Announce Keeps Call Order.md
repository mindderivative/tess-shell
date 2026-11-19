---
title: TRE-REQ-027 Announce Keeps Call Order
aliases: [TRE-REQ-027, Window.announce order, announce burst scrambled]
type: engine-request
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-19
tags: [engine-request, quality/accessibility, bug, needs-verification]
---

# TRE-REQ-027: `Window.announce` Must Emit in the Order of the Calls

> [!NOTE]
> Several `Window.announce` calls made in one loop turn reach a screen reader in a scrambled order. A user can hear "Network connected" before "Network disconnected", or a Launcher row before an earlier one, whenever two announcements of one window fall in one update. This is a bug in the behaviour built for [TRE-REQ-021 Announce Without a Node](TRE-REQ-021%20Announce%20Without%20a%20Node.md) (tre 0.6.9), found by `tess-shell` CI. The code session offered it as a candidate request (it called it 025; that number was taken by [TRE-REQ-025 Third-Party Licence Notices in the Wheel](TRE-REQ-025%20Third-Party%20Licence%20Notices%20in%20the%20Wheel.md)). Drafted on 2026-11-17. On 2026-11-19 the maintainer had the vault session inform tre by message and said he will confirm it with tre himself.

## Shell Need

Announcements are state changes read in order. Two events a frame apart (a network dropping and returning, a selection moving twice) must be heard in the order they happened. The shell can hand tre several announcements in one loop turn, under load or when two events fall within a frame.

## What Tre Does Today

By the code session's measurement, on `tesserae-engine` 0.6.9, a private sway and a private AT-SPI bus with the real `at-spi2-registryd` (the vault has not run it):

| Observation | Result |
|---|---|
| Six `announce` calls A1 to A6 in one `call_soon` | Heard as A1 A4 A6 A2 A3 A5, then A4 A5 A6 A1 A2 A3, then A3 A1 A5 A2 A6 A4: three runs, three scrambled orders |
| Six calls one loop turn apart (20 ms) | In order |
| Where order is lost | Only inside one batch; it looks like an unordered collection (a hash map or a set) drained per tree update |

How the code session met it: the M7g kit test failed once on CI with the Network pair swapped; it passed 10 of 10 locally under 48 busy loops because the two events were then far enough apart. The evidence is a runnable probe the code session wrote (`/tmp/m7/tre-announce-order-probe.py`, a throwaway test that needs the shell's `tests/atspi_env.py` and `tests/sway.py`); it was not present in `/tmp/m7/` when the vault looked, so ask the code session for a copy.

## Proposed Change

tre implements this: `Window.announce` emits in the order of the calls, for one window, and across the windows of one `App` if that is possible. A list drained in order does it. Batching and deduplication are not asked for.

## Alternatives

None needed.

## If Declined

The shell hands one announcement per loop turn to the window, through a per-window queue drained by a timer, so a burst reaches tre one turn apart. It costs a little latency for a burst and one more timer ([Shell-side mitigation](#shell-side-mitigation)).

## Shell-side mitigation

Not built. The code session would not build it if tre fixes this soon. Until then the M7g kit test asserts that every promised text is announced but not the order across events, because the sandbox drives events close together; on the real run the person waits for Orca between events, so the checklist's order holds.

## Acceptance

A test that calls `announce` six times in one loop turn and reads six AT-SPI `Announcement` signals in call order, three runs in a row; the same across two windows of one `App` if that is supported.

## Built (tre's report, 2026-11-19; not run in the vault)

Fixed on tre's local branch `fix/req-027` (`952851f1`, off main after PR #307); not pushed, merged or released; it ships in 0.6.10.

- **Reproduced first** on 0.6.9: six calls in one loop turn were heard as A4 A3 A2 A6 A1 A5, A2 A3 A1 A6 A4 A5, A1 A4 A5 A2 A3 A6 in three runs on a private AT-SPI bus.
- **Cause:** one layer lower than tre's queue. tre put every queued message into one accessibility update in call order, but AccessKit keeps the nodes one update adds in a hash set (`accesskit_consumer` `added_node_ids`, `accesskit_atspi_common` `added_nodes`), so the signals leave in hash order. Calls one loop turn apart are separate updates, hence in order.
- **Fix:** each update carries only the oldest waiting message, and the window keeps drawing frames until the queue is empty. Six messages are six frames (about 100 ms at 60 Hz). No batching or deduplication; the queue cap of 16 (newest kept) stays.
- **After:** A1 to A6 in order in all three runs. Five Rust unit tests, a live AT-SPI regression test, `cargo test --workspace` 855 passed, full pytest in a private sway 1588 passed, 13 skipped, 0 failed.
- **Limit:** ordering is per window. Each window has its own tree and updates, so order across the windows of one `App` is not guaranteed; announce from one window if that is needed.
- **Not verified:** Orca, NVDA, VoiceOver, KWin.

The shell-side queue is not needed. A burst of six now takes about 100 ms to be heard, which is a latency the shell should know about.

## Links

[TRE-REQ-021 Announce Without a Node](TRE-REQ-021%20Announce%20Without%20a%20Node.md) · [Accessibility](../60%20Quality/Accessibility.md) · [Hand Checks](../00%20Home/Hand%20Checks.md) · [M7 Brief](../00%20Home/M7%20Brief.md) · [80 Requests](80%20Requests.md)

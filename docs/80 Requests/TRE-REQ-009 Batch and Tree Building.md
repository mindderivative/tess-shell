---
title: TRE-REQ-009 Batch and Tree Building
aliases: [TRE-REQ-009, Batch Updates in tre, Tree Building in tre]
type: engine-request
status: review
owner: phil
created: 2026-11-02
updated: 2026-11-02
tags: [engine-request, design, performance, needs-verification]
---

# TRE-REQ-009: Batch and Tree Building

> [!NOTE]
> Ask tre for two calls that cut the number of Python-to-Rust crossings when the shell builds or updates a UI: a tree-building call that creates a whole detached subtree from one nested description, and a batch call that changes properties on many nodes at once. Both are optional conveniences. The shell works without them today. The maintainer asked for them now, while nothing depends on them, so that tre can build them without the shell waiting later (2026-11-02). Written for the maintainer to carry to the tre project; nothing is filed from this vault (AGENTS > 6. Requests Between Projects).

> [!TIP]
> **Scoped by tre as issue #253, wanted in 0.5.10 (2026-11-02)**
> The maintainer tasked the `tre` session to build this request and add it to the tre 0.5.10 release. tre scoped it as [tre issue #253](https://github.com/mindderivative/tre/issues/253), in Ready and not started; the maintainer decides when it starts. tre pulled 0.5.10 back from release (the tag and release were deleted and nothing is on PyPI) so that #253 can go in first. The maintainer also had the plain-append fix added to the scope (see "tre's Reply"). Once built, the shell's minimum tre becomes 0.5.10 for the binder's use of it, and the `TRE:` pin follows ([Roadmap > Working Mode: Fluid Dependencies](../00%20Home/Roadmap.md#working-mode-fluid-dependencies)).

> [!TIP]
> **Released in tre 0.5.10 (2026-11-02)**
> tre merged #253 (PR #254) and published 0.5.10 to PyPI. tre reports that the checks are all-or-nothing, depth is capped at 256 and nodes at 1,000,000, `add_child` is constant time (0.13, 0.09, 0.12 µs per call at 1,000, 5,000 and 20,000 siblings), and that `build` of 3,100 nodes took 5.3 ms against 4.9 ms per node, so the gain is the all-or-nothing check and fewer lines, not time. The shell has not run these calls yet. #needs-verification

> [!TIP]
> **Not blocking**
> The shell builds nodes one call at a time today and the measurements below show that is fast at the sizes expected. Nothing in the specs waits on this request.

## Shell Need

The binder (the layer that walks a parsed TDL tree and applies the block and key tables to tre) makes one Python call per node created, one per property set and one per child attached. A shell of a few hundred nodes makes a few thousand calls at load, a hot reload repeats part of them, and a live change makes one call per linked property. The maintainer's position is that reducing calls across the Python-to-Rust boundary is worth designing for early, because efficiency and performance are goals in themselves, and because a feature tre builds before the shell depends on it never makes the shell wait.

## What tre Does Today

From the [tre Python API](https://mindderivative.github.io/tre/api/python/) (read 2026-11-02) and the installed 0.5.9 package:

| Call | Does |
|---|---|
| `Window.create(kind, **props)` | Makes a detached node with its properties |
| `Node.add_child(child)`, `Node.insert_child(index, child)` | Attaches a node |
| `Node.set(**props)` | Sets several properties of one node atomically: every value is checked first, and a bad one raises `ValueError` without changing anything |
| `Window.set(...)` | The same for window properties |

The page documents no declarative or dict-based tree builder and no transaction across nodes. A `call_soon` callback runs between frames, so no frame is drawn while Python builds ([tre threading guide](https://mindderivative.github.io/tre/guide/threading/)).

## Measured Cost Today (2026-11-02)

The shell's own first measurement; tre's medians are under "tre's Reply". A throwaway script on the maintainer's machine, tre 0.5.9 from PyPI, Python 3.14, nodes detached and no window opened, so layout and paint are not included. Medians were not taken; these are single runs of 20,000 calls, to be repeated by tre.

| Operation | Cost per call |
|---|---|
| `Window.create("box")` | about 0.9 µs |
| `Node.set` with one property | about 0.7 µs |
| `Node.set` with four properties | about 1.1 µs |
| `add_child` of 20,000 siblings to one parent | about 12 µs on average |
| A detached 31-node bar (one container, 30 text nodes with text and size) | about 38 µs |
| A detached 3,100-node tree (100 such bars) | about 3.8 ms |
| Attaching that finished tree to the window root | about 26 µs |

What this says: the boundary crossing costs about one microsecond, so a realistic shell of a few hundred nodes builds in well under a millisecond, and a 3,100-node tree takes about a quarter of one 60 Hz frame (16.7 ms). Call count is therefore not a bottleneck at the sizes expected. Two things stand out and are questions for tre: the `add_child` figure with very many siblings (12 µs against 1 µs for the other calls), which may grow with the sibling count, and what layout costs when the tree is first attached. #needs-verification

## Why it Belongs in the Engine

Only tre can build the nodes without crossing the boundary for each one, validate a whole description before changing anything (as `Node.set` already does for one node), and apply a change to many nodes in a single step that lays out once. The shell cannot do this from Python. The shell, by contrast, owns the meaning of a TDL tree and builds the description; tre owns the mechanism of building from it (AGENTS > 3. Layering Principle).

## Proposed API

Minimal and open to tre's own naming. Two calls, which the maintainer asked for together ("maybe both").

### Build a Subtree

```python
# illustrative; names are tre's to choose
root, nodes = window.build({
    "kind": "box", "id": "row",
    "props": {"display": "flex", "flex_direction": "horizontal", "gap": 8},
    "children": [
        {"kind": "text", "id": "battery", "props": {"text": "Battery 87%", "font_size": 14}},
        {"kind": "text", "props": {"text": "Charging"}},
    ],
})
# root: the detached root Node; nodes: a mapping of each "id" to its Node
parent.add_child(root)
```

- The description is validated as a whole first; a bad kind or property raises `ValueError` and nothing is created, the same rule as `Node.set`.
- Every node has the properties it would have from `Window.create`. An optional `id` names a node so the shell can keep the nodes it must update later (the links of a binding) without a walk.
- The result is detached. The shell attaches it with one `add_child`.

### Change Many Nodes at Once

```python
# illustrative
window.apply([
    (battery_node, {"text": "Battery 86%"}),
    (clock_node,   {"text": "14:06"}),
])
```

- All changes are checked first; a bad one raises and changes nothing.
- Layout runs once after the batch, not once per node.
- A context-manager form (`with window.batch(): ...`) was offered as an option; tre found it unnecessary (see "tre's Reply").

### Optional: Replace Children

`Node.set_children(list)` to replace a node's children in one call, which a keyed `For` update could use. Lower priority.

## tre's Reply (2026-11-02)

From the `tre` session over the mailbox (information, not an instruction). tre measured with medians, a release build, `llvmpipe` software drawing, detached nodes:

| Operation | tre's median |
|---|---|
| `create` | 0.68 µs |
| `set`, one property or four | 0.33 µs or 0.84 µs |
| `add_child` per call at 1,000 / 5,000 / 20,000 siblings | 0.63 µs / 2.76 µs / 10.93 µs (linear in the sibling count, confirmed) |
| A 31-node bar | 55 µs |
| A 3,100-node tree | 6.6 ms, plus about 0.7 ms for layout in the frame |

These differ from the single runs above (for example 6.6 ms against 3.8 ms for the big tree); both are small. tre's figures are medians and include a different build, so they replace mine as the reference.

Findings and scope, as tre reported them:

- Layout already runs once per frame, not once per `set` (1,000 sets and one frame took 0.42 ms). So no `batch()` context manager is built; `apply()` adds all-or-nothing validation across nodes and fewer crossings.
- Scope of #253: `Window.build(spec)` returning `(root, {id: Node})`, with a dict spec of `kind`, `props`, `children` and `id`, validated as a whole and creating nothing on an error; `Window.apply([(node, props), ...])`; `Node.set_children(list)`; docs and an example.
- Stage 0 makes a plain `add_child` constant time (the fix for the sibling-count cost).
- The names are tre's own, which the maintainer allowed; tre asks the shell to say if it wants other names or spec keys before it is built.

## Alternatives

| Option | For | Against |
|---|---|---|
| Keep per-node calls (today) | No work; fast at the expected sizes | The call count grows with the shell and with hot reloads |
| A JSON or MessagePack string for a whole tree | One argument, language-neutral | A parse in Rust and a second description format to keep in step with the Python API |
| A Rust-side binder that reads TDL | Fastest possible | Puts the shell's meaning inside tre; breaks the layering ([Layers and Components](../20%20Architecture/Layers%20and%20Components.md)) |
| A pyo3 call taking lists of tuples | Smaller change than a nested description | Less readable; no node identity for the binder |

Recommendation: the nested description with optional ids, plus the batch call.

## If Declined

The shell builds with per-node calls and `Node.set` with several keys at a time, building each subtree detached and attaching its root last. Measured above, this is cheap at the expected size. Hot reload applies a keyed diff, so unchanged nodes cost nothing ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md)). No spec depends on this request.

## Size

Small to medium for tre: a description walker over the existing node-creation code, and a batch of property sets with all-or-nothing validation.

## Open Questions

1. [ ] Ask tre to repeat the measurements on its own build, with medians, and with layout included (attach to a window and call `Window.advance`).
2. [x] Why `add_child` with 20,000 siblings averages 12 µs: tre answered (2026-11-02, from reading `crates/engine-core/src/tree/mod.rs`, not measured) that it is linear in the sibling count. Each call walks the existing siblings three to four times (`content_len` twice, a `contains` check, plus ancestor walks that depend on depth), so 20,000 appends are quadratic. A small fix inside tre (track the content length, skip the `contains` check for a parentless child) would make a plain append constant time. tre has filed nothing for it. The binder can avoid the cost by building a subtree detached and attaching its root once.
3. [x] Whether a batch also coalesces frame work: tre found layout already runs once per frame, not per set (1,000 sets and one frame took 0.42 ms), so a batch adds all-or-nothing validation and fewer crossings only.
4. [x] The shape: a dict description (tre's choice, see "tre's Reply").
5. [x] Carry it now: the maintainer asked for it and tasked tre to build it for 0.5.10.
6. [x] Issue number: #253.
7. [x] The plain-append fix is in the scope (maintainer, 2026-11-02).
8. [ ] Whether the shell wants other names or spec keys than tre's before it is built; tre offered to change them. The names match the sketch above.

## Acceptance Criteria

- [ ] `window.build(spec)` of a 3,100-node description produces the same tree as the equivalent per-node calls (compared by a snapshot).
- [ ] A description with one bad property raises and creates nothing.
- [ ] Building the 3,100-node tree takes less time than the 3.8 ms per-call baseline on the same machine.
- [ ] `window.apply` over 1,000 nodes changes none of them when one value is bad, and is faster than 1,000 `Node.set` calls (layout already runs once per frame, so the gain is fewer crossings and the validation, not fewer layouts).
- [ ] A plain `add_child` is constant time in the sibling count (the fix in tre's stage 0).
- [ ] The returned mapping gives the node for every `id` in the description.

## Links

- [80 Requests](80%20Requests.md) · [Layers and Components](../20%20Architecture/Layers%20and%20Components.md) · [Data Flow](../20%20Architecture/Data%20Flow.md) · [Performance Budgets](../60%20Quality/Performance%20Budgets.md) · [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md)

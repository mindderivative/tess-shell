---
title: Render Binder Design
aliases: [Binder Design, Binder API, Block Table]
type: architecture
status: draft
owner: phil
created: 2026-11-03
updated: 2026-11-10
tags: [architecture, binder, needs-verification]
---

# Render Binder Design

> [!NOTE]
> The design of the binder that [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) accepted: the typed tree it takes, the two tables it applies, the converters, the calls it makes to tre, how errors get back to a file position, and what is built at M1 and what waits for M2. It is a proposal for the maintainer. The tre property names and value forms in the tables were tested against tre 0.5.10 on 2026-11-03 (see [What tre Accepts (Tested 2026-11-03)](#what-tre-accepts-tested-2026-11-03)); several differ from what [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) says.

## Purpose and Scope

- Fix the binder's input, tables, converters, output and errors so M1 can build the first Bar through it.
- In scope for M1: build once from a typed tree. Designed here for M2: slot links, update and keyed rebuild.
- Not in scope: reading files (`tess_dl`), checking keys against the schema (the `schema` package), theme tokens, modules, and window creation (the surface manager).

## Where It Sits

```mermaid
flowchart LR
    F["tess_dl tree"] --> S["schema: check and type"]
    S --> T["typed tree (binder.model)"]
    T --> B["binder: apply tables"]
    B --> SP["spec dict"]
    SP --> W["Window.build(spec)"]
    W --> N["tre nodes under window.root"]
```

The `schema` package turns the `tess_dl` tree into the binder's own typed classes, so the binder needs nothing from the shell or from `tess_dl` ([Shell Package Layout > The Binder Is Independent](Shell%20Package%20Layout.md#the-binder-is-independent)). The import table gains one allowed edge: `schema` may import `binder.model` (the classes only).

## The Typed Tree

Defined in `binder/model.py` as small immutable classes. Illustrative:

```python
@dataclass(frozen=True)
class Origin:  file: str; line: int; column: int

@dataclass(frozen=True)
class Node:
    kind: str                 # the block word: "Text", "FlexBox", "Rectangle"
    name: str | None          # the Name: value, or None
    props: Mapping[str, Value]   # typed values by TDL key (Capitalised)
    style: Mapping[str, Value]   # the inline Style block, typed
    children: tuple["Node | IfNode | ForNode", ...]
    origin: Origin
```

`Value` is a union of typed values: `Length(px)`, `Percent(n)`, `Auto`, `Expand`, `Color(r, g, b, a)`, `Enum(name)`, `Bool`, `Number`, `Text`, `Sides(left, top, right, bottom)`, `Seq(items)`, and `SlotValue(compiled)` (M2). Each carries its `Origin`. `IfNode` and `ForNode` exist from M1 so the types are stable; at M1 the binder refuses them with a clear error.

## The Tables

Two tables, both plain Python data in `binder/tables.py`.

| Table | Row | Fields |
|---|---|---|
| Block table | One per TDL block word | `tre_kind`, `fixed` (properties always set), `keys` (the TDL keys the block accepts), `children_ok`, `needs` (props tre requires on create, such as `text` for a text node) |
| Key table | One per TDL key and block it applies to | `tre` (one name, or several for a four-sided key), `convert` (a converter name), `default` |

The key table holds both property keys and style keys; a style key and a property key of the same meaning share a row, as [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) rule R2 says. The Block Reference's "tre" columns are the documentation of these tables, and a test compares them ([Testing Strategy](../60%20Quality/Testing%20Strategy.md)).

## Converters

| Converter | TDL value | tre value |
|---|---|---|
| `length` | `16`, `50%`, `AUTO`, `EXPAND` | a number; a string like `"50%"`; `AUTO` and `EXPAND` map to tre's `auto` and flex rules (see the Block Reference sizes) |
| `color` | `"#RRGGBB"`, `"#RRGGBBAA"`, `rgba(r g b a)` | an `(r, g, b, a)` tuple of 0 to 255 ints (alpha 0.0 to 1.0 becomes 0 to 255) |
| `enum` | `HORIZONTAL`, `SPACE_BETWEEN` | the lower-case tre word: `"horizontal"`, `"space_between"` |
| `sides` (padding, margin) | one number, four items, named sides | four properties: `padding_top`, `padding_right`, `padding_bottom`, `padding_left` (the shell reorders left, top, right, bottom to tre's order) |
| `radius` | one number, or four from the top-left clockwise | a number, or a `(top_left, top_right, bottom_right, bottom_left)` tuple |
| `number`, `bool`, `text` | as written | as is |
| `font_family` | an ordered list | tre's `font_family` form (to confirm) |

A converter returns the tre value or raises `BindError` with the key's origin. Converters are pure functions, tested alone, with no import outside the standard library, so they can move to a shared package unchanged ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md)). tre takes one form for each kind of value and the framework converts ([ADR-0018 One Entry Form in tre](../30%20Decisions/ADR-0018%20One%20Entry%20Form%20in%20tre.md)), so the `color` converter handles every TDL colour form.

## Building

1. Walk the typed tree and, for each node, look up its block row and the key rows of its props and style. Collect every error (`BindError`) with its origin; if there is any, stop and report them all, so a surface never half-builds.
2. Build one nested spec for the surface: `{kind, props, children, id}` per node, with an `id` for each node that has a `Name` or (from M2) a slot link.
3. Keep a parallel index from each spec path (`spec.children[2].props`) to the `Origin` of the TDL key. tre's `ValueError` names the path of a bad entry; the binder translates it to `file:line:column`.
4. Call `window.build(spec)`; `parent.add_child(root)` once. The result is the detached root and a mapping from `id` to node, held in a `View` object.

tre's `build` is not faster than per-node calls (5.3 ms against 4.9 ms for 3,100 nodes, tre's measurement); the gain is the all-or-nothing check and one place where errors surface ([TRE-REQ-009 Batch and Tree Building > tre's Reply (2026-11-02)](../80%20Requests/TRE-REQ-009%20Batch%20and%20Tree%20Building.md#tres-reply-2026-11-02)).

## The View and the Later Operations

| Operation | M1 | M2 |
|---|---|---|
| `binder.build(nodes, window, scope=None) -> View` | Yes | Yes |
| `view.update(changed)`: apply new values for the slot links whose paths changed, through `window.apply([(node, props), ...])` | No | Yes |
| `view.rebuild(new_nodes)`: diff by key against the old tree; set what changed, add and remove the rest with `set_children` | No | Yes |
| `view.dispose()`: remove the subtree | Yes | Yes |

A link records: the tracked paths of a slot, the node id, the tre property and the converter. TEL's `evaluate_tracked` gives the paths ([Expression Language Requirements](../40%20Specifications/Runtime/Expression%20Language%20Requirements.md), T20); `For` entries use TEL's entry names ([ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) D65).

### The Keyed Diff (Proposed, for M2b)

`view.rebuild(new_nodes)` compares the old typed tree with the new one and changes only what differs. It is the design behind hot reload ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md)) and the `For` updates in [TEL Integration](TEL%20Integration.md); G9 of the [M2 Brief](../00%20Home/M2%20Brief.md).

**Identity of a child.** A child is matched by key, in this order:

1. its `Name:` if it has one (unique in its file, so unique among siblings);
2. else the pair (block word, how many earlier siblings have that word), the same positional naming the registry uses for repeats (`Square_1`, `Square_2`);
3. for the entries of a `For`, TEL's entry name (`<name>_0001`, never reused), which is stable while the item's key is.

**Steps**

1. Build the new typed tree completely and validate it. If it has any error, the old view stays untouched and every error is reported with `file:line:column`.
2. Walk old and new children in step, by key. For each key present in both with the same block word: compute the properties whose converted values differ, and recurse into the children. A different block word under the same key is a replacement (remove, then create).
3. Keys only in the new tree are created detached with `Window.build`; keys only in the old tree are removed.
4. If the order of the kept children changed, set the parent's children once with `Node.set_children(list)`.
5. Collect every change first, then apply: the property changes of the whole surface in one `Window.apply`, then the `set_children` calls, then attach the new subtrees. Because tre checks `apply` and `build` as a whole, a refused value changes nothing and is reported at its key.
6. Re-resolve the links of the changed slots; unchanged links stay. The `RepeaterState`s are dropped on a reload, because the compiled expressions may have changed, and the diff then matches entries by TEL's names (D30, accepted 2026-11-04; [TEL Integration](TEL%20Integration.md)). A module whose `Name` and file are unchanged keeps its instance; a changed TDL file for the module calls `reload()`; a changed `.py` replaces the instance ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md)).

**Surfaces.** A window is kept when its surface key (the `Name:` of the Bar, Panel or Popup) is unchanged and only keys that tre can change live differ (`anchor`, `size`, `margin`, `exclusive_zone`, the children); the shell sends one `set()` for the layer-window keys. A change of `Layer`, of the namespace or of the monitor closes and recreates the window ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md) lists the keys).

**Cost.** The comparison is one pass over both trees, linear in the number of nodes, and all of it runs on the loop thread between frames. The target is a reload on screen within about 300 ms of the save, 200 ms of which is the debounce ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md)).

**Built in M2b** (reported by `tess-shell`, [M2 Build Log](../00%20Home/M2%20Build%20Log.md)): `View.rebuild` follows the steps above. A kept node that loses a property is replaced, because tre has no way to unset a property (D28, accepted 2026-11-04); a moved child with a changed `Name:` is a replacement, as recommended. `For` entry names restart on a reload (the `RepeaterState` is dropped because the compiled expressions may have changed) and the diff matches entries by those names; a use whose layout has `If` or `For` is resolved again whole and diffed (D27, accepted 2026-11-04). A Bar window is kept when its key, output, `Layer` and exclusive edge are unchanged; `exclusive_edge` is not a key of `LayerWindow.set`, so changing it recreates the window.

## What tre Accepts (Tested 2026-11-03)

On tre 0.5.10, calling `Window.create` with each form. #needs-verification again on tre 0.6.0, which only renames the package.

| Need | tre accepts | The Block Reference says |
|---|---|---|
| Background of a box | `fill`, as an `(r, g, b, a)` tuple of 0 to 255 ints, or a `Gradient`; a string is refused | A colour string; mapping not given for `Background` |
| Text colour | The tuple form of `fill` (also refused as a string); whether `fill` colours text was not drawn-tested | `Foreground` is a style key |
| Border | `stroke_color` (tuple) and `stroke_width` | `Border_Color`, `Border_Width` |
| Corner radius | A number, or `(top_left, top_right, bottom_right, bottom_left)` | `Corner_Radius` |
| Padding and margin | `padding`, `margin`: a number or a percentage only; four sides need `padding_top`, `padding_right`, `padding_bottom`, `padding_left` (and the same for margin) | `padding` is shown as four-sided: this is wrong |
| Direction | `flex_direction`: `"horizontal"` or `"vertical"` | `HORIZONTAL`, `VERTICAL` |
| Alignment | `justify_content`, `align_items`: `start`, `end`, `flex_start`, `flex_end`, `center`, `stretch`, `space_between` and others | Upper-case enums |
| Sizes | `width`, `height`: a number or `"50%"` | `Width`, `Height` |
| Spacing | `gap`, `row_gap`, `column_gap` | `Spacing` |
| Text | `text`, `font_size`, `font_weight`, `font_family`, `line_height`, `text_align`, `wrap`, `max_lines`, `overflow` | As listed |
| Layer window | `LayerWindow(namespace, *, layer='top', anchor=None, size=None, exclusive_zone=None, exclusive_edge=None, margin=None, keyboard='none', output=None, input_region=None, click_through=None)` | As in [Bar > Mapping to tre](../40%20Specifications/Surfaces/Bar.md#mapping-to-tre) |

The first M1 task that touches the tables is a test that builds a node for every table row on a headless tre window, so a wrong name or form is found by the test and not by a user.

### More Forms Found While Building M1 (Reported by `tess-shell`, 2026-11-04; the vault checked the first column on `tess_re` 0.6.0)

| Need | tre accepts |
|---|---|
| Font family | One string (a list is refused). A comma-separated stack such as `"Inter, sans-serif"` is accepted by the setter; whether tre then falls back along the stack could not be seen headless (no text pixels for any family). The binder joins a TDL list with `", "`. #needs-verification in a real window |
| Text colour | `fill`, as for a box (the key `color` does not exist); `tess-shell` saw text pixels change colour in a snapshot |
| Wrap | `flex_wrap` is the word `wrap` or `no_wrap`, not a boolean |
| Text alignment | `text_align`: `start`, `center`, `end` (not `left` or `right`); a box refuses it |
| Font weight | A number from 1 to 1000, not `bold` |
| Width and height | A number, `auto`, `fit-content` or a percentage string; `expand` is refused, so `EXPAND` is `flex_grow` 1 with `align_self` `stretch` |
| Read-back | `grid_column` and `grid_row` read back as strings; other properties read back as set |
| Layer window root | No padding and a horizontal flex container; an ordinary window root has padding 16. A `FlexBox` that must fill a Bar needs `Width: EXPAND` |
| Headless | `Window` and `LayerWindow` work with no display and `snapshot()` renders off screen |

## Threading and Failure

- The binder runs on the loop thread only, in a callback between frames ([Process Model and Threading](Process%20Model%20and%20Threading.md)). It makes no blocking call.
- A bind error leaves the surface empty and logs every error with its position; other surfaces open ([Shell Start and Stop > Start Sequence](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#start-sequence), step 11).
- A converter or table bug is a test failure, not a runtime state.

## Configuration

None.

## Open Questions

1. [x] `font_family` takes one string; a comma-separated stack is accepted; rendering of the fallback is to check in a real window.

3. [x] `fill` colours text (`tess-shell`, snapshot test).
4. [ ] Does the binder resolve theme tokens (`$color.surface`) itself, or does the shell resolve them before binding? Context: tokens arrive with M2. Recommendation: the shell resolves them, so the binder sees literal values.
5. [ ] What shape does `View` take for `If` and `For` branches (M2)? Context: `IfNode` and `ForNode` exist from M1, and M2b built `View.rebuild` ([The View and the Later Operations](#the-view-and-the-later-operations)). Recommendation: keep the one `View` and let `rebuild` replace the branch or entry that TEL reports as changed.
6. [ ] **Is the key table hand-written or generated from the Block Reference?** Context: a test guards it either way. Recommendation: hand-written, guarded by the test.

## Questions After Testing

- [ ] Do `AUTO` and `EXPAND` map in tre as the Block Reference sizes say, for each block? Context: the shell maps `EXPAND` to `flex_grow` 1 with `align_self` `stretch` because tre refuses `expand`; this is untested per block ([Block Reference](../41%20TDL%20Reference/Block%20Reference.md)). Answered by: rendering each block with both values in a real window. Recommendation: test the blocks that take `Width` and `Height` first and record the result in the Block Reference.

## Acceptance Criteria

- [ ] Every block row and key row builds a node on a headless `tess_re` window without error.
- [ ] A bad value reports the `file:line:column` of its key, through the spec-path index.
- [ ] A typed tree of 3,100 nodes binds in 15 ms or less (decided 2026-11-04, D12; measured 12.6 ms median, of which tre's `build` is 5.3 ms; [Performance Budgets](../60%20Quality/Performance%20Budgets.md)).
- [ ] The binder imports only `tess_re` and the standard library.
- [ ] A tree with an `If` or `For` is refused at M1 with a clear message.

## Links

- [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) · [Layers and Components](Layers%20and%20Components.md) · [Data Flow](Data%20Flow.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [Shell Package Layout](Shell%20Package%20Layout.md) · [M1 Brief](../00%20Home/M1%20Brief.md)

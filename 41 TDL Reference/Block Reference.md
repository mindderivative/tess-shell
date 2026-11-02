---
title: Block Reference
aliases: [Blocks Reference, Building Block Properties]
type: tdl-ref
status: draft
owner: phil
created: 2026-11-01
updated: 2026-11-01
tags: [tdl-ref, spec/widget, needs-verification]
related: ["[[Building Blocks]]", "[[V1 Widgets]]", "[[Style Schema]]", "[[TDL Language]]", "[[Common Keys and Conventions]]", "[[Module File]]", "[[Hit Testing for Concave Corners]]"]
depends_on: ["[[Building Blocks]]", "[[TDL Language]]"]
---

# Block Reference

> [!summary]
> The properties, events, accessibility defaults and tre mapping of every building block. The set of blocks is decided ([[Building Blocks]]). The maintainer decided proposals R1 to R11 on 2026-11-01 ("as recommended", with R7 changed); the decisions are in "Decisions of 2026-11-01" below. Anything marked Open or Proposed is not decided. Visual keys (fill, border, text styling, shadow, motion, states) are style keys and live in [[Style Schema]]; this note covers what a block is, holds, does and reports. Written 2026-11-01 from tre's documentation ([properties](https://mindderivative.github.io/tre/reference/properties/), [paint](https://mindderivative.github.io/tre/reference/paint/), [events](https://mindderivative.github.io/tre/reference/events/), [accessibility](https://mindderivative.github.io/tre/guide/accessibility/), [building a widget](https://mindderivative.github.io/tre/guide/building-a-widget/), read 2026-11-01). Where tre's page does not document a default or a value set, the cell says so and the claim is #needs-verification.

## How to Read the Tables

- Keys follow [[TDL Language#Names and the Registry]]: Capitalised words joined by `_`, enum values in upper case. A key that has a tre property keeps tre's name where the shell has not chosen another (`Min_Width` for `min_width`), and the tre column names it.
- A block is called by its head (`Text { }`). The properties below go inside it. Default `none` means the key is not set.
- A key that is also a style key (`Padding`, `Margin`, `Spacing`, `Opacity`) is a shorthand: writing it on a block is the same as writing it in that block's inline `Style`, with the priority of inline style (proposed rule R2 below).
- tre's defaults mostly are not documented; the tre defaults named here are the ones the page states.

## What tre Offers (Read 2026-11-01)

| Fact                                                                                                                                                       | Consequence for the blocks                                                                                          |
|------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| Node kinds: `box`, `text`, `text_input`, `image`, `svg`, `path`, `canvas`, `scroll_view`, `virtual_list`, `terminal`.                                       | Every block maps to one kind or to a composition of kinds. Two kinds, `scroll_view` and `virtual_list`, have no block yet (see R3). |
| Every node with children is a flex container by default (`display` is `"flex"`); `display: "grid"` gives a grid with `grid_template_columns`, `grid_template_rows`, `row_gap`, `column_gap`, `grid_auto_flow`. | `FlexBox` and `Grid` are direct. Grid is supported; the open item "Grid against tre's layout" is closed.            |
| `disabled` does not block focus, clicks or keys; the widget must do it.                                                                                     | The shell's `Enabled` key is implemented by the block, not by tre.                                                  |
| tre has no hover or pressed state; it gives `pointer_enter`, `pointer_leave`, `pointer_down`, `pointer_up`, `focus`, `unfocus` and `focus_visible`.          | The shell tracks `Hovered`, `Pressed` and `Focused` itself and applies the style states.                           |
| Input that does the same thing arrives as one `click` (mouse, Space or Enter on a focused node, assistive activation).                                      | A block exposes one `On_Click` for all three.                                                                       |
| `node.on(event, handler)` replaces an earlier listener for that event on the node.                                                                          | The shell owns the single listener per event and multiplexes to the module.                                         |
| A canvas's `draw` runs on creation, when set and on `redraw()`, not every frame.                                                                            | A `Canvas` fits "Python runs only in callbacks".                                                                    |

## Common Properties

Every block has these.

### Identity and Style

| Key       | Values                                        | Default | tre | Meaning                                                                                       |
|-----------|-----------------------------------------------|---------|-----|-----------------------------------------------------------------------------------------------|
| `Name`    | An identifier ([[TDL Language]], D28)          | none    | none | The unique name; gives the block a path (`RootShell.DP1.Top_Bar.Title`)                       |
| `Class`   | One class name, or a list                      | none    | none | Style classes ([[Style, Theme and Stylesheet Files#Classes]])                                  |
| `Style`   | A style file, or an inline `Style { }` block   | none    | none | [[Style, Theme and Stylesheet Files#Rules]]                                                    |
| `Tooltip` | A Popup file, or an inline `Popup { }` block   | none    | none | Available on every block and module (decided 2026-10-28, [[Popup#Tooltips (decided 2026-10-28)]]) |

### State

| Key         | Values        | Default                 | tre         | Meaning                                                                                                   |
|-------------|---------------|-------------------------|-------------|-----------------------------------------------------------------------------------------------------------|
| `Visible`   | true, false   | true                    | `visible`   | False hides the block from everyone, including assistive technology, and takes no space                   |
| `Enabled`   | true, false   | true                    | `disabled`  | False sets the accessibility state `disabled`, applies the style state `Disabled` and makes the block ignore input; tre does not do this |
| `Focusable` | true, false   | true on interactive blocks, false otherwise | `focusable` | Joins the Tab order                                                                                       |
| `Cursor`    | An enum       | none                    | `cursor`    | The pointer shape while over the block. tre's examples use `cursor="pointer"`; its page does not list the values #needs-verification |

### Size, Placement and Order

| Key                                               | Values                                        | Default | tre                                       | Meaning                                                                                                                         |
|---------------------------------------------------|-----------------------------------------------|---------|-------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| `Width`, `Height`                                 | A length (pixels or `50%`), `AUTO`, `EXPAND`    | `AUTO`  | `width`, `height` (number, `"auto"`, percentage) | `AUTO` fits the content. `EXPAND` takes the free space: it is `flex_grow: 1` along the parent's main axis and `align_self: stretch` across it (proposed mapping) |
| `Min_Width`, `Min_Height`, `Max_Width`, `Max_Height` | A length                                    | none    | `min_width` and so on                     | Bounds on a resolved size                                                                                                       |
| `Aspect_Ratio`                                    | A number                                      | none    | `aspect_ratio`                            | Width over height                                                                                                               |
| `Position`                                        | `RELATIVE`, `ABSOLUTE`                         | `RELATIVE` | `position`                              | `ABSOLUTE` takes the block out of the layout and places it by `Left`, `Top`, `Right`, `Bottom`                                   |
| `Left`, `Top`, `Right`, `Bottom`                  | A length                                      | none    | `left`, `top`, `right`, `bottom`           | Insets of an absolute block                                                                                                     |
| `Z_Index`                                         | A whole number                                | 0       | `z_index`                                 | Paint order among siblings                                                                                                      |
| `Margin`                                          | Four-sided, left, top, right, bottom           | 0       | `margin`                                  | Transparent space around the block. Also a style key                                                                            |

### As a Child

| Key                                    | Values                                             | Default   | tre                                           | Applies in      |
|----------------------------------------|----------------------------------------------------|-----------|-----------------------------------------------|-----------------|
| `Flex_Grow`, `Flex_Shrink`, `Flex_Basis` | Numbers, and a length or `AUTO` for the basis      | 0, 1, `AUTO` | `flex_grow`, `flex_shrink`, `flex_basis`   | A `FlexBox`     |
| `Align_Self`                           | `START`, `CENTER`, `END`, `STRETCH`                 | by the parent | `align_self`                              | A `FlexBox`, a `Grid`, a `Box` |
| `Grid_Column`, `Grid_Row`              | A start line, or `[start, span]`                    | auto      | `grid_column`, `grid_row`                     | A `Grid`, a `Box` |
| `Justify_Self`                         | `START`, `CENTER`, `END`, `STRETCH`                 | by the parent | `justify_self`                            | A `Grid`, a `Box` |

The value sets of the align and justify keys are CSS-like and tre's page does not list them #needs-verification.

### Transform and Clip

| Key                          | Values            | Default | tre                         | Meaning                                                              |
|------------------------------|-------------------|---------|-----------------------------|----------------------------------------------------------------------|
| `Translate_X`, `Translate_Y` | A number (pixels) | 0       | `translate_x`, `translate_y` | Moves the painted block without changing layout; animatable          |
| `Scale`                      | A number          | 1.0     | `scale`                     | Scales the painted block; animatable                                  |
| `Rotation`                   | A number (degrees) | 0      | `rotation_deg`              | Rotates the painted block; animatable                                 |
| `Clip_Children`              | true, false       | false   | `clip_children`             | Clips the children, not the block's own paint                         |

### Accessibility

| Key           | Values                                                                                                                        | Default            | tre           | Meaning                                                           |
|---------------|-------------------------------------------------------------------------------------------------------------------------------|--------------------|---------------|-------------------------------------------------------------------|
| `Role`        | `BUTTON`, `CHECKBOX`, `SWITCH`, `SLIDER`, `TEXTBOX`, `MENU`, `MENUITEM`, `DIALOG`, `TAB`, `HEADING`, `LIST`, `LISTITEM` (tre's page lists more) | by block, below    | `role`        | What assistive technology announces                               |
| `Label`       | A string                                                                                                                      | none               | `label`       | The name read aloud. A text node's words are not exposed alone, so the block that shows text carries the label |
| `Live`        | `POLITE`, `ASSERTIVE`                                                                                                         | none               | `live`        | Announces changes                                                 |
| `A11y_Hidden` | true, false                                                                                                                   | by block, below    | `a11y_hidden` | Hides the block from assistive technology while it stays visible  |

State flags (`checked`, `selected`, `expanded`, `pressed`, `value`, `value_min`, `value_max`, `value_step`) are set by the block that has them, not written by the author.

### Events

An event key is `On_` plus the event name. The `On_` prefix is reserved for events (maintainer, 2026-11-01, R5): the events in the table below are the first set, and event names are added here as blocks need them. An unknown `On_` key is an error that names the closest events.

An action is what the shell does when the event happens. It is a method of the module's Python class marked `@action`, or a built-in shell action ([[Module Contract#The Class (Proposed)]]; decided 2026-10-26 that nothing else can be called from a shell file). Arguments may be TEL expressions, evaluated when the event fires ([[ADR-0007 Shell UI Layer#Events and Module Reload (2026-10-26)]]).

Proposed value form (the agent's recommendation, not decided):

```
On_Click: toggle_mute

On_Change {
    Action: set_volume
    value: {{ event.value }}
}
```

- A bare name is an action with no arguments.
- The block form has an `Action:` key, which is syntax (Capitalised), and the action's arguments. Argument keys are written as the Python parameters are, like a module's params (D18); their values are literals or slots.
- `event` is a name in the scope of those slots, with the fields of tre's event (for example `value` on `change`).
- A name resolves first among the module's `@action` methods, then among the built-in shell actions. The list of built-in actions is open.
- One action per event key. A sequence is a method that calls others: Python owns intent.

| Key                                                         | tre event                                      | On which blocks                               |
|-------------------------------------------------------------|------------------------------------------------|-----------------------------------------------|
| `On_Click`                                                  | `click` (mouse, Space or Enter, assistive activation) | Every block; the interactive ones by default |
| `On_Secondary_Click`                                        | `secondary_click`                              | Every block                                   |
| `On_Pointer_Enter`, `On_Pointer_Leave`                      | `pointer_enter`, `pointer_leave` (do not bubble) | Every block                                |
| `On_Pointer_Down`, `On_Pointer_Move`, `On_Pointer_Up`, `On_Pointer_Cancel` | `pointer_down`, `pointer_move`, `pointer_up`, `pointer_cancel` | Every block |
| `On_Wheel`                                                  | `wheel` (`delta_x`, `delta_y`)                 | Every block                                   |
| `On_Key_Down`, `On_Key_Up`                                  | `key_down`, `key_up`                           | Focusable blocks                              |
| `On_Focus`, `On_Unfocus`                                    | `focus`, `unfocus` (`focus_visible` on focus)   | Focusable blocks                              |

Block-specific events are listed with the block. tre has no double-click and no drag event; a drag is `pointer_down` plus `pointer_move` with pointer capture.

## Containers

### Box

> [!success] How a Box differs from a FlexBox (decided 2026-11-01, R1)
> The maintainer defined a Box as a basic container with no auto-stacking, invisible when unstyled and a panel of its own when fully styled. In tre every node with children lays them out as flex. Decided (R1): a Box is a one-cell grid. All children occupy the same cell and overlap; the Box is as large as its largest child unless sized; each child can align itself with `Align_Self` and `Justify_Self`. Nothing is stacked automatically, and the Stack module becomes a Box.

| Key       | Values                  | Default | tre                         | Meaning                                                           |
|-----------|-------------------------|---------|-----------------------------|-------------------------------------------------------------------|
| `Padding` | Four-sided              | 0       | `padding`                   | Transparent space between the children and the four sides (D42)   |
| `Children` | A block of blocks      | none    | children                    | The contents                                                      |

Maps to a tre `box` with `display: "grid"`, one column and one row, and every child placed in cell (1, 1). Role none; `A11y_Hidden` false.

### FlexBox

| Key               | Values                                                          | Default      | tre                        | Meaning                                                                    |
|-------------------|-----------------------------------------------------------------|--------------|----------------------------|----------------------------------------------------------------------------|
| `Flex`            | `HORIZONTAL`, `VERTICAL`                                        | `HORIZONTAL` | `flex_direction`           | How the children are stacked (D35). `NONE` is an error on a FlexBox        |
| `Wrap`            | true, false                                                     | false        | `flex_wrap`                | Wraps children onto further lines                                          |
| `Align_Items`     | `START`, `CENTER`, `END`, `STRETCH`                              | `STRETCH`    | `align_items`              | Placement across the stacking direction                                    |
| `Justify_Content` | `START`, `CENTER`, `END`, `SPACE_BETWEEN`, `SPACE_AROUND`, `SPACE_EVENLY` | `START` | `justify_content`      | Placement along the stacking direction                                     |
| `Spacing`         | A number (pixels)                                                | 0            | `gap`                      | Space between the children (D49). Also a style key                         |
| `Padding`         | Four-sided                                                       | 0            | `padding`                  | Space between the children and the four sides                              |

A vertical Bar is a FlexBox with `Flex: VERTICAL` (decided 2026-10-27). The defaults of the align and justify keys are CSS-like and tre's page does not state them #needs-verification.

### Grid

| Key                              | Values                                                             | Default  | tre                                       | Meaning                                                                                      |
|----------------------------------|--------------------------------------------------------------------|----------|-------------------------------------------|----------------------------------------------------------------------------------------------|
| `Columns`, `Rows`                | A whole number (that many equal tracks), or a list of track sizes   | one track | `grid_template_columns`, `grid_template_rows` | A track size is a length, `AUTO` or `EXPAND` (a share of the free space); a number N is N `EXPAND` tracks |
| `Spacing`                        | A number                                                           | 0        | `row_gap`, `column_gap`                   | Space between tracks on both axes                                                            |
| `Column_Spacing`, `Row_Spacing`  | A number                                                           | `Spacing` | `column_gap`, `row_gap`                  | One axis                                                                                     |
| `Auto_Flow`                      | `ROW`, `COLUMN`                                                    | `ROW`    | `grid_auto_flow`                          | Where an unplaced child goes                                                                  |
| `Auto_Columns`, `Auto_Rows`      | A track size                                                       | `AUTO`   | `grid_auto_columns`, `grid_auto_rows`     | The size of tracks the template did not define                                                |
| `Justify_Items`, `Align_Items`, `Align_Content` | `START`, `CENTER`, `END`, `STRETCH`                 | `STRETCH` | `justify_items`, `align_items`, `align_content` | Placement of items and of the tracks                                                  |
| `Padding`                        | Four-sided                                                         | 0        | `padding`                                 | Space between the tracks and the four sides                                                   |

The exact text form of tre's `grid_template_columns` is not on the page; the shell builds it from the list above #needs-verification. A child sets its cell with `Grid_Column` and `Grid_Row`.

### ScrollBox (Decided 2026-11-01, R3)

The decided block set has no scrolling block, yet the List module needs one: tre's scrolling is a node kind of its own (`scroll_view`). Decided: `ScrollBox` is added to the block set.

| Key              | Values                                | Default    | tre              | Meaning                                                                  |
|------------------|---------------------------------------|------------|------------------|--------------------------------------------------------------------------|
| `Orientation`    | `VERTICAL`, `HORIZONTAL`              | `VERTICAL` | `orientation`    | The scrolling direction                                                   |
| `Scroll_Snap`    | `NONE`, `START`, `CENTER`, `END`      | `NONE`     | `scroll_snap`    | Snap points                                                               |
| `Scroll_Offset`  | A number (pixels)                     | 0          | `scroll_offset`  | The current offset; animatable                                            |
| `Padding`        | Four-sided                            | 0          | `padding`        | Inside space                                                              |
| `On_Scroll`      | event                                 | none       | `scroll`         | Fires when the offset changes (`old_value`, `new_value`)                  |

### VirtualList (Later, R3)

For long lists (launcher results, tasks) where only visible entries are built. Maps to tre's `virtual_list`: `item_count`, `item_extent` (or `size_hint`), `materialize`, `scroll_offset`. The properties would be `Item_Count`, `Item_Extent`, `Scroll_Offset`, and an item template. How an item template is written in TDL, and how it meets the `For` repeater (TEL reconciles by key), is open; recommendation: leave VirtualList until a module needs more entries than a ScrollBox can build.

## Typography

### Text

| Key          | Values                       | Default | tre                         | Meaning                                                                                              |
|--------------|------------------------------|---------|-----------------------------|------------------------------------------------------------------------------------------------------|
| `Text`       | A string; may hold slots      | empty   | `text`                      | The words. `Text: Battery {{ battery.percent }}%`                                                    |
| `Wrap`       | `WORD`, `NONE`                | `WORD`  | `wrap`                      | `NONE` keeps one line                                                                                 |
| `Max_Lines`  | A whole number                | none    | `max_lines`                 | Truncates after this many lines                                                                       |
| `Selectable` | true, false                   | false   | `selectable` (default false) | Lets the user select the text                                                                         |
| `Padding`    | Four-sided                    | 0       | `padding`                   | Inset around the words (R6)                                                                           |
| `On_Link`    | event                         | none    | `link` (`href`)             | A press and release on a link span                                                                    |

Style keys: `Font_Family`, `Size`, `Weight`, `Line_Height`, `Align`, `Overflow`, `Foreground` ([[Style Schema#Style Keys]]). tre also has `font_style`, `letter_spacing`, `spans` (rich text) and `fill`; the shell has no key for `font_style` and `letter_spacing` yet, and rich text is post-v1 (R10). `Width: AUTO` is tre's `"fit-content"` for text. Role none; the block that shows the text carries the label. Label is a Text with `Wrap: NONE`; TextBox is a Text with `Wrap: WORD`.

### TextField

tre's advice is a `text_input` inside a box that paints the background and border ([[Building Blocks#What Tre Offers]], building a widget). The block is that composition.

| Key               | Values                    | Default | tre                       | Meaning                                                                                                            |
|-------------------|---------------------------|---------|---------------------------|--------------------------------------------------------------------------------------------------------------------|
| `Text`            | A string                  | empty   | `text`                    | The value. Data goes in through this key; edits come out through `On_Change` (R6)                                  |
| `Placeholder`     | A string                  | none    | `placeholder` (only in an example, not in a property table) | Shown while empty #needs-verification; otherwise a Text drawn by the composition |
| `Multiline`       | true, false               | false   | `multiline`               | A multi-line field. The TextEditor module is a TextField with this set                                              |
| `Selection`       | `[start, end]` (byte offsets) | none | `selection`               | The selection                                                                                                       |
| `Show_Whitespace` | true, false               | false   | `show_whitespace`         | Draws whitespace marks (a code editor)                                                                              |
| `Padding`         | Four-sided                | by theme | the box's `padding`      | Inset of the text inside the field                                                                                  |
| `On_Change`       | event                     | none    | `change` (`old_value`, `new_value`, user edits only) | Fires for edits by the user, not for a value the module set |
| `On_Submit`       | event                     | none    | `submit`                  | Enter in a single-line field                                                                                        |
| `On_Input`        | event                     | none    | `input` (`text`)          | Committed text; with `On_Change` it covers input methods (`compose_start`, `compose_update`, `compose_end` are handled inside the block) |

Not available in tre and so not offered: password masking, a maximum length, a read-only flag (none are on tre's page). A module that needs one makes an engine request ([[AGENTS#6. Engine requests (tre / Tesserae)]]). `syntax_spans` and `folded_ranges` exist in tre for code editing and are post-v1. Role `TEXTBOX`, focusable. Input methods work on layer surfaces in tre 0.5.8; no real input method was tested ([[V1 Widgets#Open Questions]]).

## Graphics

### Bitmap

| Key      | Values                         | Default   | tre                    | Meaning                                                                                              |
|----------|--------------------------------|-----------|------------------------|------------------------------------------------------------------------------------------------------|
| `Source` | A file path, relative to the file that names it | none | `rgba`, `pixel_width`, `pixel_height` | The image. The shell reads and decodes the file and gives tre the pixels (data in, not files, [[AGENTS#3. Layering principle]]) |
| `Fit`    | `FILL`, `CONTAIN`, `COVER`      | `CONTAIN` | `fit`                  | How the image fits the block                                                                         |

A side is at most 8192 pixels (tre). Decoding png, jpeg, gif and webp needs an image library in the shell, and an animated gif needs frame stepping through repeated `set(rgba=...)`; both are open (R8). A tint is not documented in tre; an icon that must take the theme colour is an `SVG`. Role none; `A11y_Hidden` true unless `Label` is set.

### SVG

| Key      | Values                         | Default | tre                | Meaning                                                                                                   |
|----------|--------------------------------|---------|--------------------|-----------------------------------------------------------------------------------------------------------|
| `Source` | A file path, relative to the file that names it | none | `svg` (str or bytes, gzip allowed) | The document, read by the shell and given to tre. A malformed document is an error with the file position |
| `Color`  | A colour                       | none    | `svg_color`        | What `currentColor` resolves to; the `Foreground` style key sets it, so a themed icon follows the theme    |

tre fits an SVG uniformly and centres it (`xMidYMid meet`), so `Fit` is not offered. `svg_images` (pixels for an `<image>` inside the document) is not exposed. Width and Height default to the document's size #needs-verification. Role none; `A11y_Hidden` true unless `Label` is set.

## Shapes

All shapes are drawn as a tre `path` (SVG path data) and take the style keys `Fill` (the interior) and `Border_Color`, `Border_Thickness` (the stroke, centred on the outline). A shape's default hit shape is `PAINTED` (decided 2026-10-27); `Hit_Shape` can set `BOX` ([[Hit Testing for Concave Corners]]; tre's `hit_shape` is `"box"` by default and `"painted"`). Shapes have no `Children`, so no `Padding`. Role none; `A11y_Hidden` true.

| Block     | Own keys                                                                                       | Notes                                                                                            |
|-----------|------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| Rectangle | `Corner_Radius` (one number, or four from the top-left corner clockwise)                        | `Width`, `Height`                                                                                |
| Square    | `Side` (a length), `Corner_Radius`                                                              | A Rectangle with equal sides                                                                     |
| Circle    | `Diameter` (a length)                                                                           | A circle fits its box                                                                            |
| Ellipse   | `Width`, `Height`                                                                               | A Circle with two sizes                                                                          |
| Ring      | `Diameter`; the ring's thickness is `Border_Thickness`                                          | A Circle with no fill and a border                                                               |
| Triangle  | `Direction` (`UP`, `DOWN`, `LEFT`, `RIGHT`; default `UP`)                                       | An isosceles triangle in its box                                                                 |
| Hexagon   | `Orientation` (`POINTY`, `FLAT`; default `POINTY`)                                              | A regular hexagon in its box                                                                     |
| Path      | `Data` (SVG path syntax), `View_Box` (`[min_x, min_y, width, height]`), `Trim_Start`, `Trim_End` | tre's `path`: `data`, `view_box`, `trim_start`, `trim_end` (0.0 to 1.0). Used for the Frame's concave corners and Panel joins. Caps and joins are round and not settable in tre |

Differences from a Box: a Box's stroke is drawn inside the box without changing layout (`stroke_color`, `stroke_width`); a path's stroke is centred on the outline and is the same width whatever the view box. The shape blocks are generated path data, so the shell computes them from `Width` and `Height`. Triangle and Hexagon have no corner rounding in v1.

## Other

### Terminal

| Key                | Values                   | Default | tre                        | Meaning                                                                          |
|--------------------|--------------------------|---------|----------------------------|----------------------------------------------------------------------------------|
| `Columns`, `Rows`  | 1 to 1000                | 80, 24 (the shell's choice) #needs-verification | `cols`, `rows` | The terminal's size in character cells                              |
| `Scrollback_Lines` | A whole number           | tre's default | `scrollback_lines` (creation only) | History kept                                                |
| `Selection`        | Four numbers             | none    | `selection`                | The selection                                                                    |

Style keys: `Size` (font), and a `Terminal_Palette` block for `palette` (`ansi`, `foreground`, `background`, `cursor`, `selection`). Role `TEXTBOX`.

> [!danger] A Terminal starts a process
> tre's `shell` argument is set at creation and runs a program. TDL is data from a configuration file and must not start processes. Decided (R4): TDL has no `Command` key. A Terminal is attached by a module's Python, which supplies the process. A shell file can place a Terminal block but cannot make it run anything. Recorded in [[Risk Register]] as R-22. Post-v1.

### Canvas

| Key    | Values                        | Default | tre          | Meaning                                                                                              |
|--------|-------------------------------|---------|--------------|------------------------------------------------------------------------------------------------------|
| `Draw` | A module method               | none    | `draw`       | Called with tre's painter when the Canvas is created, when `Draw` is set and when the module calls `redraw` ([tre painter reference](https://mindderivative.github.io/tre/reference/painter/)) |

The drawing is Python, so a Canvas is for a module that ships its own `.py`. Role none; `A11y_Hidden` true unless `Label` is set. Post-v1.

## Accessibility Defaults

| Block or module              | Role (`Role`)                 | Focusable | Notes                                                                                                   |
|------------------------------|-------------------------------|-----------|---------------------------------------------------------------------------------------------------------|
| Box, FlexBox, Grid, ScrollBox | none                         | no        | A container with a role of its own (a `LIST`, a `MENU`) takes it from its module                       |
| Text                         | none                          | no        | The block that shows text carries the `Label`                                                           |
| TextField                    | `TEXTBOX`                      | yes       | Enter submits a single-line field                                                                       |
| Bitmap, SVG, shapes, Canvas  | none                          | no        | `A11y_Hidden` true unless `Label` is set: a decorative image is not announced                           |
| Terminal                     | `TEXTBOX`                      | yes       |                                                                                                         |
| Button (module)              | `BUTTON`                       | yes       | `On_Click` runs on mouse, Space and Enter alike, and on the assistive activate action                   |
| Toggle (module)              | `SWITCH`, state `checked`      | yes       |                                                                                                         |
| Checkbox (module)            | `CHECKBOX`, state `checked`    | yes       |                                                                                                         |
| Slider (module)              | `SLIDER`, `value`, `value_min`, `value_max`, `value_step` | yes | Arrow keys step it; `a11y_action` handles `increment`, `decrement` and `set_value`                 |
| Menu, MenuItem (modules)     | `MENU`, `MENUITEM`            | yes       | `expanded` on a menu with a submenu                                                                     |
| List (module)                | `LIST`, `LISTITEM`            | yes       | `selected` on the chosen entry                                                                          |

A focus ring appears only for keyboard focus (`focus_visible`), as a non-blurred shadow with spread so it does not shift layout (tre's building-a-widget guide). The style state `Focused` therefore means keyboard focus. Reduced motion and high contrast are the theme's job ([[Goals and Non-Goals]] G7).

## Decisions of 2026-11-01

Proposals R1 to R11 were decided by the maintainer in chat ("As recommended"), except R7, which the maintainer changed. R12 to R14 record the maintainer's other answers of the same day.

| #   | Topic                      | Decision                                                                                                                                                                                                                                                                |
|-----|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| R1  | What is a Box?              | A one-cell grid: children overlap, the Box sizes to the largest, children align themselves.                                                                                                                                                                              |
| R2  | Property or style?          | Layout and behaviour are properties; visual keys are style keys. A key that is both (`Padding`, `Margin`, `Spacing`, `Opacity`) is accepted on the block as a shorthand for inline `Style`, with inline priority.                                                         |
| R3  | Scrolling blocks            | `ScrollBox` is added to the block set. `VirtualList` waits until a module needs it.                                                                                                                                                                                      |
| R4  | Terminal                    | No `Command` key in TDL; a module's Python attaches the process. Post-v1.                                                                                                                                                                                                |
| R5  | Event values                | `On_` is reserved for events; event names are added as blocks need them. An action is an `@action` method or a built-in shell action. The value form under Events is a proposal.                                                                                                                                                                  |
| R6  | Input state and Padding     | Data in through `Text`, edits out through `On_Change`; no two-way binding. `Padding` is on every block with `Children` and also on `Text` and `TextField` (this decides D59 of [[ADR-0014 Shell File Language]]).                                                          |
| R7  | Icons                       | Changed by the maintainer. Lookup order: (1) a shipped set of SVG icons in a JSON file, (2) the desktop's freedesktop icon theme, (3) the `Icons` folder in the shell's config directory, (4) the locations a developer lists in `settings.tdl`. See "Icons" below. The maintainer provides the JSON file. |
| R8  | Image decoding              | The shell decodes png, jpeg, gif and webp with an image library (a dependency to choose). An animated gif is stepped by the shell. Post-v1 for animation.                                                                                                                |
| R9  | A block handle for Python   | A module can reach a block it names and call `focus()`, `capture_pointer()`, `release_pointer()`, `redraw()` and read `layout_width` and `layout_height`. To be written into [[Module Context]].                                                                         |
| R10 | Rich text                   | tre's `spans` become repeated `Span` blocks inside a Text. Post-v1.                                                                                                                                                                                                       |
| R11 | v1 block set                | Box, FlexBox, Grid, Text, TextField (single line), Bitmap, SVG, Rectangle, Circle, Ring, Path and ScrollBox. The rest follow when a module needs them ([[V1 Widgets]]).                                                                                                    |
| R12 | Custom blocks               | A module author can add a block, in Python, shipped with the module. The mechanism is under "Custom Blocks" below and is a proposal.                                                                                                                                     |
| R13 | Revealer renamed            | The module Revealer is now Expander, the familiar name (maintainer, 2026-11-01).                                                                                                                                                                                          |
| R14 | Stack                       | The maintainer asked what separates a Stack from a FlexBox. A FlexBox places children side by side or one under another. A Stack puts them on top of each other in one cell. With R1 a Box already does that, so the Stack module has nothing left to add. Decided (maintainer, 2026-11-01): Stack is dropped; use a Box. |

## Icons (R7)

The Icon module finds an icon by name in this order; the first hit wins. A file path (relative to the file that names it) skips the lookup.

| Order | Source                                                                                                              | Notes                                                                                                                                                       |
|-------|---------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1     | The shipped set: SVG icons in one JSON file that ships with the shell                                               | Proposed shape: a JSON object that maps an icon name to an SVG document, plus the set's name and licence. The shell reads it once at start and gives the SVG text to tre |
| 2     | The desktop's freedesktop icon theme                                                                                | [Icon Theme Specification](https://specifications.freedesktop.org/icon-theme-spec/latest/); the current theme comes from the desktop settings #needs-verification |
| 3     | The `Icons` folder in the shell's config directory                                                                  | `$HOME/.config/tesserae-shell/Icons/` ([[Settings File]])                                                                                                    |
| 4     | The locations a developer lists in `settings.tdl`                                                                   | Under `Directories { Icons: [...] }`, searched in order (proposed key; [[Settings File]])                                                                    |

The maintainer will provide the JSON file of the icon set (2026-11-01). Its format and licence information come with it, so the shape in row 1 is a placeholder.

Settings key (recommended, not decided): `Directories { Icons: [...] }`, the same key as the other file types, one path or a list searched in order. The config `Icons/` folder (row 3) comes first and the listed paths follow, as the maintainer set the order; this is the one place where a listed path is searched after the default folder, because the Settings File note proposes the opposite for the other types ([[Settings File]]).

Consequences to confirm: because the shipped set is first, a file in `Icons/` or the desktop theme cannot replace a shipped icon of the same name; to use another `battery-full` a user names the file by path or uses another name. Open: how the JSON file is versioned and updated, and the Icon module's parameter for the name (not `Name`, which is the unique name). The icon set's licence goes into the delivery notes.

## Custom Blocks (R12)

The maintainer decided that a module author can add a block, in Python, shipped with the module. The mechanism below is the agent's proposal.

- A block is a Python class in the module's `<Name>_Module.py`, derived from a shell `Block` base. It declares its properties (type, default, choices, doc), parts, states and events the way a built-in does, so the schema and the error messages cover it ([[Style Schema]], [[JSON Schema and Editor Support]]).
- It is built from tre nodes: a tree of the existing node kinds. It cannot add a new tre node kind.
- It is registered by name in the one registry when the module loads, and removed when the module is unloaded or reloaded ([[Hot Reload]]). A name used twice is a load error, except that a user module overrides a shipped one.
- Once the module has loaded, any file can use the block by its name, like any other.
- It runs the module's Python in the shell's process, so the unwritten security model for user Python applies ([[Risk Register]] R-19).
- Recommended API (not decided): v1 custom blocks are leaf blocks, with no `Children`, because composition is what modules are for. A name needs no prefix: a name used twice is a load error that names both places. The class sketch is under "Custom Block API (Recommended)" and is mirrored in [[Module Contract#Custom Blocks (Proposed)]].

### Custom Block API (Recommended)

An illustration, not the import path or the final names:

```python
# Modules/Meter/Meter_Module.py
from tesserae_shell import Module, Block, Prop

class Meter(Block):
    name = "Meter"                               # the head used in TDL
    properties = {
        "Value": Prop(float, default=0.0, doc="0.0 to 1.0"),
        "Segments": Prop(int, default=10, doc="Number of bars"),
    }
    parts = ("track", "fill")                    # a style can address them
    states = ("hovered", "disabled")             # a style can target them
    events = ("On_Click",)                       # event keys it offers

    def build(self, ctx, props):                 # once, on the loop thread
        ...                                      # returns a tree of tre nodes

    def update(self, ctx, props, changed):       # when a property changes
        ...
```

- `build` and `update` are callbacks that return fast; neither runs per frame. A `Canvas` is redrawn on a change, not every frame.
- The shell validates the properties from the declaration (type, default, doc) and puts the block in the project schema ([[JSON Schema and Editor Support]]).
- A file holds one `Module` class and any number of `Block` classes.
- The shell's own node builder wraps tre's node kinds; the exact calls are not decided, and no tre API is invented here.

## Open

- [ ] The recommended custom-block API (R12), the settings key for icon locations, the action value form under Events, and the list of built-in shell actions.
- [ ] The icon JSON file: its format and licence, which the maintainer provides.
- [ ] The value sets and defaults of the align, justify and cursor keys, and the text form of grid tracks (#needs-verification against tre's source or a test).
- [ ] The default sizes of an SVG and of a Terminal (#needs-verification).
- [ ] The event and action vocabulary and the value form of an `On_` key.
- [ ] Which style keys have no tre property yet (`font_style`, `letter_spacing`) and whether the shell offers them.

## Acceptance Criteria

- Every block in the decided set has a table here, and every key has a type, a default or `none`, and the tre property it maps to, or `none`.
- An unknown key on a block is an error that names the closest keys ([[Common Keys and Conventions]]).
- `Flex: NONE` on a `FlexBox` is an error that says so.
- A `Box` with two children lays them in one cell, and sizes to the larger.
- `Enabled: false` stops `On_Click`, sets the accessibility state `disabled` and applies the style state `Disabled`.
- A `Bitmap` or `SVG` with no `Label` is hidden from assistive technology.
- A `Terminal` in a TDL file does not start a process.
- A `TextField` reports a user edit through `On_Change` and does not report a value the module set.

## Links

- [[Building Blocks]] · [[V1 Widgets]] · [[Style Schema]] · [[TDL Language]] · [[Common Keys and Conventions]] · [[Module File]] · [[41 TDL Reference]]

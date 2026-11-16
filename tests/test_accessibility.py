"""The accessibility pass (M6 Brief, E1): the role, name, description and state of the
shipped modules, and each announcement, read back through the accessibility tree of a headless tre
window (``node.get``: tre publishes exactly what was set, and a node with ``live`` is announced when
its label changes). The announcements are polite live regions named ``Announcer``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.launcher_rig import launcher_desk
from tests.modules_rig import desk, shell
from tests.tasks_rig import tasks_desk, tasks_shell
from tests.test_launcher import BROWSERS
from tests.test_tasks import a, buttons, lists, start
from tests.widgets_live import Widgets, running

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


def announcer(w: Widgets, module: str, index: int = 0) -> Any:
    return w.of_use(module, "Announcer", index)


def heard(w: Widgets, module: str) -> str | None:
    """What the module's live region says now."""
    return announcer(w, module).get("label") or None


# -- the static modules: role, name, state -------------------------------------------------------

STATIC = [
    ("Label", 'Label { Text: "Hi" }', "Label", "#0", {"label": "Hi", "role": None}),
    ("TextBox", 'TextBox { Text: "a b" }', "TextBox", "#0", {"label": "a b"}),
    ("Button", 'Button { Text: "Save" }', "Button", "Root", {"role": "button", "label": "Save"}),
    (
        "Button icon",
        'Button { Icon: "mdi:home", Label: "Home" }',
        "Button",
        "Root",
        {"role": "button", "label": "Home"},
    ),
    (
        "Toggle",
        "Toggle { Label: Wi-Fi, Checked: true }",
        "Toggle",
        "Root",
        {"role": "switch", "label": "Wi-Fi", "checked": True, "focusable": True},
    ),
    (
        "Checkbox",
        "Checkbox { Text: Agree }",
        "Checkbox",
        "Root",
        {"role": "checkbox", "label": "Agree", "checked": False},
    ),
    (
        "Slider",
        'Slider { Label: Vol, Value: 30, Value_Text: "30 percent" }',
        "Slider",
        "Root",
        {"role": "slider", "label": "Vol", "value_text": "30 percent", "value_max": 100},
    ),
    (
        "ProgressBar",
        "ProgressBar { Value: 25, Label: Up }",
        "ProgressBar",
        "Root",
        {"role": "progressbar", "label": "Up", "value": 25},
    ),
    ("Badge", "Badge { Count: 3 }", "Badge", "Root", {"a11y_hidden": True}),
    ("Icon", 'Icon { Icon: "mdi:home" }', "Icon", "Root", {"a11y_hidden": True}),
    (
        "Icon named",
        'Icon { Icon: "mdi:home", Label: Home }',
        "Icon",
        "Root",
        {"label": "Home", "a11y_hidden": False},
    ),
    ("Image", 'Image { Placeholder: "#334455" }', "Image", "Root", {"a11y_hidden": True}),
    ("Marquee_Text", 'Marquee_Text { Text: "abc" }', "Marquee_Text", "Root", {"label": "abc"}),
    (
        "Expander closed",
        "Expander { Expanded: false, Children { Label { Text: x } } }",
        "Expander",
        "Body",
        {"a11y_hidden": True},
    ),
    (
        "TextInput placeholder",
        "TextInput { Placeholder: Search }",
        "TextInput",
        "#1",
        {"role": "textbox", "label": "Search"},
    ),
    (
        "TextInput label",
        "TextInput { Placeholder: Search, Label: Query }",
        "TextInput",
        "#1",
        {"label": "Query"},
    ),
    (
        "TextEditor",
        "TextEditor { Placeholder: Notes }",
        "TextEditor",
        "#2",
        {"role": "textbox", "label": "Notes"},
    ),
    (
        "List",
        "List { Label: L, Selected: b, Children { Label { Text: A, Key: a } "
        "Label { Text: B, Key: b } } }",
        "List",
        "Root",
        {"role": "list", "label": "L", "focusable": True},
    ),
    (
        "Button expandable",
        "Button { Text: More, Expandable: true, Expanded: true }",
        "Button",
        "Root",
        {"expanded": True},
    ),
    (
        "Button disabled",
        "Button { Text: x, Enabled: false }",
        "Button",
        "Root",
        {"disabled": True},
    ),
]


@pytest.mark.parametrize(
    ("body", "module", "suffix", "expected"),
    [pytest.param(b, m, s, e, id=i) for i, b, m, s, e in STATIC],
)
def test_the_tree_of_a_static_module(
    body: str, module: str, suffix: str, expected: dict[str, Any]
) -> None:
    with running(body) as w:
        node = w.of_use(module, suffix)
        for key, value in expected.items():
            assert node.get(key) == value, (key, node.get(key))


def test_the_list_entries_are_list_items_and_the_chosen_one_is_selected() -> None:
    body = "List { Selected: b, Children { Label { Text: A, Key: a } Label { Text: B, Key: b } } }"
    with running(body) as w:
        items = [n for k, n in w.view.nodes.items() if k.startswith("Label@")]
        assert [(n.get("role"), n.get("label"), n.get("selected")) for n in items] == [
            ("listitem", "A", False),
            ("listitem", "B", True),
        ]


def test_a_slider_without_value_text_says_its_number_only() -> None:
    with running("Slider { Label: V, Value: 4 }") as w:
        node = w.of_use("Slider", "Root")
        assert node.get("value_text") is None and node.get("value") == 4


# -- the Panel ---------------------------------------------------------------------------------


def test_a_surface_is_named_and_an_exclusive_panel_is_a_dialog(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        window = d.panel.window
        assert window.root.get("label") == "Launcher"
        (body,) = window.root.children()
        assert (body.get("role"), body.get("label")) == ("dialog", "Launcher")
        assert d.w.surface("Top_Bar").window.root.get("label") == "Top Bar"


# -- Applications ----------------------------------------------------------------------------------


def row_labels(d: Any) -> list[str]:
    return [str(n.get("label")) for n in d.rows()]


def test_the_launcher_names_its_field_its_rows_and_its_list(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        assert d.field().get("label") == "Search applications"
        assert d.field().get("role") == "textbox"
        assert "Firefox, Web Browser" in row_labels(d) and "Files, Browse folders" in row_labels(d)
        assert {n.get("role") for n in d.rows()} == {"listitem"}
        (lst,) = [n for n in d.panel.view.nodes.values() if n.get("role") == "list"]
        assert (lst.get("role"), lst.get("label")) == ("list", "Results")


def test_the_launcher_says_the_selected_row_as_the_selection_moves(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()

        def say() -> Any:
            return next(
                n.get("label") for k, n in d.panel.view.nodes.items() if k.endswith("/Announcer")
            )

        assert say() in (None, "")  # opening says nothing: the dialog and the field do
        d.press("arrow_down")
        assert say() == "Fire Dragon, 2 of 4"
        d.press("arrow_down")
        assert say() == "Firefox, 3 of 4"
        d.press("arrow_up")
        assert say() == "Fire Dragon, 2 of 4"
        live = next(n for k, n in d.panel.view.nodes.items() if k.endswith("/Announcer"))
        assert live.get("live") == "polite"


def test_the_launcher_says_no_results_and_a_typed_first_row_after_a_second(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        live = next(n for k, n in d.panel.view.nodes.items() if k.endswith("/Announcer"))
        d.type("fire")
        assert not live.get("label")  # typing is not one announcement a key
        (tick,) = d.w.host.ticks._subs
        tick.fn()  # the next second
        d.w.flush()
        d.window.advance(16)
        assert live.get("label") == "Fire Dragon, 1 of 2"
        d.type("zzz")
        assert d.message() == "No results" and live.get("label") == "No results"
        d.toggle()  # hide
        d.toggle()  # show again: nothing said before is said again
        assert not live.get("label")


# -- Tasks ---------------------------------------------------------------------------------------


@needs_daemon
def test_a_task_button_is_named_by_the_desktop_entrys_name(tmp_path: Path) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.entry("fake-app", "fake-icon", name="Fake Application")
        t.fake.script.windows = [a(1, title="Alpha")]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 1)
        assert t.settle(w, lambda: buttons(w)[0].get("label") == "Alpha, Fake Application")


@needs_daemon
def test_tasks_announces_a_window_that_opens_closes_or_wants_attention_when_asked(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t, "Tasks { announce: true }\nTasks { }") as w:
        t.fake.script.windows = [a(1, title="One")]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 1)
        assert not heard(w, "Tasks")  # the first list says nothing
        assert announcer(w, "Tasks").get("live") == "polite"
        lists(t, w, a(1, title="One"), a(2, title="Two"))
        assert t.settle(w, lambda: heard(w, "Tasks") == "Two opened")
        lists(t, w, a(1, title="One", attention=True), a(2, title="Two"))
        assert t.settle(w, lambda: heard(w, "Tasks") == "One wants attention")
        lists(t, w, a(1, title="One", attention=True))
        assert t.settle(w, lambda: heard(w, "Tasks") == "Two closed")
        # the second use has not asked: it has no live region at all
        assert len([k for k in w.view.nodes if k.endswith("/Announcer")]) == 1


# -- Network, Battery ---------------------------------------------------------------------------


@needs_daemon
def test_network_says_connected_and_disconnected_once_and_not_a_signal_change() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: w.of_use("Network", "Root").get("visible"))
            root = w.of_use("Network", "Root")
            assert root.get("description") == "Wired connection 1, ethernet, connected"
            assert not heard(w, "Network")  # the first reading says nothing
            assert announcer(w, "Network").get("live") == "polite"
            net.nothing()
            assert d.settle(w, lambda: heard(w, "Network") == "Network disconnected")
            net.wifi(72)
            assert d.settle(
                w, lambda: str(heard(w, "Network")).startswith("Network connected, Wi-Fi")
            )
            said = heard(w, "Network")
            net.ap["one"].set("Strength", 30)  # a weaker signal is not the news
            d.settle(w, lambda: False, 0.3)
            assert heard(w, "Network") == said


@needs_daemon
def test_battery_says_critical_once_and_a_change_of_percent_never() -> None:
    with desk() as d:
        fake, obj = d.battery(percentage=15.0)
        fake.up()
        with shell(d, "Battery { }") as w:
            assert d.settle(w, lambda: w.of_use("Battery", "Root").get("visible"))
            root = w.of_use("Battery", "Root")
            assert root.get("description") == "15 %, discharging, 2 h 14 min left"
            assert not heard(w, "Battery")
            obj.set("Percentage", 12.0)
            d.settle(w, lambda: False, 0.3)
            assert not heard(w, "Battery")
            obj.set("WarningLevel", 4)
            said = "Battery critical, 12 percent, discharging"
            assert d.settle(w, lambda: heard(w, "Battery") == said)
            assert announcer(w, "Battery").get("live") == "polite"


# -- Media -------------------------------------------------------------------------------------


@needs_daemon
def test_media_says_a_new_track_only_when_asked_and_its_position_in_words() -> None:
    from tests.fake_mpris import metadata

    with desk() as d:
        p = d.player("vlc", status="Playing", meta=metadata("Song", ["Ann"]))
        p.up()
        with shell(d, "Media { announce: true, show_position: true }\nMedia { }") as w:
            assert d.settle(w, lambda: w.of_use("Media", "Root").get("visible"))
            tip = w.of_use("Media", "Root").get("description")
            assert tip == "Song, Ann (Fake Player), playing"
            slider = next(n for k, n in w.view.nodes.items() if k.endswith(".Position/Root"))
            assert d.settle(w, lambda: str(slider.get("value_text")).endswith(" of 3:20"))
            assert not heard(w, "Media")
            p.track(title="Next", artist=["Bo"])
            assert d.settle(w, lambda: heard(w, "Media") == "Track changed: Next, Bo")
            assert len([k for k in w.view.nodes if k.endswith("/Announcer")]) == 1


# -- Audio -------------------------------------------------------------------------------------


def test_audio_says_mute_at_once_and_a_settled_volume_when_asked(
    fake_pulse: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tess_shell.services import audio as audio_service
    from tests import test_audio_module as T

    monkeypatch.setattr(audio_service, "SHORT_SESSION", 0.0)
    T.maintainers_desktop(fake_pulse)
    body = "Audio { announce: true, show_slider: true }"
    with T.desk(fake_pulse) as d, T.shell(d, body) as w:
        assert d.settle(w, lambda: T.icon_of(w) == "volume-medium")
        assert w.of_use("Audio", "Root").get("description") == "Razer Leviathan V2 X, 45 %"
        slider = next(n for k, n in w.view.nodes.items() if k.endswith(".Volume/Root"))
        assert slider.get("value_text") == "45 percent"
        assert not heard(w, "Audio") and announcer(w, "Audio").get("live") == "polite"
        w.window.simulate("click", node=w.of_use("Audio", "Toggle"))
        assert d.settle(w, lambda: heard(w, "Audio") == "Muted")
        w.window.simulate("click", node=w.of_use("Audio", "Toggle"))
        assert d.settle(w, lambda: heard(w, "Audio") == "Unmuted, 45 percent")
        w.window.simulate("wheel", node=w.of_use("Audio", "Root"), delta_y=-120)
        assert d.settle(w, lambda: w.host.ticks._subs != [])  # one tick waits to say it
        w.host.ticks._subs[0].fn()
        assert d.settle(w, lambda: heard(w, "Audio") == "Volume 50 percent")
        assert w.host.ticks._subs == []

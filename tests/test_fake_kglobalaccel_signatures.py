"""The fake ``org.kde.kglobalaccel`` has the signatures of the real one (Global Shortcuts > The
Service's Interface as Read, 2026-11-13, a read-only introspection by the vault session), and it is
strict: a call with another signature finds no method, as on the real service, so a client that
sends a wrong signature FAILS here. Nothing touches the real session bus."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pytest

from tess_shell.services.api import ServiceError
from tess_shell.services.bus import ServiceThread
from tests.fake_dbus import HAVE_DAEMON, fake_bus
from tests.fake_kglobalaccel import (
    COMPONENT_INTERFACE,
    INTERFACE,
    NAME,
    PATH,
    FakeKGlobalAccel,
)

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

COMPONENT = "/component/probe"
IDS = ["probe", "Act", "Probe", "Act"]
KEYS = [[[65]]]  # a(ai): one sequence holding one key


@dataclass(frozen=True)
class Method:
    path: str
    interface: str
    member: str
    sig: str
    body: list[Any]
    wrong_sig: str
    wrong_body: list[Any]


MAIN = (PATH, INTERFACE)
COMP = (COMPONENT, COMPONENT_INTERFACE)
METHODS = [
    Method(*MAIN, "doRegister", "as", [IDS], "s", ["x"]),
    Method(*MAIN, "setShortcutKeys", "asa(ai)u", [IDS, KEYS, 2], "asau", [IDS, [65], 2]),
    Method(*MAIN, "setShortcut", "asaiu", [IDS, [65], 2], "asa(ai)u", [IDS, KEYS, 2]),
    Method(*MAIN, "shortcutKeys", "as", [IDS], "s", ["Act"]),
    Method(*MAIN, "isGlobalShortcutAvailable", "is", [65, "probe"], "as", [["x"]]),
    Method(*MAIN, "globalShortcutAvailable", "(ai)s", [[[65]], "probe"], "is", [65, "probe"]),
    Method(*MAIN, "setInactive", "as", [IDS], "ss", ["probe", "Act"]),
    Method(*MAIN, "unRegister", "as", [IDS], "ss", ["probe", "Act"]),
    Method(*MAIN, "unregister", "ss", ["probe", "Gone"], "as", [["probe", "Gone"]]),
    Method(*MAIN, "getComponent", "s", ["probe"], "as", [["probe"]]),
    Method(*COMP, "allShortcutInfos", "", [], "i", [1]),
    Method(*COMP, "shortcutNames", "", [], "s", ["default"]),
    Method(*COMP, "isActive", "", [], "s", ["x"]),
    Method(*COMP, "invokeShortcut", "s", ["Act"], "as", [["Act"]]),
    Method(*COMP, "cleanUp", "", [], "s", ["x"]),
]


@contextmanager
def rig() -> Iterator[tuple[FakeKGlobalAccel, ServiceThread]]:
    with fake_bus() as bus:
        fake = FakeKGlobalAccel(bus)
        fake.start()
        service = ServiceThread(bus.address)
        service.start()
        try:
            service.submit(
                service.session.call(NAME, PATH, INTERFACE, "doRegister", "as", [IDS])
            ).result(5)
            yield fake, service
        finally:
            service.stop()


def call(service: ServiceThread, m: Method, sig: str, body: list[Any]) -> list[Any]:
    return service.submit(
        service.session.call(NAME, m.path, m.interface, m.member, sig, body)
    ).result(5)


@pytest.mark.parametrize("m", METHODS, ids=lambda m: f"{m.member}({m.sig})")
def test_the_right_signature_is_answered_and_a_wrong_one_finds_no_method(m: Method) -> None:
    with rig() as (_fake, service):
        call(service, m, m.sig, m.body)  # the real signature: answered
        with pytest.raises(ServiceError) as caught:
            call(service, m, m.wrong_sig, m.wrong_body)
        assert "UnknownMethod" in str(caught.value) or "InvalidArgs" in str(caught.value)


def test_the_answers_have_the_real_shapes() -> None:
    with rig() as (fake, service):
        by = {(m.member, m.sig): m for m in METHODS}
        set_keys = by[("setShortcutKeys", "asa(ai)u")]
        assert call(service, set_keys, set_keys.sig, set_keys.body) == [[[[65]]]]  # a(ai)
        assert call(service, by[("setShortcut", "asaiu")], "asaiu", [IDS, [66], 2]) == [[66]]  # ai
        assert call(service, by[("shortcutKeys", "as")], "as", [IDS]) == [[[[66]]]]
        free = by[("isGlobalShortcutAvailable", "is")]
        assert call(service, free, "is", [70, "probe"]) == [True]
        fake.own(70)
        assert call(service, free, "is", [70, "probe"]) == [False]
        seq = by[("globalShortcutAvailable", "(ai)s")]
        assert call(service, seq, "(ai)s", [[[70]], "x"]) == [False]
        assert call(service, by[("unregister", "ss")], "ss", ["probe", "Act"]) == [True]  # b
        assert call(service, by[("unregister", "ss")], "ss", ["probe", "Act"]) == [False]
        assert call(service, by[("getComponent", "s")], "s", ["probe"]) == [COMPONENT]  # o


def test_all_shortcut_infos_is_a_ssssssaiai() -> None:
    """The real service also takes one ``s`` (a context); dbus-fast cannot export two signatures
    of one name, so the fake has the argument-less form."""
    with rig() as (_fake, service):
        by = {(m.member, m.sig): m for m in METHODS}
        ((row,),) = call(service, by[("allShortcutInfos", "")], "", [])
        assert [type(x).__name__ for x in row] == ["str"] * 6 + ["list", "list"]
        assert row[:2] == ["probe", "Act"]


def test_the_signals_have_the_real_signatures() -> None:
    with rig() as (fake, _service):
        main = fake.main._build()
        assert main.introspect().signals  # yourShortcutsChanged, yourShortcutGotChanged
        sigs = {s.name: s.signature for s in main.introspect().signals}
        assert sigs == {"yourShortcutsChanged": "asa(ai)", "yourShortcutGotChanged": "asai"}
        component = fake._objects[COMPONENT]._build()
        csigs = {s.name: s.signature for s in component.introspect().signals}
        assert csigs == {
            "globalShortcutPressed": "ssx",
            "globalShortcutReleased": "ssx",
            "globalShortcutRepeated": "ssx",
        }
        props = {p.name: p.signature for p in component.introspect().properties}
        assert props == {"uniqueName": "s", "friendlyName": "s"}

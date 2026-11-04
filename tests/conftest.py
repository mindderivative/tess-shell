from collections.abc import Iterator

import pytest

from tests.sway import PrivateSway, SwayUnavailable


@pytest.fixture
def private_sway() -> Iterator[PrivateSway]:
    sway = PrivateSway()
    try:
        sway.start()
    except SwayUnavailable as exc:
        pytest.skip(str(exc))
    try:
        yield sway
    finally:
        sway.stop()

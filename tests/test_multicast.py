"""Tests for multicast mirror configuration."""

from kraktak.multicast import MulticastMirror, get_mirror


def test_multicast_disabled_by_default():
    assert MulticastMirror.from_config({}) is None


def test_multicast_enabled_via_flag():
    m = MulticastMirror.from_config({"ENABLE_MULTICAST_MIRROR": "true"})
    assert m is not None
    assert m._addr == ("239.2.3.1", 6969)


def test_get_mirror_runtime_overlay():
    m = get_mirror(
        {"ENABLE_MULTICAST_MIRROR": "false"},
        {"enable_multicast_mirror": True},
    )
    assert m is not None

"""Tests for KrakTAK CoT builders, geometry, and filters."""

import xml.etree.ElementTree as ET

import pytest

import kraktak
from kraktak import functions


def _event(out: bytes) -> ET.Element:
    return ET.fromstring(out.split(b"\n", 1)[1])


@pytest.mark.parametrize(
    "builder,cot_type",
    [
        ("sensor", "a-f-G-U-C"),
        ("bearing_line", "u-d-f"),
        ("range_bearing", "u-rb-a"),
        ("lob", "a-u-G"),
        ("cep", "a-u-G"),
    ],
)
def test_builders_produce_expected_type(doa, builder, cot_type):
    out = kraktak.cot_to_xml(doa, {}, builder)
    assert out is not None
    event = _event(out)
    assert event.tag == "event"
    assert event.attrib["type"] == cot_type
    assert "kraktak" in event.attrib["uid"]


def test_bearing_line_has_endpoint(doa):
    event = _event(kraktak.cot_to_xml(doa, {}, "bearing_line"))
    points = event.findall("point")
    assert len(points) == 2  # base point + LOB endpoint


def test_lob_structure(doa):
    event = _event(kraktak.cot_to_xml(doa, {}, "lob"))
    lob = event.find(".//detail/__lob")
    assert lob is not None
    assert lob.attrib["azimuth"] == "135.0"
    assert lob.attrib["unitId"] == "CTIKraken"
    assert lob.find("signalInfo") is not None
    assert lob.find("__startLocation") is not None


def test_no_position_returns_none(doa):
    doa.latitude = None
    assert functions.doa_to_cot_bearing_line(doa, {}) is None


def test_selected_builders_filters_invalid():
    cfg = {"COT_TYPES": "bearing_line,bogus,lob"}
    assert kraktak.selected_builders(cfg) == ["bearing_line", "lob"]


def test_calculate_second_point_distance():
    lat2, lon2 = functions.calculate_second_point(0.0, 0.0, 90.0, 111000.0)
    # Due east ~1 degree of longitude at the equator.
    dist, bearing = functions.bearing_and_distance(0.0, 0.0, lat2, lon2)
    assert abs(dist - 111000.0) < 50
    assert abs(bearing - 90.0) < 0.5


def test_exclusion_wedge():
    # Wedge 90-180: inside is dropped (False), outside passes (True).
    assert functions.evaluate_angle_range(90, 180, 135) is False
    assert functions.evaluate_angle_range(90, 180, 200) is True
    # Wrapping wedge 350-10 across north.
    assert functions.evaluate_angle_range(350, 10, 5) is False
    assert functions.evaluate_angle_range(350, 10, 180) is True
    # No wedge configured.
    assert functions.evaluate_angle_range(None, None, 42) is True


def test_passes_filters(doa):
    assert functions.passes_filters(doa, {}) is True
    assert functions.passes_filters(doa, {"MIN_CONFIDENCE": "90"}) is False
    assert functions.passes_filters(doa, {"MIN_RSSI": "0"}) is False


def test_gen_geochat(doa):
    out = kraktak.gen_geochat("hello", {}, "ANDROID-1")
    event = ET.fromstring(out.split(b"\n", 1)[1])
    assert event.attrib["type"] == "b-t-f"
    assert event.find(".//__chat").attrib["chatroom"] == "ANDROID-1"
    assert event.find(".//remarks").text == "hello"

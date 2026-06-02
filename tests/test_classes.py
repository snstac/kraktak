"""Tests for KrakTAK DOA parsing."""

from kraktak.classes import parse_doa_csv, settings_url_from_feed
from tests.conftest import make_doa_line


def test_parse_basic(doa):
    assert doa.station == "CTIKraken"
    assert doa.frequency == 144390000
    assert doa.max_doa_angle == 135.0
    assert doa.confidence == 42.0
    assert doa.rssi == -30.0
    assert doa.latitude == 37.7601
    assert doa.longitude == -122.4974
    assert len(doa.values) == 360


def test_parse_empty_returns_none():
    assert parse_doa_csv("") is None
    assert parse_doa_csv("   \n  ") is None
    assert parse_doa_csv("not,enough,fields") is None


def test_parse_float_frequency():
    line = make_doa_line(freq_hz="144390000.0")
    doa = parse_doa_csv(line)
    assert doa.frequency == 144390000


def test_settings_url_from_feed():
    url = settings_url_from_feed("http://192.168.50.5:8081/DOA_value.html")
    assert url == "http://192.168.50.5:8081/settings.json"

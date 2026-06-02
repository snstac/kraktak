"""Tests for the KrakTAK control plane: command parsing and validation."""

import xml.etree.ElementTree as ET

from kraktak import control


def test_parse_chat_frequency():
    cmd = control.parse_chat_command("kraken freq 462.5625")
    assert cmd.action == "set_frequency"
    assert cmd.args == {"freq": 462.5625}


def test_parse_chat_variants():
    assert control.parse_chat_command("kraken gain 16.6").action == "set_gain"
    vfo = control.parse_chat_command("kraken vfo 0 467000000")
    assert vfo.action == "set_vfo_frequency"
    assert vfo.args == {"index": 0, "vfo_freq": 467000000.0}
    coord = control.parse_chat_command("kraken coord 34.7 -86.6")
    assert coord.args == {"latitude": 34.7, "longitude": -86.6}
    assert control.parse_chat_command("kraken status").action == "status"


def test_parse_chat_ignores_non_kraken():
    assert control.parse_chat_command("hello world") is None
    assert control.parse_chat_command("") is None


def test_parse_cot_krakencmd_detail():
    xml = (
        "<event><detail>"
        "<__krakencmd action='set_frequency' freq='146.52'/>"
        "</detail></event>"
    )
    cmd = control.parse_cot_command(ET.fromstring(xml))
    assert cmd.action == "set_frequency"
    assert cmd.args["freq"] == 146.52


def test_parse_cot_geochat_remarks():
    xml = (
        "<event uid='ANDROID-7'><detail>"
        "<remarks>kraken gain 25.4</remarks>"
        "</detail></event>"
    )
    cmd = control.parse_cot_command(ET.fromstring(xml))
    assert cmd.action == "set_gain"
    assert cmd.args["gain"] == 25.4


def test_validate_frequency_range():
    assert control.validate("set_frequency", {"freq": 146.52}) is None
    assert control.validate("set_frequency", {"freq": 5000}) is not None


def test_validate_gain():
    assert control.validate("set_gain", {"gain": 16.6}) is None
    assert control.validate("set_gain", {"gain": 13.3}) is not None


def test_control_host_from_feed():
    cfg = {"FEED_URL": "http://192.168.50.5:8081/DOA_value.html"}
    assert control.control_host(cfg) == "192.168.50.5"
    assert control.control_host({"KRAKEN_HOST": "kraken.local"}) == "kraken.local"


def test_get_sender():
    xml = "<event uid='ABC'><detail><contact callsign='Alpha'/></detail></event>"
    uid, cs = control.get_sender(ET.fromstring(xml))
    assert uid == "ABC"
    assert cs == "Alpha"

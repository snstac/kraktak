"""Tests for multi-Kraken configuration loading."""

import json

import pytest

from kraktak.config_loader import (
    KrakenServerConfig,
    load_kraken_servers,
    merge_server_config,
)


def test_from_dict_ip_canary_style():
    srv = KrakenServerConfig.from_dict({"ip": "10.0.0.5", "port": 8081})
    assert srv.feed_url == "http://10.0.0.5:8081/DOA_value.html"


def test_line_distance_km_to_meters():
    srv = KrakenServerConfig.from_dict({"feed_url": "http://x/DOA_value.html", "line_distance": 5})
    assert srv.lob_length_m == 5000.0


def test_load_kraken_servers_json():
    cfg = {
        "KRAKEN_SERVERS": json.dumps(
            [
                {"feed_url": "http://a/DOA_value.html", "station": "A"},
                {"ip": "10.0.0.2"},
            ]
        )
    }
    servers = load_kraken_servers(cfg)
    assert len(servers) == 2
    assert servers[0].station == "A"
    assert "10.0.0.2" in servers[1].feed_url


def test_merge_server_overrides():
    base = {"DOA_IGNORE_START": 0, "LOB_LENGTH_KM": "10"}
    srv = KrakenServerConfig(
        feed_url="http://x/",
        doa_ignore_start=45,
        lob_length_m=2000.0,
        min_confidence=5.0,
    )
    merged = merge_server_config(base, srv)
    assert merged["DOA_IGNORE_START"] == 45
    assert merged["LOB_LENGTH_M"] == "2000.0"
    assert merged["MIN_CONFIDENCE"] == "5.0"


def test_load_requires_feed_or_ip():
    with pytest.raises(ValueError):
        KrakenServerConfig.from_dict({})

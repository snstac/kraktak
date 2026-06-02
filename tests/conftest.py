"""Shared test fixtures for KrakTAK."""

import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XSD_DIR = os.path.join(REPO_ROOT, "takcot-master", "xsd", "details")


def make_doa_line(
    *,
    epoch_ms=1718000000000,
    max_angle=135,
    confidence=42,
    rssi=-30,
    freq_hz=144390000,
    arrangement="UCA",
    latency=12.5,
    station="CTIKraken",
    lat=37.7601,
    lon=-122.4974,
    gps_heading=0,
    compass_heading=0,
    sensor="GPS",
):
    """Build one synthetic "Kraken App" DOA CSV line (13 base + 4 reserved + 360)."""
    base = [
        epoch_ms, max_angle, confidence, rssi, freq_hz, arrangement, latency,
        station, lat, lon, gps_heading, compass_heading, sensor, 0, 0, 0, 0,
    ]
    powers = [1.0] * 360
    return ",".join(str(x) for x in base + powers)


@pytest.fixture
def doa_line():
    return make_doa_line()


@pytest.fixture
def doa(doa_line):
    from kraktak.classes import parse_doa_csv

    return parse_doa_csv(doa_line)

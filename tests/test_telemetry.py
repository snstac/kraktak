"""Tests for operational telemetry."""

from kraktak.telemetry import TelemetryStore


def test_record_poll_and_packets():
    store = TelemetryStore()
    store.record_poll(
        "http://kraken/DOA_value.html",
        "K1",
        reachable=True,
        doa_angle=90.0,
        confidence=50.0,
    )
    store.record_packets(3)
    snap = store.snapshot()
    assert snap["packets_sent"] == 3
    assert snap["last_packet_ago"] is not None
    assert len(snap["servers"]) == 1
    assert snap["servers"][0]["reachable"] is True

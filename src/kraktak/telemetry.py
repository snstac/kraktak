#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Shared operational telemetry for KrakTAK workers and the dashboard."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, Optional


@dataclass
class ServerTelemetry:
    """Live status for one KrakenSDR feed."""

    feed_url: str
    station: str = ""
    reachable: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    doa_angle: Optional[float] = None
    confidence: Optional[float] = None
    rssi: Optional[float] = None
    last_error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "feed_url": self.feed_url,
            "station": self.station,
            "reachable": self.reachable,
            "lat": self.latitude,
            "lon": self.longitude,
            "doa": self.doa_angle,
            "confidence": self.confidence,
            "rssi": self.rssi,
            "last_error": self.last_error,
        }


class TelemetryStore:
    """Thread-safe counters and per-server status for ops dashboards."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.packets_sent: int = 0
        self.last_packet_time: Optional[float] = None
        self._servers: Dict[str, ServerTelemetry] = {}

    def record_poll(
        self,
        feed_url: str,
        station: str,
        *,
        reachable: bool,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        doa_angle: Optional[float] = None,
        confidence: Optional[float] = None,
        rssi: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            st = self._servers.get(feed_url)
            if st is None:
                st = ServerTelemetry(feed_url=feed_url, station=station)
                self._servers[feed_url] = st
            st.station = station or st.station
            st.reachable = reachable
            st.latitude = latitude
            st.longitude = longitude
            st.doa_angle = doa_angle
            st.confidence = confidence
            st.rssi = rssi
            st.last_error = error

    def record_packets(self, count: int) -> None:
        if count <= 0:
            return
        with self._lock:
            self.packets_sent += count
            self.last_packet_time = time.time()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            ago = None
            if self.last_packet_time is not None:
                ago = round(time.time() - self.last_packet_time, 1)
            return {
                "packets_sent": self.packets_sent,
                "last_packet_ago": ago,
                "servers": [s.as_dict() for s in self._servers.values()],
            }


# Process-wide store used by workers and the dashboard.
STORE = TelemetryStore()

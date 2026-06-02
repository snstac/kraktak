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

"""KrakTAK Class Definitions."""

import asyncio

from dataclasses import dataclass, field
from typing import List, Optional, Union
from urllib.parse import urlsplit, urlunsplit

import aiohttp

import pytak

import kraktak


@dataclass
class DOAValues:
    """A single KrakenSDR DOA record (one VFO channel)."""

    timestamp: int
    max_doa_angle: float
    confidence: float
    rssi: float
    frequency: int
    antenna: str
    latency: float
    station: str
    latitude: Optional[float]
    longitude: Optional[float]
    gps_heading: Optional[float] = None
    compass_heading: Optional[float] = None
    sensor: str = ""
    values: List[float] = field(default_factory=list)
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None


def parse_doa_csv(line: str) -> Optional[DOAValues]:
    """Parse one CSV line of the KrakenSDR "Kraken App" DOA export.

    Returns ``None`` if the line is empty or malformed.
    """
    line = (line or "").strip()
    if not line or "," not in line:
        return None

    parts = [p.strip() for p in line.split(",")]
    if len(parts) < kraktak.DOA_MIN_FIELDS:
        return None

    def _f(idx: int, default=None):
        try:
            return float(parts[idx])
        except (ValueError, IndexError):
            return default

    lat = _f(kraktak.DOA_IDX_LATITUDE)
    lon = _f(kraktak.DOA_IDX_LONGITUDE)
    values = []
    for raw in parts[kraktak.DOA_IDX_POWER_START:]:
        try:
            values.append(float(raw))
        except ValueError:
            continue

    return DOAValues(
        timestamp=int(_f(kraktak.DOA_IDX_EPOCH_MS, 0) or 0),
        max_doa_angle=_f(kraktak.DOA_IDX_MAX_ANGLE, 0.0),
        confidence=_f(kraktak.DOA_IDX_CONFIDENCE, 0.0),
        rssi=_f(kraktak.DOA_IDX_RSSI, 0.0),
        frequency=int(_f(kraktak.DOA_IDX_FREQUENCY_HZ, 0) or 0),
        antenna=parts[kraktak.DOA_IDX_ARRANGEMENT],
        latency=_f(kraktak.DOA_IDX_LATENCY_MS, 0.0),
        station=parts[kraktak.DOA_IDX_STATION_ID],
        latitude=lat,
        longitude=lon,
        gps_heading=_f(kraktak.DOA_IDX_GPS_HEADING),
        compass_heading=_f(kraktak.DOA_IDX_COMPASS_HEADING),
        sensor=parts[kraktak.DOA_IDX_HEADING_SENSOR],
        values=values,
    )


def settings_url_from_feed(feed_url: str) -> str:
    """Derive the ``settings.json`` URL from a DOA feed URL (same host:port)."""
    parts = urlsplit(feed_url)
    return urlunsplit((parts.scheme, parts.netloc, "/settings.json", "", ""))


class KrakTAKWorker(pytak.QueueWorker):
    """Poll the KrakenSDR DOA feed, convert to CoT, and enqueue for transmission."""

    def __init__(self, queue, config) -> None:
        super().__init__(queue, config)
        self.session: Optional[aiohttp.ClientSession] = None
        self._settings_position = None  # cached (lat, lon, station) fallback

    async def _fetch_settings_position(self, feed_url: str):
        """Fetch lat/lon/station from settings.json as a position fallback."""
        if self.session is None or self.session.closed:
            return None
        url = settings_url_from_feed(feed_url)
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            self._logger.debug("settings.json fetch failed: %s", exc)
            return None
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is None or lon is None:
            return None
        return (float(lat), float(lon), str(data.get("station_id", "")))

    async def _apply_position_fallback(self, doa: DOAValues, feed_url: str) -> None:
        """Backfill missing/zero position from settings.json (cached)."""
        if doa.latitude not in (None, 0.0) and doa.longitude not in (None, 0.0):
            return
        if self._settings_position is None:
            self._settings_position = await self._fetch_settings_position(feed_url)
        if self._settings_position:
            lat, lon, station = self._settings_position
            doa.latitude = lat
            doa.longitude = lon
            if not doa.station:
                doa.station = station

    async def handle_data(self, data: str, feed_url: str = "") -> None:
        """Parse the (possibly multi-VFO) DOA payload and enqueue CoT."""
        if not data or not data.strip():
            self._logger.debug("Empty DOA feed (no active signal).")
            return

        builders = kraktak.functions.selected_builders(self.config)
        if not builders:
            self._logger.warning("No valid COT_TYPES configured; nothing to emit.")
            return

        for line in data.splitlines():
            doa = parse_doa_csv(line)
            if doa is None:
                continue

            await self._apply_position_fallback(doa, feed_url)
            if doa.latitude is None or doa.longitude is None:
                self._logger.warning(
                    "No position available for station %s", doa.station
                )
                continue

            if not kraktak.functions.passes_filters(doa, self.config):
                continue

            for builder in builders:
                event = kraktak.cot_to_xml(doa, self.config, builder)
                if event:
                    await self.put_queue(event)

    async def get_feed(self, url: str) -> None:
        """Poll the DOA feed once and hand the payload to the data handler."""
        if self.session is None or self.session.closed:
            self._logger.error("Session is closed, cannot poll.")
            return

        headers = {"User-Agent": "KrakTAK", "Accept": "text/html"}
        self._logger.debug("Fetching DOA from %s", url)
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with self.session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status != 200:
                    self._logger.error("HTTP %s for %s", resp.status, url)
                    return
                data = await resp.text()
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Error polling %s: %s", url, exc)
            return

        await self.handle_data(data, feed_url=url)

    async def run(self, _=-1) -> None:
        """Main loop: poll the DOA feed on an interval."""
        url: Optional[str] = self.config.get("FEED_URL") or kraktak.DEFAULT_FEED_URL
        if not url:
            raise ValueError("Please specify a FEED_URL.")

        poll_interval: Union[int, str, None] = self.config.get("POLL_INTERVAL")
        if poll_interval in ("", None):
            poll_interval = kraktak.DEFAULT_POLL_INTERVAL

        self._logger.info("%s polling every %ss: %s", self.__class__.__name__,
                          poll_interval, url)

        async with aiohttp.ClientSession() as self.session:
            while True:
                await self.get_feed(url)
                await asyncio.sleep(int(poll_interval))

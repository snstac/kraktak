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
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlsplit, urlunsplit

import aiohttp

import pytak

import kraktak
from kraktak.config_loader import (
    KrakenServerConfig,
    load_kraken_servers,
    load_runtime_document,
    merge_server_config,
    runtime_path_from_config,
)
from kraktak.gps import get_gps_position
from kraktak.multicast import get_mirror
from kraktak.telemetry import STORE


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
    """Parse one CSV line of the KrakenSDR "Kraken App" DOA export."""
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
    """Poll one or more KrakenSDR DOA feeds, convert to CoT, enqueue for TAK."""

    def __init__(self, queue, config) -> None:
        super().__init__(queue, config)
        self.session: Optional[aiohttp.ClientSession] = None
        self._settings_cache: Dict[str, Optional[Tuple[float, float, str]]] = {}
        self._runtime_overlay: dict = {}
        self._mirror = get_mirror(config)

    async def put_queue(self, data: bytes) -> None:
        """Transmit via PyTAK and optionally mirror to ATAK multicast."""
        await super().put_queue(data)
        if self._mirror:
            await self._mirror.send(data)

    async def _fetch_settings_position(
        self, feed_url: str
    ) -> Optional[Tuple[float, float, str]]:
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

    async def _apply_position_fallback(
        self, doa: DOAValues, feed_url: str, cfg: dict
    ) -> None:
        if doa.latitude not in (None, 0.0) and doa.longitude not in (None, 0.0):
            return

        lat, lon = get_gps_position(cfg)
        if lat is not None and lon is not None:
            doa.latitude = lat
            doa.longitude = lon
            return

        if feed_url not in self._settings_cache:
            self._settings_cache[feed_url] = await self._fetch_settings_position(
                feed_url
            )
        cached = self._settings_cache.get(feed_url)
        if cached:
            doa.latitude, doa.longitude, station = cached
            if not doa.station and station:
                doa.station = station

    async def handle_data(
        self,
        data: str,
        feed_url: str,
        server: KrakenServerConfig,
        cfg: dict,
    ) -> int:
        """Parse DOA payload and enqueue CoT. Returns number of events sent."""
        if not data or not data.strip():
            self._logger.debug("Empty DOA feed from %s", feed_url)
            return 0

        builders = kraktak.functions.selected_builders(cfg)
        if not builders:
            return 0

        sent = 0
        first_doa = None
        for line in data.splitlines():
            doa = parse_doa_csv(line)
            if doa is None:
                continue
            if server.station:
                doa.station = str(server.station)
            if first_doa is None:
                first_doa = doa

            await self._apply_position_fallback(doa, feed_url, cfg)
            if doa.latitude is None or doa.longitude is None:
                self._logger.warning(
                    "No position for station %s (%s)", doa.station, feed_url
                )
                continue

            if not kraktak.functions.passes_filters(doa, cfg):
                continue

            for builder in builders:
                event = kraktak.cot_to_xml(doa, cfg, builder)
                if event:
                    await self.put_queue(event)
                    sent += 1

        if first_doa is not None:
            STORE.record_poll(
                feed_url,
                first_doa.station,
                reachable=True,
                latitude=first_doa.latitude,
                longitude=first_doa.longitude,
                doa_angle=first_doa.max_doa_angle,
                confidence=first_doa.confidence,
                rssi=first_doa.rssi,
            )
        if sent:
            STORE.record_packets(sent)
        return sent

    async def poll_server(self, server: KrakenServerConfig) -> None:
        """Poll one KrakenSDR feed."""
        if self.session is None or self.session.closed:
            return

        feed_url = server.feed_url
        cfg = merge_server_config(self.config, server)
        if self._runtime_overlay.get("doa_ignore_start") not in (None, ""):
            cfg["DOA_IGNORE_START"] = self._runtime_overlay["doa_ignore_start"]
        if self._runtime_overlay.get("doa_ignore_end") not in (None, ""):
            cfg["DOA_IGNORE_END"] = self._runtime_overlay["doa_ignore_end"]
        headers = {"User-Agent": "KrakTAK", "Accept": "text/html"}
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with self.session.get(
                feed_url, headers=headers, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    self._logger.error("HTTP %s for %s", resp.status, feed_url)
                    STORE.record_poll(
                        feed_url,
                        server.station or "",
                        reachable=False,
                        error=f"HTTP {resp.status}",
                    )
                    return
                data = await resp.text()
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Error polling %s: %s", feed_url, exc)
            STORE.record_poll(
                feed_url,
                server.station or "",
                reachable=False,
                error=str(exc),
            )
            return

        await self.handle_data(data, feed_url, server, cfg)

    async def run(self, _=-1) -> None:
        """Poll all configured Kraken servers on an interval."""
        poll_interval: Union[int, str, None] = self.config.get("POLL_INTERVAL")
        if poll_interval in ("", None):
            poll_interval = kraktak.DEFAULT_POLL_INTERVAL

        runtime_path = runtime_path_from_config(self.config)
        self._logger.info(
            "%s polling every %ss (runtime=%s)",
            self.__class__.__name__,
            poll_interval,
            runtime_path or "none",
        )

        async with aiohttp.ClientSession() as self.session:
            while True:
                self._runtime_overlay = load_runtime_document(runtime_path)
                self._mirror = get_mirror(self.config, self._runtime_overlay)

                servers = load_kraken_servers(self.config, runtime_path)
                if not servers:
                    raise ValueError("No Kraken servers configured.")

                interval = self._runtime_overlay.get("poll_interval", poll_interval)
                for server in servers:
                    await self.poll_server(server)

                await asyncio.sleep(int(interval))

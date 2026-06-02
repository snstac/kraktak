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

"""Optional duplicate CoT transmission to the ATAK mesh multicast group."""

from __future__ import annotations

import asyncio
import logging
import socket
from configparser import SectionProxy
from typing import Optional
from urllib.parse import urlparse

import kraktak

Logger = logging.getLogger(__name__)


class MulticastMirror:
    """Send a copy of each CoT payload to a UDP multicast destination."""

    def __init__(self, host: str, port: int) -> None:
        self._addr = (host, port)
        self._sock: Optional[socket.socket] = None

    @classmethod
    def from_config(cls, config) -> Optional["MulticastMirror"]:
        url = config.get("COT_MULTICAST_URL")
        if url in (None, ""):
            enabled = str(
                config.get("ENABLE_MULTICAST_MIRROR", kraktak.DEFAULT_ENABLE_MULTICAST)
            ).lower() in ("1", "true", "yes")
            if not enabled:
                return None
            url = kraktak.DEFAULT_COT_MULTICAST_URL
        parts = urlparse(str(url))
        host = parts.hostname or "239.2.3.1"
        port = parts.port or 6969
        return cls(host, port)

    def open(self) -> None:
        if self._sock is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self._sock = sock
        Logger.info("Multicast mirror enabled: %s:%s", self._addr[0], self._addr[1])

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    async def send(self, data: bytes) -> None:
        if not data or self._sock is None:
            return
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None, self._sock.sendto, data, self._addr
            )
        except OSError as exc:
            Logger.warning("Multicast mirror send failed: %s", exc)


def get_mirror(config, overlay: Optional[dict] = None) -> Optional[MulticastMirror]:
    """Build a mirror from config plus optional runtime overlay dict."""
    merged = dict(overlay or {})
    if isinstance(config, SectionProxy):
        for key in config.keys():
            if key not in merged:
                merged[key] = config.get(key)
    else:
        for key, val in dict(config or {}).items():
            if key not in merged:
                merged[key] = val
    if "enable_multicast_mirror" in merged:
        merged["ENABLE_MULTICAST_MIRROR"] = merged["enable_multicast_mirror"]
    mirror = MulticastMirror.from_config(merged)
    if mirror:
        mirror.open()
    return mirror

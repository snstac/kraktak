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

"""Optional gpsd position source (Kraken CSV / settings.json remain fallbacks)."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

Logger = logging.getLogger(__name__)

_gpsd_connected = False


def gpsd_enabled(config) -> bool:
    return str(config.get("ENABLE_GPSD", "")).lower() in ("1", "true", "yes")


def get_gps_position(config) -> Tuple[Optional[float], Optional[float]]:
    """Return (lat, lon) from gpsd if enabled and available."""
    global _gpsd_connected  # noqa: PLW0603
    if not gpsd_enabled(config):
        return None, None
    try:
        import gpsd  # type: ignore
    except ImportError:
        Logger.warning(
            "ENABLE_GPSD is set but gpsd-py3 is not installed "
            "(pip install kraktak[gpsd])"
        )
        return None, None

    try:
        if not _gpsd_connected:
            host = config.get("GPSD_HOST", "127.0.0.1")
            port = int(config.get("GPSD_PORT", "2947"))
            gpsd.connect(host=host, port=port)
            _gpsd_connected = True
        packet = gpsd.get_current()
        lat = getattr(packet, "lat", None)
        lon = getattr(packet, "lon", None)
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    except Exception as exc:  # noqa: BLE001
        Logger.debug("gpsd unavailable: %s", exc)
        _gpsd_connected = False
    return None, None

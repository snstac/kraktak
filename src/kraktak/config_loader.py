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

"""Configuration loading: multi-Kraken servers and runtime JSON overrides."""

from __future__ import annotations

import json
import os
from configparser import SectionProxy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import kraktak


@dataclass
class KrakenServerConfig:
    """One KrakenSDR DOA source with optional per-server overrides."""

    feed_url: str
    station: Optional[str] = None
    doa_ignore_start: Optional[Union[int, float, str]] = None
    doa_ignore_end: Optional[Union[int, float, str]] = None
    persist_lob: Optional[bool] = None
    lob_length_m: Optional[float] = None
    min_confidence: Optional[float] = None
    min_rssi: Optional[float] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "KrakenServerConfig":
        """Build from dashboard/JSON (supports Canary-style ``ip`` field)."""
        feed = raw.get("feed_url") or raw.get("url")
        if not feed and raw.get("ip"):
            ip = str(raw["ip"]).strip()
            port = raw.get("port", 8081)
            feed = f"http://{ip}:{port}/DOA_value.html"
        if not feed:
            raise ValueError("Kraken server entry requires feed_url or ip")

        return cls(
            feed_url=str(feed).strip(),
            station=raw.get("station") or raw.get("station_id"),
            doa_ignore_start=raw.get("doa_ignore_start", raw.get("start_angle")),
            doa_ignore_end=raw.get("doa_ignore_end", raw.get("end_angle")),
            persist_lob=raw.get("persist_lob", raw.get("persist_uid_line")),
            lob_length_m=_lob_length_from_raw(
                raw.get("lob_length_m", raw.get("line_distance"))
            ),
            min_confidence=_float_or_none(raw.get("min_confidence")),
            min_rssi=_float_or_none(raw.get("min_rssi")),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "feed_url": self.feed_url,
            "station": self.station,
            "doa_ignore_start": self.doa_ignore_start,
            "doa_ignore_end": self.doa_ignore_end,
            "persist_lob": self.persist_lob,
            "lob_length_m": self.lob_length_m,
            "min_confidence": self.min_confidence,
            "min_rssi": self.min_rssi,
        }


def _float_or_none(val) -> Optional[float]:
    if val is None or val == "":
        return None
    return float(val)


def _lob_length_from_raw(val) -> Optional[float]:
    """Parse LOB length; Canary ``line_distance`` is in kilometers."""
    if val is None or val == "":
        return None
    meters = float(val)
    if meters < 1000:
        meters *= 1000.0
    return meters


def _parse_servers_json(text: str) -> List[KrakenServerConfig]:
    data = json.loads(text)
    if isinstance(data, dict) and "kraken_servers" in data:
        data = data["kraken_servers"]
    if not isinstance(data, list):
        raise ValueError("KRAKEN_SERVERS must be a JSON array")
    return [KrakenServerConfig.from_dict(entry) for entry in data]


def load_runtime_document(path: str) -> Dict[str, Any]:
    """Load dashboard-saved JSON (returns empty dict if missing)."""
    if not path or not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_runtime_document(path: str, document: Dict[str, Any]) -> None:
    abspath = os.path.abspath(path)
    parent = os.path.dirname(abspath)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(abspath, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2)


def load_kraken_servers(
    config: Union[SectionProxy, dict],
    runtime_path: Optional[str] = None,
) -> List[KrakenServerConfig]:
    """Resolve the list of Kraken feeds to poll.

    Precedence: runtime JSON ``kraken_servers`` > ``KRAKEN_SERVERS`` in config >
    legacy single ``FEED_URL``.
    """
    config = config or {}
    runtime_path = runtime_path or config.get("RUNTIME_CONFIG") or ""
    if runtime_path:
        doc = load_runtime_document(runtime_path)
        if doc.get("kraken_servers"):
            return [
                KrakenServerConfig.from_dict(s) for s in doc["kraken_servers"]
            ]

    raw = config.get("KRAKEN_SERVERS")
    if raw not in (None, ""):
        return _parse_servers_json(str(raw))

    feed = config.get("FEED_URL") or kraktak.DEFAULT_FEED_URL
    return [
        KrakenServerConfig(
            feed_url=str(feed),
            station=config.get("STATION_ID"),
            doa_ignore_start=config.get("DOA_IGNORE_START"),
            doa_ignore_end=config.get("DOA_IGNORE_END"),
            persist_lob=_bool_from_config(config.get("PERSIST_LOB")),
            lob_length_m=_float_or_none(
                config.get("LOB_LENGTH_M") or config.get("LOB_LENGTH_KM")
            ),
        )
    ]


def merge_server_config(
    global_config: Union[SectionProxy, dict],
    server: KrakenServerConfig,
) -> dict:
    """Build an effective config dict for CoT builders and filters."""
    if isinstance(global_config, SectionProxy):
        base = {k: global_config.get(k) for k in global_config.keys()}
    else:
        base = dict(global_config)
    if server.doa_ignore_start not in (None, ""):
        base["DOA_IGNORE_START"] = server.doa_ignore_start
    if server.doa_ignore_end not in (None, ""):
        base["DOA_IGNORE_END"] = server.doa_ignore_end
    if server.persist_lob is not None:
        base["PERSIST_LOB"] = "true" if server.persist_lob else "false"
    if server.lob_length_m is not None:
        base["LOB_LENGTH_M"] = str(server.lob_length_m)
    elif base.get("LOB_LENGTH_KM") and not base.get("LOB_LENGTH_M"):
        km = _float_or_none(base.get("LOB_LENGTH_KM"))
        if km is not None:
            base["LOB_LENGTH_M"] = str(km * 1000.0)
    if server.min_confidence is not None:
        base["MIN_CONFIDENCE"] = str(server.min_confidence)
    if server.min_rssi is not None:
        base["MIN_RSSI"] = str(server.min_rssi)
    return base


def runtime_path_from_config(config: Union[SectionProxy, dict]) -> str:
    return str(
        config.get("RUNTIME_CONFIG")
        or os.getenv("RUNTIME_CONFIG", kraktak.DEFAULT_RUNTIME_CONFIG)
    )


def _bool_from_config(val) -> Optional[bool]:
    if val is None or val == "":
        return None
    return str(val).lower() in ("1", "true", "yes")

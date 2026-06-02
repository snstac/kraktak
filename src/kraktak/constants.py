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

"""KrakTAK Constants."""

# Default KrakenSDR DOA value feed URL (the "Kraken App" CSV export).
DEFAULT_FEED_URL: str = "http://krakensdr:8081/DOA_value.html"

# Default feed polling interval, in seconds.
DEFAULT_POLL_INTERVAL: str = "3"

# Radius of the Earth, in meters (WGS-84 mean).
EARTH_RADIUS_M: float = 6371000.0

# Default rendered length of a Line-of-Bearing, in meters.
DEFAULT_LOB_LENGTH_M: float = 10000.0

# CoT product families / device identifiers used in __lob / __cep details.
DEFAULT_COT_FAMILY: str = "com.snstac.kraktak"
DEFAULT_DEVICE_TYPE: str = "KrakenSDR"

# Which CoT renderings to emit per DOA record (comma separated).
# Options: lob, bearing_line, range_bearing, sensor, cep
DEFAULT_COT_TYPES: str = "lob,bearing_line"

# Minimum confidence (0-99) and RSSI (dB) required to emit CoT. Empty = no filter.
DEFAULT_MIN_CONFIDENCE: str = ""
DEFAULT_MIN_RSSI: str = ""

# ATAK mesh multicast (duplicate every CoT when ENABLE_MULTICAST_MIRROR=true).
DEFAULT_COT_MULTICAST_URL: str = "udp://239.2.3.1:6969"
DEFAULT_ENABLE_MULTICAST: str = "false"

# Dashboard-written JSON overrides (reloaded each poll).
DEFAULT_RUNTIME_CONFIG: str = "kraktak-runtime.json"

# --- Control plane (TAK -> KrakenSDR) ---------------------------------------

# Whether to enable inbound control (retune, gain, coordinates) from TAK.
DEFAULT_ENABLE_CONTROL: bool = False

# Control backend: auto | settings_json | api_agent | middleware
DEFAULT_CONTROL_BACKEND: str = "auto"

# kraken_api_agent default port.
DEFAULT_API_AGENT_PORT: int = 8181

# krakensdr_doa middleware default port.
DEFAULT_MIDDLEWARE_PORT: int = 8042

# settings.json upload / DSP web port.
DEFAULT_DSP_PORT: int = 8081

# Valid KrakenSDR uniform gain values (dB).
VALID_GAINS = (
    0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6, 19.7, 20.7,
    22.9, 25.4, 28.0, 29.7, 32.8, 33.8, 36.4, 37.2, 38.6, 40.2, 42.1, 43.4,
    43.9, 44.5, 48.0, 49.6,
)

# Tuner frequency limits (MHz) accepted by the RTL-SDR front-ends.
MIN_TUNE_MHZ: float = 24.0
MAX_TUNE_MHZ: float = 1766.0

# --- DOA CSV column indices ("Kraken App" format) ---------------------------
# See: https://forum.krakenrf.com/t/krakensdr-api-endpoints-and-documentation/171
DOA_IDX_EPOCH_MS: int = 0
DOA_IDX_MAX_ANGLE: int = 1
DOA_IDX_CONFIDENCE: int = 2
DOA_IDX_RSSI: int = 3
DOA_IDX_FREQUENCY_HZ: int = 4
DOA_IDX_ARRANGEMENT: int = 5
DOA_IDX_LATENCY_MS: int = 6
DOA_IDX_STATION_ID: int = 7
DOA_IDX_LATITUDE: int = 8
DOA_IDX_LONGITUDE: int = 9
DOA_IDX_GPS_HEADING: int = 10
DOA_IDX_COMPASS_HEADING: int = 11
DOA_IDX_HEADING_SENSOR: int = 12
# Indices 13-16 reserved; full 360-degree DOA power array begins at 17.
DOA_IDX_POWER_START: int = 17
DOA_MIN_FIELDS: int = DOA_IDX_POWER_START

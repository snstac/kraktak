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

"""KrakTAK: Next-gen KrakenSDR to TAK bridge with TAK-side control."""

from .constants import (  # NOQA
    DEFAULT_API_AGENT_PORT,
    DEFAULT_CONTROL_BACKEND,
    DEFAULT_COT_FAMILY,
    DEFAULT_COT_MULTICAST_URL,
    DEFAULT_COT_TYPES,
    DEFAULT_ENABLE_MULTICAST,
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_DEVICE_TYPE,
    DEFAULT_DSP_PORT,
    DEFAULT_ENABLE_CONTROL,
    DEFAULT_FEED_URL,
    DEFAULT_LOB_LENGTH_M,
    DEFAULT_MIDDLEWARE_PORT,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_RSSI,
    DEFAULT_POLL_INTERVAL,
    DOA_IDX_ARRANGEMENT,
    DOA_IDX_COMPASS_HEADING,
    DOA_IDX_CONFIDENCE,
    DOA_IDX_EPOCH_MS,
    DOA_IDX_FREQUENCY_HZ,
    DOA_IDX_GPS_HEADING,
    DOA_IDX_HEADING_SENSOR,
    DOA_IDX_LATENCY_MS,
    DOA_IDX_LATITUDE,
    DOA_IDX_LONGITUDE,
    DOA_IDX_MAX_ANGLE,
    DOA_IDX_POWER_START,
    DOA_IDX_RSSI,
    DOA_IDX_STATION_ID,
    DOA_MIN_FIELDS,
    EARTH_RADIUS_M,
    MAX_TUNE_MHZ,
    MIN_TUNE_MHZ,
    VALID_GAINS,
)

from . import functions  # NOQA

from .functions import (  # NOQA
    cot_to_xml,
    create_tasks,
    gen_geochat,
    selected_builders,
)

from .classes import DOAValues, KrakTAKWorker, parse_doa_csv  # NOQA

__version__ = "10.2.0"

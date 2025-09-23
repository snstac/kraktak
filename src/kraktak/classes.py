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

from typing import Optional, Union

import aiohttp
# import gps.aiogps

import pytak
import kraktak
from dataclasses import dataclass


@dataclass
class DOAValues:
    """Data class for Kraken DOA values."""
    timestamp: int
    max_doa_angle: int
    confidence: int
    rssi: int
    frequency: int
    antenna: str
    latency: float
    station: str
    latitude: float
    longitude: float
    gps_heading: int
    compass_heading: int
    sensor: str
    values: list
    second_point: Optional[tuple] = None
    uplink_rssi: Optional[int] = 0
    downlink_rssi: Optional[int] = 0
    tag: Optional[str] = ""
    error_radius: Optional[float] = 0.0
    comments: Optional[str] = ""


class KrakTAKWorker(pytak.QueueWorker):
    """Process Kraken DOA values, convert to CoT, and enqueue for transmission."""

    def __init__(self, queue, config) -> None:
        """Initialize this class."""
        super().__init__(queue, config)
        self.session: Optional[aiohttp.ClientSession] = None
        self.position = None

    async def handle_data(self, data: Union[list, dict]) -> None:
        """Handle Data: Render to CoT, put on TX queue."""
        if not data:
            self._logger.warning("Empty data ")
            return

        # If the response is a comma-separated string, split it
        kraken_data = data.strip()
        if not ',' in kraken_data:
            self._logger.warning("Data is not in expected format: %s", kraken_data)
            return
    
        data_parts = kraken_data.split(",")
        if len(data_parts) < 10:
            self._logger.warning("Data does not contain enough parts: %s", kraken_data)
            return

        values = [float(v.strip()) for v in data_parts[17:]]

        # Create a DOAValues instance
        doa_values = DOAValues(
            timestamp=int(data_parts[0]),
            max_doa_angle=int(float(data_parts[1])),
            confidence=int(float(data_parts[2])),
            rssi=int(float(data_parts[3])),
            frequency=int(data_parts[4]),
            antenna=data_parts[5].strip(),
            latency=float(data_parts[6]),
            station=data_parts[7].strip(),
            latitude=float(data_parts[8]),
            longitude=float(data_parts[9]),
            gps_heading=int(data_parts[10]),
            compass_heading=int(data_parts[11]),
            sensor=data_parts[12].strip(),
            values=values
        )

        cot_funcs = ["doa_to_cot_line_xml", "doa_to_cot_sensor_xml", "doa_to_cot_lob_xml"]
        # cot_funcs = ["doa_to_cot_lob_xml"]
        for cotf in cot_funcs:
            event = kraktak.cot_to_xml(doa_values, self.config, cotf)
            print(event)
            await self.put_queue(event)

    async def get_feed(self, url: bytes) -> None:
        """Poll the feed and pass data to the data handler."""
        if self.session is None or self.session.closed:
            self._logger.error("Session is closed, cannot proceed.")
            return

        url_b = str(url)
        headers = {
            "User-Agent": "KrakTAK/1.0 (1)",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        self._logger.debug("Fetching data from %s", url)
        async with self.session.get(url_b, headers=headers) as resp:
            if resp.status != 200:
                response_content = await resp.text()
                self._logger.error("Received HTTP Status %s for %s", resp.status, url)
                self._logger.error(response_content)
                return

            data = await resp.text()
            if not data:
                self._logger.debug("Empty response from %s", url)
                return

            self._logger.info(
                "Retrieved %s records.", str(len(data) or "No")
            )
            await self.handle_data(data)

    # async def _start_gps_session(self) -> gps.aiogps.aiogps:
    #     """Start a GPS session if configured."""
    #     await asyncio.sleep(0)  # Yield control to the event loop

    #     gps_config = self.config.get("GPS_CONFIG")
    #     gps_config = {
    #         "connection_args": {"host": "127.0.0.1", "port": 2947},
    #         "connection_type": "tcp",
    #         "connection_timeout": 5,
    #         "reconnect": 0,  # do not try to reconnect, raise exceptions
    #         "alive_opts": {
    #             "rx_timeout": 5
    #         }

    #     }
        
    #     if not gps_config:
    #         self._logger.warning("No GPS configuration found, skipping GPS session.")
    #         return None

    #     try:
    #         self.gps_session = await gps.aiogps.start_gps_session(gps_config)
    #         self._logger.info("GPS session started successfully.")
    #     except Exception as e:
    #         self._logger.error("Failed to start GPS session: %s", str(e))
    #         return None

    async def run(self, _=-1) -> None:
        """Run this Thread, Reads from Pollers."""

        url: Optional[bytes] = self.config.get("FEED_URL")
        if not url or url == "":
            raise ValueError("Please specify a FEED_URL.")

        poll_interval: Union[int, str, None] = self.config.get("POLL_INTERVAL")
        if poll_interval == "" or poll_interval is None:
            self._logger.info(
                "POLL_INTERVAL not set, using default of %s seconds.",
                kraktak.DEFAULT_POLL_INTERVAL,
            )
            poll_interval = kraktak.DEFAULT_POLL_INTERVAL

        self._logger.info(
            "Running %s at %ss for %s", self.__class__, poll_interval, url
        )

        async with aiohttp.ClientSession() as self.session:
            # async with self._start_gps_session() as self.gps_session:
            while True:
                self._logger.info(
                    "%s polling every %ss: %s", self.__class__, poll_interval, url
                )
                await self.get_feed(url)
                await asyncio.sleep(int(poll_interval))

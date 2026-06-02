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

"""KrakTAK control plane: drive a KrakenSDR from inbound TAK messages.

A :class:`KrakenControlWorker` consumes CoT received from the TAK server (the
PyTAK ``rx_queue``), parses control commands from GeoChat text or a
``<__krakencmd>`` detail element, and applies them via a pluggable
:class:`KrakenController` backend (settings.json upload, kraken_api_agent, or
the krakensdr_doa middleware).
"""

import xml.etree.ElementTree as ET

from typing import Optional, Tuple
from urllib.parse import urlsplit

import aiohttp

import pytak

import kraktak


# --------------------------------------------------------------------------- #
# Command parsing
# --------------------------------------------------------------------------- #
class Command:
    """A parsed control command: ``action`` + keyword ``args``."""

    def __init__(self, action: str, **args):
        self.action = action
        self.args = args

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Command({self.action!r}, {self.args!r})"


def parse_chat_command(text: str) -> Optional[Command]:
    """Parse a GeoChat message like ``kraken freq 462.5625`` into a Command."""
    if not text:
        return None
    tokens = text.strip().split()
    if not tokens or tokens[0].lower() != "kraken":
        return None
    tokens = tokens[1:]
    if not tokens:
        return None

    verb = tokens[0].lower()
    rest = tokens[1:]
    try:
        if verb in ("freq", "frequency") and rest:
            return Command("set_frequency", freq=float(rest[0]))
        if verb == "gain" and rest:
            return Command("set_gain", gain=float(rest[0]))
        if verb == "vfo" and len(rest) >= 2:
            return Command("set_vfo_frequency", index=int(rest[0]),
                           vfo_freq=float(rest[1]))
        if verb in ("bw", "bandwidth") and len(rest) >= 2:
            return Command("set_vfo_bandwidth", index=int(rest[0]),
                           vfo_bw=float(rest[1]))
        if verb in ("coord", "coordinates") and len(rest) >= 2:
            return Command("set_coordinates", latitude=float(rest[0]),
                           longitude=float(rest[1]))
        if verb == "status":
            return Command("status")
    except (ValueError, IndexError):
        return None
    return None


def parse_cot_command(cot: ET.Element) -> Optional[Command]:
    """Parse a control command from a received CoT event.

    Supports both a ``<__krakencmd>`` detail element and GeoChat ``<remarks>``
    text.
    """
    detail = cot.find("detail")
    if detail is None:
        return None

    cmd_el = detail.find("__krakencmd")
    if cmd_el is not None:
        action = cmd_el.get("action", "")
        args = {k: v for k, v in cmd_el.attrib.items() if k != "action"}
        for key in ("freq", "gain", "vfo_freq", "vfo_bw", "latitude", "longitude"):
            if key in args:
                args[key] = float(args[key])
        if "index" in args:
            args["index"] = int(args["index"])
        if action:
            return Command(action, **args)

    # GeoChat: <detail><remarks>...</remarks> or <__chat><...>
    remarks = detail.find("remarks")
    if remarks is not None and remarks.text:
        cmd = parse_chat_command(remarks.text)
        if cmd:
            return cmd
    chat = detail.find("__chat")
    if chat is not None:
        msg = chat.get("message") or ""
        return parse_chat_command(msg)
    return None


def get_sender(cot: ET.Element) -> Tuple[str, str]:
    """Return (uid, callsign) of the CoT sender, for addressing acks."""
    uid = cot.get("uid", "kraktak")
    callsign = ""
    detail = cot.find("detail")
    if detail is not None:
        contact = detail.find("contact")
        if contact is not None:
            callsign = contact.get("callsign", "")
    return uid, callsign


# --------------------------------------------------------------------------- #
# Controller backends
# --------------------------------------------------------------------------- #
# Per-request timeouts so a slow/unreachable KrakenSDR never stalls the worker.
PROBE_TIMEOUT = aiohttp.ClientTimeout(total=4)
OP_TIMEOUT = aiohttp.ClientTimeout(total=12)


class KrakenController:
    """Base class for KrakenSDR control backends."""

    def __init__(self, host: str, session: aiohttp.ClientSession, config=None):
        self.host = host
        self.session = session
        self.config = config or {}

    async def available(self) -> bool:
        raise NotImplementedError

    async def set_frequency(self, freq: float, gain: Optional[float] = None) -> None:
        raise NotImplementedError

    async def set_gain(self, gain: float) -> None:
        raise NotImplementedError

    async def set_vfo_frequency(self, index: int, vfo_freq: float) -> None:
        raise NotImplementedError

    async def set_vfo_bandwidth(self, index: int, vfo_bw: float) -> None:
        raise NotImplementedError

    async def set_coordinates(self, latitude: float, longitude: float, **kw) -> None:
        raise NotImplementedError

    async def get_config(self) -> dict:
        raise NotImplementedError


class ApiAgentController(KrakenController):
    """kraken_api_agent REST backend (default port 8181)."""

    def _base(self) -> str:
        port = self.config.get("API_AGENT_PORT", kraktak.DEFAULT_API_AGENT_PORT)
        return f"http://{self.host}:{port}/api/krakensdr"

    async def _get(self, path: str, timeout=OP_TIMEOUT, **params) -> dict:
        async with self.session.get(
            f"{self._base()}/{path}", params=params, timeout=timeout
        ) as resp:
            return await resp.json(content_type=None)

    async def available(self) -> bool:
        try:
            data = await self._get("get_config", timeout=PROBE_TIMEOUT)
            return data.get("errcode", 1) == 0
        except Exception:  # noqa: BLE001
            return False

    async def set_frequency(self, freq, gain=None):
        params = {"freq": freq}
        if gain is not None:
            params["gain"] = gain
        await self._get("set_frequency", **params)

    async def set_gain(self, gain):
        await self._get("set_gain", gain=gain)

    async def set_vfo_frequency(self, index, vfo_freq):
        await self._get("set_vfo_frequency", vfo_index=index, vfo_freq=vfo_freq)

    async def set_vfo_bandwidth(self, index, vfo_bw):
        await self._get("set_vfo_bandwidth", vfo_index=index, vfo_bw=vfo_bw)

    async def set_coordinates(self, latitude, longitude, **kw):
        await self._get("set_coordinates", latitude=latitude, longitude=longitude, **kw)

    async def get_config(self):
        return (await self._get("get_config")).get("settings", {})


class MiddlewareController(KrakenController):
    """krakensdr_doa middleware backend (default port 8042, GET/POST /settings)."""

    def _url(self) -> str:
        port = self.config.get("MIDDLEWARE_PORT", kraktak.DEFAULT_MIDDLEWARE_PORT)
        return f"http://{self.host}:{port}/settings"

    async def available(self) -> bool:
        try:
            async with self.session.get(self._url(), timeout=PROBE_TIMEOUT) as resp:
                return resp.status == 200
        except Exception:  # noqa: BLE001
            return False

    async def get_config(self) -> dict:
        async with self.session.get(self._url(), timeout=OP_TIMEOUT) as resp:
            return await resp.json(content_type=None)

    async def _post(self, settings: dict) -> None:
        async with self.session.post(
            self._url(), json=settings, timeout=OP_TIMEOUT
        ) as resp:
            await resp.read()

    async def set_frequency(self, freq, gain=None):
        s = await self.get_config()
        s["center_freq"] = freq
        if gain is not None:
            s["uniform_gain"] = gain
        await self._post(s)

    async def set_gain(self, gain):
        s = await self.get_config()
        s["uniform_gain"] = gain
        await self._post(s)

    async def set_vfo_frequency(self, index, vfo_freq):
        s = await self.get_config()
        s[f"vfo_freq_{index}"] = vfo_freq
        await self._post(s)

    async def set_vfo_bandwidth(self, index, vfo_bw):
        s = await self.get_config()
        s[f"vfo_bw_{index}"] = vfo_bw
        await self._post(s)

    async def set_coordinates(self, latitude, longitude, **kw):
        s = await self.get_config()
        s["latitude"] = float(latitude)
        s["longitude"] = float(longitude)
        s.update({k: v for k, v in kw.items() if k in (
            "heading", "location_source", "gps_fixed_heading")})
        await self._post(s)


class SettingsJsonController(KrakenController):
    """Portable backend: GET /settings.json, mutate, multipart-upload to /upload.

    Requires the krakensdr_doa "remote control" path; this controller flips
    ``en_remote_control`` on its first push so the DSP applies remote settings.
    """

    def _port(self) -> int:
        return self.config.get("DSP_PORT", kraktak.DEFAULT_DSP_PORT)

    def _settings_url(self) -> str:
        return f"http://{self.host}:{self._port()}/settings.json"

    def _upload_url(self) -> str:
        return f"http://{self.host}:{self._port()}/upload?path=/"

    async def available(self) -> bool:
        try:
            async with self.session.get(
                self._settings_url(), timeout=PROBE_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    return False
                await resp.json(content_type=None)
                return True
        except Exception:  # noqa: BLE001
            return False

    async def get_config(self) -> dict:
        async with self.session.get(
            self._settings_url(), timeout=OP_TIMEOUT
        ) as resp:
            return await resp.json(content_type=None)

    async def _push(self, settings: dict) -> None:
        import json

        settings["en_remote_control"] = True
        form = aiohttp.FormData()
        form.add_field(
            "path",
            json.dumps(settings),
            filename="settings.json",
            content_type="application/json",
        )
        async with self.session.post(
            self._upload_url(), data=form, timeout=OP_TIMEOUT
        ) as resp:
            await resp.read()

    async def set_frequency(self, freq, gain=None):
        s = await self.get_config()
        s["center_freq"] = freq
        if gain is not None:
            s["uniform_gain"] = gain
        await self._push(s)

    async def set_gain(self, gain):
        s = await self.get_config()
        s["uniform_gain"] = gain
        await self._push(s)

    async def set_vfo_frequency(self, index, vfo_freq):
        s = await self.get_config()
        s[f"vfo_freq_{index}"] = vfo_freq
        await self._push(s)

    async def set_vfo_bandwidth(self, index, vfo_bw):
        s = await self.get_config()
        s[f"vfo_bw_{index}"] = vfo_bw
        await self._push(s)

    async def set_coordinates(self, latitude, longitude, **kw):
        s = await self.get_config()
        s["latitude"] = float(latitude)
        s["longitude"] = float(longitude)
        s.update({k: v for k, v in kw.items() if k in (
            "heading", "location_source", "gps_fixed_heading")})
        await self._push(s)


BACKENDS = {
    "api_agent": ApiAgentController,
    "middleware": MiddlewareController,
    "settings_json": SettingsJsonController,
}

# Auto-detect probe order: prefer the richest API, fall back to the portable one.
AUTO_ORDER = ("api_agent", "middleware", "settings_json")


def control_host(config) -> str:
    """Resolve the KrakenSDR control host from KRAKEN_HOST or the FEED_URL."""
    host = config.get("KRAKEN_HOST")
    if host:
        return host
    feed = config.get("FEED_URL") or kraktak.DEFAULT_FEED_URL
    return urlsplit(feed).hostname or "krakensdr"


def validate(action: str, args: dict) -> Optional[str]:
    """Return an error string if the command args are out of range, else None."""
    if action == "set_frequency":
        f = args.get("freq")
        if f is None or f < kraktak.MIN_TUNE_MHZ or f > kraktak.MAX_TUNE_MHZ:
            return f"freq must be {kraktak.MIN_TUNE_MHZ}-{kraktak.MAX_TUNE_MHZ} MHz"
    if action == "set_gain":
        if float(args.get("gain", -1)) not in kraktak.VALID_GAINS:
            return "invalid gain (see KrakenSDR valid gains)"
    return None


# --------------------------------------------------------------------------- #
# Worker
# --------------------------------------------------------------------------- #
class KrakenControlWorker(pytak.QueueWorker):
    """Consume inbound CoT and drive the KrakenSDR control backend."""

    def __init__(self, queue, config, tx_queue=None) -> None:
        super().__init__(queue, config)
        self.tx_queue = tx_queue
        self.session: Optional[aiohttp.ClientSession] = None
        self.controller: Optional[KrakenController] = None

    async def _select_controller(self) -> Optional[KrakenController]:
        host = control_host(self.config)
        backend = (self.config.get("CONTROL_BACKEND")
                   or kraktak.DEFAULT_CONTROL_BACKEND).lower()

        if backend != "auto" and backend in BACKENDS:
            ctrl = BACKENDS[backend](host, self.session, self.config)
            return ctrl

        for name in AUTO_ORDER:
            ctrl = BACKENDS[name](host, self.session, self.config)
            if await ctrl.available():
                self._logger.info("Control backend: %s @ %s", name, host)
                return ctrl
        self._logger.error("No KrakenSDR control backend reachable at %s", host)
        return None

    async def _ack(self, sender_uid: str, text: str) -> None:
        if self.tx_queue is None:
            return
        chat = kraktak.gen_geochat(text, self.config, target_uid=sender_uid)
        if chat:
            await self.tx_queue.put(chat)

    async def handle_data(self, data) -> None:
        """Parse a received CoT payload and apply any control command."""
        try:
            xml = data.decode() if isinstance(data, (bytes, bytearray)) else str(data)
            cot = ET.fromstring(xml)
        except (ET.ParseError, UnicodeDecodeError):
            return

        cmd = parse_cot_command(cot)
        if cmd is None:
            return

        sender_uid, sender_cs = get_sender(cot)
        self._logger.info("Control command from %s: %s", sender_cs or sender_uid, cmd)

        if self.controller is None:
            self.controller = await self._select_controller()
        if self.controller is None:
            await self._ack(sender_uid, "KrakTAK: no control backend reachable")
            return

        if cmd.action == "status":
            try:
                cfg = await self.controller.get_config()
                await self._ack(
                    sender_uid,
                    f"KrakTAK: {cfg.get('center_freq')} MHz gain "
                    f"{cfg.get('uniform_gain')} station {cfg.get('station_id')}",
                )
            except Exception as exc:  # noqa: BLE001
                await self._ack(sender_uid, f"KrakTAK status error: {exc}")
            return

        err = validate(cmd.action, cmd.args)
        if err:
            await self._ack(sender_uid, f"KrakTAK: {err}")
            return

        try:
            await getattr(self.controller, cmd.action)(**cmd.args)
            await self._ack(sender_uid, f"KrakTAK: {cmd.action} ok {cmd.args}")
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Control action failed: %s", exc)
            await self._ack(sender_uid, f"KrakTAK: {cmd.action} failed: {exc}")

    async def run(self, _=-1) -> None:
        self._logger.info("Running %s control plane", self.__class__.__name__)
        async with aiohttp.ClientSession() as self.session:
            while True:
                data = await self.queue.get()
                if data:
                    await self.handle_data(data)

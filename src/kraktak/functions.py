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

"""KrakTAK Functions: KrakenSDR DOA -> Cursor on Target.

CoT detail elements (``__lob``, ``__cep``, ``signalInfo``) are built to validate
against the MITRE/TAK CoT XSD reference set (see ``takcot-master/xsd``).
"""

import datetime
import logging
import math
import os
import random
import uuid
import xml.etree.ElementTree as ET

from configparser import SectionProxy
from typing import List, Optional, Tuple, Union

import pytak
import takline

import kraktak

APP_NAME = "kraktak"
Logger = logging.getLogger(__name__)
Debug = bool(os.getenv("DEBUG", ""))

COT_TAG = f"{APP_NAME}-1"

# Kraken station marker (parent for SPI / POI / target R&B links).
SENSOR_COT_TYPE = "a-f-G-U-C"
DEFAULT_POI_COLOR_ARGB = "-65536"
DEFAULT_POI_ICONSET = "COT_MAPPING_2525C/a-n/A"

# W3C XMLSchema-instance namespace, used for ``xsi:type`` on signalInfo.
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def to_rad(deg: float) -> float:
    """Convert degrees to radians."""
    return deg * math.pi / 180.0


def to_deg(rad: float) -> float:
    """Convert radians to degrees."""
    return rad * 180.0 / math.pi


def calculate_second_point(
    lat: float, lon: float, bearing_deg: float, distance_m: float
) -> Tuple[float, float]:
    """Project a point from (lat, lon) along a compass bearing for distance_m meters.

    Bearing is in compass convention (0 = North, 90 = East), matching the
    KrakenSDR "Max DOA Angle" output.
    """
    r = kraktak.EARTH_RADIUS_M
    lat1 = to_rad(lat)
    lon1 = to_rad(lon)
    bearing = to_rad(bearing_deg)
    ang = distance_m / r

    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang)
        + math.cos(lat1) * math.sin(ang) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(ang) * math.cos(lat1),
        math.cos(ang) - math.sin(lat1) * math.sin(lat2),
    )
    return (to_deg(lat2), to_deg(lon2))


def bearing_and_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> Tuple[float, float]:
    """Return (distance_m, initial_bearing_deg) between two points (Haversine)."""
    r = kraktak.EARTH_RADIUS_M
    phi1 = to_rad(lat1)
    phi2 = to_rad(lat2)
    dphi = to_rad(lat2 - lat1)
    dlambda = to_rad(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    distance = r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        dlambda
    )
    bearing = (to_deg(math.atan2(y, x)) + 360.0) % 360.0
    return (distance, bearing)


def bearing_to_color(bearing: float, alpha: int = 255) -> int:
    """Map a compass bearing (0-360) to a signed 32-bit ARGB color (Android style)."""
    hue = ((bearing % 360.0) + 360.0) % 360.0
    c = 1.0
    x = c * (1 - abs((hue / 60.0) % 2 - 1))
    if hue < 60:
        r, g, b = c, x, 0.0
    elif hue < 120:
        r, g, b = x, c, 0.0
    elif hue < 180:
        r, g, b = 0.0, c, x
    elif hue < 240:
        r, g, b = 0.0, x, c
    elif hue < 300:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    ri, gi, bi = round(r * 255), round(g * 255), round(b * 255)
    argb = ((alpha & 0xFF) << 24) | (ri << 16) | (gi << 8) | bi
    # Convert to signed 32-bit, as TAK expects.
    return argb - 0x100000000 if argb >= 0x80000000 else argb


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
def evaluate_angle_range(
    start_angle: Union[int, str, None],
    end_angle: Union[int, str, None],
    max_doa_angle: Union[int, float, str],
) -> bool:
    """Return True if ``max_doa_angle`` is OUTSIDE the exclusion wedge.

    A return of ``False`` means the angle falls inside the wedge and should be
    dropped. If either bound is unset, no wedge is applied (always True).
    """
    if start_angle is None or end_angle is None or start_angle == "" or end_angle == "":
        return True

    start = int(float(start_angle)) % 360
    end = int(float(end_angle)) % 360
    angle = int(float(max_doa_angle)) % 360

    if start <= end:
        in_exclusion = start <= angle <= end
    else:  # wedge wraps past 0
        in_exclusion = angle >= start or angle <= end
    return not in_exclusion


def passes_filters(data, config: Union[SectionProxy, dict, None] = None) -> bool:
    """Apply confidence/RSSI thresholds and the DOA exclusion wedge."""
    config = config or {}

    min_conf = config.get("MIN_CONFIDENCE", kraktak.DEFAULT_MIN_CONFIDENCE)
    if min_conf not in ("", None) and data.confidence < float(min_conf):
        Logger.debug("Dropped: confidence %s < %s", data.confidence, min_conf)
        return False

    min_rssi = config.get("MIN_RSSI", kraktak.DEFAULT_MIN_RSSI)
    if min_rssi not in ("", None) and data.rssi < float(min_rssi):
        Logger.debug("Dropped: rssi %s < %s", data.rssi, min_rssi)
        return False

    if not evaluate_angle_range(
        config.get("DOA_IGNORE_START"),
        config.get("DOA_IGNORE_END"),
        data.max_doa_angle,
    ):
        Logger.debug("Dropped: bearing %s in exclusion wedge", data.max_doa_angle)
        return False

    return True


# --------------------------------------------------------------------------- #
# Internal builders
# --------------------------------------------------------------------------- #
def _lob_length_m(config) -> float:
    val = config.get("LOB_LENGTH_M", "")
    if val not in ("", None):
        return float(val)
    km = config.get("LOB_LENGTH_KM", "")
    if km not in ("", None):
        return float(km) * 1000.0
    return kraktak.DEFAULT_LOB_LENGTH_M


def _target_fix_range_m(config) -> float:
    """Assumed emitter range (m) for SPI / target R&B; defaults to LOB length."""
    val = config.get("TARGET_FIX_RANGE_M", "")
    if val not in ("", None):
        return float(val)
    return _lob_length_m(config)


def _sensor_uid(data) -> str:
    return f"{COT_TAG}.KrakenSDR.{data.station}"


def _sensor_link_type(config) -> str:
    return config.get("COT_SENSOR_TYPE", SENSOR_COT_TYPE)


def _target_fix_endpoint(data, config) -> Tuple[float, float, float]:
    """Return (target_lat, target_lon, ground_range_m) along the DOA."""
    length_m = _target_fix_range_m(config)
    end_lat, end_lon = calculate_second_point(
        data.latitude, data.longitude, data.max_doa_angle, length_m
    )
    return end_lat, end_lon, length_m


def _annotate_kraktak_event(event: ET.Element, config) -> ET.Element:
    event.set("access", config.get("COT_ACCESS", pytak.DEFAULT_COT_ACCESS))
    event.set("qos", "1-r-c")
    return event


def _target_fix_stale_sec(config) -> int:
    return int(config.get("COT_STALE", pytak.DEFAULT_COT_STALE))


def _target_fix_remarks(data) -> str:
    return (
        f"DOA {data.max_doa_angle} deg | conf {data.confidence} | "
        f"rssi {data.rssi} dB"
    )


def _point_attrs(lat: float, lon: float, hae="0.0", ce="9999999.0", le="9999999.0"):
    return {
        "lat": str(lat),
        "lon": str(lon),
        "hae": str(hae),
        "ce": str(ce),
        "le": str(le),
    }


def _base_cot(
    data, config, uid: str, cot_type: str, lat: float, lon: float
) -> ET.Element:
    """Build a base CoT ``event`` with point + empty detail (flow-tags preserved)."""
    cot_stale = int(config.get("COT_STALE", pytak.DEFAULT_COT_STALE))
    cot = pytak.gen_cot_xml(
        lat=str(lat),
        lon=str(lon),
        ce="9999999.0",
        le="9999999.0",
        hae="9999999.0",
        uid=uid,
        cot_type=cot_type,
        stale=cot_stale,
    )
    cot.set("access", config.get("COT_ACCESS", pytak.DEFAULT_COT_ACCESS))
    cot.set("qos", "1-r-c")
    return cot


def _swap_detail(cot: ET.Element, detail: ET.Element) -> ET.Element:
    """Replace the auto-generated detail, preserving PyTAK ``_flow-tags_``."""
    old = cot.findall("detail")[0]
    detail.extend(old.findall("_flow-tags_"))
    cot.remove(old)
    cot.append(detail)
    return cot


def _signal_info(data, config) -> ET.Element:
    """Build a schema-valid ``signalInfo`` (xsi:type RF) for __lob/__cep details."""
    si = ET.Element("signalInfo")
    si.set(f"{{{XSI_NS}}}type", "RF")
    si.set("frequency", str(int(data.frequency)))
    si.set("rssi", str(float(data.rssi)))
    return si


# --------------------------------------------------------------------------- #
# Public CoT builders. Each takes (data: DOAValues, config) -> ET.Element|None
# --------------------------------------------------------------------------- #
def doa_to_cot_sensor(data, config=None) -> Optional[ET.Element]:
    """The KrakenSDR station itself, as a friendly ground sensor marker."""
    config = config or {}
    lat, lon = data.latitude, data.longitude
    if lat is None or lon is None:
        Logger.warning("No lat/lon for sensor CoT")
        return None

    uid = _sensor_uid(data)
    cot = _base_cot(data, config, uid, SENSOR_COT_TYPE, lat, lon)

    detail = ET.Element("detail")
    contact = ET.SubElement(detail, "contact")
    contact.set("callsign", f"KrakenSDR {data.station}")
    group = ET.SubElement(detail, "__group")
    group.set("name", config.get("COT_GROUP_NAME", "Yellow"))
    group.set("role", config.get("COT_GROUP_ROLE", "Team Member"))
    remarks = ET.SubElement(detail, "remarks")
    remarks.text = (
        f"KrakenSDR {data.station} | {data.frequency} Hz | "
        f"conf {data.confidence} | rssi {data.rssi} dB"
    )
    return _swap_detail(cot, detail)


def doa_to_cot_bearing_line(data, config=None) -> Optional[ET.Element]:
    """A line-of-bearing drawn from the station along the DOA (u-d-f)."""
    config = config or {}
    lat, lon = data.latitude, data.longitude
    if lat is None or lon is None:
        Logger.warning("No lat/lon for bearing line CoT")
        return None

    length_m = _lob_length_m(config)
    end_lat, end_lon = calculate_second_point(lat, lon, data.max_doa_angle, length_m)

    if str(config.get("PERSIST_LOB", "")).lower() in ("1", "true", "yes"):
        uid = f"{COT_TAG}.{data.station}.LOB.{random.randint(1000, 9999)}"
    else:
        uid = f"{COT_TAG}.{data.station}.LOB.{data.frequency}"

    cot = _base_cot(data, config, uid, "u-d-f", lat, lon)
    color = bearing_to_color(data.max_doa_angle)

    detail = ET.Element("detail")
    contact = ET.SubElement(detail, "contact")
    contact.set("callsign", f"KrakenSDR {data.station} {data.frequency} Hz")
    ET.SubElement(detail, "link", {"point": f"{lat},{lon}"})
    ET.SubElement(detail, "link", {"point": f"{end_lat},{end_lon}"})
    ET.SubElement(detail, "remarks").text = (
        f"DOA {data.max_doa_angle} deg | conf {data.confidence} | rssi {data.rssi} dB"
    )
    ET.SubElement(detail, "strokeColor", {"value": str(color)})
    ET.SubElement(detail, "strokeWeight", {"value": "3.0"})
    ET.SubElement(detail, "strokeStyle", {"value": "solid"})
    ET.SubElement(detail, "labels_on", {"value": "false"})
    ET.SubElement(detail, "archive")

    cot = _swap_detail(cot, detail)
    # A u-d-f line carries a second <point> for its endpoint.
    cot.append(ET.Element("point", _point_attrs(end_lat, end_lon)))
    return cot


def doa_to_cot_range_bearing(data, config=None) -> Optional[ET.Element]:
    """A TAK Range & Bearing line (u-rb-a) along the DOA."""
    config = config or {}
    lat, lon = data.latitude, data.longitude
    if lat is None or lon is None:
        Logger.warning("No lat/lon for range/bearing CoT")
        return None

    length_m = _lob_length_m(config)
    uid = f"{COT_TAG}.{data.station}.RB.{data.frequency}"
    cot = _base_cot(data, config, uid, "u-rb-a", lat, lon)
    color = bearing_to_color(data.max_doa_angle)

    detail = ET.Element("detail")
    ET.SubElement(detail, "range", {"value": str(length_m)})
    ET.SubElement(detail, "bearing", {"value": str(float(data.max_doa_angle))})
    ET.SubElement(detail, "inclination", {"value": "0.0"})
    ET.SubElement(detail, "rangeUnits", {"value": "1"})
    ET.SubElement(detail, "bearingUnits", {"value": "0"})
    ET.SubElement(detail, "northRef", {"value": "1"})
    ET.SubElement(detail, "strokeColor", {"value": str(color)})
    ET.SubElement(detail, "strokeWeight", {"value": "3.0"})
    contact = ET.SubElement(detail, "contact")
    contact.set("callsign", f"KrakenSDR {data.station} {data.frequency} Hz")
    ET.SubElement(detail, "remarks").text = (
        f"conf {data.confidence} | rssi {data.rssi} dB"
    )
    ET.SubElement(detail, "archive")
    ET.SubElement(detail, "labels_on", {"value": "false"})
    ET.SubElement(detail, "color", {"value": str(color)})
    return _swap_detail(cot, detail)


def doa_to_cot_lob(data, config=None) -> Optional[ET.Element]:
    """A native TAK ``__lob`` detection (schema-valid per __lob.xsd)."""
    config = config or {}
    lat, lon = data.latitude, data.longitude
    if lat is None or lon is None:
        Logger.warning("No lat/lon for __lob CoT")
        return None

    uid = f"{COT_TAG}.{data.station}.lob.{data.frequency}"
    cot_type = config.get("COT_TYPE_LOB", "a-u-G")
    cot = _base_cot(data, config, uid, cot_type, lat, lon)

    family = config.get("COT_FAMILY", kraktak.DEFAULT_COT_FAMILY)
    device_type = config.get("DEVICE_TYPE", kraktak.DEFAULT_DEVICE_TYPE)

    lob = ET.Element("__lob")
    lob.set("azimuth", str(float(data.max_doa_angle)))
    lob.set("rssi", str(float(data.rssi)))
    lob.set("confidence", str(int(data.confidence)))
    lob.set("family", family)
    lob.set("deviceType", device_type)
    lob.set("unitId", str(data.station))
    lob.set("deviceTime", str(int(data.timestamp)))
    # Sequence order per schema: signalInfo, then __startLocation.
    lob.append(_signal_info(data, config))
    ET.SubElement(lob, "__startLocation", _point_attrs(lat, lon, hae="0.0",
                                                       ce="0.0", le="0.0"))

    detail = ET.Element("detail")
    contact = ET.SubElement(detail, "contact")
    contact.set("callsign", f"KrakenSDR {data.station} LOB {data.frequency} Hz")
    detail.append(lob)
    return _swap_detail(cot, detail)


def doa_to_cot_cep(data, config=None) -> Optional[ET.Element]:
    """A ``__cep`` error ellipse (schema-valid per __cep.xsd).

    Confidence (0-99) is mapped to an ellipse radius: lower confidence -> larger
    ellipse. The ellipse is centered at ``center_lat``/``center_lon`` if present
    on ``data`` (e.g. a multi-station fix), otherwise at the station location.
    """
    config = config or {}
    lat = getattr(data, "center_lat", None) or data.latitude
    lon = getattr(data, "center_lon", None) or data.longitude
    if lat is None or lon is None:
        Logger.warning("No lat/lon for __cep CoT")
        return None

    max_radius = float(config.get("CEP_MAX_RADIUS_M", "2000"))
    min_radius = float(config.get("CEP_MIN_RADIUS_M", "100"))
    conf = max(0.0, min(99.0, float(data.confidence)))
    major = min_radius + (max_radius - min_radius) * (1.0 - conf / 99.0)
    minor = major * 0.5

    family = config.get("COT_FAMILY", kraktak.DEFAULT_COT_FAMILY)
    device_type = config.get("DEVICE_TYPE", kraktak.DEFAULT_DEVICE_TYPE)

    uid = f"{COT_TAG}.{data.station}.cep.{data.frequency}"
    cot = _base_cot(data, config, uid, config.get("COT_TYPE_CEP", "a-u-G"), lat, lon)

    cep = ET.Element("__cep")
    cep.set("majorRadius", str(round(major, 2)))
    cep.set("minorRadius", str(round(minor, 2)))
    cep.set("ellipseHeading", str(float(data.max_doa_angle)))
    cep.set("family", family)
    cep.set("deviceType", device_type)
    cep.set("unitId", str(data.station))
    cep.set("deviceTime", str(int(data.timestamp)))
    cep.append(_signal_info(data, config))
    ET.SubElement(cep, "centerLocation", _point_attrs(lat, lon, hae="0.0",
                                                      ce="0.0", le="0.0"))

    detail = ET.Element("detail")
    contact = ET.SubElement(detail, "contact")
    contact.set("callsign", f"KrakenSDR {data.station} CEP {data.frequency} Hz")
    detail.append(cep)
    return _swap_detail(cot, detail)


def doa_to_cot_spi(data, config=None) -> Optional[ET.Element]:
    """Sensor Point of Interest at the assumed-range fix (``b-m-p-s-p-i``)."""
    config = config or {}
    if data.latitude is None or data.longitude is None:
        Logger.warning("No lat/lon for SPI CoT")
        return None

    target_lat, target_lon, _ = _target_fix_endpoint(data, config)
    event = takline.build_spi_link_event(
        uid=f"{COT_TAG}.{data.station}.spi.{data.frequency}",
        callsign=f"KrakenSDR {data.station} SPI {data.frequency} Hz",
        lat=target_lat,
        lon=target_lon,
        parent_uid=_sensor_uid(data),
        link_type=_sensor_link_type(config),
        stale_sec=_target_fix_stale_sec(config),
        remarks=_target_fix_remarks(data),
    )
    return _annotate_kraktak_event(event, config)


def doa_to_cot_spot_poi(data, config=None) -> Optional[ET.Element]:
    """Spot-map POI at the assumed-range fix (``b-m-p-s-m``). Opt-in via COT_TYPES."""
    config = config or {}
    if data.latitude is None or data.longitude is None:
        Logger.warning("No lat/lon for spot POI CoT")
        return None

    target_lat, target_lon, _ = _target_fix_endpoint(data, config)
    iconset = config.get("COT_POI_ICONSET", DEFAULT_POI_ICONSET)
    event = takline.build_track_poi_event(
        uid=f"{COT_TAG}.{data.station}.poi.{data.frequency}",
        callsign=f"KrakenSDR {data.station} POI {data.frequency} Hz",
        lat=target_lat,
        lon=target_lon,
        parent_uid=_sensor_uid(data),
        parent_type=_sensor_link_type(config),
        stale_sec=_target_fix_stale_sec(config),
        remarks=_target_fix_remarks(data),
        color=config.get("COT_POI_COLOR_ARGB", DEFAULT_POI_COLOR_ARGB),
        usericon=str(iconset) if iconset else None,
    )
    return _annotate_kraktak_event(event, config)


def doa_to_cot_target_range_bearing(data, config=None) -> Optional[ET.Element]:
    """``u-rb-a`` from the Kraken station to the assumed-range fix."""
    config = config or {}
    if data.latitude is None or data.longitude is None:
        Logger.warning("No lat/lon for target range/bearing CoT")
        return None

    _, _, range_m = _target_fix_endpoint(data, config)
    bearing = float(data.max_doa_angle) % 360.0
    stroke_color = config.get("COT_TARGET_RB_COLOR", "-65536")
    stroke_weight = config.get("COT_TARGET_RB_STROKE_WEIGHT", "3.0")
    callsign = (
        f"R&B KrakenSDR {data.station} {range_m / 1000.0:.1f}km @ {bearing:.0f}T"
    )[:200]
    event = takline.build_target_range_bearing_event(
        uid=f"{COT_TAG}.{data.station}.target_rb.{data.frequency}",
        lat=data.latitude,
        lon=data.longitude,
        range_m=range_m,
        bearing_deg=bearing,
        parent_uid=_sensor_uid(data),
        parent_type=_sensor_link_type(config),
        callsign=callsign,
        stale_sec=_target_fix_stale_sec(config),
        stroke_color=str(stroke_color),
        stroke_weight=str(stroke_weight),
        remarks=_target_fix_remarks(data),
    )
    return _annotate_kraktak_event(event, config)


# Map of COT_TYPES tokens -> builder functions.
COT_BUILDERS = {
    "sensor": doa_to_cot_sensor,
    "bearing_line": doa_to_cot_bearing_line,
    "range_bearing": doa_to_cot_range_bearing,
    "lob": doa_to_cot_lob,
    "cep": doa_to_cot_cep,
    "spi": doa_to_cot_spi,
    "spot_poi": doa_to_cot_spot_poi,
    "target_range_bearing": doa_to_cot_target_range_bearing,
}


def selected_builders(config) -> List[str]:
    """Return the list of builder tokens enabled via COT_TYPES."""
    raw = (config.get("COT_TYPES", kraktak.DEFAULT_COT_TYPES) or "").strip()
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    return [t for t in tokens if t in COT_BUILDERS]


def cot_to_xml(data, config=None, func: Optional[str] = None) -> Optional[bytes]:
    """Render a DOAValues record to a CoT XML byte-string via the named builder."""
    config = config or {}
    builder = COT_BUILDERS.get(func or "bearing_line")
    if builder is None:
        Logger.warning("Unknown CoT builder: %s", func)
        return None
    cot: Optional[ET.Element] = builder(data, config)
    if cot is None:
        Logger.debug("No CoT XML generated for %s", func)
        return None
    return b"\n".join([pytak.DEFAULT_XML_DECLARATION, ET.tostring(cot)])


def gen_geochat(
    message: str, config=None, target_uid: str = "All Chat Rooms"
) -> Optional[bytes]:
    """Build a minimal TAK GeoChat CoT carrying ``message`` to ``target_uid``."""
    config = config or {}
    sender_uid = config.get("COT_HOST_ID", pytak.DEFAULT_HOST_ID) or "KrakTAK"
    sender_cs = config.get("CONTROL_CALLSIGN", "KrakTAK")
    now = datetime.datetime.now(datetime.timezone.utc)
    stale = now + datetime.timedelta(seconds=60)
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    msg_id = str(uuid.uuid4())

    event = ET.Element("event")
    event.set("version", "2.0")
    event.set("uid", f"GeoChat.{sender_uid}.{target_uid}.{msg_id}")
    event.set("type", "b-t-f")
    event.set("how", "h-g-i-g-o")
    event.set("time", now.strftime(fmt))
    event.set("start", now.strftime(fmt))
    event.set("stale", stale.strftime(fmt))
    ET.SubElement(event, "point", _point_attrs(0.0, 0.0))

    detail = ET.SubElement(event, "detail")
    chat = ET.SubElement(detail, "__chat")
    chat.set("parent", "RootContactGroup")
    chat.set("groupOwner", "false")
    chat.set("messageId", msg_id)
    chat.set("chatroom", target_uid)
    chat.set("id", target_uid)
    chat.set("senderCallsign", sender_cs)
    chatgrp = ET.SubElement(chat, "chatgrp")
    chatgrp.set("uid0", sender_uid)
    chatgrp.set("uid1", target_uid)
    chatgrp.set("id", target_uid)

    link = ET.SubElement(detail, "link")
    link.set("uid", sender_uid)
    link.set("type", "a-f-G")
    link.set("relation", "p-p")

    remarks = ET.SubElement(detail, "remarks")
    remarks.set("source", f"BAO.F.KrakTAK.{sender_uid}")
    remarks.set("to", target_uid)
    remarks.set("time", now.strftime(fmt))
    remarks.text = message

    return b"\n".join([pytak.DEFAULT_XML_DECLARATION, ET.tostring(event)])


def create_tasks(config: SectionProxy, clitool: pytak.CLITool) -> set:
    """Create the coroutine task set for this application."""
    tasks = set()
    tasks.add(kraktak.KrakTAKWorker(clitool.tx_queue, config))

    enable_control = str(
        config.get("ENABLE_CONTROL", kraktak.DEFAULT_ENABLE_CONTROL)
    ).lower() in ("1", "true", "yes")
    if enable_control:
        # Imported lazily so the core bridge has no hard control-plane deps.
        from kraktak.control import KrakenControlWorker

        tasks.add(KrakenControlWorker(clitool.rx_queue, config, clitool.tx_queue))
    return tasks

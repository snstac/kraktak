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

"""kraktak Functions."""

import logging
import math
import os
import warnings
import xml.etree.ElementTree as ET
import random


from configparser import SectionProxy
from typing import Optional, Set, Union

import pytak
import kraktak


APP_NAME = "kraktak"
Logger = logging.getLogger(__name__)
Debug = bool(os.getenv("DEBUG", False))

COT_TAG = f"{APP_NAME}-1-"

def create_tasks(config: SectionProxy, clitool: pytak.CLITool) -> Set[pytak.Worker,]:
    """Create specific coroutine task set for this application.

    Parameters
    ----------
    config : `SectionProxy`
        Configuration options & values.
    clitool : `pytak.CLITool`
        A PyTAK Worker class instance.

    Returns
    -------
    `set`
        Set of PyTAK Worker classes for this application.
    """
    tasks = set()
    tasks.add(kraktak.KrakTAKWorker(clitool.tx_queue, config))
    return tasks


def doa_to_cot_sensor_xml(  # NOQA pylint: disable=too-many-locals,too-many-branches,too-many-statements
    data: dict,
    config: Union[SectionProxy, dict, None] = None,
) -> Optional[ET.Element]:

    remarks_fields = []
    config = config or {}
    
    default_cot_val = '999999'

    lat = data.latitude
    lon = data.longitude
    
    if lat is None or lon is None:
        Logger.warning(f"No value for lat={lat} lon={lon}")
        return None

    kraken_station = data.station
    callsign = f"KrakenSDR {kraken_station}"
    cot_uid = f"{COT_TAG}-KrakenSDR-{kraken_station}"
    cot_type = "a-f-G-U-C"

    cot_stale: int = int(config.get("COT_STALE", pytak.DEFAULT_COT_STALE))
    cot_host_id: str = config.get("COT_HOST_ID", pytak.DEFAULT_HOST_ID)
    ce = default_cot_val
    le = default_cot_val
    hae = default_cot_val

    __krakensdr = ET.Element("__krakensdr")
    # __krakensdr.set("cot_host_id", cot_host_id)
    # __krakensdr.set("feed_url", config.get("FEED_URL", ""))

    contact: ET.Element = ET.Element("contact")
    contact.set("callsign", callsign)

    uid = ET.Element("UID")
    uid.set("Droid", str(callsign))

    # remarks_fields.append(f"FEED_URL: {config.get('FEED_URL', '')}")
    # Remarks should always be the first sub-entity within the Detail entity.
    remarks = ET.Element("remarks")
    remarks_fields.append(f"{cot_host_id}")
    _remarks = " ".join(list(filter(None, remarks_fields)))
    remarks.text = _remarks

    __group = ET.Element("__group")
    __group.set("name", config.get("COT_GROUP_NAME", "Yellow"))
    __group.set("role", config.get("COT_GROUP_ROLE", "Team Member")) 

    precisionlocation = ET.Element("precisionlocation")
    geopointsrc = config.get("COT_GEOPOINTSRC", "GPS")
    altsrc = config.get("COT_ALTSRC", "")
    precisionlocation.set("geopointsrc", geopointsrc)
    precisionlocation.set("altsrc", altsrc)

    status = ET.Element("status")
    battery = config.get("COT_BATTERY", default_cot_val)
    status.set("battery", battery)

    device = config.get("COT_DEVICE", "")
    platform = config.get("COT_PLATFORM", "")
    os = config.get("COT_OS", "")
    version = config.get("COT_VERSION", "")
    takv = ET.Element("takv")
    takv.set("device", device)
    takv.set("platform", platform)
    takv.set("os", os)
    takv.set("version", version)

    speed = config.get("COT_SPEED", "0.00000000")
    course = config.get("COT_COURSE", "")   
    track = ET.Element("track")
    track.set("speed", speed)
    track.set("course", course)
    track.set("slope", default_cot_val)
    
    color = ET.Element("color")
    color.set("argb", "-256")  # Default color, can be changed if needed

    usericon = ET.Element("usericon")
    iconsetpath = config.get("COT_ICONSETPATH", "-256")
    usericon.set("iconsetpath", iconsetpath)

    detail = ET.Element("detail")
    detail.append(contact)
    # detail.append(remarks)
    # detail.append(__krakensdr)
    detail.append(uid)
    detail.append(__group)
    detail.append(precisionlocation)
    # detail.append(status)
    # detail.append(takv)
    # detail.append(track)
    detail.append(color)
    # detail.append(usericon)

    cot_d = {
        "lat": str(lat),
        "lon": str(lon),
        "ce": str(0),
        "le": str(0),
        "hae": str(0),
        "uid": cot_uid,
        "cot_type": cot_type,
        "stale": cot_stale,
    }
    cot = pytak.gen_cot_xml(**cot_d)
    cot.set("access", config.get("COT_ACCESS", pytak.DEFAULT_COT_ACCESS))
    cot.set("qos", "1-r-c")

    _detail = cot.findall("detail")[0]
    flowtags = _detail.findall("_flow-tags_")
    detail.extend(flowtags)

    cot.remove(_detail)
    cot.append(detail)

    return cot


def doa_to_cot_line_xml(
    data: dict,
    config: Union[SectionProxy, dict, None] = None,
) -> Optional[ET.Element]:
    remarks_fields = []

    config = config or {}

    default_cot_val = '0.0'

    lat = data.latitude
    lon = data.longitude
    if lat is None or lon is None:
        Logger.warning(f"No value for lat={lat} lon={lon}")

        return None
    kraken_station = data.station

    callsign = f"KrakenSDR {kraken_station} DOA {data.frequency} Hz"
    cot_uid = f"{COT_TAG}-KrakenSDR-{kraken_station}-DOA-{data.frequency}"
    cot_type = "u-d-f"

    cot_stale: int = int(config.get("COT_STALE", pytak.DEFAULT_COT_STALE))

    cot_host_id: str = config.get("COT_HOST_ID", pytak.DEFAULT_HOST_ID)
    ce = default_cot_val
    le = default_cot_val
    hae = default_cot_val

    # FIXME: No magic numbers!
    MAGIC_NUMBER = 6
    second_point = calculate_second_point(
        data.latitude, data.longitude, data.max_doa_angle, MAGIC_NUMBER
    )

    __krakensdr = ET.Element("__krakensdr")
    # __krakensdr.set("cot_host_id", cot_host_id)
    # __krakensdr.set("feed_url", config.get("FEED_URL", ""))

    contact: ET.Element = ET.Element("contact")
    contact.set("callsign", callsign)

    uid = ET.Element("UID")
    uid.set("Droid", str(callsign))

    # remarks_fields.append(f"FEED_URL: {config.get('FEED_URL', '')}")
    # Remarks should always be the first sub-entity within the Detail entity.
    remarks = ET.Element("remarks")
    remarks_fields.append(f"{cot_host_id}")
    _remarks = " ".join(list(filter(None, remarks_fields)))
    remarks.text = _remarks

    __group = ET.Element("__group")
    __group.set("name", config.get("COT_GROUP_NAME", "Yellow"))
    __group.set("role", config.get("COT_GROUP_ROLE", "Team Member"))

    precisionlocation = ET.Element("precisionlocation")
    geopointsrc = config.get("COT_GEOPOINTSRC", "GPS")
    altsrc = config.get("COT_ALTSRC", "")
    precisionlocation.set("geopointsrc", geopointsrc)
    precisionlocation.set("altsrc", altsrc)

    status = ET.Element("status")
    battery = config.get("COT_BATTERY", default_cot_val)
    status.set("battery", battery)

    device = config.get("COT_DEVICE", "")
    platform = config.get("COT_PLATFORM", "")
    os = config.get("COT_OS", "")
    version = config.get("COT_VERSION", "")
    takv = ET.Element("takv")
    takv.set("device", device)
    takv.set("platform", platform)
    takv.set("os", os)
    takv.set("version", version)

    speed = config.get("COT_SPEED",
        "0.00000000"
    )  # Default speed, can be changed if needed
    course = config.get("COT_COURSE", "")  # Default course, can be changed if needed
    track = ET.Element("track")
    track.set("speed", speed)
    track.set("course", course)
    track.set("slope", default_cot_val)
    
    color = ET.Element("color")
    color.set("argb", "-256")  # Default color, can be changed if needed
   
    usericon = ET.Element("usericon")
    iconsetpath = config.get("COT_ICONSETPATH", "-256")
    usericon.set("iconsetpath", iconsetpath)
    
    point2 = ET.Element("point")
    point2.set("lat", str(second_point[0]))
    point2.set("lon", str(second_point[1]))
    point2.set("hae", str(default_cot_val))
    point2.set("ce", str(default_cot_val))
    point2.set("le", str(default_cot_val))
    
    link = ET.Element("link")
    link.set("point", f"{lat},{lon}")

    link2 = ET.Element("link")
    link2.set("point", f"{second_point[0]},{second_point[1]}")
    # Set the point attribute for the second link

    __shape_extras = ET.Element("__shapeExtras")
    __shape_extras.set("cpvis", "true")
    __shape_extras.set("editable", "true")

    __milsym = ET.Element("__milsym")
    __milsym.set("id", "10002500003406000000")  # Example ID, can be changed if needed

    labels_on = ET.Element("labels_on")
    labels_on.set("value", "false")  # Default value, can be changed if needed

    # Create the detail element and append all sub-elements
    detail = ET.Element("detail")
    # detail.append(contact)
    detail.append(remarks)
    # detail.append(__krakensdr)
    # detail.append(uid)
    # detail.append(__group)
    # detail.append(precisionlocation)
    # detail.append(status)
    # detail.append(takv)
    # detail.append(track)
    # detail.append(color)
    # detail.append(usericon)
    detail.append(link)
    detail.append(link2)
    # detail.append(__shape_extras)
    # detail.append(__milsym)
    # detail.append(labels_on)
    detail.append(ET.Element("archive"))  # Empty archive element
    detail.append(ET.Element("strokeColor", {"value": "-256"}))  # Default stroke color
    detail.append(ET.Element("strokeWeight", {"value": "3.0"}))  # Default stroke weight
    detail.append(ET.Element("strokeStyle", {"value": "solid"}))  # Default stroke style


    # Create the CoT XML payload
    cot_d = {
        "lat": str(lat),
        "lon": str(lon),
        "ce": str(ce),
        "le": str(le),
        "hae": str(hae),
        "uid": cot_uid,
        "cot_type": cot_type,
        "stale": cot_stale,
    }

    cot = pytak.gen_cot_xml(**cot_d)
    cot.set("access", config.get("COT_ACCESS", pytak.DEFAULT_COT_ACCESS))
    cot.set("qos", "1-r-c")

    _detail = cot.findall("detail")[0]
    flowtags = _detail.findall("_flow-tags_")
    detail.extend(flowtags)

    cot.remove(_detail)
    cot.append(detail)
    cot.append(point2)

    return cot


def doa_to_cot_lob_xml(
    data: dict,
    config: Union[SectionProxy, dict, None] = None,
) -> Optional[ET.Element]:
    remarks_fields = []

    config = config or {}

    default_cot_val = '0.0'

    lat = data.latitude
    lon = data.longitude
    if lat is None or lon is None:
        Logger.warning(f"No value for lat={lat} lon={lon}")

        return None
    kraken_station = data.station

    callsign = f"KrakenSDR {kraken_station} LOB {data.frequency} Hz"
    cot_uid = f"{COT_TAG}-KrakenSDR-{kraken_station}-LOB-{data.frequency}"
    cot_type = "b-d"

    cot_stale: int = int(config.get("COT_STALE", pytak.DEFAULT_COT_STALE))

    cot_host_id: str = config.get("COT_HOST_ID", pytak.DEFAULT_HOST_ID)
    ce = default_cot_val
    le = default_cot_val
    hae = default_cot_val

    # FIXME: No magic numbers!
    MAGIC_NUMBER = 6
    second_point = calculate_second_point(
        data.latitude, data.longitude, data.max_doa_angle, MAGIC_NUMBER
    )

    __krakensdr = ET.Element("__krakensdr")
    # __krakensdr.set("cot_host_id", cot_host_id)
    # __krakensdr.set("feed_url", config.get("FEED_URL", ""))

    contact: ET.Element = ET.Element("contact")
    contact.set("callsign", callsign)

    uid = ET.Element("UID")
    uid.set("Droid", str(callsign))

    # remarks_fields.append(f"FEED_URL: {config.get('FEED_URL', '')}")
    # Remarks should always be the first sub-entity within the Detail entity.
    remarks = ET.Element("remarks")
    remarks_fields.append(f"{cot_host_id}")
    _remarks = " ".join(list(filter(None, remarks_fields)))
    remarks.text = _remarks

    __group = ET.Element("__group")
    __group.set("name", config.get("COT_GROUP_NAME", "Yellow"))
    __group.set("role", config.get("COT_GROUP_ROLE", "Team Member"))

    precisionlocation = ET.Element("precisionlocation")
    geopointsrc = config.get("COT_GEOPOINTSRC", "GPS")
    altsrc = config.get("COT_ALTSRC", "")
    precisionlocation.set("geopointsrc", geopointsrc)
    precisionlocation.set("altsrc", altsrc)

    status = ET.Element("status")
    battery = config.get("COT_BATTERY", default_cot_val)
    status.set("battery", battery)

    device = config.get("COT_DEVICE", "")
    platform = config.get("COT_PLATFORM", "")
    os = config.get("COT_OS", "")
    version = config.get("COT_VERSION", "")
    takv = ET.Element("takv")
    takv.set("device", device)
    takv.set("platform", platform)
    takv.set("os", os)
    takv.set("version", version)

    speed = config.get("COT_SPEED",
        "0.00000000"
    )  # Default speed, can be changed if needed
    course = config.get("COT_COURSE", "")  # Default course, can be changed if needed
    track = ET.Element("track")
    track.set("speed", speed)
    track.set("course", course)
    track.set("slope", default_cot_val)
    
    color = ET.Element("color")
    color.set("argb", "-256")  # Default color, can be changed if needed
   
    usericon = ET.Element("usericon")
    iconsetpath = config.get("COT_ICONSETPATH", "-256")
    usericon.set("iconsetpath", iconsetpath)
    
    __lob = ET.Element("__lob")
    __lob.set("deviceType", "KrakenSDR")
    __lob.set("rssi", str(data.rssi))
    __lob.set("confidence", str(data.confidence))
    __lob.set("unitId", str(data.station))
    __lob.set("azimuth", str(data.max_doa_angle))
    __lob.set("family", "com.snstac.kraktak")
    # __lob.set("deviceTime", str(data.timestamp))
    __lob.set("frequency", str(data.frequency))
    # __lob.set("elevationAngle", str(0))

    startLocation = ET.Element("startLocation")
    startLocation.set("lat", str(lat))
    startLocation.set("lon", str(lon))
    startLocation.set("hae", str("0.0"))
    startLocation.set("ce", str("0.0"))
    startLocation.set("le", str("0.0"))

    __rf = ET.Element("__rf")
    __rf.set("rssi", str(data.rssi))
    # __rf.set("uplinkRssi", str(data.uplink_rssi))
    # __rf.set("downlinkRssi", str(data.downlink_rssi))
    # __rf.set("tag", str(data.tag))
    # __rf.set("errorRadius", str(data.error_radius))
    __rf.set("comments", str("test comment"))
    __rf.set("frequency", str(data.frequency))

    __lob.append(startLocation)
    __lob.append(__rf)

    link = ET.Element("link")
    link.set("point", f"{lat},{lon}")

    __shape_extras = ET.Element("__shapeExtras")
    __shape_extras.set("cpvis", "true")
    __shape_extras.set("editable", "true")

    __milsym = ET.Element("__milsym")
    __milsym.set("id", "10002500003406000000")  # Example ID, can be changed if needed

    labels_on = ET.Element("labels_on")
    labels_on.set("value", "false")  # Default value, can be changed if needed

    # Create the detail element and append all sub-elements
    detail = ET.Element("detail")
    detail.append(contact)
    # detail.append(remarks)
    # detail.append(__krakensdr)
    # detail.append(uid)
    # detail.append(__group)
    # detail.append(precisionlocation)
    # detail.append(status)
    # detail.append(takv)
    # detail.append(track)
    # detail.append(color)
    # detail.append(usericon)
    # detail.append(link)
    # detail.append(__shape_extras)
    # detail.append(__milsym)
    # detail.append(labels_on)
    # detail.append(ET.Element("archive"))  # Empty archive element
    # detail.append(ET.Element("strokeColor", {"value": "-256"}))  # Default stroke color
    # detail.append(ET.Element("strokeWeight", {"value": "3.0"}))  # Default stroke weight
    # detail.append(ET.Element("strokeStyle", {"value": "solid"}))  # Default stroke style
    detail.append(__lob)

    # Create the CoT XML payload
    cot_d = {
        "lat": str(lat),
        "lon": str(lon),
        "ce": str("0.0"),
        "le": str("0.0"),
        "hae": str("0.0"),
        "uid": cot_uid,
        "cot_type": cot_type,
        "stale": cot_stale,
        # "how": "u-X"
    }

    cot = pytak.gen_cot_xml(**cot_d)
    cot.set("access", config.get("COT_ACCESS", pytak.DEFAULT_COT_ACCESS))
    cot.set("qos", "1-r-c")

    _detail = cot.findall("detail")[0]
    flowtags = _detail.findall("_flow-tags_")
    detail.extend(flowtags)

    cot.remove(_detail)
    cot.append(detail)

    return cot


def cot_to_xml(
    data: dict,
    config: Union[SectionProxy, dict, None] = None,
    func=None,
) -> Optional[bytes]:
    """Return a CoT XML object as an XML string, using the given func."""
    func = func or "ais_to_cot"
    cot: Optional[ET.Element] = getattr(kraktak.functions, func)(
        data, config, 
    )
    if cot is not None:
        return b"\n".join([pytak.DEFAULT_XML_DECLARATION, ET.tostring(cot)])
    Logger.debug("No CoT XML generated.")
    return None


# Function to calculate the second point
def calculate_second_point(lat1, lon1, bearing_deg, distance_m):
    """
    Calculate the latitude and longitude of a point given a start point,
    initial bearing, and distance.

    Parameters
    ----------
    lat1 : float
        Latitude of the starting point in degrees.
    lon1 : float
        Longitude of the starting point in degrees.
    bearing_deg : float
        Initial bearing in degrees.
    distance_m : float
        Distance to the second point in meters.

    Returns
    -------
    tuple
        (latitude, longitude) of the second point in degrees.
    """
    # Convert inputs to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    bearing_rad = math.radians(bearing_deg)

    # Earth's radius in meters
    earth_radius = getattr(kraktak, "EARTH_RADIUS", 6371000)

    # Angular distance
    angular_distance = distance_m / earth_radius

    # Calculate new latitude
    lat2_rad = math.asin(
        math.sin(lat1_rad) * math.cos(angular_distance) +
        math.cos(lat1_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
    )

    # Calculate new longitude
    lon2_rad = lon1_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat1_rad),
        math.cos(angular_distance) - math.sin(lat1_rad) * math.sin(lat2_rad)
    )

    # Convert results back to degrees
    lat2 = math.degrees(lat2_rad)
    lon2 = math.degrees(lon2_rad)

    return lat2, lon2


def evaluate_angle_range(start_angle, end_angle, max_doa_angle):
    """
    Determines if max_doa_angle falls within the exclusion wedge defined by start_angle and end_angle.

    Returns True if payloads should be sent (angle is outside exclusion wedge),
    False if max_doa_angle is within the exclusion wedge.

    Parameters
    ----------
    start_angle : int or str
        Start of the exclusion wedge (degrees, 0-359).
    end_angle : int or str
        End of the exclusion wedge (degrees, 0-359).
    max_doa_angle : int or str
        Angle to evaluate (degrees, 0-359).

    Returns
    -------
    bool
        True if angle is outside exclusion wedge, False otherwise.
    """
    if start_angle is None or end_angle is None:
        print("No DOA Ignore wedge set")
        return True

    # Normalize angles to [0, 359]
    start_angle = int(start_angle) % 360
    end_angle = int(end_angle) % 360
    max_doa_angle = int(max_doa_angle) % 360

    if start_angle <= end_angle:
        # Simple range: exclusion wedge does not wrap around 0
        in_exclusion = start_angle <= max_doa_angle <= end_angle
    else:
        # Wrapped range: exclusion wedge crosses 0
        in_exclusion = max_doa_angle >= start_angle or max_doa_angle <= end_angle

    if in_exclusion:
        print("max doa angle between exclusion wedge.")
        return False
    else:
        print("sending payloads")
        return True


# Function to generate uid_line with a random number every second
def generate_uid_line():
    uid_line = f'DOA-to-TAK-{random.randint(1000, 9999)}'
    return uid_line 



# Function to get GPS data
def get_gps_data():
    try:
        gpsd.connect()
        packet = gpsd.get_current()
        latitude = getattr(packet, 'lat', None)
        longitude = getattr(packet, 'lon', None)

        # If GPSD data is available, return it
        if latitude is not None and longitude is not None:
            return latitude, longitude
        
    except Exception as e:
        # Log any errors encountered while connecting to GPSD
        logging.error(f"Error connecting to GPSD: {e}")

    # If GPSD is not available or encountered an error, use alternate source (if available)
    try:
        # Fetch data from Kraken server
        kraken_response = requests.get(url(kraken_server))
        kraken_data = kraken_response.text

        # Split the data and extract latitude and longitude
        data_parts = kraken_data.split(',')
        latitude_kraken = float(data_parts[8])
        longitude_kraken = float(data_parts[9])
        
        # If alternate source data is available, return it
        return latitude_kraken, longitude_kraken
    
    except Exception as e:
        # Log any errors encountered while using alternate source
        logging.error(f"Error using alternate source for GPS data: {e}")

    # If both GPSD and alternate source fail, return None
    return None, None



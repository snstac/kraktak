"""Validate generated detail elements against the TAK CoT XSD reference set.

These tests confirm KrakTAK's ``__lob`` and ``__cep`` output conforms to the
schemas in ``takcot-master/xsd`` (skipped if lxml or the schemas are absent).
"""

import os
import xml.etree.ElementTree as ET

import pytest

import kraktak
from tests.conftest import XSD_DIR

lxml_etree = pytest.importorskip("lxml.etree")


def _validate(detail_tag: str, builder: str, xsd_name: str, doa) -> None:
    xsd_path = os.path.join(XSD_DIR, xsd_name)
    if not os.path.exists(xsd_path):
        pytest.skip(f"schema not found: {xsd_path}")

    out = kraktak.cot_to_xml(doa, {}, builder)
    event = ET.fromstring(out.split(b"\n", 1)[1])
    el = event.find(f".//detail/{detail_tag}")
    assert el is not None

    schema = lxml_etree.XMLSchema(lxml_etree.parse(xsd_path))
    fragment = lxml_etree.fromstring(ET.tostring(el))
    if not schema.validate(fragment):
        raise AssertionError(f"{detail_tag} invalid: {schema.error_log}")


def test_lob_is_schema_valid(doa):
    _validate("__lob", "lob", "__lob.xsd", doa)


def test_cep_is_schema_valid(doa):
    _validate("__cep", "cep", "__cep.xsd", doa)

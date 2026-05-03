from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from xml.etree.ElementTree import Element, SubElement, tostring


_XML_CONTENT_TYPE = "application/xml; charset=utf-8"


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _entry_xml(parent: Element, entry: dict) -> None:
    node = SubElement(parent, "entry")
    fields = [
        "id",
        "medicine_name",
        "status",
        "dose",
        "start_date",
        "end_date",
        "notes",
        "created_at",
        "updated_at",
    ]
    for key in fields:
        child = SubElement(node, key)
        child.text = _text(entry.get(key))


def build_medicine_history_xml(entries: Iterable[dict]) -> bytes:
    root = Element("medicine_history")
    items = SubElement(root, "entries")
    for entry in entries:
        _entry_xml(items, entry)
    return tostring(root, encoding="utf-8", xml_declaration=True)


def build_paginated_medicine_history_xml(payload: dict) -> bytes:
    root = Element("medicine_history_response")

    meta = SubElement(root, "meta")
    for key in ["count", "total_pages", "next", "previous"]:
        child = SubElement(meta, key)
        child.text = _text(payload.get(key))

    entries = SubElement(root, "results")
    for row in payload.get("results", []):
        _entry_xml(entries, row)

    return tostring(root, encoding="utf-8", xml_declaration=True)


def xml_content_type() -> str:
    return _XML_CONTENT_TYPE

"""XSD-to-Python type mapping."""

from __future__ import annotations

_XSD = "http://www.w3.org/2001/XMLSchema#"

_GROUPS: list[tuple[str, str | None, list[str]]] = [
    ("str", None, [
        "string", "normalizedString", "token", "Name", "NCName", "NMTOKEN",
        "language", "ID", "IDREF", "ENTITY", "anyURI", "QName", "NOTATION",
        "gYear", "gMonth", "gDay", "gMonthDay", "gYearMonth",
    ]),
    ("int", None, [
        "integer", "int", "long", "short", "byte", "nonNegativeInteger",
        "positiveInteger", "nonPositiveInteger", "negativeInteger",
        "unsignedInt", "unsignedLong", "unsignedShort", "unsignedByte",
    ]),
    ("Decimal", "from decimal import Decimal", ["decimal"]),
    ("float", None, ["float", "double"]),
    ("bool", None, ["boolean"]),
    ("date", "from datetime import date", ["date"]),
    ("datetime", "from datetime import datetime", ["dateTime"]),
    ("time", "from datetime import time", ["time"]),
    ("timedelta", "from datetime import timedelta", [
        "duration", "dayTimeDuration", "yearMonthDuration",
    ]),
    ("bytes", None, ["base64Binary", "hexBinary"]),
]

_MAP: dict[str, tuple[str, str | None]] = {
    f"{_XSD}{name}": (py, imp) for py, imp, names in _GROUPS for name in names
}


def resolve_xsd_type(uri: str) -> tuple[str, str | None]:
    """Return ``(python_type, import_or_none)`` for an XSD datatype URI."""
    for pfx in ("xsd:", "xs:"):
        if uri.startswith(pfx):
            uri = f"{_XSD}{uri[len(pfx):]}"
            break
    return _MAP.get(uri, ("Any", "from typing import Any"))

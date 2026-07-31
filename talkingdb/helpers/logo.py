import base64
import os
import re
from typing import Optional, Tuple

from fastapi import HTTPException, status
from lxml import etree


MAX_LOGO_BASE64_BYTES = int(os.getenv("TDB_MAX_LOGO_BASE64_BYTES", str(64 * 1024)))
ALLOWED_LOGO_TYPES = (
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/svg+xml",
)

_DATA_URI = re.compile(r"^data:([a-zA-Z0-9.+/-]+);base64,(.*)$", re.DOTALL)
_MAGIC = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}


def _invalid(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error_code": "VALIDATION_ERROR", "message": message},
    )


# ------------------------------------------------------------------------- SVG
_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    dtd_validation=False,
    huge_tree=False,
)

_ALLOWED_SVG_TAGS = frozenset(
    {
        "svg",
        "g",
        "path",
        "circle",
        "ellipse",
        "rect",
        "line",
        "polyline",
        "polygon",
        "defs",
        "linearGradient",
        "radialGradient",
        "stop",
        "title",
        "desc",
    }
)

_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def _local_name(tag) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _scrub_attributes(element) -> None:
    for name in list(element.attrib):
        local = _local_name(name).lower()

        if local.startswith("on"):
            del element.attrib[name]
            continue

        if local == "href" or name == _XLINK_HREF:
            if not str(element.attrib[name]).lstrip().startswith("#"):
                del element.attrib[name]
            continue

        if local == "style":
            value = str(element.attrib[name]).lower()
            if "url(" in value or "expression(" in value:
                del element.attrib[name]


def sanitise_svg(raw: bytes) -> bytes:
    try:
        root = etree.fromstring(raw, parser=_PARSER)
    except etree.XMLSyntaxError as exc:
        raise _invalid(f"logo is not valid SVG: {exc}") from exc

    if _local_name(root.tag) != "svg":
        raise _invalid("logo SVG must have an <svg> root element")

    for element in list(root.iter()):
        tag = _local_name(element.tag)
        if not tag or tag not in _ALLOWED_SVG_TAGS:
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
            continue

        _scrub_attributes(element)

    return etree.tostring(root, xml_declaration=False)


# ------------------------------------------------------------------ validation
def _split_data_uri(data_uri: str) -> Tuple[str, str]:
    match = _DATA_URI.match(data_uri.strip())
    if match is None:
        raise _invalid(
            "logo must be a base64 data URI, e.g. 'data:image/png;base64,...'"
        )
    media_type, payload = match.group(1).lower(), match.group(2)
    if media_type not in ALLOWED_LOGO_TYPES:
        raise _invalid("logo must be one of: " + ", ".join(ALLOWED_LOGO_TYPES))
    return media_type, payload


def validate_logo(data_uri: Optional[str]) -> Tuple[str, str]:
    if data_uri is None or not data_uri.strip():
        raise _invalid("logo is required")

    if len(data_uri) > MAX_LOGO_BASE64_BYTES:
        limit_kb = MAX_LOGO_BASE64_BYTES // 1024
        raise _invalid(
            f"logo must be at most {limit_kb}KB encoded; resize the image before upload"
        )

    media_type, payload = _split_data_uri(data_uri)

    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, TypeError) as exc:
        raise _invalid("logo is not valid base64") from exc

    if not raw:
        raise _invalid("logo is empty")

    if media_type == "image/svg+xml":
        return base64.b64encode(sanitise_svg(raw)).decode("ascii"), media_type

    if media_type == "image/webp":
        if not (raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"):
            raise _invalid("logo bytes are not a valid WebP image")
        return payload, media_type

    if not any(raw.startswith(prefix) for prefix in _MAGIC[media_type]):
        raise _invalid(f"logo bytes do not match the declared type {media_type}")

    return payload, media_type

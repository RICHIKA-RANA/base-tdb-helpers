"""Resolve the release-channel (rc) for the current request.

The channel is derived from the incoming request's hostname rather than a
per-instance env var, so one deployed binary behaves correctly regardless of
which rc/v slot serves it - no extra infra plumbing required.

Recognized hostnames (first label only, used as-is as the folder name):
    ttt-rcn.talkingdb.io -> "ttt-rcn"
    ttt-vn.talkingdb.io  -> "ttt-vn"

Anything else (localhost, 127.0.0.1, an unrecognised host) falls back to
"localhost", which doubles as the local-dev / DevPod bucket namespace.
"""

import re

from fastapi import Request
from talkingdb.logger.console import logger

_CHANNEL_PATTERN = re.compile(r"^(ttt-(?:rc\d+|v\d+))(?:[.:]|$)")

DEFAULT_CHANNEL = "localhost"


def get_release_channel(request: Request) -> str:
    """Resolve the MinIO release-channel folder name for this request.

    Prefers X-Forwarded-Host (correct if another proxy hop is ever added in
    front of Traefik), falls back to the raw Host header (what Traefik sends
    today by default).
    """
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or ""
    ).strip().lower()

    match = _CHANNEL_PATTERN.match(host)
    if not match:
        logger.warning(
            "Could not resolve release channel from host=%r; falling back to default channel %r",
            host, DEFAULT_CHANNEL,
        )
        return DEFAULT_CHANNEL
    return match.group(1)
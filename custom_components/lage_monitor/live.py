"""Parse the user-configured live stream / camera list (pure Python).

One entry per line: ``Label | URL or camera entity | optional region``.

Supported targets:
  * ``camera.entity_id``        -> rendered with Home Assistant's own camera stream
  * YouTube watch/live/embed/short URLs or ``youtube.com/channel/UC...``
                                -> click-to-load privacy embed
  * ``*.m3u8``                  -> HLS (native playback; desktop Chrome may need a camera entity)
  * ``*.jpg|jpeg|png|webp``     -> snapshot image, reloaded periodically
  * any other http(s) URL       -> link that opens in a new tab

Stream addresses are never shipped as defaults: they change and must be
checked by the owner of the dashboard.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

MAX_STREAMS = 12
CAMERA_RE = re.compile(r"^camera\.[a-z0-9_]+$")
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YT_CHANNEL_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}


def _youtube_embed(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.strip("/")
    video = ""
    channel = ""
    if host == "youtu.be":
        video = path.split("/")[0]
    elif host in YT_HOSTS:
        parts = path.split("/")
        if parts[0] == "watch":
            video = (parse_qs(parsed.query).get("v") or [""])[0]
        elif parts[0] in ("live", "embed", "shorts") and len(parts) > 1:
            if parts[1] == "live_stream":
                channel = (parse_qs(parsed.query).get("channel") or [""])[0]
            else:
                video = parts[1]
        elif parts[0] == "channel" and len(parts) > 1:
            channel = parts[1]
    if YT_ID_RE.match(video):
        return f"https://www.youtube-nocookie.com/embed/{video}"
    if YT_CHANNEL_RE.match(channel):
        return f"https://www.youtube-nocookie.com/embed/live_stream?channel={channel}"
    return ""


def classify(target: str) -> tuple[str, str]:
    """Return (type, normalized url/entity) or ("", "") when unusable."""
    target = target.strip()
    if CAMERA_RE.match(target):
        return "camera", target
    if not target.lower().startswith(("https://", "http://")):
        return "", ""
    parsed = urlparse(target)
    if not parsed.hostname:
        return "", ""
    host = parsed.hostname.lower()
    if host == "youtu.be" or host in YT_HOSTS:
        embed = _youtube_embed(target)
        return ("youtube", embed) if embed else ("", "")
    path = parsed.path.lower()
    if path.endswith(".m3u8"):
        return "hls", target
    if path.endswith(IMAGE_EXT):
        return "image", target
    return "link", target


def parse_streams(raw: str) -> list[dict[str, str]]:
    streams: list[dict[str, str]] = []
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2 or not parts[0]:
            continue
        kind, target = classify(parts[1])
        if not kind:
            continue
        streams.append(
            {
                "label": parts[0][:60],
                "type": kind,
                "url": target,
                "region": (parts[2] if len(parts) > 2 else "")[:30],
            }
        )
        if len(streams) >= MAX_STREAMS:
            break
    return streams

"""Helpers for HTTP and feed parsing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import html
import logging
import re
from typing import Any
import xml.etree.ElementTree as ET

from aiohttp import ClientError

from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


@dataclass(slots=True)
class FeedItem:
    """Normalized feed item."""

    title: str
    link: str
    summary: str
    published: str
    source: str


def _clean_text(value: str | None) -> str:
    """Strip HTML and normalize whitespace."""
    if not value:
        return ""
    text = TAG_RE.sub(" ", value)
    text = html.unescape(text)
    return WS_RE.sub(" ", text).strip()


def _find_text(node: ET.Element, *names: str) -> str:
    """Find child text across multiple tag names."""
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def parse_rss(xml_text: str, source: str, limit: int) -> list[FeedItem]:
    """Parse a basic RSS or Atom feed."""
    items: list[FeedItem] = []
    root = ET.fromstring(xml_text)

    rss_items = root.findall(".//item")
    atom_items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    nodes = rss_items or atom_items

    for node in nodes[:limit]:
        if node.tag.endswith("entry"):
            link = ""
            for link_node in node.findall("{http://www.w3.org/2005/Atom}link"):
                href = link_node.attrib.get("href")
                if href:
                    link = href
                    break
            item = FeedItem(
                title=_clean_text(
                    _find_text(node, "{http://www.w3.org/2005/Atom}title")
                ),
                link=link,
                summary=_clean_text(
                    _find_text(
                        node,
                        "{http://www.w3.org/2005/Atom}summary",
                        "{http://www.w3.org/2005/Atom}content",
                    )
                ),
                published=_find_text(
                    node,
                    "{http://www.w3.org/2005/Atom}updated",
                    "{http://www.w3.org/2005/Atom}published",
                ),
                source=source,
            )
        else:
            item = FeedItem(
                title=_clean_text(_find_text(node, "title")),
                link=_find_text(node, "link"),
                summary=_clean_text(
                    _find_text(
                        node,
                        "description",
                        "{http://purl.org/rss/1.0/modules/content/}encoded",
                    )
                ),
                published=_find_text(node, "pubDate"),
                source=source,
            )
        if item.title:
            items.append(item)

    return items


async def fetch_json(hass, url: str) -> Any:
    """Fetch JSON data."""
    session = async_get_clientsession(hass)
    async with session.get(url, timeout=20) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


async def fetch_feed(hass, url: str, source: str, limit: int) -> list[FeedItem]:
    """Fetch and parse a feed."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(url, timeout=20) as response:
            response.raise_for_status()
            text = await response.text()
    except (TimeoutError, ClientError, ET.ParseError) as err:
        _LOGGER.warning("Could not fetch feed %s from %s: %s", source, url, err)
        return []

    try:
        return parse_rss(text, source, limit)
    except ET.ParseError as err:
        _LOGGER.warning("Could not parse feed %s: %s", source, err)
        return []


def iso_timestamp() -> str:
    """Return UTC timestamp."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

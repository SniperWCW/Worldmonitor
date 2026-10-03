"""Helpers for HTTP and feed parsing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import html
import logging
import re
from typing import Any
import xml.etree.ElementTree as ET

from aiohttp import ClientTimeout

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .fetchcache import NotModified

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=20)

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
    async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
        response.raise_for_status()
        return await response.json(content_type=None)


def _validator_headers(etag: str | None, last_modified: str | None) -> dict[str, str]:
    """Build conditional-request headers from cached validators."""
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    return headers


async def fetch_feed(
    hass,
    url: str,
    source: str,
    limit: int,
    etag: str | None = None,
    last_modified: str | None = None,
) -> tuple[list[FeedItem], str | None, str | None]:
    """Fetch and parse a feed with conditional-request support.

    Raises on any failure (network, HTTP status, XML) so the caller can
    decide how to degrade. Raises ``NotModified`` on HTTP 304.
    """
    session = async_get_clientsession(hass)
    async with session.get(
        url,
        headers=_validator_headers(etag, last_modified),
        timeout=REQUEST_TIMEOUT,
    ) as response:
        if response.status == 304:
            raise NotModified
        response.raise_for_status()
        text = await response.text()
        new_etag = response.headers.get("ETag")
        new_last_modified = response.headers.get("Last-Modified")
    return parse_rss(text, source, limit), new_etag, new_last_modified


async def fetch_json_conditional(
    hass,
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
) -> tuple[Any, str | None, str | None]:
    """Fetch JSON with conditional-request support (raises ``NotModified``)."""
    session = async_get_clientsession(hass)
    async with session.get(
        url,
        headers=_validator_headers(etag, last_modified),
        timeout=REQUEST_TIMEOUT,
    ) as response:
        if response.status == 304:
            raise NotModified
        response.raise_for_status()
        data = await response.json(content_type=None)
        return data, response.headers.get("ETag"), response.headers.get("Last-Modified")


def iso_timestamp() -> str:
    """Return UTC timestamp."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

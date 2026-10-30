"""Tests for the live stream list parser."""

from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "lage_monitor"
if "lm" not in sys.modules:
    pkg = types.ModuleType("lm")
    pkg.__path__ = [str(PKG_DIR)]
    sys.modules["lm"] = pkg

from lm import live  # noqa: E402


class LiveTests(unittest.TestCase):
    def kind(self, target):
        return live.classify(target)

    def test_camera_entity(self):
        self.assertEqual(("camera", "camera.garage"), self.kind("camera.garage"))
        self.assertEqual(("", ""), self.kind("camera.Garage;x"))

    def test_youtube_variants(self):
        vid = "dQw4w9WgXcQ"
        embed = f"https://www.youtube-nocookie.com/embed/{vid}"
        for url in (
            f"https://www.youtube.com/watch?v={vid}",
            f"https://youtu.be/{vid}",
            f"https://www.youtube.com/live/{vid}",
            f"https://www.youtube.com/embed/{vid}",
        ):
            self.assertEqual(("youtube", embed), self.kind(url), url)

    def test_youtube_channel_live(self):
        channel = "UC" + "a" * 22
        expected = f"https://www.youtube-nocookie.com/embed/live_stream?channel={channel}"
        self.assertEqual(("youtube", expected), self.kind(f"https://www.youtube.com/channel/{channel}"))
        self.assertEqual(("youtube", expected), self.kind(f"https://www.youtube.com/embed/live_stream?channel={channel}"))

    def test_invalid_youtube_is_rejected(self):
        self.assertEqual(("", ""), self.kind("https://www.youtube.com/watch?v=short"))
        self.assertEqual(("", ""), self.kind("https://www.youtube.com/@somehandle"))

    def test_hls_image_link(self):
        self.assertEqual("hls", self.kind("https://example.org/live/stream.m3u8?x=1")[0])
        self.assertEqual("image", self.kind("https://example.org/cam.JPG")[0])
        self.assertEqual("link", self.kind("https://example.org/page")[0])

    def test_dangerous_schemes(self):
        for url in ("javascript:alert(1)", "data:text/html,x", "file:///etc/passwd", "ftp://x/y.m3u8"):
            self.assertEqual(("", ""), self.kind(url), url)

    def test_parse_streams(self):
        raw = """
        # Kommentar
        Tagesschau | https://example.org/a.m3u8 | Nachrichten
        Garage | camera.garage
        kaputt
        Ohne Ziel |
        Böse | javascript:alert(1)
        """
        streams = live.parse_streams(raw)
        self.assertEqual(["Tagesschau", "Garage"], [s["label"] for s in streams])
        self.assertEqual("Nachrichten", streams[0]["region"])
        self.assertEqual("", streams[1]["region"])

    def test_cap(self):
        raw = "\n".join(f"Cam {i} | camera.cam{i}" for i in range(30))
        self.assertEqual(live.MAX_STREAMS, len(live.parse_streams(raw)))


if __name__ == "__main__":
    unittest.main()

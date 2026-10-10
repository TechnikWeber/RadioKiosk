import unittest

from radiokiosk.feeds import parse_feed, plain, seconds
from radiokiosk.sources.sensors import reading

RSS = b"""<?xml version="1.0"?><rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel><title>Example &amp; Co</title><itunes:image href="https://example.org/cover.jpg"/>
<item><title>Second</title><link>https://example.org/2</link><guid>two</guid>
<description><![CDATA[<p>Some <b>bold</b> text.</p>]]></description>
<pubDate>Sat, 10 Oct 2026 08:00:00 +0200</pubDate>
<enclosure url="https://example.org/2.mp3" type="audio/mpeg" length="1"/><itunes:duration>1:02:03</itunes:duration></item>
<item><title>First</title><pubDate>Fri, 09 Oct 2026 08:00:00 +0200</pubDate></item>
</channel></rss>"""

ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom feed</title>
<entry><title>Entry</title><link rel="alternate" href="https://example.org/e"/><id>urn:1</id>
<updated>2026-10-10T06:00:00Z</updated><summary>Short</summary></entry></feed>"""


class FeedTest(unittest.TestCase):
    def test_rss_with_a_podcast_episode(self):
        feed = parse_feed(RSS)
        self.assertEqual((feed["title"], feed["image"]), ("Example & Co", "https://example.org/cover.jpg"))
        episode = feed["items"][0]
        self.assertEqual((episode["id"], episode["summary"], episode["audio"], episode["seconds"]),
                         ("two", "Some bold text.", "https://example.org/2.mp3", 3723))
        self.assertGreater(episode["date"], feed["items"][1]["date"])
        self.assertIsNone(feed["items"][1]["audio"])

    def test_atom(self):
        entry = parse_feed(ATOM)["items"][0]
        self.assertEqual((entry["title"], entry["link"], entry["summary"]), ("Entry", "https://example.org/e", "Short"))
        self.assertEqual(entry["date"], 1791612000)

    def test_something_else_is_not_a_feed(self):
        for data in (b"<html><body>no</body></html>", b"not xml at all"):
            with self.assertRaises(RuntimeError):
                parse_feed(data)

    def test_text_and_lengths(self):
        self.assertEqual(plain("a&nbsp;b <br> c"), "a b c")
        self.assertEqual(plain("one two three four", 9), "one two …")
        self.assertEqual([seconds("3723"), seconds("62:03"), seconds("soon")], [3723, 3723, 0])


class SensorTest(unittest.TestCase):
    def test_a_reading_keeps_what_it_measures(self):
        key, sensor = reading('{"time":"x","model":"Bresser-3CH","id":42,"channel":1,'
                              '"temperature_F":68.0,"humidity":55,"battery_ok":1,"mic":"CHECKSUM"}')
        self.assertEqual(key, "Bresser-3CH/42/1")
        self.assertEqual((sensor["temperature_C"], sensor["humidity"], sensor["battery_ok"]), (20.0, 55, 1))
        self.assertNotIn("mic", sensor)

    def test_other_output_is_ignored(self):
        for line in ("rtl_433 version 25.02", "[1, 2]", '{"no": "model"}'):
            self.assertIsNone(reading(line))

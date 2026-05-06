"""RSS feed XML sanitization before ElementTree parse."""

import xml.etree.ElementTree as ET

import pytest

from sources.rss_fetcher import RSSFetcher


def test_parse_feed_strips_null_byte():
    fetcher = RSSFetcher.__new__(RSSFetcher)
    raw = (
        '<?xml version="1.0"?><rss version="2.0"><channel>'
        '<item><title>Hello\x00World</title>'
        '<link>http://example.com/a</link><description>x</description></item>'
        "</channel></rss>"
    )
    articles = RSSFetcher._parse_feed(fetcher, raw, "test_null")  # noqa: SLF001
    assert len(articles) == 1
    assert "Hello" in articles[0].title and "World" in articles[0].title


def test_parse_feed_escapes_bare_ampersand_in_element():
    fetcher = RSSFetcher.__new__(RSSFetcher)
    raw = (
        '<?xml version="1.0"?><rss version="2.0"><channel>'
        "<item><title>AT&amp;T vs AT&T</title>"
        "<link>http://example.com/a</link><description>d</description></item>"
        "</channel></rss>"
    )
    # Second AT&T is invalid XML — sanitizer should escape it.
    articles = RSSFetcher._parse_feed(fetcher, raw, "test_amp")  # noqa: SLF001
    assert len(articles) == 1
    assert "AT&T" in articles[0].title or "AT&amp;T" in articles[0].title


def test_bare_ampersand_invalid_xml_before_fix():
    broken = (
        '<?xml version="1.0"?><rss version="2.0"><channel>'
        "<item><title>Bad AT&T Co</title>"
        "<link>http://x</link><description>d</description></item>"
        "</channel></rss>"
    )
    with pytest.raises(ET.ParseError):
        ET.fromstring(broken)

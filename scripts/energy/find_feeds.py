#!/usr/bin/env python3
"""Find RSS/Atom feeds for a list of websites.

Reads a CSV with columns name,url,category,active and writes a CSV with the
feed found for each active row. Only feeds that were actually fetched and
parsed as RSS/Atom with at least one entry are reported as found.

Usage:
    python3 find_feeds.py sources.csv feeds.csv

Standard library only; no install needed.
"""

import csv
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; EmBird feed finder)"
FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/rdf+xml")
# Paths tried (relative to the page, then to the site root) when a page
# does not advertise a feed via <link rel="alternate">.
COMMON_PATHS = ("feed/", "rss/", "feed", "rss", "rss.xml", "feed.xml",
                "atom.xml", "index.rss", "rss.php", "?format=feed&type=rss")

OUTPUT_FIELDS = ["name", "category", "source_url", "feed_url", "entries",
                 "method", "include", "note"]


class FeedLinkParser(HTMLParser):
    """Collects <link rel="alternate" type="application/rss+xml"> hrefs."""

    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        if "alternate" in a.get("rel", "").lower() and a.get("type", "").lower() in FEED_TYPES and a.get("href"):
            self.hrefs.append(a["href"])


def fetch(url):
    """Return (final_url, body_bytes) or raise."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                              "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.geturl(), resp.read(2_000_000)


def count_feed_entries(body):
    """Return number of entries if body is an RSS/Atom/RDF feed, else None."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    tag = root.tag.rsplit("}", 1)[-1].lower()
    if tag not in ("rss", "feed", "rdf"):
        return None
    return sum(1 for el in root.iter() if el.tag.rsplit("}", 1)[-1].lower() in ("item", "entry"))


def try_feed(url):
    """Return (final_url, entries) if url is a feed with entries, else None."""
    try:
        final_url, body = fetch(url)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    entries = count_feed_entries(body)
    if entries:
        return final_url, entries
    return None


def candidate_urls(page_url, page_body):
    """Yield (url, method) feed candidates in order of preference."""
    if page_body is not None:
        parser = FeedLinkParser()
        try:
            parser.feed(page_body.decode("utf-8", errors="replace"))
        except Exception:
            pass
        for href in parser.hrefs:
            yield urljoin(page_url, href), "page-link"

    base = page_url if page_url.endswith("/") else page_url + "/"
    root = "{0.scheme}://{0.netloc}/".format(urlparse(page_url))
    for prefix in dict.fromkeys((base, root)):
        for path in COMMON_PATHS:
            yield urljoin(prefix, path), "guessed"


def is_site_wide(source_url, feed_url):
    """True when the source is a section page but the feed is not under it."""
    src_path = urlparse(source_url).path.strip("/")
    feed_path = urlparse(feed_url).path.strip("/")
    return bool(src_path) and not feed_path.startswith(src_path.split("/")[0])


def find_feed(source_url):
    """Return a result dict for one source URL."""
    # The source itself may already be a feed.
    hit = try_feed(source_url)
    if hit:
        return {"feed_url": hit[0], "entries": hit[1], "method": "source-is-feed"}

    try:
        page_url, page_body = fetch(source_url)
    except (urllib.error.URLError, OSError, ValueError) as e:
        page_url, page_body = source_url, None
        page_error = str(e)
    else:
        page_error = ""

    seen = set()
    for url, method in candidate_urls(page_url, page_body):
        if url in seen:
            continue
        seen.add(url)
        hit = try_feed(url)
        if hit:
            return {"feed_url": hit[0], "entries": hit[1], "method": method}

    note = f"page fetch failed: {page_error}" if page_error else "no feed found"
    return {"feed_url": "", "entries": 0, "method": "", "note": note}


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    src_path, out_path = argv[1], argv[2]

    with open(src_path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("url")]

    results = []
    seen_feeds = set()
    for row in rows:
        base = {"name": row["name"], "category": row.get("category", ""),
                "source_url": row["url"]}
        if row.get("active", "yes").strip().lower() != "yes":
            results.append({**base, "include": "no", "note": "inactive in source list"})
            print(f"SKIP  {row['name']}: inactive")
            continue

        res = find_feed(row["url"])
        result = {**base, **res}
        if not res["feed_url"]:
            result["include"] = "no"
        elif res["feed_url"] in seen_feeds:
            result["include"] = "no"
            result["note"] = "duplicate feed"
        elif is_site_wide(row["url"], res["feed_url"]):
            # e.g. a site's general news feed found on its energy section page
            result["include"] = "review"
            result["note"] = "feed is not under the section path - may be site-wide/off-topic"
        else:
            result["include"] = "yes"
        if res["feed_url"]:
            seen_feeds.add(res["feed_url"])

        status = result["include"].upper()
        print(f"{status:6} {row['name']}: {res['feed_url'] or result.get('note', '')}")
        results.append(result)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    counts = {k: sum(1 for r in results if r.get("include") == k) for k in ("yes", "review", "no")}
    print(f"\nWrote {out_path}: {counts['yes']} yes, {counts['review']} review, {counts['no']} no")
    print("Edit the 'include' column (yes/no) before running apply_energy_section.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
